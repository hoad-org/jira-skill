"""Data models for Jira skill."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class TicketStatus(Enum):
    """Standard Jira ticket statuses."""

    TO_DO = "To Do"
    IN_PROGRESS = "In Progress"
    IN_REVIEW = "In Review"
    DONE = "Done"


@dataclass
class Subtask:
    """Represents a Jira subtask."""

    key: str
    summary: str
    status: str
    assignee: Optional[str] = None
    points: Optional[int] = None
    created: Optional[datetime] = None
    updated: Optional[datetime] = None

    def __str__(self) -> str:
        return f"{self.key} [{self.status}] {self.summary}"


@dataclass
class Ticket:
    """Represents a Jira ticket/story."""

    key: str
    summary: str
    description: str
    status: str
    assignee: Optional[str] = None
    reporter: Optional[str] = None
    points: Optional[int] = None
    labels: List[str] = field(default_factory=list)
    epic_key: Optional[str] = None
    created: Optional[datetime] = None
    updated: Optional[datetime] = None
    subtasks: List[Subtask] = field(default_factory=list)
    url: Optional[str] = None

    def is_critical(self, critical_labels: List[str]) -> bool:
        """Check if ticket has any critical labels."""
        return any(label in self.labels for label in critical_labels)

    def __str__(self) -> str:
        return f"{self.key} [{self.status}] {self.summary}"


@dataclass
class Epic:
    """Represents a Jira epic."""

    key: str
    name: str
    description: str
    status: str
    assignee: Optional[str] = None
    points: Optional[int] = None
    labels: List[str] = field(default_factory=list)
    created: Optional[datetime] = None
    updated: Optional[datetime] = None
    tickets: List[Ticket] = field(default_factory=list)
    url: Optional[str] = None

    @property
    def total_points(self) -> int:
        """Sum of all ticket points."""
        return sum(t.points or 0 for t in self.tickets)

    @property
    def completed_points(self) -> int:
        """Sum of completed ticket points."""
        return sum(t.points or 0 for t in self.tickets if t.status == TicketStatus.DONE.value)

    def progress_percent(self) -> int:
        """Progress percentage (0-100)."""
        if not self.total_points:
            return 0
        return int(100 * self.completed_points / self.total_points)

    def __str__(self) -> str:
        return f"{self.key} [{self.status}] {self.name} ({self.progress_percent()}%)"


@dataclass
class ProjectConfig:
    """Per-project configuration."""

    key: str
    name: str
    epic_link_field: str
    story_point_field: str = "customfield_10000"
    require_confirmation_for: List[str] = field(default_factory=lambda: ["reassign", "move_epic"])
    critical_labels: List[str] = field(
        default_factory=lambda: ["critical", "security", "compliance"]
    )
    max_auto_create_subtasks: int = 3
    stale_days_threshold: int = 14


@dataclass
class JiraConfig:
    """Jira skill configuration."""

    cloud_id: str
    use_mcp_auth: bool = True
    api_token: Optional[str] = None
    max_auto_transitions_per_run: int = 10
    max_auto_reassignments_per_run: int = 5
    default_assignee: Optional[str] = None
    default_reporter: Optional[str] = None
    default_labels: List[str] = field(default_factory=list)
    require_confirmation_for: List[str] = field(default_factory=lambda: ["reassign", "move_epic"])
    never_auto_transition: List[str] = field(default_factory=lambda: ["Done", "Closed"])
    never_auto_reassign_critical: bool = True
    critical_labels: List[str] = field(
        default_factory=lambda: ["critical", "security", "compliance", "blocker"]
    )
    max_auto_create_subtasks: int = 3
    stale_days_threshold: int = 14
    complexity_keywords: Dict[str, int] = field(
        default_factory=lambda: {
            "integrate": 3,
            "refactor": 2,
            "testing": 1,
            "redesign": 3,
            "performance": 2,
            "migration": 3,
            "security": 2,
            "api": 2,
            "ui": 2,
            "database": 2,
            "documentation": 1,
            "bug": 1,
            "fix": 1,
            "optimize": 1,
        }
    )
    branch_pattern: str = r"^(feat|fix|refactor|docs|test|chore)/([A-Z]+-[0-9]+)"
    title_pattern: str = r"^\[?([A-Z]+-[0-9]+)\]?"
    auto_transition_on_pr_open: bool = True
    auto_transition_on_pr_merge: bool = True
    projects: Dict[str, ProjectConfig] = field(default_factory=dict)


@dataclass
class RequirementScope:
    """Parsed requirement broken down into work units."""

    type: str  # "epic", "ticket", "subtask"
    title: str
    description: str
    estimated_points: int
    dependencies: List[str] = field(default_factory=list)
    sub_items: List["RequirementScope"] = field(default_factory=list)

    def __str__(self) -> str:
        return f"{self.type.upper()}: {self.title} (~{self.estimated_points}pts)"


@dataclass
class AuditFinding:
    """Finding from code/Jira audit."""

    severity: str  # "error", "warning", "info"
    ticket: Optional[Ticket] = None
    message: str = ""
    suggestion: str = ""
    related_files: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        level = f"[{self.severity.upper()}]"
        ticket_ref = f" {self.ticket.key}" if self.ticket else ""
        return f"{level}{ticket_ref} {self.message}"


@dataclass
class TransitionAction:
    """A ticket status transition."""

    ticket_key: str
    from_status: str
    to_status: str
    reason: str
    requires_confirmation: bool = False

    def __str__(self) -> str:
        return f"{self.ticket_key}: {self.from_status} → {self.to_status} ({self.reason})"


@dataclass
class ReassignmentAction:
    """A ticket reassignment."""

    ticket_key: str
    from_assignee: Optional[str]
    to_assignee: str
    reason: str
    requires_confirmation: bool = False

    def __str__(self) -> str:
        from_str = self.from_assignee or "unassigned"
        return f"{self.ticket_key}: {from_str} → {self.to_assignee} ({self.reason})"


@dataclass
class ExecutionPlan:
    """Execution plan for actions."""

    transitions: List[TransitionAction] = field(default_factory=list)
    reassignments: List[ReassignmentAction] = field(default_factory=list)
    creations: List[Dict[str, Any]] = field(default_factory=list)
    updates: List[Dict[str, Any]] = field(default_factory=list)
    confirmations_needed: List[str] = field(default_factory=list)

    @property
    def total_actions(self) -> int:
        """Total number of actions planned."""
        return (
            len(self.transitions)
            + len(self.reassignments)
            + len(self.creations)
            + len(self.updates)
        )

    @property
    def needs_confirmation(self) -> bool:
        """Check if any actions need confirmation."""
        return bool(self.confirmations_needed)
