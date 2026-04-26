"""Audit code changes against Jira tickets."""

import subprocess
from typing import List, Dict, Set, Optional
from pathlib import Path

from .models import Ticket, AuditFinding, JiraConfig


class CodeAuditor:
    """Compare code changes to Jira tickets."""

    def __init__(self, config: JiraConfig, repo_root: Path = None):
        """Initialize auditor."""
        self.config = config
        self.repo_root = repo_root or Path.cwd()

    def audit(self, tickets: List[Ticket], since_days: int = 7) -> List[AuditFinding]:
        """Audit tickets vs code changes."""
        findings = []

        # Get recent code changes
        changes = self._get_code_changes(since_days)
        changed_files = set(changes.keys())

        if not changed_files:
            return findings  # No changes, nothing to audit

        # Check each ticket
        for ticket in tickets:
            if ticket.status in ["Done", "Closed"]:
                # Check for changes on closed tickets
                related_files = self._get_related_files(ticket)
                recent_changes = related_files & changed_files

                if recent_changes:
                    findings.append(AuditFinding(
                        severity="error",
                        ticket=ticket,
                        message=f"Code changed on closed ticket",
                        suggestion="Create new ticket or reopen this one",
                        related_files=list(recent_changes)
                    ))

            elif ticket.status == "To Do":
                # Check if code changed on untouched tickets
                related_files = self._get_related_files(ticket)
                recent_changes = related_files & changed_files

                if recent_changes and len(recent_changes) >= 2:
                    findings.append(AuditFinding(
                        severity="error",
                        ticket=ticket,
                        message="Code changed but ticket is still 'To Do'",
                        suggestion="Transition to 'In Progress' or create new ticket",
                        related_files=list(recent_changes)
                    ))

            elif ticket.status == "In Progress":
                # Check for stale in-progress tickets
                if self._is_stale(ticket):
                    findings.append(AuditFinding(
                        severity="warning",
                        ticket=ticket,
                        message="In Progress but no recent updates",
                        suggestion="Update ticket status or check if blocked"
                    ))

        return findings

    def _get_code_changes(self, since_days: int) -> Dict[str, List[str]]:
        """Get recent code changes from git."""
        try:
            # Get commits in last N days
            cmd = [
                "git", "log",
                f"--since={since_days} days ago",
                "--name-only",
                "--pretty=format:%H"
            ]
            result = subprocess.run(
                cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                return {}

            changes = {}
            current_commit = None

            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue

                # Lines with 40 hex chars are commit hashes
                if len(line) == 40 and all(c in "0123456789abcdef" for c in line):
                    current_commit = line[:8]  # Short hash
                else:
                    # It's a file
                    if current_commit:
                        if line not in changes:
                            changes[line] = []
                        changes[line].append(current_commit)

            return changes
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return {}

    def _get_related_files(self, ticket: Ticket) -> Set[str]:
        """Extract files related to ticket from description/key."""
        related = set()

        # Try to extract file patterns from ticket key and description
        description = (ticket.description or "").lower()
        key = ticket.key.lower()

        # Common patterns
        keywords = ["auth", "api", "db", "ui", "frontend", "backend", "cache"]
        found_keywords = [kw for kw in keywords if kw in description or kw in key]

        # Map keywords to potential file patterns
        patterns = {
            "auth": ["auth", "login", "session", "password"],
            "api": ["api", "endpoint", "route", "handler"],
            "db": ["database", "migration", "query", "orm"],
            "ui": ["component", "page", "view", "template"],
            "frontend": ["src/", "components", "pages"],
            "backend": ["server", "api", "models", "services"],
            "cache": ["cache", "redis", "memcached"],
        }

        # Broad matching - just use keywords for now
        for keyword in found_keywords:
            related.add(keyword)

        return related

    def _is_stale(self, ticket: Ticket) -> bool:
        """Check if ticket is stale."""
        if not ticket.updated:
            return False

        from datetime import datetime, timedelta
        threshold = self.config.stale_days_threshold
        days_old = (datetime.now().timestamp() - ticket.updated.timestamp()) / 86400
        return days_old > threshold

    def suggest_fixes(self, findings: List[AuditFinding]) -> Dict[str, str]:
        """Suggest fixes for findings."""
        fixes = {}

        for finding in findings:
            if not finding.ticket:
                continue

            key = finding.ticket.key
            if finding.severity == "error" and "closed" in finding.message.lower():
                fixes[key] = f"reopen:{key}"
            elif finding.severity == "error" and "To Do" in finding.message:
                fixes[key] = f"transition:{key}:In Progress"
            elif finding.severity == "warning":
                fixes[key] = f"comment:{key}:Checking status"

        return fixes
