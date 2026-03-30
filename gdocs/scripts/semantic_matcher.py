#!/usr/bin/env python3
"""
Semantic Matcher - Maps semantic units to document sections.

Determines which document sections are relevant for each semantic unit
using type-based mapping, keyword matching, and semantic similarity.
"""

from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass

from .semantic_units import SemanticUnit, MatchedSection


class SemanticMatcher:
    """Matches semantic units to document sections."""

    # Type-to-section mapping
    # Maps unit types to likely section names
    TYPE_SECTION_MAP = {
        'timeline': [
            'development roadmap', 'roadmap', 'timeline', 'schedule',
            'milestones', 'delivery schedule', 'project timeline',
            'release schedule', 'sprint plan'
        ],
        'feature': [
            'features', 'core features', 'functionality', 'capabilities',
            'feature list', 'product features', 'key features',
            'requirements', 'functional requirements'
        ],
        'decision': [
            'decisions', 'outcomes', 'conclusions', 'resolutions',
            'decisions made', 'key decisions', 'agreements'
        ],
        'risk': [
            'risks', 'technical risks', 'challenges', 'concerns',
            'potential issues', 'risk assessment', 'mitigation',
            'dependencies', 'blockers'
        ],
        'metric': [
            'metrics', 'kpis', 'business impact', 'roi', 'impact',
            'performance metrics', 'success metrics', 'measurements',
            'business value', 'outcomes'
        ],
        'action_item': [
            'next steps', 'action items', 'tasks', 'todos',
            'action plan', 'follow-up', 'deliverables',
            'upcoming tasks'
        ],
        'team_assignment': [
            'team', 'project team', 'roles', 'responsibilities',
            'team members', 'assignments', 'ownership',
            'project roles', 'contributors'
        ],
        'technical_detail': [
            'technical architecture', 'architecture', 'implementation',
            'technical details', 'system design', 'technical approach',
            'technology stack', 'infrastructure'
        ],
        'requirement': [
            'requirements', 'specifications', 'specs',
            'functional requirements', 'technical requirements',
            'product requirements', 'user requirements'
        ],
        'business_impact': [
            'business impact', 'business value', 'roi',
            'value proposition', 'benefits', 'outcomes',
            'impact analysis', 'business case'
        ],
        'dependency': [
            'dependencies', 'prerequisites', 'blockers',
            'constraints', 'limitations', 'requirements'
        ],
        'resource': [
            'resources', 'budget', 'costs', 'investment',
            'resource allocation', 'staffing', 'tools'
        ]
    }

    def __init__(self):
        """Initialize semantic matcher."""
        pass

    def find_target_sections(
        self,
        unit: SemanticUnit,
        document_sections: List[Dict]
    ) -> List[MatchedSection]:
        """
        Find document sections where this unit could be integrated.

        Args:
            unit: Semantic unit to match
            document_sections: List of section dictionaries from document

        Returns:
            List of MatchedSection objects, sorted by confidence (high to low)
        """

        matches = []

        for section in document_sections:
            score = self._calculate_match_score(unit, section)

            if score > 0.3:  # Minimum threshold
                matches.append(MatchedSection(
                    section_name=section.get('heading', 'Unknown'),
                    section=section,
                    confidence=score,
                    reasoning=self._generate_reasoning(unit, section, score)
                ))

        # Sort by confidence (highest first)
        matches.sort(key=lambda m: m.confidence, reverse=True)

        return matches

    def _calculate_match_score(
        self,
        unit: SemanticUnit,
        section: Dict
    ) -> float:
        """
        Calculate how well a unit matches a section.

        Scoring factors:
        1. Type-based matching (0.0-0.6)
        2. Keyword overlap (0.0-0.3)
        3. Content similarity (0.0-0.1)

        Returns:
            Confidence score between 0.0 and 1.0
        """

        score = 0.0
        section_name = section.get('heading', '').lower()

        if not section_name:
            return 0.0

        # 1. Type-based matching (up to 0.6)
        type_score = self._calculate_type_match_score(unit.type, section_name)
        score += type_score

        # 2. Keyword overlap (up to 0.3)
        keyword_score = self._calculate_keyword_score(unit, section_name)
        score += keyword_score

        # 3. Boost for exact matches
        if self._is_exact_match(unit.type, section_name):
            score += 0.2

        # Cap at 1.0
        return min(score, 1.0)

    def _calculate_type_match_score(
        self,
        unit_type: str,
        section_name: str
    ) -> float:
        """
        Calculate type-based match score.

        Returns:
            Score between 0.0 and 0.6
        """

        # Get expected section names for this type
        expected_sections = self.TYPE_SECTION_MAP.get(unit_type, [])

        if not expected_sections:
            return 0.0

        # Check for matches
        for expected in expected_sections:
            if expected in section_name:
                # Exact substring match
                return 0.6
            elif self._fuzzy_match(expected, section_name):
                # Fuzzy match (e.g., "roadmap" matches "development roadmap")
                return 0.5

        return 0.0

    def _calculate_keyword_score(
        self,
        unit: SemanticUnit,
        section_name: str
    ) -> float:
        """
        Calculate keyword overlap score.

        Returns:
            Score between 0.0 and 0.3
        """

        # Extract keywords from unit content
        unit_keywords = self._extract_keywords(unit.content.lower())

        # Extract keywords from section name
        section_keywords = self._extract_keywords(section_name)

        if not unit_keywords or not section_keywords:
            return 0.0

        # Calculate overlap
        overlap = len(unit_keywords & section_keywords)
        total = len(unit_keywords | section_keywords)

        if total == 0:
            return 0.0

        # Jaccard similarity
        similarity = overlap / total

        # Scale to max 0.3
        return min(similarity * 0.6, 0.3)

    def _is_exact_match(self, unit_type: str, section_name: str) -> bool:
        """Check if section name is an exact match for unit type."""

        exact_matches = {
            'timeline': ['roadmap', 'timeline', 'schedule'],
            'feature': ['features', 'functionality'],
            'decision': ['decisions', 'outcomes'],
            'risk': ['risks', 'challenges'],
            'metric': ['metrics', 'impact'],
            'action_item': ['next steps', 'action items', 'tasks'],
            'team_assignment': ['team', 'roles'],
        }

        expected = exact_matches.get(unit_type, [])

        for match in expected:
            if section_name == match or section_name.endswith(match):
                return True

        return False

    def _fuzzy_match(self, pattern: str, text: str) -> bool:
        """
        Check if pattern fuzzy matches text.

        Example: "roadmap" matches "development roadmap"
        """

        # Split into words
        pattern_words = set(pattern.split())
        text_words = set(text.split())

        # Check if pattern words are subset of text words
        return pattern_words.issubset(text_words)

    def _extract_keywords(self, text: str) -> set:
        """
        Extract meaningful keywords from text.

        Filters out stop words and keeps substantive terms.
        """

        # Common stop words
        stop_words = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for',
            'from', 'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on',
            'that', 'the', 'to', 'was', 'will', 'with', '&'
        }

        # Split and filter
        words = text.lower().split()
        keywords = {
            word.strip('.,!?:;()[]{}')
            for word in words
            if len(word) > 2 and word not in stop_words
        }

        return keywords

    def _generate_reasoning(
        self,
        unit: SemanticUnit,
        section: Dict,
        score: float
    ) -> str:
        """
        Generate human-readable reasoning for the match.

        Args:
            unit: Semantic unit
            section: Document section
            score: Calculated match score

        Returns:
            Reasoning string
        """

        section_name = section.get('heading', 'Unknown')
        reasons = []

        # Type-based reasoning
        expected_sections = self.TYPE_SECTION_MAP.get(unit.type, [])
        section_lower = section_name.lower()

        for expected in expected_sections:
            if expected in section_lower:
                reasons.append(
                    f"'{section_name}' matches expected section for {unit.type}"
                )
                break

        # Keyword overlap
        unit_keywords = self._extract_keywords(unit.content.lower())
        section_keywords = self._extract_keywords(section_lower)
        overlap = unit_keywords & section_keywords

        if overlap:
            keywords_str = ', '.join(list(overlap)[:3])
            reasons.append(f"Keyword overlap: {keywords_str}")

        # Confidence level
        if score > 0.8:
            reasons.append("Very high confidence match")
        elif score > 0.6:
            reasons.append("High confidence match")
        elif score > 0.4:
            reasons.append("Good confidence match")
        else:
            reasons.append("Moderate confidence match")

        return " • ".join(reasons) if reasons else "Generic match"

    def find_best_match(
        self,
        unit: SemanticUnit,
        document_sections: List[Dict]
    ) -> Optional[MatchedSection]:
        """
        Find the single best matching section for a unit.

        Returns:
            MatchedSection with highest confidence, or None if no good match
        """

        matches = self.find_target_sections(unit, document_sections)

        if not matches:
            return None

        # Return highest confidence match
        return matches[0]

    def match_all_units(
        self,
        units: List[SemanticUnit],
        document_sections: List[Dict]
    ) -> List[Tuple[SemanticUnit, List[MatchedSection]]]:
        """
        Match all units to sections at once.

        Returns:
            List of tuples mapping each unit to its matched sections
        """

        results = []

        for unit in units:
            matches = self.find_target_sections(unit, document_sections)
            results.append((unit, matches))

        return results

    def get_match_summary(
        self,
        units: List[SemanticUnit],
        document_sections: List[Dict]
    ) -> Dict[str, Any]:
        """
        Get summary statistics of matching results.

        Returns:
            Dictionary with match statistics
        """

        matches = self.match_all_units(units, document_sections)

        total_units = len(units)
        matched_units = sum(1 for unit, m in matches if len(m) > 0)
        high_confidence = sum(
            1 for unit, m in matches
            if len(m) > 0 and m[0].confidence > 0.7
        )

        # Count units by type
        by_type = {}
        for unit in units:
            if unit.type not in by_type:
                by_type[unit.type] = 0
            by_type[unit.type] += 1

        # Sections that will be modified
        sections_modified = set()
        for unit, matched_sections in matches:
            if matched_sections:
                sections_modified.add(matched_sections[0].section_name)

        return {
            'total_units': total_units,
            'matched_units': matched_units,
            'unmatched_units': total_units - matched_units,
            'high_confidence_matches': high_confidence,
            'match_rate': (matched_units / total_units * 100) if total_units > 0 else 0,
            'units_by_type': by_type,
            'sections_modified': sorted(list(sections_modified)),
            'avg_confidence': sum(
                m[0].confidence for unit, m in matches if m
            ) / matched_units if matched_units > 0 else 0
        }


