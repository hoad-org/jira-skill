"""Parse requirements into epic/ticket/subtask scope."""

import re
from typing import Dict, List

from .models import JiraConfig, RequirementScope


class RequirementParser:
    """Parse plain-language requirements into work units."""

    def __init__(self, config: JiraConfig):
        """Initialize parser with config."""
        self.config = config
        self.complexity_keywords = config.complexity_keywords
        self.epic_max = 40
        self.ticket_max = 13

    def parse(self, requirement: str) -> RequirementScope:
        """Parse requirement into scope tree (epic > tickets > subtasks)."""
        # Clean up requirement text
        requirement = requirement.strip()

        # Calculate base complexity from keywords
        base_points = self._estimate_points(requirement)

        # Determine scope type (epic vs ticket)
        if base_points > self.epic_max or self._is_complex_requirement(requirement):
            # Decompose into sub-requirements
            root = self._decompose_into_epic(requirement, base_points)
        else:
            # Single ticket
            root = self._create_ticket_scope(requirement, base_points)

        return root

    def _decompose_into_epic(self, requirement: str, total_points: int) -> RequirementScope:
        """Decompose large requirement into epic with tickets."""
        # Extract key noun phrases as ticket titles
        sentences = re.split(r"[.!?]+", requirement)
        sub_items = []

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence or len(sentence) < 10:
                continue

            # Each sentence becomes a ticket
            points = self._estimate_points(sentence)
            if points > 0:
                sub_items.append(self._create_ticket_scope(sentence, points))

        # If no decomposition happened, just create sub-tickets
        if len(sub_items) < 2:
            sub_items = self._suggest_subtasks(requirement, total_points)

        return RequirementScope(
            type="epic",
            title=self._extract_title(requirement),
            description=requirement,
            estimated_points=total_points,
            sub_items=sub_items,
        )

    def _create_ticket_scope(self, requirement: str, points: int) -> RequirementScope:
        """Create a ticket scope, optionally with subtasks."""
        if points > self.ticket_max:
            sub_items = self._suggest_subtasks(requirement, points)
        else:
            sub_items = []

        return RequirementScope(
            type="ticket",
            title=self._extract_title(requirement),
            description=requirement,
            estimated_points=points,
            sub_items=sub_items,
        )

    def _suggest_subtasks(self, requirement: str, parent_points: int) -> List[RequirementScope]:
        """Suggest subtasks for a requirement."""
        subtasks = []

        # Common subtask patterns
        patterns = [
            (r"implement|write|code|develop", "Implementation"),
            (r"test|testing|verify|validation", "Testing"),
            (r"document|doc|docs|comment", "Documentation"),
            (r"review|refactor|optimize|performance", "Code Review & Optimization"),
            (r"deploy|release|staging|production", "Deployment"),
            (r"integrate|integration|connect", "Integration"),
        ]

        found_patterns = []
        for pattern, label in patterns:
            if re.search(pattern, requirement, re.IGNORECASE):
                found_patterns.append(label)

        # If we found patterns, create subtasks
        if found_patterns:
            points_per_subtask = max(1, parent_points // (len(found_patterns) + 1))
            for pattern_label in found_patterns[:3]:  # Max 3 subtasks
                subtasks.append(
                    RequirementScope(
                        type="subtask",
                        title=pattern_label,
                        description=f"{pattern_label} for: {self._extract_title(requirement)}",
                        estimated_points=points_per_subtask,
                    )
                )

        return subtasks

    def _estimate_points(self, text: str) -> int:
        """Estimate story points from requirement text."""
        points = 2  # Base points

        # Add points for complexity keywords
        text_lower = text.lower()
        for keyword, value in self.complexity_keywords.items():
            if keyword in text_lower:
                points += value

        # Adjust based on text length (longer requirements tend to be more complex)
        word_count = len(text.split())
        if word_count > 50:
            points += 2
        elif word_count > 100:
            points += 3

        # Adjust based on common complexity markers
        if any(
            marker in text_lower for marker in ["third-party", "external", "multiple", "cross-team"]
        ):
            points += 2

        return min(points, 40)  # Cap at 40

    def _is_complex_requirement(self, requirement: str) -> bool:
        """Check if requirement is complex enough to be an epic."""
        # Check for multiple sections
        sections = re.split(r"\n\s*\n|;|and", requirement)
        if len(sections) >= 3:
            return True

        # Check for dependency markers
        if any(
            marker in requirement.lower()
            for marker in ["after", "before", "depends on", "requires"]
        ):
            return True

        # Check for cross-domain work
        if any(
            marker in requirement.lower() for marker in ["frontend", "backend", "database", "api"]
        ):
            return True

        return False

    def _extract_title(self, requirement: str) -> str:
        """Extract a concise title from requirement text."""
        # First sentence or first 80 chars
        sentences = re.split(r"[.!?]+", requirement)
        first = sentences[0].strip()

        if len(first) > 80:
            # Truncate at word boundary
            words = first[:80].split()
            return " ".join(words[:-1]) + "..."

        return first

    def scope_to_dict(self, scope: RequirementScope) -> Dict:
        """Convert RequirementScope to dict for display."""
        result = {
            "type": scope.type,
            "title": scope.title,
            "points": scope.estimated_points,
        }

        if scope.sub_items:
            result["subtasks"] = [self.scope_to_dict(sub) for sub in scope.sub_items]

        return result

    def format_scope(self, scope: RequirementScope, indent: int = 0) -> str:
        """Format scope for human-readable output."""
        prefix = "  " * indent
        lines = [f"{prefix}{scope.type.upper()}: {scope.title} (~{scope.estimated_points}pts)"]

        for sub in scope.sub_items:
            lines.append(self.format_scope(sub, indent + 1))

        return "\n".join(lines)
