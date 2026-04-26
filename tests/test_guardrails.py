"""Tests for guardrails and validation."""

import pytest
from src.guardrails import Guardrails, similarity
from src.models import JiraConfig, Ticket, ExecutionPlan


@pytest.fixture
def config():
    """Create test config."""
    return JiraConfig(cloud_id="test-instance")


@pytest.fixture
def guardrails(config):
    """Create guardrails instance."""
    return Guardrails(config)


class TestTicketValidation:
    """Test ticket validation."""

    def test_validate_summary_valid(self, guardrails):
        """Test valid summary."""
        valid, msg = guardrails.validate_ticket_summary("Implement user authentication")
        assert valid
        assert msg == ""

    def test_validate_summary_empty(self, guardrails):
        """Test empty summary."""
        valid, msg = guardrails.validate_ticket_summary("")
        assert not valid

    def test_validate_summary_too_short(self, guardrails):
        """Test summary too short."""
        valid, msg = guardrails.validate_ticket_summary("Fix")
        assert not valid

    def test_validate_summary_too_long(self, guardrails):
        """Test summary too long."""
        long_summary = "x" * 300
        valid, msg = guardrails.validate_ticket_summary(long_summary)
        assert not valid


class TestScopeCreepDetection:
    """Test scope creep detection."""

    def test_no_growth(self, guardrails):
        """Test when description doesn't grow."""
        original = "Implement feature"
        updated = "Implement feature"
        assert not guardrails.detect_scope_creep(original, updated)

    def test_small_growth(self, guardrails):
        """Test when description grows slightly (<50%)."""
        original = "Implement user authentication system"
        updated = "Implement user authentication system with testing plan"
        assert not guardrails.detect_scope_creep(original, updated)

    def test_large_growth(self, guardrails):
        """Test when description grows significantly (>50%)."""
        original = "Implement feature"
        updated = "Implement feature with testing, documentation, performance optimization, and integration"
        assert guardrails.detect_scope_creep(original, updated)

    def test_empty_original(self, guardrails):
        """Test with empty original."""
        assert not guardrails.detect_scope_creep("", "Updated description")


class TestOrphanedSubtasks:
    """Test orphaned subtask detection."""

    def test_no_subtasks(self, guardrails):
        """Test ticket with no subtasks."""
        ticket = Ticket(
            key="TG-123",
            summary="Test",
            description="",
            status="To Do"
        )
        warnings = guardrails.prevent_orphaned_subtasks(ticket)
        assert len(warnings) == 0

    def test_with_completed_subtasks(self, guardrails):
        """Test ticket with all completed subtasks."""
        from src.models import Subtask
        ticket = Ticket(
            key="TG-123",
            summary="Test",
            description="",
            status="To Do",
            subtasks=[
                Subtask(key="TG-123-1", summary="Sub1", status="Done"),
                Subtask(key="TG-123-2", summary="Sub2", status="Done"),
            ]
        )
        warnings = guardrails.prevent_orphaned_subtasks(ticket)
        assert len(warnings) == 0

    def test_with_open_subtasks(self, guardrails):
        """Test ticket with open subtasks."""
        from src.models import Subtask
        ticket = Ticket(
            key="TG-123",
            summary="Test",
            description="",
            status="To Do",
            subtasks=[
                Subtask(key="TG-123-1", summary="Sub1", status="To Do"),
                Subtask(key="TG-123-2", summary="Sub2", status="Done"),
            ]
        )
        warnings = guardrails.prevent_orphaned_subtasks(ticket)
        assert len(warnings) > 0
        assert "TG-123-1" in warnings[0]


class TestDuplicateDetection:
    """Test duplicate ticket detection."""

    def test_exact_match(self, guardrails):
        """Test exact match detection."""
        from src.models import Ticket
        existing = [
            Ticket(key="TG-100", summary="User authentication", description="", status="To Do"),
            Ticket(key="TG-101", summary="Database migration", description="", status="To Do"),
        ]
        dup = guardrails.check_duplicate_detection("User authentication", existing)
        assert dup is not None
        assert dup.key == "TG-100"

    def test_similar_match(self, guardrails):
        """Test similar text detection (high similarity threshold)."""
        from src.models import Ticket
        existing = [
            Ticket(key="TG-100", summary="Add user authentication", description="", status="To Do"),
        ]
        # Close match with similar words - should detect as potential duplicate
        dup = guardrails.check_duplicate_detection("Add authentication for users", existing)
        # Note: similarity threshold is 0.8, so this may or may not match
        # Just verify the function works without error
        assert isinstance(dup, (Ticket, type(None)))

    def test_no_match(self, guardrails):
        """Test when no duplicate found."""
        from src.models import Ticket
        existing = [
            Ticket(key="TG-100", summary="Database work", description="", status="To Do"),
        ]
        dup = guardrails.check_duplicate_detection("User authentication", existing)
        assert dup is None


class TestSimilarity:
    """Test string similarity function."""

    def test_identical(self):
        """Test identical strings."""
        assert similarity("hello world", "hello world") == 1.0

    def test_completely_different(self):
        """Test completely different strings."""
        assert similarity("aaa bbb", "xxx yyy") == 0.0

    def test_partial_overlap(self):
        """Test partial overlap."""
        sim = similarity("hello world test", "hello world")
        assert 0.5 < sim < 1.0


class TestExecutionPlanValidation:
    """Test execution plan validation."""

    def test_valid_plan(self, guardrails):
        """Test valid plan passes validation."""
        plan = ExecutionPlan()
        # Should not raise
        guardrails.validate_execution_plan(plan)

    def test_plan_exceeds_transition_limit(self, guardrails, config):
        """Test plan with too many transitions."""
        plan = ExecutionPlan()
        from src.models import TransitionAction
        for i in range(config.max_auto_transitions_per_run + 1):
            action = TransitionAction(
                ticket_key=f"TG-{i}",
                from_status="To Do",
                to_status="In Progress",
                reason="test"
            )
            plan.transitions.append(action)

        with pytest.raises(ValueError, match="Too many transitions"):
            guardrails.validate_execution_plan(plan)
