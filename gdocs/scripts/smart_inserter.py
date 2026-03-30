#!/usr/bin/env python3
"""
AI-Powered Smart Content Insertion for Google Docs.

This module uses contextual analysis to intelligently insert content
into Google Docs by understanding document structure, style, and semantics.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple
import json
import re


@dataclass
class InsertionStrategy:
    """Represents an AI-determined strategy for inserting content."""
    section_name: str
    index: int
    format_type: str  # 'paragraph', 'bullet_list', 'numbered_list', 'inline'
    position_description: str  # Human-readable explanation
    style_adjustments: Dict[str, Any]  # Formatting to apply
    reasoning: str  # Why this location and format
    confidence: float  # 0.0-1.0
    preview: str  # What it will look like


@dataclass
class DocumentContext:
    """Rich context about the document for AI decision-making."""
    title: str
    sections: List[Dict]
    total_chars: int
    writing_style: Dict[str, str]
    existing_patterns: Dict[str, Any]
    content_preview: str


class SmartInserter:
    """AI-powered contextual content insertion."""

    def __init__(self, editor):
        """
        Initialize smart inserter.

        Args:
            editor: GoogleDocsEditor instance
        """
        self.editor = editor

    def analyze_document_context(self, doc_url: str) -> DocumentContext:
        """
        Build rich context about the document for AI analysis.

        Args:
            doc_url: Google Doc URL or ID

        Returns:
            DocumentContext with comprehensive document information
        """
        # Get document analysis
        analysis = self.editor.analyze_document(doc_url, include_comments=False)

        # Get full document for style analysis
        doc = self.editor.get_document(doc_url, include_tabs_content=True)

        # Extract document text
        full_text = analysis.content

        # Analyze writing style
        writing_style = self._analyze_writing_style(full_text, analysis.sections)

        # Detect existing patterns (lists, tables, common structures)
        patterns = self._detect_content_patterns(doc, analysis)

        return DocumentContext(
            title=analysis.title,
            sections=analysis.sections,
            total_chars=analysis.total_chars,
            writing_style=writing_style,
            existing_patterns=patterns,
            content_preview=full_text[:1000]  # First 1000 chars for context
        )

    def _analyze_writing_style(
        self,
        text: str,
        sections: List[Dict]
    ) -> Dict[str, str]:
        """
        Analyze the document's writing style.

        Args:
            text: Full document text
            sections: Section structure

        Returns:
            Dictionary describing writing style
        """
        style = {}

        # Detect tone (formal vs casual)
        formal_indicators = ['shall', 'therefore', 'furthermore', 'pursuant']
        casual_indicators = ["we'll", "you'll", 'basically', 'just']

        formal_count = sum(1 for word in formal_indicators if word in text.lower())
        casual_count = sum(1 for word in casual_indicators if word in text.lower())

        style['tone'] = 'formal' if formal_count > casual_count else 'casual'

        # Detect heading style
        if sections:
            first_heading = sections[0].get('heading', '')
            style['heading_style'] = (
                'Title Case' if first_heading and first_heading.istitle()
                else 'Sentence case'
            )

        # Detect list preference (bullets vs numbered)
        bullet_count = text.count('•') + text.count('- ')
        numbered_count = len(re.findall(r'\n\d+\.\s', text))

        style['list_preference'] = (
            'bullets' if bullet_count > numbered_count
            else 'numbered'
        )

        # Detect person (first person "we" vs third person "the system")
        first_person = text.lower().count(' we ') + text.lower().count(' our ')
        third_person = text.lower().count('the system') + text.lower().count('the application')

        style['voice'] = 'first_person' if first_person > third_person else 'third_person'

        # Detect tense (present vs future)
        present_verbs = ['implements', 'provides', 'uses', 'handles']
        future_verbs = ['will implement', 'will provide', 'will use', 'will handle']

        present_count = sum(1 for verb in present_verbs if verb in text.lower())
        future_count = sum(1 for verb in future_verbs if verb in text.lower())

        style['tense'] = 'present' if present_count > future_count else 'future'

        return style

    def _detect_content_patterns(
        self,
        doc: Dict,
        analysis: Any
    ) -> Dict[str, Any]:
        """
        Detect existing content patterns in the document.

        Args:
            doc: Full document resource
            analysis: DocumentAnalysis object

        Returns:
            Dictionary of detected patterns
        """
        patterns = {
            'has_bullet_lists': False,
            'has_numbered_lists': False,
            'has_tables': False,
            'has_code_blocks': False,
            'section_structure': 'heading_then_content',
            'common_subsection_pattern': None
        }

        # Get body content
        tabs = doc.get('tabs', [])
        if tabs:
            body = tabs[0].get('documentTab', {}).get('body', {})
        else:
            body = doc.get('body', {})

        content_elements = body.get('content', [])

        # Check for lists
        for element in content_elements:
            if 'paragraph' in element:
                para = element['paragraph']
                bullet = para.get('bullet')

                if bullet:
                    nesting_level = bullet.get('nestingLevel', 0)
                    list_id = bullet.get('listId')

                    # Detect list type from first element
                    if list_id and nesting_level == 0:
                        # Check glyph type (bullet vs numbered)
                        glyph_type = bullet.get('glyphType', 'BULLET_DISC_CIRCLE_SQUARE')

                        if 'DECIMAL' in glyph_type or 'ALPHA' in glyph_type:
                            patterns['has_numbered_lists'] = True
                        else:
                            patterns['has_bullet_lists'] = True

            # Check for tables
            if 'table' in element:
                patterns['has_tables'] = True

        # Analyze section structure
        if len(analysis.sections) > 2:
            # Look at pattern: Heading → Content type
            # Most common pattern wins
            section_patterns = []

            for section in analysis.sections[:5]:  # Sample first 5 sections
                # This is simplified - in real implementation,
                # would analyze actual content between headings
                section_patterns.append('heading_then_bullets')

            if section_patterns:
                patterns['section_structure'] = max(
                    set(section_patterns),
                    key=section_patterns.count
                )

        return patterns

    def determine_insertion_strategy(
        self,
        context: DocumentContext,
        content: str,
        intent: str,
        target_section: Optional[str] = None
    ) -> List[InsertionStrategy]:
        """
        Use AI-like analysis to determine best insertion strategy.

        In production, this would call Claude API. For POC, uses rule-based
        heuristics that mimic AI reasoning.

        Args:
            context: Document context
            content: Content to insert
            intent: Description of what this content is (e.g., "security feature")
            target_section: Optional specific section to target

        Returns:
            List of InsertionStrategy options, sorted by confidence
        """
        strategies = []

        # Find relevant sections based on intent
        relevant_sections = self._find_relevant_sections(
            context.sections,
            intent,
            target_section
        )

        for section in relevant_sections:
            # Determine format based on existing patterns and content type
            format_type = self._determine_format_type(
                content,
                context.existing_patterns,
                section
            )

            # Calculate insertion index
            index = section.get('end_index', 0) - 1

            # Determine style adjustments
            style_adjustments = self._determine_style_adjustments(
                content,
                context.writing_style,
                format_type
            )

            # Generate position description
            position_desc = self._generate_position_description(
                section,
                format_type,
                content
            )

            # Calculate confidence score
            confidence = self._calculate_confidence(
                section,
                intent,
                context,
                target_section
            )

            # Generate preview
            preview = self._generate_preview(
                section,
                content,
                format_type,
                style_adjustments,
                context
            )

            # Build reasoning
            reasoning = self._generate_reasoning(
                section,
                intent,
                format_type,
                context,
                confidence
            )

            strategies.append(InsertionStrategy(
                section_name=section.get('heading', 'Document'),
                index=index,
                format_type=format_type,
                position_description=position_desc,
                style_adjustments=style_adjustments,
                reasoning=reasoning,
                confidence=confidence,
                preview=preview
            ))

        # Sort by confidence (highest first)
        strategies.sort(key=lambda s: s.confidence, reverse=True)

        return strategies

    def _find_relevant_sections(
        self,
        sections: List[Dict],
        intent: str,
        target_section: Optional[str] = None
    ) -> List[Dict]:
        """Find sections relevant to the content intent."""

        if target_section:
            # User specified a section
            matching = [
                s for s in sections
                if target_section.lower() in s.get('heading', '').lower()
            ]
            if matching:
                return matching

        # Semantic matching based on intent keywords
        intent_lower = intent.lower()

        relevant = []
        for section in sections:
            heading = section.get('heading', '').lower()

            # Calculate relevance score
            score = 0

            # Direct keyword matches
            if 'security' in intent_lower and 'security' in heading:
                score += 100
            if 'auth' in intent_lower and 'auth' in heading:
                score += 100
            if 'feature' in intent_lower and 'feature' in heading:
                score += 80
            if 'api' in intent_lower and 'api' in heading:
                score += 100
            if 'meeting' in intent_lower and ('overview' in heading or 'summary' in heading):
                score += 70
            if 'ux' in intent_lower and ('design' in heading or 'experience' in heading):
                score += 90

            # Broader matches
            if 'technical' in heading:
                score += 30
            if 'implementation' in heading:
                score += 30

            if score > 50:
                section['_relevance_score'] = score
                relevant.append(section)

        # Sort by relevance
        relevant.sort(key=lambda s: s.get('_relevance_score', 0), reverse=True)

        # Return top 3 most relevant
        return relevant[:3] if relevant else sections[:1]

    def _determine_format_type(
        self,
        content: str,
        patterns: Dict[str, Any],
        section: Dict
    ) -> str:
        """Determine what format to use for insertion."""

        # If content has bullet structure, use bullet list
        if content.count('•') > 2 or content.count('\n- ') > 2:
            return 'bullet_list'

        # If content has numbered list structure
        if len(re.findall(r'\n\d+\.', content)) > 2:
            return 'numbered_list'

        # If document uses bullets and this is a short item, use bullet
        if patterns.get('has_bullet_lists') and len(content) < 500:
            return 'bullet_item'

        # Default to paragraph
        return 'paragraph'

    def _determine_style_adjustments(
        self,
        content: str,
        writing_style: Dict[str, str],
        format_type: str
    ) -> Dict[str, Any]:
        """Determine style adjustments to match document."""

        adjustments = {
            'color': 'blue',  # New content marker
            'rewrite_tone': writing_style.get('tone'),
            'rewrite_voice': writing_style.get('voice'),
            'rewrite_tense': writing_style.get('tense'),
            'format': format_type
        }

        return adjustments

    def _generate_position_description(
        self,
        section: Dict,
        format_type: str,
        content: str
    ) -> str:
        """Generate human-readable description of where content will go."""

        section_name = section.get('heading', 'the document')

        if format_type == 'bullet_item':
            return f"Add as bullet point at end of '{section_name}' section"
        elif format_type == 'paragraph':
            return f"Insert paragraph at end of '{section_name}' section"
        elif format_type == 'numbered_list':
            return f"Add as numbered list at end of '{section_name}' section"
        else:
            return f"Insert at end of '{section_name}' section"

    def _calculate_confidence(
        self,
        section: Dict,
        intent: str,
        context: DocumentContext,
        target_section: Optional[str]
    ) -> float:
        """Calculate confidence score for this insertion strategy."""

        confidence = 0.5  # Base confidence

        # User specified this section
        if target_section and target_section.lower() in section.get('heading', '').lower():
            confidence += 0.4

        # High relevance score
        relevance = section.get('_relevance_score', 0)
        if relevance > 90:
            confidence += 0.3
        elif relevance > 70:
            confidence += 0.2
        elif relevance > 50:
            confidence += 0.1

        # Section has related content (simplified heuristic)
        if relevance > 0:
            confidence += 0.1

        return min(confidence, 1.0)

    def _generate_preview(
        self,
        section: Dict,
        content: str,
        format_type: str,
        style_adjustments: Dict,
        context: DocumentContext
    ) -> str:
        """Generate preview of what insertion will look like."""

        section_name = section.get('heading', 'Document')

        # Simulate content rewrite to match style
        adjusted_content = self._adjust_content_style(
            content,
            style_adjustments
        )

        preview_lines = [
            f"📄 Preview of insertion in '{section_name}':",
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"   ...existing content in {section_name}...",
            "   ",
        ]

        if format_type == 'bullet_item':
            preview_lines.append(f"   • {adjusted_content[:100]}...")
        elif format_type == 'numbered_list':
            preview_lines.append(f"   1. {adjusted_content[:100]}...")
        else:
            preview_lines.append(f"   {adjusted_content[:150]}...")

        preview_lines.extend([
            "   ",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"Format: {format_type}",
            f"Style: {style_adjustments.get('rewrite_tone', 'neutral')} tone, "
            f"{style_adjustments.get('rewrite_voice', 'neutral')} voice"
        ])

        return "\n".join(preview_lines)

    def _adjust_content_style(
        self,
        content: str,
        style_adjustments: Dict
    ) -> str:
        """
        Adjust content to match document style.

        In production, this would use Claude API to rewrite.
        For POC, uses simple transformations.
        """
        adjusted = content

        # Tone adjustment (formal vs casual)
        tone = style_adjustments.get('rewrite_tone')
        if tone == 'formal':
            # Replace casual phrases
            adjusted = adjusted.replace("we'll", "we will")
            adjusted = adjusted.replace("you'll", "you will")
            adjusted = adjusted.replace("basically", "essentially")

        # Voice adjustment (first person vs third person)
        voice = style_adjustments.get('rewrite_voice')
        if voice == 'third_person':
            adjusted = adjusted.replace("We implement", "The application implements")
            adjusted = adjusted.replace("Our system", "The system")
        elif voice == 'first_person':
            adjusted = adjusted.replace("The application implements", "We implement")
            adjusted = adjusted.replace("The system", "Our system")

        # Tense adjustment
        tense = style_adjustments.get('rewrite_tense')
        if tense == 'present':
            adjusted = adjusted.replace("will implement", "implements")
            adjusted = adjusted.replace("will provide", "provides")

        return adjusted

    def _generate_reasoning(
        self,
        section: Dict,
        intent: str,
        format_type: str,
        context: DocumentContext,
        confidence: float
    ) -> str:
        """Generate explanation of why this strategy was chosen."""

        section_name = section.get('heading', 'this section')

        reasons = []

        # Section relevance
        if section.get('_relevance_score', 0) > 80:
            reasons.append(
                f"'{section_name}' is highly relevant to '{intent}' content"
            )

        # Format choice
        if format_type == 'bullet_item':
            reasons.append(
                "Document uses bullet lists extensively, formatting as bullet point"
            )

        # Style matching
        tone = context.writing_style.get('tone')
        if tone:
            reasons.append(
                f"Document uses {tone} tone, content will be adjusted to match"
            )

        # Confidence explanation
        if confidence > 0.8:
            reasons.append("High confidence in this placement")
        elif confidence > 0.6:
            reasons.append("Good confidence in this placement")
        else:
            reasons.append("Moderate confidence - may want to verify placement")

        return " • ".join(reasons)

    def smart_insert(
        self,
        doc_url: str,
        content: str,
        intent: str,
        target_section: Optional[str] = None,
        auto_execute: bool = False
    ) -> Dict[str, Any]:
        """
        Main API: Intelligently insert content into document.

        Args:
            doc_url: Google Doc URL
            content: Content to insert
            intent: What this content is (e.g., "security feature", "meeting notes")
            target_section: Optional specific section to target
            auto_execute: If True, execute top strategy automatically

        Returns:
            Dictionary with strategies and execution result
        """
        # 1. Analyze document context
        print("🔍 Analyzing document context...")
        context = self.analyze_document_context(doc_url)

        print(f"   Document: {context.title}")
        print(f"   Sections: {len(context.sections)}")
        print(f"   Style: {context.writing_style.get('tone')} tone, "
              f"{context.writing_style.get('voice')} voice")
        print()

        # 2. Determine insertion strategies
        print("🧠 Determining optimal insertion strategy...")
        strategies = self.determine_insertion_strategy(
            context,
            content,
            intent,
            target_section
        )

        if not strategies:
            return {
                'success': False,
                'error': 'Could not determine insertion strategy',
                'strategies': []
            }

        # 3. Display strategies
        print(f"   Found {len(strategies)} possible strategies:\n")

        for i, strategy in enumerate(strategies, 1):
            print(f"   Option {i} (Confidence: {strategy.confidence:.0%}):")
            print(f"   └─ {strategy.position_description}")
            print(f"   └─ {strategy.reasoning}")
            print()

        # 4. Show preview of top strategy
        top_strategy = strategies[0]
        print("📋 Preview of recommended insertion:")
        print(top_strategy.preview)
        print()

        result = {
            'success': True,
            'strategies': strategies,
            'recommended': top_strategy,
            'context': context,
            'executed': False
        }

        # 5. Execute if auto_execute enabled
        if auto_execute and top_strategy.confidence > 0.6:
            print("✅ Auto-executing top strategy...")
            execution_result = self._execute_strategy(
                doc_url,
                content,
                top_strategy,
                context
            )
            result['executed'] = True
            result['execution_result'] = execution_result

        return result

    def _execute_strategy(
        self,
        doc_url: str,
        content: str,
        strategy: InsertionStrategy,
        context: DocumentContext
    ) -> Dict[str, Any]:
        """Execute an insertion strategy."""

        doc_id = self.editor.extract_doc_id(doc_url)

        # Adjust content style
        adjusted_content = self._adjust_content_style(
            content,
            strategy.style_adjustments
        )

        # Format content based on format type
        formatted_content = self._format_content(
            adjusted_content,
            strategy.format_type
        )

        # Build requests
        requests = self._build_insertion_requests(
            strategy.index,
            formatted_content,
            strategy.style_adjustments
        )

        # Execute
        try:
            self.editor._ensure_authenticated()
            result = self.editor.docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': requests}
            ).execute()

            return {
                'success': True,
                'index': strategy.index,
                'section': strategy.section_name,
                'formatted_content': formatted_content
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def _format_content(
        self,
        content: str,
        format_type: str
    ) -> str:
        """Format content based on type."""

        if format_type == 'bullet_item':
            # Ensure content starts with newline and bullet
            if not content.startswith('\n'):
                content = '\n' + content
            if not content.lstrip().startswith('•'):
                content = content.replace('\n', '\n• ', 1)

        elif format_type == 'paragraph':
            # Ensure proper spacing
            if not content.startswith('\n'):
                content = '\n\n' + content
            if not content.endswith('\n'):
                content = content + '\n\n'

        return content

    def _build_insertion_requests(
        self,
        index: int,
        content: str,
        style_adjustments: Dict
    ) -> List[Dict]:
        """Build Google Docs API requests for insertion."""

        requests = [
            # Insert text
            {
                'insertText': {
                    'location': {'index': index},
                    'text': content
                }
            },
            # Apply blue color (new content marker)
            {
                'updateTextStyle': {
                    'range': {
                        'startIndex': index,
                        'endIndex': index + len(content)
                    },
                    'textStyle': {
                        'foregroundColor': {
                            'color': {
                                'rgbColor': {
                                    'red': 0.0,
                                    'green': 0.4,
                                    'blue': 0.8
                                }
                            }
                        }
                    },
                    'fields': 'foregroundColor'
                }
            }
        ]

        return requests
