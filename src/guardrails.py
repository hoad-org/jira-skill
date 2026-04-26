"""Guardrails and validation for Jira operations."""

from typing import List, Optional
from .models import Ticket, JiraConfig, ExecutionPlan, TransitionAction, ReassignmentAction


class Guardrails:
    """Safety checks and confirmation requirements."""

    def __init__(self, config: JiraConfig):
        """Initialize with config."""
        self.config = config

    def validate_execution_plan(self, plan: ExecutionPlan) -> None:
        """Validate an execution plan before running."""
        # Check transition limits
        if len(plan.transitions) > self.config.max_auto_transitions_per_run:
            raise ValueError(
                f"Too many transitions ({len(plan.transitions)} > {self.config.max_auto_transitions_per_run}). "
                f"Run multiple times or increase limit in config."
            )

        # Check reassignment limits
        if len(plan.reassignments) > self.config.max_auto_reassignments_per_run:
            raise ValueError(
                f"Too many reassignments ({len(plan.reassignments)} > {self.config.max_auto_reassignments_per_run}). "
                f"Run multiple times or increase limit in config."
            )

        # Validate transitions don't target forbidden statuses
        for transition in plan.transitions:
            if transition.to_status in self.config.never_auto_transition:
                plan.confirmations_needed.append(
                    f"Manual approval needed: cannot auto-transition {transition.ticket_key} to {transition.to_status}"
                )

    def check_transition_needs_confirmation(self, ticket: Ticket, to_status: str) -> bool:
        """Check if transition requires confirmation."""
        # Never auto-transition to certain statuses
        if to_status in self.config.never_auto_transition:
            return True

        # Require confirmation for Done/Closed transitions
        if to_status in ["Done", "Closed"]:
            # Check if ticket has open subtasks
            if ticket.subtasks and any(s.status != "Done" for s in ticket.subtasks):
                return True

        return "transition_to_done" in self.config.require_confirmation_for and to_status == "Done"

    def check_reassignment_needs_confirmation(self, ticket: Ticket, to_assignee: str) -> bool:
        """Check if reassignment requires confirmation."""
        # Always require for critical tickets if configured
        if self.config.never_auto_reassign_critical and ticket.is_critical(self.config.critical_labels):
            return True

        # Require confirmation if configured
        return "reassign" in self.config.require_confirmation_for

    def check_move_epic_needs_confirmation(self) -> bool:
        """Check if moving ticket to epic needs confirmation."""
        return "move_epic" in self.config.require_confirmation_for

    def validate_ticket_assignee(self, assignee: Optional[str]) -> bool:
        """Validate that assignee is valid (basic check)."""
        if not assignee:
            return True
        # Could add Jira user lookup here in future
        return len(assignee) > 0

    def validate_ticket_summary(self, summary: str) -> tuple[bool, str]:
        """Validate ticket summary."""
        if not summary:
            return False, "Summary is required"
        if len(summary) < 5:
            return False, "Summary too short (min 5 chars)"
        if len(summary) > 255:
            return False, "Summary too long (max 255 chars)"
        return True, ""

    def detect_scope_creep(self, original: str, updated: str) -> bool:
        """Detect if ticket description has grown significantly (>50%)."""
        original_len = len(original) if original else 0
        updated_len = len(updated)

        if original_len == 0:
            return False

        growth = (updated_len - original_len) / original_len
        return growth > 0.5

    def prevent_orphaned_subtasks(self, ticket: Ticket) -> List[str]:
        """Check for subtasks that would be orphaned if ticket is closed."""
        warnings = []
        open_subtasks = [s for s in ticket.subtasks if s.status != "Done"]

        if open_subtasks:
            for subtask in open_subtasks:
                warnings.append(
                    f"Cannot close {ticket.key}: has open subtask {subtask.key}"
                )

        return warnings

    def check_duplicate_detection(self, summary: str, existing_tickets: List[Ticket]) -> Optional[Ticket]:
        """Detect potential duplicate tickets."""
        summary_lower = summary.lower()

        for ticket in existing_tickets:
            if similarity(summary_lower, ticket.summary.lower()) > 0.8:
                return ticket

        return None

    def format_confirmation_prompt(self, action_description: str) -> str:
        """Format a confirmation prompt for user."""
        return f"\n⚠️  {action_description}\n\nContinue? [y/n]: "


def similarity(s1: str, s2: str) -> float:
    """Simple string similarity (0-1)."""
    # Simple Jaccard similarity on tokens
    tokens1 = set(s1.split())
    tokens2 = set(s2.split())

    if not tokens1 or not tokens2:
        return 0.0

    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)
    return intersection / union if union > 0 else 0.0
