#!/usr/bin/env python3
"""
Content Finder - Locates existing content in document sections.

Searches document sections to find existing content that relates to
semantic units. Returns matches with confidence scores to support
ADD/UPDATE/MERGE/SKIP decisions.
"""

import re
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from .semantic_units import SemanticUnit, ExistingContent


class ContentFinder:
    """Finds existing content in document sections that relates to semantic units."""

    def __init__(self, similarity_threshold: float = 0.5):
        """
        Initialize content finder.

        Args:
            similarity_threshold: Minimum similarity score (0.0-1.0) to consider a match
        """
        self.similarity_threshold = similarity_threshold

    def find_existing_content(
        self,
        unit: SemanticUnit,
        section: Dict[str, Any]
    ) -> List[ExistingContent]:
        """
        Find existing content in section that relates to this unit.

        Args:
            unit: Semantic unit to search for
            section: Document section to search in

        Returns:
            List of ExistingContent matches, sorted by confidence (high to low)
        """

        section_content = section.get('content', '')

        if not section_content or not section_content.strip():
            return []

        matches = []

        # 1. Check for exact matches
        exact_matches = self._find_exact_matches(unit, section_content, section)
        matches.extend(exact_matches)

        # 2. Check for partial matches (if no exact match)
        if not exact_matches:
            partial_matches = self._find_partial_matches(unit, section_content, section)
            matches.extend(partial_matches)

        # 3. Check for semantic matches (keyword-based similarity)
        semantic_matches = self._find_semantic_matches(unit, section_content, section)
        matches.extend(semantic_matches)

        # Remove duplicates and sort by confidence
        matches = self._deduplicate_matches(matches)
        matches.sort(key=lambda m: m.confidence, reverse=True)

        # Filter by threshold
        matches = [m for m in matches if m.confidence >= self.similarity_threshold]

        return matches

    def _find_exact_matches(
        self,
        unit: SemanticUnit,
        section_content: str,
        section: Dict[str, Any]
    ) -> List[ExistingContent]:
        """
        Find exact text matches in section content.

        Returns matches where unit content appears verbatim.
        """

        matches = []
        unit_text = unit.content.strip()

        # Normalize whitespace for comparison
        normalized_unit = ' '.join(unit_text.split())
        normalized_section = ' '.join(section_content.split())

        # Case-insensitive exact match
        pattern = re.escape(normalized_unit)
        for match in re.finditer(pattern, normalized_section, re.IGNORECASE):
            start_idx = match.start()
            end_idx = match.end()
            matched_text = normalized_section[start_idx:end_idx]

            matches.append(ExistingContent(
                match_type='exact',
                content=matched_text,
                start_index=start_idx,
                end_index=end_idx,
                confidence=1.0,
                reasoning=f"Exact match found for '{unit_text[:40]}...'"
            ))

        return matches

    def _find_partial_matches(
        self,
        unit: SemanticUnit,
        section_content: str,
        section: Dict[str, Any]
    ) -> List[ExistingContent]:
        """
        Find partial matches where significant portions of content match.

        Uses longest common substring and keyword overlap.
        """

        matches = []

        # Extract key phrases from unit (significant word sequences)
        unit_phrases = self._extract_key_phrases(unit.content)

        if not unit_phrases:
            return []

        # Search for each phrase in section content
        for phrase in unit_phrases:
            # Skip very short phrases
            if len(phrase) < 10:
                continue

            # Look for phrase in content
            pattern = r'\b' + re.escape(phrase) + r'\b'
            for match in re.finditer(pattern, section_content, re.IGNORECASE):
                start_idx = match.start()
                end_idx = match.end()

                # Expand context to include surrounding sentence
                context_start, context_end = self._expand_to_sentence(
                    section_content, start_idx, end_idx
                )

                matched_text = section_content[context_start:context_end]

                # Calculate confidence based on phrase length relative to unit
                confidence = min(len(phrase) / len(unit.content) * 1.5, 0.9)

                matches.append(ExistingContent(
                    match_type='partial',
                    content=matched_text.strip(),
                    start_index=context_start,
                    end_index=context_end,
                    confidence=confidence,
                    reasoning=f"Partial match on phrase: '{phrase[:30]}...'"
                ))

        return matches

    def _find_semantic_matches(
        self,
        unit: SemanticUnit,
        section_content: str,
        section: Dict[str, Any]
    ) -> List[ExistingContent]:
        """
        Find semantic matches based on keyword overlap and similarity.

        Identifies content that discusses the same topic even if wording differs.
        """

        matches = []

        # Extract keywords from unit
        unit_keywords = self._extract_keywords(unit.content)

        if len(unit_keywords) < 2:
            return []

        # Split section into sentences
        sentences = self._split_into_sentences(section_content)

        for sentence_idx, sentence in enumerate(sentences):
            if len(sentence.strip()) < 10:
                continue

            # Extract keywords from sentence
            sentence_keywords = self._extract_keywords(sentence)

            if len(sentence_keywords) < 2:
                continue

            # Calculate keyword overlap
            overlap = unit_keywords & sentence_keywords
            overlap_ratio = len(overlap) / len(unit_keywords)

            # Need at least 30% keyword overlap for semantic match
            if overlap_ratio >= 0.3:
                # Find sentence position in content
                start_idx = section_content.find(sentence)
                if start_idx == -1:
                    continue

                end_idx = start_idx + len(sentence)

                # Confidence based on overlap ratio
                confidence = min(overlap_ratio * 1.2, 0.85)

                overlapping_keywords = ', '.join(list(overlap)[:5])

                matches.append(ExistingContent(
                    match_type='semantic',
                    content=sentence.strip(),
                    start_index=start_idx,
                    end_index=end_idx,
                    confidence=confidence,
                    reasoning=f"Semantic match on keywords: {overlapping_keywords}"
                ))

        return matches

    def _extract_key_phrases(self, text: str) -> List[str]:
        """
        Extract meaningful phrases from text.

        Returns sequences of words that form coherent phrases.
        """

        # Remove common prefixes and clean text
        text = text.strip()

        # Split into words
        words = text.split()

        phrases = []

        # Extract 3-5 word sequences as key phrases
        for n in [5, 4, 3]:
            for i in range(len(words) - n + 1):
                phrase = ' '.join(words[i:i+n])

                # Skip if phrase is too short or starts with common words
                if len(phrase) >= 15 and not phrase.lower().startswith(('the ', 'a ', 'an ')):
                    phrases.append(phrase)

        return phrases

    def _extract_keywords(self, text: str) -> set:
        """
        Extract meaningful keywords from text.

        Filters out stop words and keeps substantive terms.
        """

        # Common stop words
        stop_words = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for',
            'from', 'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on',
            'that', 'the', 'to', 'was', 'will', 'with', 'we', 'this',
            'should', 'would', 'could', 'have', 'been', 'being',
            'our', 'their', 'there', 'which', 'when', 'where'
        }

        # Split and filter
        words = text.lower().split()
        keywords = {
            word.strip('.,!?:;()[]{}"\'-')
            for word in words
            if len(word) > 2 and word.lower() not in stop_words
        }

        # Remove empty strings
        keywords.discard('')

        return keywords

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""

        # Simple sentence splitting on . ! ?
        sentences = re.split(r'[.!?]+', text)

        # Clean up
        sentences = [s.strip() for s in sentences if s.strip()]

        return sentences

    def _expand_to_sentence(self, text: str, start: int, end: int) -> tuple:
        """
        Expand match boundaries to include full sentence.

        Args:
            text: Full text content
            start: Match start index
            end: Match end index

        Returns:
            Tuple of (expanded_start, expanded_end)
        """

        # Find sentence boundaries (. ! ? or start/end of text)
        sentence_start = start
        sentence_end = end

        # Expand backward to sentence start
        while sentence_start > 0:
            char = text[sentence_start - 1]
            if char in '.!?\n':
                break
            sentence_start -= 1

        # Expand forward to sentence end
        while sentence_end < len(text):
            char = text[sentence_end]
            if char in '.!?\n':
                sentence_end += 1
                break
            sentence_end += 1

        return sentence_start, sentence_end

    def _deduplicate_matches(self, matches: List[ExistingContent]) -> List[ExistingContent]:
        """
        Remove duplicate or overlapping matches.

        Keeps highest confidence match for overlapping regions.
        """

        if not matches:
            return []

        # Sort by confidence (highest first)
        sorted_matches = sorted(matches, key=lambda m: m.confidence, reverse=True)

        deduplicated = []

        for match in sorted_matches:
            # Check if this match overlaps with any already-kept match
            overlaps = False

            for kept_match in deduplicated:
                # Check for overlap
                if (match.start_index < kept_match.end_index and
                    match.end_index > kept_match.start_index):
                    overlaps = True
                    break

            if not overlaps:
                deduplicated.append(match)

        return deduplicated

    def find_best_match(
        self,
        unit: SemanticUnit,
        section: Dict[str, Any]
    ) -> Optional[ExistingContent]:
        """
        Find single best matching content in section.

        Returns:
            ExistingContent with highest confidence, or None if no match
        """

        matches = self.find_existing_content(unit, section)

        if not matches:
            return None

        return matches[0]

    def search_all_sections(
        self,
        unit: SemanticUnit,
        sections: List[Dict[str, Any]]
    ) -> Dict[str, List[ExistingContent]]:
        """
        Search all sections for existing content related to unit.

        Returns:
            Dictionary mapping section names to lists of matches
        """

        results = {}

        for section in sections:
            section_name = section.get('heading', 'Unknown')
            matches = self.find_existing_content(unit, section)

            if matches:
                results[section_name] = matches

        return results


# Testing helper
def test_content_finder(unit: SemanticUnit, section: Dict[str, Any]):
    """Test content finder with a unit and section (for development)."""

    finder = ContentFinder()

    print("\n" + "="*80)
    print("CONTENT FINDER TEST")
    print("="*80 + "\n")

    print(f"Unit: {unit.type.upper()}")
    print(f"Content: {unit.content[:80]}...")
    print()

    print(f"Section: {section.get('heading', 'Unknown')}")
    print(f"Section content length: {len(section.get('content', ''))} chars")
    print()

    print("Searching for existing content...\n")

    matches = finder.find_existing_content(unit, section)

    if matches:
        print(f"Found {len(matches)} match(es):\n")

        for i, match in enumerate(matches, 1):
            print(f"{i}. {match.match_type.upper()} match")
            print(f"   Confidence: {match.confidence:.0%}")
            print(f"   Content: {match.content[:100]}...")
            print(f"   Position: {match.start_index}-{match.end_index}")
            print(f"   Reasoning: {match.reasoning}")
            print()
    else:
        print("No existing content found (will ADD new content)")

    print("="*80 + "\n")

    return matches
