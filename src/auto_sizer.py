"""Auto-sizing logic for story points."""

from typing import Optional, List, Dict
from .models import Ticket, JiraConfig


class AutoSizer:
    """Intelligent story point estimation."""

    def __init__(self, config: JiraConfig):
        """Initialize with config."""
        self.config = config
        self.complexity_keywords = config.complexity_keywords

    def estimate(self, summary: str, description: str = "") -> int:
        """Estimate story points for a ticket."""
        points = 2  # Base points

        combined_text = f"{summary} {description}".lower()

        # Keyword analysis
        for keyword, value in self.complexity_keywords.items():
            if keyword in combined_text:
                points += value

        # Length-based adjustment
        word_count = len(combined_text.split())
        if word_count > 100:
            points += 3
        elif word_count > 50:
            points += 2

        # Complexity markers
        if any(m in combined_text for m in ["integrate", "migrate", "cross-team", "third-party"]):
            points += 2

        # Uncertainty markers
        if any(m in combined_text for m in ["unknown", "research", "investigate", "spike"]):
            points += 1

        return min(max(points, 1), 21)  # Clamp to 1-21

    def refine_with_history(
        self,
        estimate: int,
        similar_tickets: List[Ticket]
    ) -> int:
        """Refine estimate based on historical similar tickets."""
        if not similar_tickets or not any(t.points for t in similar_tickets):
            return estimate

        historical_points = [t.points for t in similar_tickets if t.points]
        avg_points = sum(historical_points) / len(historical_points)

        # Adjust estimate if significantly different from history
        if avg_points > 0 and estimate > 0:
            ratio = avg_points / estimate
            if 0.5 < ratio < 2:
                # Within reasonable range, blend them
                return int((estimate + avg_points) / 2)

        return estimate

    def suggest_subtasks(self, points: int) -> bool:
        """Suggest creating subtasks if points exceed max."""
        return points > self.config.projects and points > 13
