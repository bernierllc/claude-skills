#!/usr/bin/env python3
"""
Integration Strategy - Determines how to integrate semantic units.

Takes semantic units, matched sections, and existing content to determine
the appropriate integration action (ADD, UPDATE, MERGE, SKIP) for each unit.
"""

from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

from .semantic_units import (
    SemanticUnit,
    MatchedSection,
    ExistingContent,
    IntegrationStrategy,
    IntegrationAction
)
from .content_finder import ContentFinder


class StrategyDeterminer:
    """Determines integration strategies for semantic units."""

    def __init__(self):
        """Initialize strategy determiner."""
        self.content_finder = ContentFinder(similarity_threshold=0.5)

    def determine_strategy(
        self,
        unit: SemanticUnit,
        matched_section: MatchedSection
    ) -> IntegrationStrategy:
        """
        Determine how to integrate this unit into the matched section.

        Args:
            unit: Semantic unit to integrate
            matched_section: Target section for integration

        Returns:
            IntegrationStrategy with action, content, and reasoning
        """

        # Find existing related content in the section
        existing_matches = self.content_finder.find_existing_content(
            unit,
            matched_section.section
        )

        # Determine action based on existing content
        if existing_matches:
            # Have existing content - decide UPDATE, MERGE, or SKIP
            best_match = existing_matches[0]

            if best_match.confidence >= 0.95:
                # Nearly identical - SKIP
                return self._create_skip_strategy(unit, matched_section, best_match)

            elif best_match.confidence >= 0.75:
                # Similar but different - UPDATE
                return self._create_update_strategy(unit, matched_section, best_match)

            else:
                # Related but complementary - MERGE
                return self._create_merge_strategy(unit, matched_section, best_match)

        else:
            # No existing content - ADD
            return self._create_add_strategy(unit, matched_section)

    def _create_add_strategy(
        self,
        unit: SemanticUnit,
        matched_section: MatchedSection
    ) -> IntegrationStrategy:
        """
        Create ADD strategy for new content.

        Adds unit content as new bullet/paragraph in section.
        """

        # Format new content based on unit type
        new_content = self._format_new_content(unit)

        # Determine insertion index (append to end of section)
        section = matched_section.section
        target_index = section.get('end_index', 0) - 1

        # Calculate confidence (based on section match confidence)
        confidence = matched_section.confidence * 0.9

        reasoning = (
            f"No existing content found. "
            f"Adding new {unit.type} to '{matched_section.section_name}' "
            f"(section match: {matched_section.confidence:.0%})"
        )

        return IntegrationStrategy(
            unit=unit,
            action='add',
            target_section=matched_section.section_name,
            target_index=target_index,
            existing_content=None,
            new_content=new_content,
            confidence=confidence,
            reasoning=reasoning,
            formatting={'type': 'bullet', 'indent': 0}
        )

    def _create_update_strategy(
        self,
        unit: SemanticUnit,
        matched_section: MatchedSection,
        existing: ExistingContent
    ) -> IntegrationStrategy:
        """
        Create UPDATE strategy to replace outdated content.

        Replaces existing content with updated version from unit.
        """

        # Format replacement content
        new_content = self._format_new_content(unit)

        # Use existing content's position
        target_index = existing.start_index

        # Confidence based on match quality
        confidence = min(matched_section.confidence * existing.confidence, 0.95)

        reasoning = (
            f"Found similar content ({existing.confidence:.0%} match). "
            f"Updating existing content with new information. "
            f"Reason: {existing.reasoning}"
        )

        return IntegrationStrategy(
            unit=unit,
            action='update',
            target_section=matched_section.section_name,
            target_index=target_index,
            existing_content=existing,
            new_content=new_content,
            confidence=confidence,
            reasoning=reasoning,
            formatting={'type': 'replace', 'preserve_formatting': True}
        )

    def _create_merge_strategy(
        self,
        unit: SemanticUnit,
        matched_section: MatchedSection,
        existing: ExistingContent
    ) -> IntegrationStrategy:
        """
        Create MERGE strategy to combine complementary content.

        Combines unit content with existing related content.
        """

        # Format merged content
        merged_content = self._format_merged_content(unit, existing)

        # Use existing content's position
        target_index = existing.start_index

        # Confidence reflects uncertainty of merging
        confidence = min(matched_section.confidence * existing.confidence * 0.85, 0.90)

        reasoning = (
            f"Found related content ({existing.confidence:.0%} match). "
            f"Merging new information with existing content. "
            f"Reason: {existing.reasoning}"
        )

        return IntegrationStrategy(
            unit=unit,
            action='merge',
            target_section=matched_section.section_name,
            target_index=target_index,
            existing_content=existing,
            new_content=merged_content,
            confidence=confidence,
            reasoning=reasoning,
            formatting={'type': 'merge', 'combine_method': 'append'}
        )

    def _create_skip_strategy(
        self,
        unit: SemanticUnit,
        matched_section: MatchedSection,
        existing: ExistingContent
    ) -> IntegrationStrategy:
        """
        Create SKIP strategy for duplicate content.

        No changes needed - content already exists.
        """

        # No new content for skipped items
        new_content = ""

        # Use existing content's position for reference
        target_index = existing.start_index

        # High confidence since exact match
        confidence = existing.confidence

        reasoning = (
            f"Content already exists ({existing.confidence:.0%} match). "
            f"Skipping duplicate. "
            f"Found: '{existing.content[:60]}...'"
        )

        return IntegrationStrategy(
            unit=unit,
            action='skip',
            target_section=matched_section.section_name,
            target_index=target_index,
            existing_content=existing,
            new_content=new_content,
            confidence=confidence,
            reasoning=reasoning,
            formatting={}
        )

    def _format_new_content(self, unit: SemanticUnit) -> str:
        """
        Format semantic unit content for insertion into document.

        Args:
            unit: Semantic unit to format

        Returns:
            Formatted content string ready for insertion
        """

        content = unit.content.strip()

        # Remove prefixes that were used for detection
        prefixes_to_remove = [
            '• ', '- ', '* ', '→ ', '⮕ ', '» ',
            '✓ ', '✔ ', '☑ '
        ]

        for prefix in prefixes_to_remove:
            if content.startswith(prefix):
                content = content[len(prefix):].strip()

        # Format based on unit type
        if unit.type == 'timeline':
            # Timeline items as bullets
            return f"• {content}"

        elif unit.type == 'feature':
            # Feature items as bullets
            return f"• {content}"

        elif unit.type == 'decision':
            # Decisions as checked bullets
            return f"✓ {content}"

        elif unit.type == 'risk':
            # Risks with risk indicator
            if not content.lower().startswith('risk:'):
                return f"Risk: {content}"
            return content

        elif unit.type == 'action_item':
            # Action items with arrow
            return f"→ {content}"

        elif unit.type == 'team_assignment':
            # Team assignments as bullets
            return f"• {content}"

        elif unit.type == 'metric':
            # Metrics as plain text or bullets
            if any(indicator in content.lower() for indicator in [':', 'expected', 'roi', 'impact']):
                return content
            return f"• {content}"

        else:
            # Default: bullet point
            return f"• {content}"

    def _format_merged_content(
        self,
        unit: SemanticUnit,
        existing: ExistingContent
    ) -> str:
        """
        Format merged content combining unit with existing content.

        Args:
            unit: New semantic unit
            existing: Existing content to merge with

        Returns:
            Merged content string
        """

        new_part = self._format_new_content(unit)
        existing_part = existing.content.strip()

        # For most types, append new info to existing
        # (More sophisticated merging logic can be added later)

        if unit.type == 'timeline':
            # Combine timelines chronologically (simple append for now)
            return f"{existing_part}\n{new_part}"

        elif unit.type == 'feature':
            # Add as additional feature
            return f"{existing_part}\n{new_part}"

        elif unit.type == 'metric':
            # Combine metrics
            return f"{existing_part} {new_part}"

        else:
            # Default: append with newline
            return f"{existing_part}\n{new_part}"

    def determine_strategies_for_all(
        self,
        units_and_sections: List[Tuple[SemanticUnit, MatchedSection]]
    ) -> List[IntegrationStrategy]:
        """
        Determine integration strategies for multiple units.

        Args:
            units_and_sections: List of (unit, matched_section) tuples

        Returns:
            List of integration strategies
        """

        strategies = []

        for unit, matched_section in units_and_sections:
            strategy = self.determine_strategy(unit, matched_section)
            strategies.append(strategy)

        return strategies

    def get_strategy_summary(
        self,
        strategies: List[IntegrationStrategy]
    ) -> Dict[str, Any]:
        """
        Get summary statistics of integration strategies.

        Returns:
            Dictionary with strategy statistics
        """

        total = len(strategies)

        # Count by action
        action_counts = {
            'add': sum(1 for s in strategies if s.action == 'add'),
            'update': sum(1 for s in strategies if s.action == 'update'),
            'merge': sum(1 for s in strategies if s.action == 'merge'),
            'skip': sum(1 for s in strategies if s.action == 'skip')
        }

        # High confidence strategies (>80%)
        high_confidence = sum(1 for s in strategies if s.confidence > 0.8)

        # Sections that will be modified
        sections_modified = set(
            s.target_section for s in strategies
            if s.action != 'skip'
        )

        # Average confidence
        avg_confidence = (
            sum(s.confidence for s in strategies) / total
            if total > 0 else 0
        )

        return {
            'total_strategies': total,
            'actions': action_counts,
            'high_confidence': high_confidence,
            'sections_modified': sorted(list(sections_modified)),
            'avg_confidence': avg_confidence,
            'modification_rate': (
                (total - action_counts['skip']) / total * 100
                if total > 0 else 0
            )
        }


