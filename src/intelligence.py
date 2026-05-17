"""Intelligence layer — velocity, scope creep, stale detection."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .models import Epic, JiraConfig, Ticket


class Intelligence:
    """Intelligent analysis of Jira state."""

    def __init__(self, config: JiraConfig):
        """Initialize intelligence layer."""
        self.config = config

    def calculate_velocity(self, completed_tickets: List[Ticket], days: int = 7) -> float:
        """Calculate team velocity (points per day)."""
        if not completed_tickets:
            return 0.0

        total_points = sum(t.points or 0 for t in completed_tickets)
        return total_points / days if days > 0 else 0.0

    def estimate_completion_date(
        self, remaining_points: int, velocity: float
    ) -> Optional[datetime]:
        """Estimate completion date based on velocity."""
        if velocity <= 0:
            return None

        days_needed = remaining_points / velocity
        return datetime.now() + timedelta(days=days_needed)

    def detect_scope_creep_tickets(self, tickets: List[Ticket]) -> List[Dict]:
        """Find tickets with likely scope creep."""
        issues = []

        for ticket in tickets:
            if not ticket.description:
                continue

            # Check description length vs points
            desc_length = len(ticket.description)
            points = ticket.points or 5

            # Rough heuristic: should be ~50 chars per point
            expected_length = points * 50
            if desc_length > expected_length * 1.5:  # 50% over expected
                issues.append(
                    {
                        "ticket": ticket,
                        "reason": f"Description longer than expected for {points}pts ({desc_length} chars)",
                        "suggestion": "Consider splitting into subtasks or reducing scope",
                    }
                )

        return issues

    def find_stale_tickets(
        self, tickets: List[Ticket], days_threshold: Optional[int] = None
    ) -> List[Ticket]:
        """Find tickets inactive for too long."""
        if days_threshold is None:
            days_threshold = self.config.stale_days_threshold

        stale = []
        cutoff = datetime.now() - timedelta(days=days_threshold)

        for ticket in tickets:
            if ticket.status in ["Done", "Closed"]:
                continue  # Closed tickets don't count

            if ticket.status == "In Progress":
                # Check update time
                if ticket.updated and ticket.updated < cutoff:
                    stale.append(ticket)

        return stale

    def detect_blocked_tickets(self, tickets: List[Ticket]) -> List[Ticket]:
        """Find likely blocked tickets."""
        blocked = []

        for ticket in tickets:
            if ticket.status == "In Progress":
                # Check if has "blocked" label
                if any("block" in label.lower() for label in ticket.labels):
                    blocked.append(ticket)

                # Check for dependency markers in description
                if ticket.description:
                    desc_lower = ticket.description.lower()
                    if any(marker in desc_lower for marker in ["blocked", "waiting", "depends"]):
                        blocked.append(ticket)

        return blocked

    def calculate_epic_health(self, epic: Epic) -> Dict:
        """Calculate health metrics for an epic."""
        total_tickets = len(epic.tickets)
        if total_tickets == 0:
            return {"health": "empty", "progress": 0, "summary": "Epic has no tickets"}

        completed = sum(1 for t in epic.tickets if t.status == "Done")
        in_progress = sum(1 for t in epic.tickets if t.status == "In Progress")
        blocked = sum(
            1 for t in epic.tickets if any("block" in label.lower() for label in t.labels)
        )

        progress = epic.progress_percent()

        # Determine health
        if progress == 100:
            health = "complete"
        elif progress >= 75:
            health = "good"
        elif progress >= 50:
            health = "fair"
        elif progress >= 25:
            health = "slow"
        elif progress == 0:
            health = "not_started"
        else:
            health = "critical"

        return {
            "health": health,
            "progress": progress,
            "completed": completed,
            "in_progress": in_progress,
            "blocked": blocked,
            "total": total_tickets,
            "summary": f"{completed}/{total_tickets} done ({progress}%)"
            + (f", {blocked} blocked" if blocked > 0 else ""),
        }

    def suggest_ticket_consolidation(self, tickets: List[Ticket]) -> List[tuple]:
        """Suggest consolidating similar tickets."""
        suggestions = []

        # Group by keyword similarity
        keyword_groups = {}

        for ticket in tickets:
            if ticket.status in ["Done", "Closed"]:
                continue

            keywords = self._extract_keywords(ticket.summary)
            key_str = " ".join(sorted(keywords))

            if key_str not in keyword_groups:
                keyword_groups[key_str] = []
            keyword_groups[key_str].append(ticket)

        # Find groups with multiple tickets
        for keywords, group in keyword_groups.items():
            if len(group) >= 2 and keywords:
                suggestions.append((keywords, group))

        return suggestions

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text."""
        stop_words = {"a", "the", "and", "or", "is", "to", "for", "with", "in", "on"}
        words = text.lower().split()
        return [w for w in words if len(w) > 3 and w not in stop_words]

    def risk_assessment(self, epic: Epic, velocity: float) -> Dict:
        """Assess risk for epic completion."""
        health = self.calculate_epic_health(epic)

        risks = []

        if health["blocked"] > 0:
            risks.append("blocked_tickets")

        if epic.total_points > 0 and velocity > 0:
            days_to_complete = epic.total_points / velocity
            if days_to_complete > 30:
                risks.append("schedule_risk")

        if health["in_progress"] > 3:
            risks.append("too_many_wip")

        if len([t for t in epic.tickets if not t.assignee]) > 2:
            risks.append("unassigned_work")

        risk_level = "high" if len(risks) >= 3 else "medium" if risks else "low"

        return {
            "level": risk_level,
            "risks": risks,
            "estimated_days": epic.total_points / velocity if velocity > 0 else None,
        }
