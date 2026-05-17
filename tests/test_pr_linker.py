"""Tests for PR linking logic."""

import pytest

from src.models import JiraConfig
from src.pr_linker import PRLinker


@pytest.fixture
def config():
    """Create test config."""
    return JiraConfig(cloud_id="test-instance")


@pytest.fixture
def linker(config):
    """Create linker instance."""
    return PRLinker(config)


class TestBranchDetection:
    """Test branch name ticket detection."""

    def test_detect_feat_branch(self, linker):
        """Test feature branch with ticket."""
        ticket = linker.detect_ticket_from_branch("feat/TG-123-user-auth")
        assert ticket == "TG-123"

    def test_detect_fix_branch(self, linker):
        """Test fix branch with ticket."""
        ticket = linker.detect_ticket_from_branch("fix/HCP-456-database-bug")
        assert ticket == "HCP-456"

    def test_detect_refactor_branch(self, linker):
        """Test refactor branch with ticket."""
        ticket = linker.detect_ticket_from_branch("refactor/TG-789-auth-module")
        assert ticket == "TG-789"

    def test_no_ticket_in_branch(self, linker):
        """Test branch without ticket."""
        ticket = linker.detect_ticket_from_branch("feature/random-work")
        assert ticket is None

    def test_ticket_without_prefix(self, linker):
        """Test ticket in branch without feat/fix prefix."""
        ticket = linker.detect_ticket_from_branch("TG-123-auth")
        assert ticket is None  # Our pattern requires prefix


class TestTitleDetection:
    """Test PR title ticket detection."""

    def test_bracketed_ticket_in_title(self, linker):
        """Test [TG-123] format."""
        ticket = linker.detect_ticket_from_title("[TG-123] Implement user auth")
        assert ticket == "TG-123"

    def test_ticket_with_colon(self, linker):
        """Test TG-123: format."""
        ticket = linker.detect_ticket_from_title("TG-123: Fix database query")
        assert ticket == "TG-123"

    def test_no_ticket_in_title(self, linker):
        """Test title without ticket."""
        ticket = linker.detect_ticket_from_title("Fix authentication bug")
        assert ticket is None


class TestDescriptionDetection:
    """Test PR description ticket detection."""

    def test_closes_pattern(self, linker):
        """Test 'Closes TG-123' pattern."""
        desc = "This PR closes TG-123"
        ticket = linker.detect_ticket_from_description(desc)
        assert ticket == "TG-123"

    def test_fixes_pattern(self, linker):
        """Test 'Fixes HCP-456' pattern."""
        desc = "This fixes HCP-456"
        ticket = linker.detect_ticket_from_description(desc)
        assert ticket == "HCP-456"

    def test_relates_to_pattern(self, linker):
        """Test 'relates to TG-789' pattern."""
        desc = "This relates to TG-789"
        ticket = linker.detect_ticket_from_description(desc)
        assert ticket == "TG-789"

    def test_no_ticket_in_description(self, linker):
        """Test description without ticket."""
        desc = "This PR adds new features"
        ticket = linker.detect_ticket_from_description(desc)
        assert ticket is None


class TestDetectTicketPriority:
    """Test ticket detection priority."""

    def test_branch_takes_priority(self, linker):
        """Test that branch name has highest priority."""
        ticket = linker.detect_ticket(
            branch_name="feat/TG-123-branch",
            pr_title="[HCP-456] title",
            pr_description="Closes TG-789",
        )
        assert ticket == "TG-123"

    def test_title_fallback(self, linker):
        """Test that title is fallback when branch has no ticket."""
        ticket = linker.detect_ticket(
            branch_name="feature/work", pr_title="[HCP-456] title", pr_description="Closes TG-789"
        )
        assert ticket == "HCP-456"

    def test_description_fallback(self, linker):
        """Test that description is last resort."""
        ticket = linker.detect_ticket(
            branch_name="feature/work", pr_title="Fix bug", pr_description="Closes TG-789"
        )
        assert ticket == "TG-789"


class TestExtractTickets:
    """Test extracting all tickets from text."""

    def test_extract_single_ticket(self, linker):
        """Test extracting one ticket."""
        tickets = linker.extract_tickets("Work on TG-123")
        assert "TG-123" in tickets

    def test_extract_multiple_tickets(self, linker):
        """Test extracting multiple tickets."""
        text = "Related to TG-123 and HCP-456 and TG-789"
        tickets = linker.extract_tickets(text)
        assert "TG-123" in tickets
        assert "HCP-456" in tickets
        assert "TG-789" in tickets

    def test_extract_no_duplicates(self, linker):
        """Test that duplicates are removed."""
        text = "TG-123 and TG-123 again"
        tickets = linker.extract_tickets(text)
        assert tickets.count("TG-123") == 1
