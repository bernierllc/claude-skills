#!/usr/bin/env python3
"""
Content Decomposer - Extracts semantic units from source content.

Breaks down content (meeting notes, feature specs, etc.) into discrete
facts that can be individually integrated into target documents.
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .semantic_units import (
    SemanticUnit,
    create_timeline_unit,
    create_feature_unit,
    create_decision_unit,
    create_metric_unit,
    create_risk_unit,
    create_action_item_unit,
    create_team_assignment_unit,
)


class ContentDecomposer:
    """Decomposes content into semantic units."""

    def decompose(self, content: str, content_type: str) -> List[SemanticUnit]:
        """
        Main entry point for content decomposition.

        Args:
            content: Raw content to decompose
            content_type: Type hint ("meeting_notes", "feature_spec", etc.)

        Returns:
            List of SemanticUnit objects
        """

        if content_type == "meeting_notes":
            return self.decompose_meeting_notes(content)
        elif content_type == "feature_spec":
            return self.decompose_feature_spec(content)
        elif content_type == "api_docs":
            return self.decompose_api_docs(content)
        else:
            # Generic decomposition for unknown types
            return self.decompose_generic(content)

    def decompose_meeting_notes(self, content: str) -> List[SemanticUnit]:
        """
        Extract semantic units from meeting notes.

        Patterns detected:
        - Timelines: "Q1 2026", "March 15", "Phase 1", etc.
        - Features: Bullet points, "capability:", "feature:", etc.
        - Decisions: "✓", "approved", "decided", etc.
        - Metrics: Numbers with %, $, "ROI", "efficiency", etc.
        - Risks: "Risk:", "challenge:", "concern:", etc.
        - Action items: "→", "TODO:", "Action:", assigned tasks
        - Team: "assigned", role assignments, names
        """

        units = []
        lines = content.split('\n')

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # Check each pattern in priority order
            # (Some lines might match multiple patterns, take highest priority)

            # 1. Action items (highest priority)
            if self._is_action_item(line):
                unit = self._extract_action_item(line, i)
                if unit:
                    units.append(unit)
                    continue

            # 2. Decisions
            if self._is_decision(line):
                unit = self._extract_decision(line, i)
                if unit:
                    units.append(unit)
                    continue

            # 3. Timeline
            if self._is_timeline(line):
                unit = self._extract_timeline(line, i)
                if unit:
                    units.append(unit)
                    continue

            # 4. Risk
            if self._is_risk(line):
                unit = self._extract_risk(line, i)
                if unit:
                    units.append(unit)
                    continue

            # 5. Metric
            if self._is_metric(line):
                unit = self._extract_metric(line, i)
                if unit:
                    units.append(unit)
                    continue

            # 6. Team assignment
            if self._is_team_assignment(line):
                unit = self._extract_team_assignment(line, i)
                if unit:
                    units.append(unit)
                    continue

            # 7. Feature
            if self._is_feature(line):
                unit = self._extract_feature(line, i)
                if unit:
                    units.append(unit)

        return units

    # ===== PATTERN DETECTION =====

    def _is_timeline(self, line: str) -> bool:
        """Detect if line contains timeline information."""
        timeline_patterns = [
            r'Q\d \d{4}',                    # Q1 2026
            r'\w+ \d{4}',                     # March 2026
            r'\w+ \d{1,2},? \d{4}',          # March 15, 2026
            r'Phase \d+',                     # Phase 1
            r'\d{1,2}/\d{1,2}/\d{2,4}',      # 3/15/2026
            r'Week \d+',                      # Week 5
            r'Sprint \d+',                    # Sprint 3
        ]

        return any(re.search(p, line, re.IGNORECASE) for p in timeline_patterns)

    def _is_feature(self, line: str) -> bool:
        """Detect if line describes a feature."""
        # Bullet points often list features
        if line.startswith('• ') or line.startswith('- ') or line.startswith('* '):
            return True

        # Feature indicators
        indicators = [
            'feature:', 'capability:', 'functionality:',
            'includes:', 'provides:', 'supports:',
            'enables:', 'allows:',
        ]

        return any(ind in line.lower() for ind in indicators)

    def _is_decision(self, line: str) -> bool:
        """Detect if line contains a decision."""
        decision_indicators = [
            '✓', '✔', '☑',
            'approved', 'decided', 'agreed',
            'decision:', 'outcome:',
            'accepted', 'rejected',
            'go ahead', 'greenlit',
        ]

        return any(ind in line.lower() for ind in decision_indicators)

    def _is_risk(self, line: str) -> bool:
        """Detect if line describes a risk or challenge."""
        risk_indicators = [
            'risk:', 'challenge:', 'concern:',
            'potential issue', 'problem:',
            'blocker:', 'dependency:',
            'limitation:', 'constraint:',
        ]

        return any(ind in line.lower() for ind in risk_indicators)

    def _is_metric(self, line: str) -> bool:
        """Detect if line contains a metric or measurement."""
        # Look for numbers with units
        metric_patterns = [
            r'\d+%',                          # 40%
            r'\$\d+',                         # $100K
            r'\d+x',                          # 5x
            r'\d+ (hours?|days?|weeks?)',     # 3 weeks
        ]

        if any(re.search(p, line) for p in metric_patterns):
            return True

        # Metric keywords
        metric_keywords = [
            'roi', 'efficiency', 'improvement',
            'reduction', 'increase', 'savings',
            'revenue', 'cost', 'performance',
        ]

        return any(kw in line.lower() for kw in metric_keywords)

    def _is_action_item(self, line: str) -> bool:
        """Detect if line contains an action item."""
        action_indicators = [
            '→', '⮕', '»',
            'todo:', 'action:', 'next step:',
            'to do:', 'task:',
        ]

        # Check for assignment pattern: "Name to do X by Date"
        if ' to ' in line.lower() and ' by ' in line.lower():
            return True

        return any(ind in line.lower() for ind in action_indicators)

    def _is_team_assignment(self, line: str) -> bool:
        """Detect if line contains team/role assignment."""
        team_indicators = [
            'assigned', 'lead:', 'owner:',
            'responsible:', 'point person:',
            'manager:', 'engineer:', 'designer:',
        ]

        return any(ind in line.lower() for ind in team_indicators)

    # ===== CONTENT EXTRACTION =====

    def _extract_timeline(self, line: str, source_line: int) -> Optional[SemanticUnit]:
        """Extract timeline information from line."""
        # Clean up the line
        content = line.strip()

        # Remove common prefixes
        prefixes = ['Timeline:', 'Milestone:', 'Date:', 'Schedule:']
        for prefix in prefixes:
            if content.startswith(prefix):
                content = content[len(prefix):].strip()

        if not content:
            return None

        return create_timeline_unit(
            content=content,
            source_line=source_line,
            original_line=line
        )

    def _extract_feature(self, line: str, source_line: int) -> Optional[SemanticUnit]:
        """Extract feature from line."""
        # Clean up
        content = line.strip()

        # Remove bullet points
        for bullet in ['• ', '- ', '* ', '→ ']:
            if content.startswith(bullet):
                content = content[len(bullet):].strip()

        # Remove "Feature:" prefix
        if content.lower().startswith('feature:'):
            content = content[8:].strip()

        if not content:
            return None

        return create_feature_unit(
            content=content,
            source_line=source_line,
            original_line=line
        )

    def _extract_decision(self, line: str, source_line: int) -> Optional[SemanticUnit]:
        """Extract decision from line."""
        content = line.strip()

        # Remove checkmarks
        for check in ['✓ ', '✔ ', '☑ ']:
            if content.startswith(check):
                content = content[2:].strip()

        # Remove "Decision:" prefix
        if content.lower().startswith('decision:'):
            content = content[9:].strip()

        if not content:
            return None

        return create_decision_unit(
            content=content,
            source_line=source_line,
            original_line=line
        )

    def _extract_risk(self, line: str, source_line: int) -> Optional[SemanticUnit]:
        """Extract risk from line."""
        content = line.strip()

        # Extract risk and mitigation if present
        if 'mitigation:' in content.lower():
            # Split into risk and mitigation
            parts = re.split(r'mitigation:', content, flags=re.IGNORECASE)
            if len(parts) == 2:
                risk_part = parts[0].strip()
                mitigation_part = parts[1].strip()

                # Remove "Risk:" prefix from risk part
                if risk_part.lower().startswith('risk:'):
                    risk_part = risk_part[5:].strip()

                # Combine for full content
                content = f"{risk_part} (Mitigation: {mitigation_part})"
        else:
            # Just risk, remove prefix
            if content.lower().startswith('risk:'):
                content = content[5:].strip()

        if not content:
            return None

        return create_risk_unit(
            content=content,
            source_line=source_line,
            original_line=line
        )

    def _extract_metric(self, line: str, source_line: int) -> Optional[SemanticUnit]:
        """Extract metric from line."""
        content = line.strip()

        # Remove common metric prefixes
        prefixes = ['Impact:', 'ROI:', 'Metric:', 'KPI:']
        for prefix in prefixes:
            if content.startswith(prefix):
                content = content[len(prefix):].strip()

        if not content:
            return None

        return create_metric_unit(
            content=content,
            source_line=source_line,
            original_line=line
        )

    def _extract_action_item(self, line: str, source_line: int) -> Optional[SemanticUnit]:
        """Extract action item from line."""
        content = line.strip()

        # Remove arrow prefixes
        for arrow in ['→ ', '⮕ ', '» ']:
            if content.startswith(arrow):
                content = content[2:].strip()

        # Remove "TODO:" prefix
        if content.lower().startswith('todo:'):
            content = content[5:].strip()
        elif content.lower().startswith('action:'):
            content = content[7:].strip()

        if not content:
            return None

        return create_action_item_unit(
            content=content,
            source_line=source_line,
            original_line=line
        )

    def _extract_team_assignment(self, line: str, source_line: int) -> Optional[SemanticUnit]:
        """Extract team assignment from line."""
        content = line.strip()

        # Remove checkmarks if present
        for check in ['✓ ', '✔ ', '☑ ']:
            if content.startswith(check):
                content = content[2:].strip()

        # Extract role and person
        # Pattern: "Assigned X as Y" or "Y: X"
        if 'assigned' in content.lower():
            # "Assigned Kevin as technical lead"
            pass  # Keep as is
        elif ':' in content:
            # "Technical Lead: Kevin Patel"
            pass  # Keep as is

        if not content:
            return None

        return create_team_assignment_unit(
            content=content,
            source_line=source_line,
            original_line=line
        )

    def decompose_feature_spec(self, content: str) -> List[SemanticUnit]:
        """Decompose feature specification document."""
        # TODO: Implement feature spec decomposition
        # For now, use generic decomposition
        return self.decompose_generic(content)

    def decompose_api_docs(self, content: str) -> List[SemanticUnit]:
        """Decompose API documentation."""
        # TODO: Implement API docs decomposition
        # For now, use generic decomposition
        return self.decompose_generic(content)

    def decompose_generic(self, content: str) -> List[SemanticUnit]:
        """
        Generic decomposition for unknown content types.

        Uses simple heuristics to extract units.
        """
        units = []
        lines = content.split('\n')

        for i, line in enumerate(lines):
            line = line.strip()
            if not line or len(line) < 10:  # Skip very short lines
                continue

            # Try timeline first
            if self._is_timeline(line):
                unit = self._extract_timeline(line, i)
                if unit:
                    units.append(unit)

        return units


# Helper functions for testing

def decompose_and_print(content: str, content_type: str):
    """Decompose content and print results (for testing)."""
    decomposer = ContentDecomposer()
    units = decomposer.decompose(content, content_type)

    print(f"\n{'='*80}")
    print(f"CONTENT DECOMPOSITION ({content_type})")
    print(f"{'='*80}\n")

    print(f"Found {len(units)} semantic units:\n")

    for i, unit in enumerate(units, 1):
        print(f"{i}. {unit}")

    print(f"\n{'='*80}\n")

    return units