# Testing helper
def test_matcher_with_document(
    units: List[SemanticUnit],
    document_sections: List[Dict]
):
    """Test matcher with units and document sections (for development)."""

    matcher = SemanticMatcher()

    print("\n" + "="*80)
    print("SEMANTIC MATCHING TEST")
    print("="*80 + "\n")

    print(f"Matching {len(units)} units to {len(document_sections)} sections\n")

    # Match all units
    results = matcher.match_all_units(units, document_sections)

    # Print results
    for unit, matches in results:
        print(f"\n{unit.type.upper()}: {unit.content[:60]}...")
        print(f"  Source line: {unit.source_line} | Priority: {unit.priority}/5")

        if matches:
            print(f"  Matched to {len(matches)} section(s):")
            for i, match in enumerate(matches[:3], 1):  # Show top 3
                print(f"    {i}. {match.section_name}")
                print(f"       Confidence: {match.confidence:.0%}")
                print(f"       Reasoning: {match.reasoning}")
        else:
            print("  ❌ No matching sections found")

    # Print summary
    summary = matcher.get_match_summary(units, document_sections)

    print("\n" + "="*80)
    print("MATCHING SUMMARY")
    print("="*80 + "\n")

    print(f"Total Units: {summary['total_units']}")
    print(f"Matched: {summary['matched_units']} ({summary['match_rate']:.1f}%)")
    print(f"High Confidence (>70%): {summary['high_confidence_matches']}")
    print(f"Average Confidence: {summary['avg_confidence']:.0%}")
    print()

    print("Sections that will be modified:")
    for i, section in enumerate(summary['sections_modified'], 1):
        print(f"  {i}. {section}")

    print("\n" + "="*80 + "\n")

    return results, summary
