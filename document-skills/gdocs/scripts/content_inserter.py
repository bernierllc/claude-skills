#!/usr/bin/env python3
"""
Content insertion with comment preservation for Google Docs.

This module implements intelligent content insertion that:
1. Detects existing comments before insertion
2. Calculates safe insertion points that avoid disrupting comments
3. Preserves comments using verified insert-then-delete strategy
4. Warns users when operations might affect commented text

Usage:
    from scripts.gdocs_editor import GoogleDocsEditor
    from scripts.content_inserter import ContentInserter, MergeOptions

    editor = GoogleDocsEditor()
    inserter = ContentInserter(editor)

    result = inserter.merge_content(
        doc_url="https://docs.google.com/document/d/ABC123/edit",
        content="Meeting notes...",
        section="Project Updates",
        options=MergeOptions(preserve_comments=True)
    )
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
import re


@dataclass
class CommentedRange:
    """A range of text that has a comment attached."""
    start_index: int
    end_index: int
    comment_id: str
    comment_content: str
    anchor_text: str

    def contains(self, index: int) -> bool:
        """Check if an index falls within this commented range."""
        return self.start_index <= index <= self.end_index

    def overlaps(self, start: int, end: int) -> bool:
        """Check if a range overlaps with this commented range."""
        return not (end < self.start_index or start > self.end_index)


@dataclass
class InsertionPoint:
    """A calculated position for content insertion."""
    index: int
    section_name: Optional[str] = None
    safe: bool = True  # True if no comments will be affected
    affected_comments: List[str] = field(default_factory=list)  # Comment IDs
    strategy: str = 'after'  # 'before', 'after', 'within', 'new_section'
    reason: str = ''  # Human-readable explanation


@dataclass
class MergeOptions:
    """Options for content merging."""
    preserve_comments: bool = True  # Default: conservative
    comment_strategy: str = 'preserve'  # 'preserve', 'update', 'ask'
    add_source_comment: bool = True  # Add "Added from meeting..." comment
    add_inline_attribution: bool = True  # Add inline "(from: ...)" text in italic purple
    source_description: Optional[str] = None  # e.g., "meeting on 2025-10-31"
    target_section: Optional[str] = None  # Section to insert into


class ContentInserter:
    """Handles intelligent content insertion with comment awareness."""

    def __init__(self, editor):
        """
        Initialize content inserter.

        Args:
            editor: GoogleDocsEditor instance
        """
        self.editor = editor

    def find_commented_ranges(self, doc_id: str) -> List[CommentedRange]:
        """
        Find all text ranges that have comments attached.

        Args:
            doc_id: Google Doc ID

        Returns:
            List of CommentedRange objects with exact start/end indices
        """
        # Get document and comments
        doc = self.editor.get_document(doc_id)
        comments = self.editor.comment_manager.get_comments(doc_id, include_resolved=False)

        # Get full document content for searching
        body = doc.get('body', {})
        content_elements = body.get('content', [])

        commented_ranges = []

        for comment in comments:
            if not comment.anchor:
                continue

            # Find this anchor text in the document structure
            anchor_text = comment.anchor
            found_range = self._find_text_range(content_elements, anchor_text)

            if found_range:
                start_idx, end_idx = found_range
                commented_ranges.append(CommentedRange(
                    start_index=start_idx,
                    end_index=end_idx,
                    comment_id=comment.comment_id,
                    comment_content=comment.content,
                    anchor_text=anchor_text
                ))

        return commented_ranges

    def _find_text_range(
        self,
        content_elements: List[Dict],
        target_text: str
    ) -> Optional[Tuple[int, int]]:
        """
        Find the start and end index of target text in document structure.

        Args:
            content_elements: Document content elements from Google Docs API
            target_text: Text to search for

        Returns:
            Tuple of (start_index, end_index) or None if not found
        """
        for element in content_elements:
            if 'paragraph' in element:
                para = element['paragraph']
                for text_elem in para.get('elements', []):
                    if 'textRun' in text_elem:
                        text_run = text_elem['textRun']
                        text_content = text_run.get('content', '')

                        if target_text in text_content:
                            start_index = text_elem.get('startIndex', 0)
                            text_offset = text_content.index(target_text)
                            actual_start = start_index + text_offset
                            actual_end = actual_start + len(target_text)
                            return (actual_start, actual_end)

            # Check nested structures (tables, lists, etc.)
            if 'table' in element:
                for row in element['table'].get('tableRows', []):
                    for cell in row.get('tableCells', []):
                        result = self._find_text_range(
                            cell.get('content', []),
                            target_text
                        )
                        if result:
                            return result

        return None

    def calculate_insertion_point(
        self,
        doc_id: str,
        section_name: Optional[str] = None,
        strategy: str = 'safe'
    ) -> InsertionPoint:
        """
        Calculate optimal insertion point that avoids disrupting comments.

        Args:
            doc_id: Google Doc ID
            section_name: Optional section name to target
            strategy: 'safe' (avoid comments), 'update' (can use preservation),
                     'ask' (return options for user)

        Returns:
            InsertionPoint with calculated index and metadata
        """
        # Get document structure
        analysis = self.editor.analyze_document(doc_id, include_comments=True)

        # Get commented ranges
        commented_ranges = self.find_commented_ranges(doc_id)

        # If section specified, find its boundaries
        if section_name:
            section_bounds = self._find_section_boundaries(analysis, section_name)
            if section_bounds:
                section_start, section_end = section_bounds

                # Safe strategy: Insert at END of section, after any comments
                if strategy == 'safe':
                    # Find the last position in section that's not commented
                    # Use section_end - 1 to stay within paragraph bounds
                    insertion_idx = section_end - 1

                    # Check if this position affects any comments
                    affected = [
                        cr.comment_id for cr in commented_ranges
                        if cr.contains(insertion_idx)
                    ]

                    return InsertionPoint(
                        index=insertion_idx,
                        section_name=section_name,
                        safe=len(affected) == 0,
                        affected_comments=affected,
                        strategy='after',
                        reason=f'End of section "{section_name}"'
                    )
            else:
                # Section not found - insert at document end
                doc = self.editor.get_document(doc_id)
                doc_end = doc.get('body', {}).get('content', [{}])[-1].get('endIndex', 1)

                return InsertionPoint(
                    index=doc_end - 1,
                    section_name=None,
                    safe=True,
                    affected_comments=[],
                    strategy='new_section',
                    reason=f'Section "{section_name}" not found, inserting at document end'
                )

        # No section specified - insert at document end
        doc = self.editor.get_document(doc_id)
        doc_end = doc.get('body', {}).get('content', [{}])[-1].get('endIndex', 1)

        return InsertionPoint(
            index=doc_end - 1,
            section_name=None,
            safe=True,
            affected_comments=[],
            strategy='new_section',
            reason='Inserting at document end'
        )

    def _find_section_boundaries(
        self,
        analysis,
        section_name: str
    ) -> Optional[Tuple[int, int]]:
        """
        Find the start and end indices of a named section.

        Args:
            analysis: DocumentAnalysis object
            section_name: Section name to find

        Returns:
            Tuple of (start_index, end_index) or None if not found
        """
        # Search through sections
        for section in analysis.sections:
            # Sections are dicts with 'heading', 'level', 'start_index', 'end_index'
            heading = section.get('heading', '')
            if heading and section_name.lower() in heading.lower():
                # Found the section - return its boundaries
                start_idx = section.get('start_index')
                end_idx = section.get('end_index')
                if start_idx is not None and end_idx is not None:
                    return (start_idx, end_idx)

        return None

    def insert_content(
        self,
        doc_id: str,
        index: int,
        content: str,
        tab_id: str = None,
        commented_range: Optional[CommentedRange] = None,
        add_inline_attribution: bool = False,
        attribution_text: str = None
    ) -> bool:
        """
        Insert content at specified index, preserving comment if in range.

        Args:
            doc_id: Google Doc ID
            index: Character index for insertion
            content: Text content to insert
            tab_id: Optional tab ID to target specific tab
            commented_range: Optional CommentedRange if updating commented text
            add_inline_attribution: Whether to add inline attribution text
            attribution_text: Text for inline attribution (e.g., "meeting on 10/31/25")

        Returns:
            True if successful
        """
        if commented_range:
            # Use verified preservation strategy
            return self._insert_with_comment_preservation(
                doc_id, index, content, commented_range
            )
        else:
            # Simple insertion with optional inline attribution
            return self._simple_insert(
                doc_id, index, content,
                tab_id=tab_id,
                add_inline_attribution=add_inline_attribution,
                attribution_text=attribution_text
            )

    def _simple_insert(
        self,
        doc_id: str,
        index: int,
        content: str,
        tab_id: str = None,
        add_inline_attribution: bool = False,
        attribution_text: str = None
    ) -> bool:
        """
        Perform simple content insertion without comment considerations.

        Inserts text and explicitly sets paragraph style to NORMAL_TEXT
        to prevent inheriting header formatting from adjacent content.
        Optionally adds inline attribution text in italicized purple.

        Args:
            doc_id: Google Doc ID
            index: Character index for insertion
            content: Text content to insert
            tab_id: Optional tab ID to target specific tab
            add_inline_attribution: Whether to add inline attribution text
            attribution_text: Text to add (e.g., "from: meeting on 10/31/25")

        Returns:
            True if successful
        """
        try:
            # Build location dict with optional tab ID
            location = {'index': index}
            if tab_id:
                location['tabId'] = tab_id

            # Build requests:
            # 1. Insert the text
            # 2. Set paragraph style to NORMAL_TEXT (prevents header inheritance)
            # 3. Optionally add inline attribution in italicized purple
            requests = [
                # Request 1: Insert text
                {
                    'insertText': {
                        'location': location,
                        'text': content
                    }
                },
                # Request 2: Set paragraph style to NORMAL_TEXT
                {
                    'updateParagraphStyle': {
                        'range': {
                            'startIndex': index,
                            'endIndex': index + len(content)
                        },
                        'paragraphStyle': {
                            'namedStyleType': 'NORMAL_TEXT'
                        },
                        'fields': 'namedStyleType'
                    }
                }
            ]

            # Add inline attribution if requested
            if add_inline_attribution and attribution_text:
                attribution_full = f" (from: {attribution_text})"
                attribution_index = index + len(content)

                # Build location for attribution with optional tab ID
                attribution_location = {'index': attribution_index}
                if tab_id:
                    attribution_location['tabId'] = tab_id

                # Insert attribution text
                requests.append({
                    'insertText': {
                        'location': attribution_location,
                        'text': attribution_full
                    }
                })

                # Format attribution: italic + purple color
                requests.append({
                    'updateTextStyle': {
                        'range': {
                            'startIndex': attribution_index,
                            'endIndex': attribution_index + len(attribution_full)
                        },
                        'textStyle': {
                            'italic': True,
                            'foregroundColor': {
                                'color': {
                                    'rgbColor': {
                                        'red': 0.6,
                                        'green': 0.2,
                                        'blue': 0.8
                                    }
                                }
                            }
                        },
                        'fields': 'italic,foregroundColor'
                    }
                })

            self.editor.docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': requests}
            ).execute()

            return True

        except Exception as e:
            print(f"Error during simple insert: {e}")
            return False

    def _insert_with_comment_preservation(
        self,
        doc_id: str,
        index: int,
        new_text: str,
        commented_range: CommentedRange
    ) -> bool:
        """
        Insert content using verified comment preservation strategy.

        Uses the pattern proven in test_comment_preservation.py:
        1. Insert new text within commented range
        2. Delete old text after insertion
        3. Delete old text before insertion

        Args:
            doc_id: Google Doc ID
            index: Character index within commented range
            new_text: New text to insert
            commented_range: CommentedRange object

        Returns:
            True if successful
        """
        try:
            # Build requests using verified strategy
            requests = []

            # Calculate positions based on commented range
            start_idx = commented_range.start_index
            end_idx = commented_range.end_index

            # Choose insertion position (middle of range for safety)
            insert_position = start_idx + (end_idx - start_idx) // 2

            # Request 1: Insert new text within range
            requests.append({
                'insertText': {
                    'location': {'index': insert_position},
                    'text': new_text
                }
            })

            # Request 2: Delete text after insertion (indices shift)
            delete_after_start = insert_position + len(new_text)
            delete_after_end = end_idx + len(new_text)

            if delete_after_end > delete_after_start:
                requests.append({
                    'deleteContentRange': {
                        'range': {
                            'startIndex': delete_after_start,
                            'endIndex': delete_after_end
                        }
                    }
                })

            # Request 3: Delete text before insertion (indices stable)
            if insert_position > start_idx:
                requests.append({
                    'deleteContentRange': {
                        'range': {
                            'startIndex': start_idx,
                            'endIndex': insert_position
                        }
                    }
                })

            # Execute batch update
            self.editor.docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': requests}
            ).execute()

            return True

        except Exception as e:
            print(f"Error during comment-preserving insert: {e}")
            import traceback
            traceback.print_exc()
            return False

    def merge_content(
        self,
        doc_url: str,
        content: str,
        section: Optional[str] = None,
        options: Optional[MergeOptions] = None
    ) -> Dict[str, Any]:
        """
        High-level API: Merge content into document intelligently.

        This is the main entry point for merging meeting notes into Google Docs.

        Args:
            doc_url: Google Doc URL or ID
            content: Content to insert
            section: Optional section name to target
            options: MergeOptions for controlling behavior

        Returns:
            Dictionary with:
            {
                'success': bool,
                'insertion_point': InsertionPoint,
                'comments_preserved': int,
                'new_comment_id': Optional[str],
                'message': str
            }
        """
        options = options or MergeOptions()

        try:
            # Extract doc_id and tab_id from URL
            doc_id = self.editor.extract_doc_id(doc_url)
            tab_id = self.editor.extract_tab_id(doc_url)

            # Calculate insertion point
            strategy = 'safe' if options.preserve_comments else 'simple'
            insertion_point = self.calculate_insertion_point(
                doc_id,
                section or options.target_section,
                strategy=strategy
            )

            # Check if user decision needed
            if insertion_point.affected_comments and options.comment_strategy == 'ask':
                return {
                    'success': False,
                    'requires_user_decision': True,
                    'affected_comments': insertion_point.affected_comments,
                    'insertion_point': insertion_point,
                    'options': ['insert_before', 'insert_after', 'update_with_preservation'],
                    'message': f'Insertion would affect {len(insertion_point.affected_comments)} comment(s)'
                }

            # Format content for insertion
            formatted_content = self._format_content_for_insertion(content)

            # Insert content with optional inline attribution
            success = self.insert_content(
                doc_id,
                insertion_point.index,
                formatted_content,
                tab_id=tab_id,  # Target specific tab if provided in URL
                commented_range=None,  # Phase 3 uses safe insertion
                add_inline_attribution=options.add_inline_attribution,
                attribution_text=options.source_description
            )

            if not success:
                return {
                    'success': False,
                    'message': 'Failed to insert content',
                    'insertion_point': insertion_point
                }

            # Phase 4: Add source comment with context
            new_comment_id = None
            if success and options.add_source_comment and options.source_description:
                try:
                    # Try to create contextual comment that searches for inserted text
                    # Strip formatting markers to get clean search text
                    clean_content = formatted_content.strip()

                    # Use first 50 chars as search text (or less if content is short)
                    search_length = min(50, len(clean_content))
                    search_text = clean_content[:search_length]

                    # Create comment with rich context (paragraph number + excerpt)
                    comment_text = f"📝 Added from {options.source_description}"
                    new_comment_id = self.editor.comment_manager.create_comment_with_context(
                        doc_id=doc_id,
                        content=comment_text,
                        search_text=search_text,
                        occurrence=0  # First occurrence
                    )

                    # Fallback to simple document-level comment if search fails
                    if new_comment_id is None:
                        print("Falling back to document-level comment")
                        new_comment_id = self.editor.comment_manager.create_comment(
                            doc_id=doc_id,
                            content=comment_text
                        )

                except Exception as e:
                    # Don't fail entire operation if comment creation fails
                    print(f"Warning: Could not create source comment: {e}")

            return {
                'success': True,
                'insertion_point': insertion_point,
                'comments_preserved': len(insertion_point.affected_comments),
                'new_comment_id': new_comment_id,
                'message': f'Content inserted successfully. {insertion_point.reason}'
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error: {str(e)}',
                'error': str(e)
            }

    def _format_content_for_insertion(self, content: str) -> str:
        """
        Format content for insertion into Google Docs.

        Args:
            content: Raw content string

        Returns:
            Formatted content with proper spacing
        """
        # Ensure content starts with newlines for separation
        if not content.startswith('\n'):
            content = '\n\n' + content

        # Ensure content ends with newlines
        if not content.endswith('\n'):
            content = content + '\n\n'

        return content
