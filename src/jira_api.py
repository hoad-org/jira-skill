"""Jira Cloud API client wrapper."""

import os
from typing import List, Dict, Any, Optional
import requests
from datetime import datetime

from .models import Epic, Ticket, Subtask, TicketStatus, JiraConfig


class JiraAPIError(Exception):
    """Jira API error."""
    pass


class JiraAPI:
    """Wrapper around Jira Cloud REST API."""

    def __init__(self, config: JiraConfig):
        """Initialize Jira API client."""
        self.config = config
        self.base_url = f"https://{config.cloud_id}.atlassian.net/rest/api/3"
        self.headers = self._get_headers()

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        if self.config.use_mcp_auth:
            # MCP auth is handled by the MCP connector
            # For now, we'll assume token is in JIRA_API_TOKEN env var
            token = os.getenv("JIRA_API_TOKEN", self.config.api_token)
        else:
            token = self.config.api_token

        if token:
            headers["Authorization"] = f"Bearer {token}"

        return headers

    def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to Jira API."""
        url = f"{self.base_url}{path}"

        try:
            response = requests.request(
                method,
                url,
                headers=self.headers,
                json=json_data,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            return response.json() if response.text else {}
        except requests.exceptions.RequestException as e:
            raise JiraAPIError(f"Jira API error: {e}") from e

    def get_epics(self, project_key: str) -> List[Epic]:
        """Fetch all epics in a project."""
        # JQL query for epics
        jql = f"project = {project_key} AND type = Epic ORDER BY created DESC"
        issues = self._request(
            "GET",
            "/search",
            params={"jql": jql, "maxResults": 50}
        )

        epics = []
        for issue in issues.get("issues", []):
            epic = self._parse_epic(issue)
            epics.append(epic)

        return epics

    def get_epic(self, epic_key: str) -> Epic:
        """Fetch a specific epic with its tickets."""
        issue = self._request("GET", f"/issues/{epic_key}")
        epic = self._parse_epic(issue)

        # Fetch tickets linked to this epic
        epic_link_field = self.config.projects.get(epic_key.split("-")[0])
        if epic_link_field:
            jql = f'"{epic_link_field.epic_link_field}" = {epic_key}'
            tickets_data = self._request(
                "GET",
                "/search",
                params={"jql": jql, "maxResults": 100}
            )
            for ticket_issue in tickets_data.get("issues", []):
                ticket = self._parse_ticket(ticket_issue)
                epic.tickets.append(ticket)

        return epic

    def get_tickets(self, project_key: str, epic_key: Optional[str] = None) -> List[Ticket]:
        """Fetch tickets from a project or epic."""
        if epic_key:
            jql = f'"{self._get_epic_link_field(project_key)}" = {epic_key} AND type != Epic'
        else:
            jql = f"project = {project_key} AND type != Epic ORDER BY created DESC"

        issues = self._request(
            "GET",
            "/search",
            params={"jql": jql, "maxResults": 100}
        )

        tickets = []
        for issue in issues.get("issues", []):
            ticket = self._parse_ticket(issue)
            tickets.append(ticket)

        return tickets

    def get_ticket(self, ticket_key: str) -> Ticket:
        """Fetch a specific ticket with subtasks."""
        issue = self._request("GET", f"/issues/{ticket_key}")
        ticket = self._parse_ticket(issue)

        # Parse subtasks
        for sub in issue.get("fields", {}).get("subtasks", []):
            subtask = self._parse_subtask(sub)
            ticket.subtasks.append(subtask)

        return ticket

    def create_epic(
        self,
        project_key: str,
        name: str,
        description: str,
        assignee: Optional[str] = None,
    ) -> str:
        """Create a new epic. Returns epic key."""
        assignee = assignee or self.config.default_assignee
        fields = {
            "project": {"key": project_key},
            "summary": name,
            "description": description,
            "issuetype": {"name": "Epic"},
        }

        if assignee:
            fields["assignee"] = {"name": assignee}

        result = self._request(
            "POST",
            "/issues",
            json_data={"fields": fields}
        )
        return result.get("key")

    def create_ticket(
        self,
        project_key: str,
        summary: str,
        description: str,
        story_points: Optional[int] = None,
        assignee: Optional[str] = None,
        epic_key: Optional[str] = None,
        labels: Optional[List[str]] = None,
    ) -> str:
        """Create a new ticket. Returns ticket key."""
        assignee = assignee or self.config.default_assignee
        labels = labels or self.config.default_labels

        fields = {
            "project": {"key": project_key},
            "summary": summary,
            "description": description,
            "issuetype": {"name": "Story"},
        }

        if assignee:
            fields["assignee"] = {"name": assignee}

        if story_points:
            point_field = self.config.projects[project_key].story_point_field
            fields[point_field] = story_points

        if epic_key:
            epic_field = self.config.projects[project_key].epic_link_field
            fields[epic_field] = epic_key

        if labels:
            fields["labels"] = labels

        result = self._request(
            "POST",
            "/issues",
            json_data={"fields": fields}
        )
        return result.get("key")

    def create_subtask(
        self,
        parent_key: str,
        summary: str,
        description: str,
        story_points: Optional[int] = None,
        assignee: Optional[str] = None,
    ) -> str:
        """Create a subtask. Returns subtask key."""
        assignee = assignee or self.config.default_assignee

        fields = {
            "project": {"key": parent_key.split("-")[0]},
            "parent": {"key": parent_key},
            "summary": summary,
            "description": description,
            "issuetype": {"name": "Subtask"},
        }

        if assignee:
            fields["assignee"] = {"name": assignee}

        if story_points:
            project_key = parent_key.split("-")[0]
            point_field = self.config.projects[project_key].story_point_field
            fields[point_field] = story_points

        result = self._request(
            "POST",
            "/issues",
            json_data={"fields": fields}
        )
        return result.get("key")

    def update_ticket(
        self,
        ticket_key: str,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        story_points: Optional[int] = None,
        status: Optional[str] = None,
        assignee: Optional[str] = None,
        labels: Optional[List[str]] = None,
    ) -> None:
        """Update a ticket."""
        fields = {}

        if summary:
            fields["summary"] = summary
        if description:
            fields["description"] = description
        if assignee:
            fields["assignee"] = {"name": assignee}
        if labels is not None:
            fields["labels"] = labels

        if story_points:
            project_key = ticket_key.split("-")[0]
            point_field = self.config.projects[project_key].story_point_field
            fields[point_field] = story_points

        if fields:
            self._request(
                "PUT",
                f"/issues/{ticket_key}",
                json_data={"fields": fields}
            )

        # Status transitions require a separate transition API call
        if status:
            self.transition_ticket(ticket_key, status)

    def transition_ticket(self, ticket_key: str, to_status: str) -> None:
        """Transition a ticket to a new status."""
        # Get available transitions
        transitions = self._request(
            "GET",
            f"/issues/{ticket_key}/transitions"
        )

        target_transition = None
        for trans in transitions.get("transitions", []):
            if trans["to"]["name"] == to_status:
                target_transition = trans
                break

        if not target_transition:
            raise JiraAPIError(f"Cannot transition to '{to_status}' from current status")

        self._request(
            "POST",
            f"/issues/{ticket_key}/transitions",
            json_data={"transition": {"id": target_transition["id"]}}
        )

    def assign_ticket(self, ticket_key: str, assignee: str) -> None:
        """Assign a ticket to a user."""
        self._request(
            "PUT",
            f"/issues/{ticket_key}/assignee",
            json_data={"name": assignee}
        )

    def add_comment(self, ticket_key: str, comment: str) -> None:
        """Add a comment to a ticket."""
        self._request(
            "POST",
            f"/issues/{ticket_key}/comments",
            json_data={
                "body": {
                    "version": 1,
                    "type": "doc",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": comment}]
                        }
                    ]
                }
            }
        )

    def search(self, jql: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Search Jira using JQL."""
        results = self._request(
            "GET",
            "/search",
            params={"jql": jql, "maxResults": max_results}
        )
        return results.get("issues", [])

    def _parse_epic(self, issue: Dict[str, Any]) -> Epic:
        """Parse Jira issue into Epic object."""
        fields = issue.get("fields", {})
        return Epic(
            key=issue.get("key"),
            name=fields.get("summary", ""),
            description=fields.get("description", "") or "",
            status=fields.get("status", {}).get("name", "Unknown"),
            assignee=fields.get("assignee", {}).get("name"),
            labels=fields.get("labels", []),
            created=fields.get("created"),
            updated=fields.get("updated"),
            url=issue.get("self"),
        )

    def _parse_ticket(self, issue: Dict[str, Any]) -> Ticket:
        """Parse Jira issue into Ticket object."""
        fields = issue.get("fields", {})
        project_key = issue.get("key").split("-")[0]

        points = None
        if project_key in self.config.projects:
            point_field = self.config.projects[project_key].story_point_field
            points = fields.get(point_field)

        return Ticket(
            key=issue.get("key"),
            summary=fields.get("summary", ""),
            description=fields.get("description", "") or "",
            status=fields.get("status", {}).get("name", "Unknown"),
            assignee=fields.get("assignee", {}).get("name"),
            reporter=fields.get("reporter", {}).get("name"),
            points=points,
            labels=fields.get("labels", []),
            created=fields.get("created"),
            updated=fields.get("updated"),
            url=issue.get("self"),
        )

    def _parse_subtask(self, issue: Dict[str, Any]) -> Subtask:
        """Parse Jira subtask into Subtask object."""
        fields = issue.get("fields", {})
        return Subtask(
            key=issue.get("key"),
            summary=fields.get("summary", ""),
            status=fields.get("status", {}).get("name", "Unknown"),
            assignee=fields.get("assignee", {}).get("name"),
            created=fields.get("created"),
            updated=fields.get("updated"),
        )

    def _get_epic_link_field(self, project_key: str) -> str:
        """Get epic link field ID for project."""
        if project_key not in self.config.projects:
            return "customfield_10001"  # Default
        return self.config.projects[project_key].epic_link_field
