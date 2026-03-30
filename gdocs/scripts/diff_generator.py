#!/usr/bin/env python3
"""
Diff Generator - Creates visual previews of document changes.

Generates human-readable diffs showing exactly what will change in the document
before any modifications are applied. Supports multiple integration strategies
and presents changes in a clear, reviewable format.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from .semantic_units import IntegrationStrategy


@dataclass
class DiffEntry:
    """A single change in the diff preview."""

    section_name: str
    action: str  # 'add', 'update', 'merge', 'skip'
    old_content: Optional[str]
    new_content: str
    unit_type: str
    confidence: float
    reasoning: str
    line_context: str  # Additional context for display


class DiffGenerator:
    """Generates visual diff previews from integration strategies."""

    def __init__(self):
        """Initialize diff generator."""
        pass

    def generate_diff(
        self,
        strategies: List[IntegrationStrategy]
    ) -> List[DiffEntry]:
        """
        Generate diff entries from integration strategies.

        Args:
            strategies: List of integration strategies

        Returns:
            List of diff entries for display
        """

        diff_entries = []

        for strategy in strategies:
            # Skip items don't show in diff (no changes)
            if strategy.action == 'skip':
                continue

            # Create diff entry based on action
            if strategy.action == 'add':
                entry = self._create_add_entry(strategy)
            elif strategy.action == 'update':
                entry = self._create_update_entry(strategy)
            elif strategy.action == 'merge':
                entry = self._create_merge_entry(strategy)
            else:
                continue

            diff_entries.append(entry)

        return diff_entries

    def _create_add_entry(self, strategy: IntegrationStrategy) -> DiffEntry:
        """Create diff entry for ADD action."""

        return DiffEntry(
            section_name=strategy.target_section,
            action='add',
            old_content=None,
            new_content=strategy.new_content,
            unit_type=strategy.unit.type,
            confidence=strategy.confidence,
            reasoning=strategy.reasoning,
            line_context=f"Adding new {strategy.unit.type}"
        )

    def _create_update_entry(self, strategy: IntegrationStrategy) -> DiffEntry:
        """Create diff entry for UPDATE action."""

        old_content = (
            strategy.existing_content.content
            if strategy.existing_content else ""
        )

        return DiffEntry(
            section_name=strategy.target_section,
            action='update',
            old_content=old_content,
            new_content=strategy.new_content,
            unit_type=strategy.unit.type,
            confidence=strategy.confidence,
            reasoning=strategy.reasoning,
            line_context=f"Updating existing {strategy.unit.type}"
        )

    def _create_merge_entry(self, strategy: IntegrationStrategy) -> DiffEntry:
        """Create diff entry for MERGE action."""

        old_content = (
            strategy.existing_content.content
            if strategy.existing_content else ""
        )

        return DiffEntry(
            section_name=strategy.target_section,
            action='merge',
            old_content=old_content,
            new_content=strategy.new_content,
            unit_type=strategy.unit.type,
            confidence=strategy.confidence,
            reasoning=strategy.reasoning,
            line_context=f"Merging with existing {strategy.unit.type}"
        )

    def format_diff_for_display(
        self,
        diff_entries: List[DiffEntry],
        show_skipped: bool = False
    ) -> str:
        """
        Format diff entries as human-readable text.

        Args:
            diff_entries: List of diff entries
            show_skipped: Whether to show skipped items

        Returns:
            Formatted diff string
        """

        output = []

        # Header
        output.append("=" * 80)
        output.append("DOCUMENT CHANGES PREVIEW")
        output.append("=" * 80)
        output.append("")

        # Summary
        total_changes = len(diff_entries)
        adds = sum(1 for e in diff_entries if e.action == 'add')
        updates = sum(1 for e in diff_entries if e.action == 'update')
        merges = sum(1 for e in diff_entries if e.action == 'merge')

        output.append(f"Total Changes: {total_changes}")
        output.append(f"  • {adds} additions")
        output.append(f"  • {updates} updates")
        output.append(f"  • {merges} merges")
        output.append("")
        output.append("-" * 80)
        output.append("")

        # Group by section
        by_section = {}
        for entry in diff_entries:
            if entry.section_name not in by_section:
                by_section[entry.section_name] = []
            by_section[entry.section_name].append(entry)

        # Display each section's changes
        for section_name in sorted(by_section.keys()):
            entries = by_section[section_name]

            output.append(f"\n📄 Section: {section_name}")
            output.append(f"   {len(entries)} change(s)")
            output.append("")

            for i, entry in enumerate(entries, 1):
                output.append(f"   {i}. {entry.action.upper()} - {entry.unit_type}")
                output.append(f"      Confidence: {entry.confidence:.0%}")
                output.append("")

                if entry.action == 'add':
                    output.append(f"      + {entry.new_content}")

                elif entry.action == 'update':
                    output.append(f"      - {entry.old_content}")
                    output.append(f"      + {entry.new_content}")

                elif entry.action == 'merge':
                    output.append(f"      ~ {entry.old_content}")
                    output.append(f"      + {entry.new_content}")

                output.append("")

        output.append("=" * 80)
        output.append("")

        return "\n".join(output)

    def format_diff_as_unified(
        self,
        diff_entries: List[DiffEntry]
    ) -> str:
        """
        Format diff entries as unified diff format.

        Similar to git diff output.
        """

        output = []

        # Group by section
        by_section = {}
        for entry in diff_entries:
            if entry.section_name not in by_section:
                by_section[entry.section_name] = []
            by_section[entry.section_name].append(entry)

        for section_name in sorted(by_section.keys()):
            entries = by_section[section_name]

            output.append(f"diff --git a/{section_name} b/{section_name}")
            output.append(f"--- a/{section_name}")
            output.append(f"+++ b/{section_name}")
            output.append("")

            for entry in entries:
                if entry.action == 'add':
                    output.append(f"+ {entry.new_content}")

                elif entry.action == 'update':
                    output.append(f"- {entry.old_content}")
                    output.append(f"+ {entry.new_content}")

                elif entry.action == 'merge':
                    output.append(f"  {entry.old_content}")
                    output.append(f"+ {entry.new_content}")

            output.append("")

        return "\n".join(output)

    def get_diff_summary(
        self,
        diff_entries: List[DiffEntry]
    ) -> Dict[str, Any]:
        """
        Get summary statistics of diff.

        Returns:
            Dictionary with diff statistics
        """

        total_changes = len(diff_entries)

        # Count by action
        action_counts = {
            'add': sum(1 for e in diff_entries if e.action == 'add'),
            'update': sum(1 for e in diff_entries if e.action == 'update'),
            'merge': sum(1 for e in diff_entries if e.action == 'merge')
        }

        # Count by section
        sections = set(e.section_name for e in diff_entries)

        # Average confidence
        avg_confidence = (
            sum(e.confidence for e in diff_entries) / total_changes
            if total_changes > 0 else 0
        )

        # High confidence changes
        high_confidence = sum(1 for e in diff_entries if e.confidence > 0.8)

        return {
            'total_changes': total_changes,
            'actions': action_counts,
            'sections_modified': sorted(list(sections)),
            'avg_confidence': avg_confidence,
            'high_confidence_changes': high_confidence
        }

    def export_diff_as_json(
        self,
        diff_entries: List[DiffEntry]
    ) -> Dict[str, Any]:
        """
        Export diff as JSON for programmatic use.

        Returns:
            Dictionary representation of diff
        """

        return {
            'timestamp': datetime.now().isoformat(),
            'summary': self.get_diff_summary(diff_entries),
            'changes': [
                {
                    'section': entry.section_name,
                    'action': entry.action,
                    'type': entry.unit_type,
                    'old_content': entry.old_content,
                    'new_content': entry.new_content,
                    'confidence': entry.confidence,
                    'reasoning': entry.reasoning
                }
                for entry in diff_entries
            ]
        }

    def generate_interactive_preview(
        self,
        diff_entries: List[DiffEntry]
    ) -> str:
        """
        Generate interactive preview with color indicators.

        Uses emoji and formatting for terminal display.
        """

        output = []

        # Header with emoji
        output.append("\n" + "🔍 " + "=" * 76 + " 🔍")
        output.append("                    DOCUMENT INTEGRATION PREVIEW")
        output.append("=" * 80 + "\n")

        # Quick summary
        summary = self.get_diff_summary(diff_entries)

        output.append(f"📊 Summary:")
        output.append(f"   Total Changes: {summary['total_changes']}")
        output.append(f"   ➕ Additions: {summary['actions']['add']}")
        output.append(f"   🔄 Updates: {summary['actions']['update']}")
        output.append(f"   🔀 Merges: {summary['actions']['merge']}")
        output.append(f"   📁 Sections Modified: {len(summary['sections_modified'])}")
        output.append(f"   ✅ Confidence: {summary['avg_confidence']:.0%}")
        output.append("")

        output.append("─" * 80)
        output.append("")

        # Group by section
        by_section = {}
        for entry in diff_entries:
            if entry.section_name not in by_section:
                by_section[entry.section_name] = []
            by_section[entry.section_name].append(entry)

        # Display each section
        for idx, section_name in enumerate(sorted(by_section.keys()), 1):
            entries = by_section[section_name]

            # Section header
            output.append(f"\n📄 [{idx}/{len(by_section)}] {section_name}")
            output.append(f"   {len(entries)} change(s) in this section")
            output.append("")

            for i, entry in enumerate(entries, 1):
                # Action icon
                action_icons = {
                    'add': '➕',
                    'update': '🔄',
                    'merge': '🔀'
                }
                icon = action_icons.get(entry.action, '❓')

                # Confidence indicator
                conf_icon = "🟢" if entry.confidence > 0.8 else "🟡" if entry.confidence > 0.6 else "🟠"

                output.append(f"   {icon} [{i}] {entry.action.upper()} {entry.unit_type}")
                output.append(f"       {conf_icon} Confidence: {entry.confidence:.0%}")
                output.append("")

                # Show changes
                if entry.action == 'add':
                    output.append(f"       ➕ {self._format_content(entry.new_content)}")

                elif entry.action == 'update':
                    output.append(f"       ➖ OLD: {self._format_content(entry.old_content)}")
                    output.append(f"       ➕ NEW: {self._format_content(entry.new_content)}")

                elif entry.action == 'merge':
                    output.append(f"       📝 EXISTING: {self._format_content(entry.old_content)}")
                    output.append(f"       ➕ ADDING: {self._format_content(entry.new_content)}")

                output.append("")

        output.append("=" * 80)
        output.append("")

        return "\n".join(output)

    def _format_content(self, content: Optional[str], max_length: int = 80) -> str:
        """Format content for display, truncating if needed."""

        if not content:
            return "(empty)"

        # Remove extra whitespace
        content = " ".join(content.split())

        # Truncate if too long
        if len(content) > max_length:
            return content[:max_length-3] + "..."

        return content


# Testing helper
def test_diff_generator(strategies: List[IntegrationStrategy]):
    """Test diff generator with integration strategies (for development)."""

    generator = DiffGenerator()

    print("\n" + "="*80)
    print("DIFF GENERATOR TEST")
    print("="*80 + "\n")

    print(f"Generating diff from {len(strategies)} strategies...\n")

    # Generate diff
    diff_entries = generator.generate_diff(strategies)

    print(f"Created {len(diff_entries)} diff entries\n")

    # Show interactive preview
    preview = generator.generate_interactive_preview(diff_entries)
    print(preview)

    # Show summary
    summary = generator.get_diff_summary(diff_entries)

    print("\nDiff Summary:")
    print(f"  Total Changes: {summary['total_changes']}")
    print(f"  Sections Modified: {len(summary['sections_modified'])}")
    print(f"  Average Confidence: {summary['avg_confidence']:.0%}")
    print()

    return diff_entries, preview
