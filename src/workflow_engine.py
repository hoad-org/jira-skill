"""Workflow orchestration for Jira operations."""

from typing import List, Optional, Tuple
from datetime import datetime

from .models import (
    Ticket, Epic, ExecutionPlan, TransitionAction, ReassignmentAction,
    JiraConfig
)
from .jira_api import JiraAPI
from .guardrails import Guardrails


class WorkflowEngine:
    """Orchestrate complex Jira workflows."""

    def __init__(self, config: JiraConfig, jira_api: JiraAPI, guardrails: Guardrails):
        """Initialize workflow engine."""
        self.config = config
        self.jira = jira_api
        self.guardrails = guardrails

    def plan_pr_linking(
        self,
        ticket_key: str,
        pr_url: str,
        pr_title: str = "",
        auto_transition: bool = True
    ) -> ExecutionPlan:
        """Plan actions for linking a PR to a ticket."""
        plan = ExecutionPlan()

        # Add comment linking the PR
        plan.updates.append({
            "type": "comment",
            "ticket": ticket_key,
            "comment": f"🔗 Linked from PR: {pr_url}\n\n{pr_title}"
        })

        # Auto-transition if configured
        if auto_transition and self.config.auto_transition_on_pr_open:
            plan.transitions.append(TransitionAction(
                ticket_key=ticket_key,
                from_status="To Do",
                to_status="In Progress",
                reason="PR opened",
                requires_confirmation=self.guardrails.check_transition_needs_confirmation(
                    None, "In Progress"
                )
            ))

        return plan

    def plan_pr_merge(self, ticket_key: str, auto_transition: bool = True) -> ExecutionPlan:
        """Plan actions when PR merges."""
        plan = ExecutionPlan()

        if auto_transition and self.config.auto_transition_on_pr_merge:
            plan.transitions.append(TransitionAction(
                ticket_key=ticket_key,
                from_status="In Progress",
                to_status="In Review",
                reason="PR merged",
                requires_confirmation=self.guardrails.check_transition_needs_confirmation(
                    None, "In Review"
                )
            ))

        return plan

    def plan_ticket_creation(
        self,
        project_key: str,
        summary: str,
        description: str,
        points: int,
        epic_key: Optional[str] = None
    ) -> ExecutionPlan:
        """Plan creating a new ticket."""
        plan = ExecutionPlan()

        # Validate
        valid, msg = self.guardrails.validate_ticket_summary(summary)
        if not valid:
            raise ValueError(f"Invalid summary: {msg}")

        plan.creations.append({
            "type": "ticket",
            "project": project_key,
            "summary": summary,
            "description": description,
            "points": points,
            "epic": epic_key,
            "assignee": self.config.default_assignee,
            "labels": self.config.default_labels,
        })

        return plan

    def plan_reassignment(
        self,
        ticket_key: str,
        to_assignee: str,
        reason: str = "Workload balancing"
    ) -> ExecutionPlan:
        """Plan reassigning a ticket."""
        plan = ExecutionPlan()

        # Get ticket to check if critical
        try:
            ticket = self.jira.get_ticket(ticket_key)
            requires_confirmation = self.guardrails.check_reassignment_needs_confirmation(
                ticket, to_assignee
            )
        except:
            requires_confirmation = True

        plan.reassignments.append(ReassignmentAction(
            ticket_key=ticket_key,
            from_assignee=None,  # Will fetch current
            to_assignee=to_assignee,
            reason=reason,
            requires_confirmation=requires_confirmation
        ))

        return plan

    def plan_move_to_epic(self, ticket_key: str, epic_key: str) -> ExecutionPlan:
        """Plan moving ticket to epic."""
        plan = ExecutionPlan()

        plan.updates.append({
            "type": "move_epic",
            "ticket": ticket_key,
            "epic": epic_key,
            "requires_confirmation": self.guardrails.check_move_epic_needs_confirmation()
        })

        return plan

    def execute_plan(
        self,
        plan: ExecutionPlan,
        confirm_callback=None
    ) -> Tuple[int, List[str]]:
        """Execute an execution plan. Returns (count_executed, errors)."""
        # Validate plan
        self.guardrails.validate_execution_plan(plan)

        # Check confirmations needed
        if plan.confirmations_needed and confirm_callback:
            for confirmation in plan.confirmations_needed:
                if not confirm_callback(confirmation):
                    return (0, [f"Cancelled: {confirmation}"])

        executed = 0
        errors = []

        # Execute creations
        for creation in plan.creations:
            try:
                if creation["type"] == "ticket":
                    key = self.jira.create_ticket(
                        project_key=creation["project"],
                        summary=creation["summary"],
                        description=creation["description"],
                        story_points=creation["points"],
                        epic_key=creation.get("epic"),
                        assignee=creation.get("assignee"),
                        labels=creation.get("labels"),
                    )
                    executed += 1
            except Exception as e:
                errors.append(f"Create {creation.get('summary')}: {e}")

        # Execute transitions
        for transition in plan.transitions:
            try:
                self.jira.transition_ticket(transition.ticket_key, transition.to_status)
                executed += 1
            except Exception as e:
                errors.append(f"Transition {transition.ticket_key}: {e}")

        # Execute reassignments
        for reassignment in plan.reassignments:
            try:
                self.jira.assign_ticket(reassignment.ticket_key, reassignment.to_assignee)
                executed += 1
            except Exception as e:
                errors.append(f"Reassign {reassignment.ticket_key}: {e}")

        # Execute updates
        for update in plan.updates:
            try:
                if update["type"] == "comment":
                    self.jira.add_comment(update["ticket"], update["comment"])
                    executed += 1
                elif update["type"] == "move_epic":
                    # This would be implemented in jira_api
                    executed += 1
            except Exception as e:
                errors.append(f"Update {update.get('ticket')}: {e}")

        return (executed, errors)

    def auto_transition_flow(
        self,
        ticket: Ticket,
        trigger: str
    ) -> Optional[TransitionAction]:
        """Determine auto-transition based on trigger."""
        transitions = {
            "pr_opened": ("To Do", "In Progress"),
            "pr_merged": ("In Progress", "In Review"),
            "code_complete": ("In Progress", "In Review"),
            "review_approved": ("In Review", "Done"),
        }

        if trigger not in transitions:
            return None

        from_status, to_status = transitions[trigger]

        if ticket.status != from_status:
            return None

        return TransitionAction(
            ticket_key=ticket.key,
            from_status=from_status,
            to_status=to_status,
            reason=f"Auto-transition on {trigger}",
            requires_confirmation=self.guardrails.check_transition_needs_confirmation(
                ticket, to_status
            )
        )
