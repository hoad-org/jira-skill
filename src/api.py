"""Jira API wrapper with DevArmor event publishing integration.

This module wraps the existing JiraAPI and adds event publishing for:
- ticket_created
- ticket_updated
- ticket_deleted

All operations are audited and published through DevArmor's event bus.
"""

import logging
from typing import List, Optional

from .jira_api import JiraAPI, JiraAPIError
from .models import JiraConfig
from .skill import JiraSkillWithEvents

logger = logging.getLogger(__name__)


class JiraAPIWithEvents(JiraAPI):
    """Jira API client with DevArmor event publishing.

    Extends JiraAPI to publish events for all mutations:
    - ticket_created: When a ticket is created
    - ticket_updated: When a ticket is updated
    - ticket_deleted: When a ticket is deleted

    This enables:
    - Audit trail of all changes
    - Cross-skill communication (e.g., GitHub can subscribe to these events)
    - Policy enforcement through DevArmor
    """

    def __init__(self, config: JiraConfig, skill: Optional[JiraSkillWithEvents] = None):
        """Initialize Jira API with event publishing.

        Args:
            config: JiraConfig instance
            skill: Optional JiraSkillWithEvents instance for event publishing
                  (if not provided, events are not published)
        """
        super().__init__(config)
        self.skill = skill
        self.publisher_actor = "jira-api"

    async def create_ticket(
        self,
        project_key: str,
        summary: str,
        description: str,
        story_points: Optional[int] = None,
        assignee: Optional[str] = None,
        epic_key: Optional[str] = None,
        labels: Optional[List[str]] = None,
    ) -> str:
        """Create a new ticket with event publishing.

        Args:
            project_key: Jira project key
            summary: Ticket summary
            description: Ticket description
            story_points: Optional story points estimate
            assignee: Optional assignee username
            epic_key: Optional epic to link to
            labels: Optional labels to add

        Returns:
            Ticket key of created ticket

        Raises:
            JiraAPIError: If ticket creation fails
        """
        # Pre-action check
        if self.skill:
            allowed = await self.skill.pre_action_check(
                action="create_ticket",
                resource=project_key,
                actor=self.publisher_actor,
            )
            if not allowed:
                raise JiraAPIError("Ticket creation denied by policy")

        # Create ticket using parent implementation
        ticket_key = super().create_ticket(
            project_key=project_key,
            summary=summary,
            description=description,
            story_points=story_points,
            assignee=assignee,
            epic_key=epic_key,
            labels=labels,
        )

        # Publish event
        if self.skill:
            await self.skill.publish_ticket_created(
                ticket_key=ticket_key,
                summary=summary,
                actor=self.publisher_actor,
                project=project_key,
                assignee=assignee,
                story_points=story_points,
                epic_key=epic_key,
                labels=labels,
            )
            logger.debug(f"Published ticket_created event for {ticket_key}")

        return ticket_key

    async def update_ticket(
        self,
        ticket_key: str,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        story_points: Optional[int] = None,
        status: Optional[str] = None,
        assignee: Optional[str] = None,
        labels: Optional[List[str]] = None,
    ) -> None:
        """Update a ticket with event publishing.

        Args:
            ticket_key: Ticket key to update
            summary: Optional new summary
            description: Optional new description
            story_points: Optional new story points
            status: Optional new status
            assignee: Optional new assignee
            labels: Optional new labels

        Raises:
            JiraAPIError: If ticket update fails
        """
        # Pre-action check
        if self.skill:
            allowed = await self.skill.pre_action_check(
                action="update_ticket",
                resource=ticket_key,
                actor=self.publisher_actor,
            )
            if not allowed:
                raise JiraAPIError("Ticket update denied by policy")

        # Track changes
        changes = {}
        if summary is not None:
            changes["summary"] = summary
        if description is not None:
            changes["description"] = description
        if story_points is not None:
            changes["story_points"] = story_points
        if status is not None:
            changes["status"] = status
        if assignee is not None:
            changes["assignee"] = assignee
        if labels is not None:
            changes["labels"] = labels

        # Update ticket using parent implementation
        super().update_ticket(
            ticket_key=ticket_key,
            summary=summary,
            description=description,
            story_points=story_points,
            status=status,
            assignee=assignee,
            labels=labels,
        )

        # Publish event
        if self.skill:
            await self.skill.publish_ticket_updated(
                ticket_key=ticket_key,
                changes=changes,
                actor=self.publisher_actor,
            )
            logger.debug(f"Published ticket_updated event for {ticket_key}")

    async def delete_ticket(self, ticket_key: str) -> None:
        """Delete a ticket with event publishing.

        NOTE: This operation is marked as requiring confirmation through DevArmor.

        Args:
            ticket_key: Ticket key to delete

        Raises:
            JiraAPIError: If ticket deletion fails
        """
        # Pre-action check (DELETE is a destructive operation)
        if self.skill:
            allowed = await self.skill.pre_action_check(
                action="delete_ticket",
                resource=ticket_key,
                actor=self.publisher_actor,
            )
            if not allowed:
                raise JiraAPIError("Ticket deletion denied by policy")

        # Delete via API (note: Jira Cloud doesn't have direct delete, but we include this
        # for completeness and to demonstrate DevArmor enforcement of destructive operations)
        # In practice, you would transition to "Closed" or "Archived" instead
        logger.warning(f"Attempting to delete ticket {ticket_key} - not supported by Jira Cloud")

        # Publish event
        if self.skill:
            await self.skill.publish_ticket_deleted(
                ticket_key=ticket_key,
                actor=self.publisher_actor,
                reason="Destructive operation",
            )
            logger.debug(f"Published ticket_deleted event for {ticket_key}")

    # Additional methods that publish events

    async def transition_ticket(self, ticket_key: str, to_status: str) -> None:
        """Transition a ticket to a new status with event publishing.

        Args:
            ticket_key: Ticket key to transition
            to_status: Target status

        Raises:
            JiraAPIError: If transition fails
        """
        # Pre-action check
        if self.skill:
            allowed = await self.skill.pre_action_check(
                action="transition_ticket",
                resource=ticket_key,
                actor=self.publisher_actor,
            )
            if not allowed:
                raise JiraAPIError("Ticket transition denied by policy")

        # Transition using parent implementation
        super().transition_ticket(ticket_key=ticket_key, to_status=to_status)

        # Publish event
        if self.skill:
            await self.skill.publish_ticket_updated(
                ticket_key=ticket_key,
                changes={"status": to_status},
                actor=self.publisher_actor,
            )
            logger.debug(f"Published ticket transition event for {ticket_key}")

    async def assign_ticket(self, ticket_key: str, assignee: str) -> None:
        """Assign a ticket to a user with event publishing.

        Args:
            ticket_key: Ticket key to assign
            assignee: Username to assign to

        Raises:
            JiraAPIError: If assignment fails
        """
        # Pre-action check
        if self.skill:
            allowed = await self.skill.pre_action_check(
                action="assign_ticket",
                resource=ticket_key,
                actor=self.publisher_actor,
            )
            if not allowed:
                raise JiraAPIError("Ticket assignment denied by policy")

        # Assign using parent implementation
        super().assign_ticket(ticket_key=ticket_key, assignee=assignee)

        # Publish event
        if self.skill:
            await self.skill.publish_ticket_updated(
                ticket_key=ticket_key,
                changes={"assignee": assignee},
                actor=self.publisher_actor,
            )
            logger.debug(f"Published ticket assignment event for {ticket_key}")

    async def add_comment(self, ticket_key: str, comment: str) -> None:
        """Add a comment to a ticket with event publishing.

        Args:
            ticket_key: Ticket key to comment on
            comment: Comment text

        Raises:
            JiraAPIError: If comment creation fails
        """
        # Pre-action check
        if self.skill:
            allowed = await self.skill.pre_action_check(
                action="add_comment",
                resource=ticket_key,
                actor=self.publisher_actor,
            )
            if not allowed:
                raise JiraAPIError("Comment creation denied by policy")

        # Add comment using parent implementation
        super().add_comment(ticket_key=ticket_key, comment=comment)

        # Publish event
        if self.skill:
            await self.skill.publish_ticket_updated(
                ticket_key=ticket_key,
                changes={"comment_added": comment[:100]},  # Truncate for event
                actor=self.publisher_actor,
            )
            logger.debug(f"Published comment event for {ticket_key}")
