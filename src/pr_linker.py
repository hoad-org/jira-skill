"""Detect and link PRs to Jira tickets."""

import re
from typing import List, Optional

from .models import JiraConfig


class PRLinker:
    """Link pull requests to Jira tickets."""

    def __init__(self, config: JiraConfig):
        """Initialize with config."""
        self.config = config
        self.branch_pattern = re.compile(config.branch_pattern)
        self.title_pattern = re.compile(config.title_pattern)

    def detect_ticket_from_branch(self, branch_name: str) -> Optional[str]:
        """Detect ticket key from git branch name.

        Examples:
        - feat/TG-123-user-auth -> TG-123
        - fix/HCP-456-database-query -> HCP-456
        """
        match = self.branch_pattern.search(branch_name)
        if match and len(match.groups()) >= 2:
            return match.group(2)
        return None

    def detect_ticket_from_title(self, pr_title: str) -> Optional[str]:
        """Detect ticket key from PR title.

        Examples:
        - [TG-123] Implement user auth
        - TG-123: User authentication
        - Fix TG-123 database query
        """
        match = self.title_pattern.search(pr_title)
        if match:
            return match.group(1)
        return None

    def detect_ticket_from_description(self, pr_description: str) -> Optional[str]:
        """Detect ticket key from PR description.

        Looks for patterns like:
        - Closes TG-123
        - Fixes #TG-123
        - Related to TG-123
        """
        # Look for common patterns
        patterns = [
            r"(?:close|closes|closed|fix|fixes|fixed|resolve|resolves)s?\s+#?([A-Z]+-[0-9]+)",
            r"(?:relates? to|related to|part of)\s+#?([A-Z]+-[0-9]+)",
            r"ticket:?\s+([A-Z]+-[0-9]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, pr_description, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def detect_ticket(
        self, branch_name: str, pr_title: str, pr_description: str = ""
    ) -> Optional[str]:
        """Detect ticket key from PR, in priority order.

        Priority:
        1. Branch name (most reliable)
        2. PR title
        3. PR description
        """
        # Try branch first (most reliable)
        ticket = self.detect_ticket_from_branch(branch_name)
        if ticket:
            return ticket

        # Try title
        ticket = self.detect_ticket_from_title(pr_title)
        if ticket:
            return ticket

        # Try description
        ticket = self.detect_ticket_from_description(pr_description)
        if ticket:
            return ticket

        return None

    def extract_tickets(self, text: str) -> List[str]:
        """Extract all ticket keys from text."""
        pattern = r"([A-Z]+-[0-9]+)"
        return list(set(re.findall(pattern, text)))
