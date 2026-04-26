"""Integration tests for Jira skill."""

import pytest
from pathlib import Path

from src.config_loader import ConfigLoader
from src.requirement_parser import RequirementParser
from src.auto_sizer import AutoSizer
from src.pr_linker import PRLinker
from src.workflow_engine import WorkflowEngine
from src.guardrails import Guardrails
from src.models import JiraConfig


@pytest.fixture
def skill_root():
    """Get skill root."""
    return Path(__file__).parent.parent


@pytest.fixture
def config_loader(skill_root):
    """Create config loader."""
    return ConfigLoader(skill_root)


@pytest.fixture
def config(config_loader):
    """Load default config."""
    config_dict = config_loader.load_default_config()
    return config_loader.create_jira_config(config_dict)


class TestRequirementFlow:
    """Test requirement parsing flow."""

    def test_simple_requirement_flow(self, config):
        """Test parsing simple requirement."""
        parser = RequirementParser(config)

        requirement = "Implement user authentication with OAuth2 and session management"

        # Parse
        scope = parser.parse(requirement)

        # Verify scope tree
        assert scope.type in ["epic", "ticket"]
        assert scope.estimated_points > 0
        assert scope.title
        assert scope.description

        # If it's a ticket with subtasks, those should be valid
        if scope.sub_items:
            for item in scope.sub_items:
                assert item.estimated_points > 0

    def test_complex_requirement_decomposition(self, config):
        """Test decomposing complex requirement."""
        parser = RequirementParser(config)

        requirement = """
        Build user authentication system.
        This involves:
        1. Implement OAuth2 provider integration
        2. Add session management with timeout
        3. Create API endpoints for auth
        4. Add comprehensive testing
        5. Write documentation
        6. Deploy to production
        """

        scope = parser.parse(requirement)

        # Should decompose into epic
        assert scope.type == "epic"
        assert len(scope.sub_items) >= 3  # At least 3 tickets


class TestPRLinkingFlow:
    """Test PR linking workflow."""

    def test_pr_detection_priority(self, config):
        """Test PR detection priority."""
        linker = PRLinker(config)

        # Branch takes priority
        ticket = linker.detect_ticket(
            branch_name="feat/TG-123-auth",
            pr_title="[HCP-456] Something",
            pr_description="Closes TG-789"
        )
        assert ticket == "TG-123"

    def test_pr_fallback_chain(self, config):
        """Test PR detection fallback."""
        linker = PRLinker(config)

        # Title is fallback
        ticket = linker.detect_ticket(
            branch_name="feature/something",
            pr_title="[TG-456] Auth work",
            pr_description="Description"
        )
        assert ticket == "TG-456"

        # Description is last resort
        ticket = linker.detect_ticket(
            branch_name="feature/work",
            pr_title="Fix something",
            pr_description="Closes TG-789"
        )
        assert ticket == "TG-789"


class TestGuardrails:
    """Test guardrails."""

    def test_plan_validation(self, config):
        """Test execution plan validation."""
        from src.models import ExecutionPlan, TransitionAction

        guardrails = Guardrails(config)
        plan = ExecutionPlan()

        # Add transitions
        for i in range(5):
            plan.transitions.append(TransitionAction(
                ticket_key=f"TG-{i}",
                from_status="To Do",
                to_status="In Progress",
                reason="test"
            ))

        # Should pass
        guardrails.validate_execution_plan(plan)

    def test_plan_exceeds_limits(self, config):
        """Test plan exceeding limits."""
        from src.models import ExecutionPlan, TransitionAction

        guardrails = Guardrails(config)
        plan = ExecutionPlan()

        # Add too many transitions
        for i in range(config.max_auto_transitions_per_run + 5):
            plan.transitions.append(TransitionAction(
                ticket_key=f"TG-{i}",
                from_status="To Do",
                to_status="In Progress",
                reason="test"
            ))

        # Should fail
        with pytest.raises(ValueError, match="Too many transitions"):
            guardrails.validate_execution_plan(plan)


class TestWorkflowIntegration:
    """Test workflow orchestration."""

    def test_sizing_consistency(self, config):
        """Test that sizing is consistent across modules."""
        parser = RequirementParser(config)
        sizer = AutoSizer(config)

        requirement = "Implement payment integration with Stripe"

        # Parse requirement
        scope = parser.parse(requirement)
        parser_points = scope.estimated_points

        # Size same text
        sizer_points = sizer.estimate(requirement)

        # Should be in same range
        assert abs(parser_points - sizer_points) <= 5

    def test_config_cascading(self, skill_root):
        """Test config cascading (master + project override)."""
        loader = ConfigLoader(skill_root)

        master = loader.load_default_config()
        assert master["jira"]["cloudId"] == "your-instance"

        # Merge with project override
        project = {
            "jira": {
                "projectKey": "TG"
            },
            "guardrails": {
                "requireConfirmationFor": ["reassign"]
            }
        }

        merged = loader.merge_configs(master, project)

        # Master value preserved
        assert merged["jira"]["cloudId"] == master["jira"]["cloudId"]

        # Project override applied
        assert merged["guardrails"]["requireConfirmationFor"] == ["reassign"]


class TestEnd2EndFlow:
    """Test end-to-end flows."""

    def test_requirement_to_jira_flow(self, config):
        """Test flow from requirement to Jira items."""
        parser = RequirementParser(config)

        requirement = "Build dashboard with notifications"
        scope = parser.parse(requirement)

        # Verify we could create this in Jira
        assert scope.type in ["epic", "ticket"]
        assert scope.estimated_points > 0

        # If epic, should have tickets
        if scope.type == "epic":
            assert len(scope.sub_items) > 0
            for item in scope.sub_items:
                assert item.type == "ticket"
                assert item.estimated_points > 0

    def test_multi_project_config(self, skill_root):
        """Test multi-project configuration."""
        loader = ConfigLoader(skill_root)
        config_dict = loader.load_default_config()
        config = loader.create_jira_config(config_dict)

        # Should have multiple projects
        assert len(config.projects) >= 2

        # Each should be valid
        for key, proj_config in config.projects.items():
            assert proj_config.key == key
            assert proj_config.name
            assert proj_config.epic_link_field