# Testing helper
def test_strategy_determiner(
    unit: SemanticUnit,
    matched_section: MatchedSection
):
    """Test strategy determiner with unit and section (for development)."""

    determiner = StrategyDeterminer()

    print("\n" + "="*80)
    print("INTEGRATION STRATEGY TEST")
    print("="*80 + "\n")

    print(f"Unit: {unit.type.upper()}")
    print(f"Content: {unit.content[:80]}...")
    print(f"Priority: {unit.priority}/5")
    print()

    print(f"Target Section: {matched_section.section_name}")
    print(f"Section Match Confidence: {matched_section.confidence:.0%}")
    print()

    print("Determining integration strategy...\n")

    strategy = determiner.determine_strategy(unit, matched_section)

    print(f"Action: {strategy.action.upper()}")
    print(f"Confidence: {strategy.confidence:.0%}")
    print(f"Reasoning: {strategy.reasoning}")
    print()

    if strategy.existing_content:
        print("Existing Content:")
        print(f"  Type: {strategy.existing_content.match_type}")
        print(f"  Confidence: {strategy.existing_content.confidence:.0%}")
        print(f"  Content: {strategy.existing_content.content[:100]}...")
        print()

    print("New Content:")
    print(f"  {strategy.new_content[:200]}...")
    print()

    print("="*80 + "\n")

    return strategy
