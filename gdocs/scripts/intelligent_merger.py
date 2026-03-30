#!/usr/bin/env python3
"""
Intelligent document merger using Claude for content analysis.

This module provides agentic merging that:
1. Analyzes document structure
2. Analyzes meeting notes content
3. Determines optimal merge strategy
4. Intelligently integrates content
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import anthropic
import os


@dataclass
class MergeStrategy:
    """Strategy for merging content."""
    action: str  # 'append_section', 'update_section', 'create_section', 'multiple'
    target_section: Optional[str] = None
    reason: str = ""
    operations: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.operations is None:
            self.operations = []


class IntelligentMerger:
    """
    Uses Claude to intelligently merge meeting notes into documents.

    Instead of just appending content, this analyzer:
    - Understands document structure
    - Analyzes meeting notes content
    - Determines best merge locations
    - Integrates content contextually
    """

    def __init__(self, editor):
        """
        Initialize intelligent merger.

        Args:
            editor: GoogleDocsEditor instance
        """
        self.editor = editor

        # Initialize Claude client
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable not set. "
                "Please set it to use intelligent merging."
            )
        self.client = anthropic.Anthropic(api_key=api_key)

    def analyze_and_merge(
        self,
        doc_url: str,
        meeting_notes: str,
        add_source_comment: bool = True,
        source_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze document and meeting notes, then intelligently merge.

        Args:
            doc_url: Google Doc URL or ID
            meeting_notes: Meeting notes content
            add_source_comment: Whether to add source attribution
            source_description: Description for source comment

        Returns:
            Dictionary with merge results
        """
        print("🤖 Starting intelligent merge analysis...")
        print()

        # Step 1: Analyze current document
        print("📄 Step 1: Analyzing document structure...")
        analysis = self.editor.analyze_document(doc_url, include_comments=True)

        doc_structure = self._format_document_structure(analysis)
        print(f"   ✓ Found {len(analysis.sections)} sections")
        print(f"   ✓ Current length: {analysis.total_chars} characters")
        print()

        # Step 2: Determine merge strategy using Claude
        print("🧠 Step 2: Analyzing content and determining merge strategy...")
        strategy = self._determine_merge_strategy(
            doc_structure=doc_structure,
            document_content=analysis.content[:2000],  # First 2000 chars for context
            meeting_notes=meeting_notes
        )

        print(f"   ✓ Strategy: {strategy.action}")
        print(f"   ✓ Reason: {strategy.reason}")
        print()

        # Step 3: Execute merge strategy
        print("⚙️  Step 3: Executing merge operations...")
        result = self._execute_merge_strategy(
            doc_url=doc_url,
            strategy=strategy,
            meeting_notes=meeting_notes,
            add_source_comment=add_source_comment,
            source_description=source_description
        )

        return result

    def _format_document_structure(self, analysis) -> str:
        """Format document structure for Claude analysis."""
        lines = [f"Document: {analysis.title}"]
        lines.append(f"Total length: {analysis.total_chars} characters")
        lines.append(f"Sections: {len(analysis.sections)}")
        lines.append("")
        lines.append("Section structure:")

        for i, section in enumerate(analysis.sections, 1):
            indent = "  " * (section.level - 1)
            lines.append(f"{indent}{i}. [{section.level}] {section.title}")

        return "\n".join(lines)

    def _determine_merge_strategy(
        self,
        doc_structure: str,
        document_content: str,
        meeting_notes: str
    ) -> MergeStrategy:
        """
        Use Claude to analyze and determine optimal merge strategy.
        """
        prompt = f"""You are helping merge meeting notes into a Google Doc. Analyze the document structure and meeting notes, then determine the best merge strategy.

CURRENT DOCUMENT STRUCTURE:
{doc_structure}

DOCUMENT CONTENT PREVIEW:
{document_content[:1000]}

MEETING NOTES TO MERGE:
{meeting_notes}

Analyze:
1. What is the document about?
2. What content is in the meeting notes?
3. Where should this content be integrated?

Determine the best strategy:

Option A: CREATE_NEW_SECTION
- Use when: Meeting notes are about a new topic not covered in the document
- Creates a new section at the end

Option B: UPDATE_EXISTING_SECTION
- Use when: Meeting notes expand on or update an existing section
- Identifies which section to update and where to insert

Option C: APPEND_TO_END
- Use when: Meeting notes are supplementary and don't fit existing structure
- Simple append (what we currently do)

Option D: MULTIPLE_OPERATIONS
- Use when: Meeting notes contain content for multiple sections
- Requires breaking notes into parts and placing each appropriately

Respond in this exact format:

STRATEGY: [CREATE_NEW_SECTION|UPDATE_EXISTING_SECTION|APPEND_TO_END|MULTIPLE_OPERATIONS]
TARGET_SECTION: [section name if updating, "NEW: Section Title" if creating, or "N/A"]
REASON: [one sentence explanation]

OPERATIONS:
[If MULTIPLE_OPERATIONS, list each operation:
  1. Action: [create/update/append] | Section: [name] | Content: [description]
  2. ...
Otherwise write: Single operation as described above]
"""

        # Call Claude for analysis
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        # Parse response
        return self._parse_strategy_response(response.content[0].text)

    def _parse_strategy_response(self, response: str) -> MergeStrategy:
        """Parse Claude's strategy response."""
        lines = response.strip().split('\n')

        strategy_line = next((l for l in lines if l.startswith('STRATEGY:')), '')
        target_line = next((l for l in lines if l.startswith('TARGET_SECTION:')), '')
        reason_line = next((l for l in lines if l.startswith('REASON:')), '')

        action = strategy_line.split(':', 1)[1].strip() if strategy_line else 'APPEND_TO_END'
        target = target_line.split(':', 1)[1].strip() if target_line else None
        reason = reason_line.split(':', 1)[1].strip() if reason_line else "No specific reason provided"

        # Parse operations if multiple
        operations = []
        if action == 'MULTIPLE_OPERATIONS':
            ops_start = next((i for i, l in enumerate(lines) if l.startswith('OPERATIONS:')), -1)
            if ops_start >= 0:
                for line in lines[ops_start + 1:]:
                    if line.strip() and line[0].isdigit():
                        # Parse operation line
                        parts = line.split('|')
                        if len(parts) >= 2:
                            operations.append({
                                'action': parts[0].split(':')[1].strip() if ':' in parts[0] else 'append',
                                'section': parts[1].split(':')[1].strip() if ':' in parts[1] else None,
                                'description': parts[2].split(':')[1].strip() if len(parts) > 2 and ':' in parts[2] else ''
                            })

        return MergeStrategy(
            action=action,
            target_section=target if target != "N/A" else None,
            reason=reason,
            operations=operations
        )

    def _execute_merge_strategy(
        self,
        doc_url: str,
        strategy: MergeStrategy,
        meeting_notes: str,
        add_source_comment: bool,
        source_description: Optional[str]
    ) -> Dict[str, Any]:
        """Execute the determined merge strategy."""
        from .content_inserter import ContentInserter, MergeOptions

        inserter = ContentInserter(self.editor)

        # For now, implement the basic strategies
        # Phase 5+ can implement more sophisticated multi-section merging

        if strategy.action in ['APPEND_TO_END', 'CREATE_NEW_SECTION']:
            # Use existing merge_content for these cases
            result = inserter.merge_content(
                doc_url=doc_url,
                content=meeting_notes,
                options=MergeOptions(
                    preserve_comments=True,
                    add_source_comment=add_source_comment,
                    source_description=source_description
                )
            )

            result['strategy_used'] = strategy.action
            result['strategy_reason'] = strategy.reason

            return result

        elif strategy.action == 'UPDATE_EXISTING_SECTION':
            # TODO: Implement section-specific insertion
            # For now, fall back to append
            print(f"   ℹ️  UPDATE_EXISTING_SECTION not yet implemented")
            print(f"   ℹ️  Falling back to APPEND_TO_END")

            result = inserter.merge_content(
                doc_url=doc_url,
                content=meeting_notes,
                options=MergeOptions(
                    preserve_comments=True,
                    add_source_comment=add_source_comment,
                    source_description=source_description
                )
            )

            result['strategy_used'] = 'APPEND_TO_END (fallback)'
            result['strategy_reason'] = f"Target: {strategy.target_section}. {strategy.reason}"

            return result

        elif strategy.action == 'MULTIPLE_OPERATIONS':
            # TODO: Implement multi-section merging
            # For now, fall back to append
            print(f"   ℹ️  MULTIPLE_OPERATIONS not yet implemented")
            print(f"   ℹ️  Falling back to APPEND_TO_END")

            result = inserter.merge_content(
                doc_url=doc_url,
                content=meeting_notes,
                options=MergeOptions(
                    preserve_comments=True,
                    add_source_comment=add_source_comment,
                    source_description=source_description
                )
            )

            result['strategy_used'] = 'APPEND_TO_END (fallback)'
            result['strategy_reason'] = f"Multiple ops planned: {len(strategy.operations)}. {strategy.reason}"

            return result

        else:
            raise ValueError(f"Unknown strategy: {strategy.action}")
