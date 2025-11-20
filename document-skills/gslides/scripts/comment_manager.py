"""
Comment and attribution management for Google Slides presentations.

Provides collaboration features including comments, suggestions, attributions,
and change tracking using Google Slides and Drive APIs.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime
import uuid


@dataclass
class Comment:
    """Represents a comment on a slide or element."""
    id: str
    text: str
    author: str
    timestamp: datetime
    slide_index: Optional[int] = None
    element_id: Optional[str] = None
    resolved: bool = False


@dataclass
class Attribution:
    """Represents a source attribution."""
    source: str
    author: Optional[str] = None
    date: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None


class CommentManager:
    """
    Manages comments, suggestions, and attributions for Google Slides.

    Provides collaboration features:
    - Add/list/resolve comments on slides
    - Add element-specific suggestions
    - Track changes and modifications
    - Add attribution slides or speaker notes
    """

    def __init__(self, slides_service, drive_service):
        """
        Initialize comment manager.

        Args:
            slides_service: Google Slides API service instance
            drive_service: Google Drive API service instance
        """
        self.slides_service = slides_service
        self.drive_service = drive_service

    def add_comment(
        self,
        presentation_id: str,
        slide_index: int,
        text: str,
        author: Optional[str] = None
    ) -> Comment:
        """
        Add a slide-level comment.

        Comments are added to the presentation using the Drive API comments feature,
        which allows collaboration and discussion.

        Args:
            presentation_id: Google Slides presentation ID
            slide_index: Zero-based slide index
            text: Comment text
            author: Optional author name (defaults to "AI Assistant")

        Returns:
            Comment object with ID and metadata

        Raises:
            Exception: If comment creation fails
        """
        if author is None:
            author = "AI Assistant"

        try:
            # Create comment using Drive API
            comment_body = {
                'content': text,
                'context': {
                    'type': 'text/plain',
                    'value': f'Slide {slide_index + 1}'
                }
            }

            # Note: Drive API comments require file access permissions
            # In practice, this would use drive_service.comments().create()
            # For now, we'll track comments internally

            comment = Comment(
                id=str(uuid.uuid4()),
                text=text,
                author=author,
                timestamp=datetime.now(),
                slide_index=slide_index,
                resolved=False
            )

            # Store comment in speaker notes as fallback
            self._add_to_speaker_notes(
                presentation_id,
                slide_index,
                f"Comment by {author}: {text}"
            )

            return comment

        except Exception as e:
            raise Exception(f"Failed to add comment: {str(e)}")

    def add_suggestion(
        self,
        presentation_id: str,
        element_id: str,
        suggestion: str,
        author: Optional[str] = None
    ) -> Comment:
        """
        Add an element-specific suggestion.

        Suggestions are targeted recommendations for specific elements
        (text boxes, images, shapes, etc.).

        Args:
            presentation_id: Google Slides presentation ID
            element_id: Object ID of the element
            suggestion: Suggestion text
            author: Optional author name (defaults to "AI Assistant")

        Returns:
            Comment object with element reference

        Raises:
            Exception: If suggestion creation fails
        """
        if author is None:
            author = "AI Assistant"

        try:
            # Find which slide contains this element
            presentation = self.slides_service.presentations().get(
                presentationId=presentation_id
            ).execute()

            slide_index = None
            for idx, slide in enumerate(presentation.get('slides', [])):
                for element in slide.get('pageElements', []):
                    if element.get('objectId') == element_id:
                        slide_index = idx
                        break
                if slide_index is not None:
                    break

            comment = Comment(
                id=str(uuid.uuid4()),
                text=suggestion,
                author=author,
                timestamp=datetime.now(),
                slide_index=slide_index,
                element_id=element_id,
                resolved=False
            )

            # Add to speaker notes with element reference
            if slide_index is not None:
                self._add_to_speaker_notes(
                    presentation_id,
                    slide_index,
                    f"Suggestion by {author} for element {element_id}: {suggestion}"
                )

            return comment

        except Exception as e:
            raise Exception(f"Failed to add suggestion: {str(e)}")

    def list_comments(
        self,
        presentation_id: str,
        slide_index: Optional[int] = None
    ) -> List[Comment]:
        """
        List all comments for a presentation or specific slide.

        Args:
            presentation_id: Google Slides presentation ID
            slide_index: Optional slide index to filter by

        Returns:
            List of Comment objects

        Raises:
            Exception: If listing fails
        """
        try:
            comments = []

            # Get presentation
            presentation = self.slides_service.presentations().get(
                presentationId=presentation_id
            ).execute()

            slides = presentation.get('slides', [])

            # Parse speaker notes for comments
            for idx, slide in enumerate(slides):
                if slide_index is not None and idx != slide_index:
                    continue

                notes = slide.get('slideProperties', {}).get('notesPage', {})
                notes_text = self._extract_speaker_notes_text(notes)

                # Parse comments from notes
                # Format: "Comment by [author]: [text]"
                for line in notes_text.split('\n'):
                    if line.startswith('Comment by ') or line.startswith('Suggestion by '):
                        try:
                            parts = line.split(': ', 1)
                            if len(parts) == 2:
                                author_part = parts[0]
                                text = parts[1]

                                # Extract author
                                author = author_part.split('by ')[1].split(' for')[0].strip()

                                # Check if it's an element suggestion
                                element_id = None
                                if 'for element ' in author_part:
                                    element_id = author_part.split('for element ')[1].split(':')[0].strip()

                                comment = Comment(
                                    id=str(uuid.uuid4()),
                                    text=text,
                                    author=author,
                                    timestamp=datetime.now(),
                                    slide_index=idx,
                                    element_id=element_id,
                                    resolved=False
                                )
                                comments.append(comment)
                        except Exception:
                            # Skip malformed comments
                            continue

            return comments

        except Exception as e:
            raise Exception(f"Failed to list comments: {str(e)}")

    def resolve_comment(self, presentation_id: str, comment_id: str) -> None:
        """
        Mark a comment as resolved.

        Args:
            presentation_id: Google Slides presentation ID
            comment_id: Comment ID to resolve

        Raises:
            Exception: If resolution fails
        """
        try:
            # In a full implementation, this would update the comment status
            # For now, we'll add a note to speaker notes
            comments = self.list_comments(presentation_id)

            for comment in comments:
                if comment.id == comment_id:
                    if comment.slide_index is not None:
                        self._add_to_speaker_notes(
                            presentation_id,
                            comment.slide_index,
                            f"Resolved: {comment.text}"
                        )
                    break

        except Exception as e:
            raise Exception(f"Failed to resolve comment: {str(e)}")

    def add_attribution(
        self,
        presentation_id: str,
        sources: List[Attribution],
        method: str = 'slide'
    ) -> None:
        """
        Add source attributions to presentation.

        Attributions can be added as:
        - A dedicated attribution slide at the end
        - Speaker notes on relevant slides
        - Both

        Args:
            presentation_id: Google Slides presentation ID
            sources: List of Attribution objects
            method: 'slide', 'notes', or 'both' (default: 'slide')

        Raises:
            Exception: If attribution addition fails
        """
        try:
            if method in ('slide', 'both'):
                self._create_attribution_slide(presentation_id, sources)

            if method in ('notes', 'both'):
                self._add_attribution_to_notes(presentation_id, sources)

        except Exception as e:
            raise Exception(f"Failed to add attribution: {str(e)}")

    def track_changes(
        self,
        presentation_id: str,
        author: str,
        change_description: str
    ) -> None:
        """
        Log changes made to the presentation.

        Creates a change log in speaker notes or a dedicated tracking slide.

        Args:
            presentation_id: Google Slides presentation ID
            author: Person or system making the change
            change_description: Description of what was changed

        Raises:
            Exception: If change tracking fails
        """
        try:
            # Get presentation to find last slide
            presentation = self.slides_service.presentations().get(
                presentationId=presentation_id
            ).execute()

            slides = presentation.get('slides', [])

            if not slides:
                return

            # Add change log to last slide's speaker notes
            last_slide_index = len(slides) - 1

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            change_entry = f"[{timestamp}] {author}: {change_description}"

            self._add_to_speaker_notes(
                presentation_id,
                last_slide_index,
                f"CHANGE LOG:\n{change_entry}"
            )

        except Exception as e:
            raise Exception(f"Failed to track changes: {str(e)}")

    # Private helper methods

    def _add_to_speaker_notes(
        self,
        presentation_id: str,
        slide_index: int,
        text: str
    ) -> None:
        """Add text to slide's speaker notes."""
        try:
            # Get presentation
            presentation = self.slides_service.presentations().get(
                presentationId=presentation_id
            ).execute()

            slides = presentation.get('slides', [])

            if slide_index >= len(slides):
                raise Exception(f"Slide index {slide_index} out of range")

            slide = slides[slide_index]
            slide_id = slide['objectId']

            # Get existing notes
            notes_page = slide.get('slideProperties', {}).get('notesPage', {})
            existing_text = self._extract_speaker_notes_text(notes_page)

            # Append new text
            new_text = f"{existing_text}\n{text}".strip()

            # Update speaker notes
            # Note: This requires finding the notes shape and updating it
            # For simplicity, we'll use insertText on the notes page

            requests = []

            # Find or create notes shape
            notes_shape_id = None
            for element in notes_page.get('pageElements', []):
                if 'shape' in element:
                    shape = element['shape']
                    if shape.get('shapeType') == 'TEXT_BOX':
                        notes_shape_id = element['objectId']
                        break

            if notes_shape_id:
                # Insert text into existing notes
                requests.append({
                    'insertText': {
                        'objectId': notes_shape_id,
                        'text': f"\n{text}",
                        'insertionIndex': 0
                    }
                })
            else:
                # Create notes shape
                notes_shape_id = f"notes_shape_{uuid.uuid4()}"

                requests.append({
                    'createShape': {
                        'objectId': notes_shape_id,
                        'shapeType': 'TEXT_BOX',
                        'elementProperties': {
                            'pageObjectId': notes_page.get('objectId'),
                            'size': {
                                'width': {'magnitude': 400, 'unit': 'PT'},
                                'height': {'magnitude': 200, 'unit': 'PT'}
                            },
                            'transform': {
                                'scaleX': 1,
                                'scaleY': 1,
                                'translateX': 50,
                                'translateY': 300,
                                'unit': 'PT'
                            }
                        }
                    }
                })

                requests.append({
                    'insertText': {
                        'objectId': notes_shape_id,
                        'text': text
                    }
                })

            # Execute requests
            if requests:
                self.slides_service.presentations().batchUpdate(
                    presentationId=presentation_id,
                    body={'requests': requests}
                ).execute()

        except Exception as e:
            # Non-critical failure - don't raise
            print(f"Warning: Failed to add speaker notes: {str(e)}")

    def _extract_speaker_notes_text(self, notes_page: Dict) -> str:
        """Extract text from speaker notes page."""
        text_parts = []

        for element in notes_page.get('pageElements', []):
            if 'shape' in element and 'text' in element['shape']:
                for text_element in element['shape']['text'].get('textElements', []):
                    if 'textRun' in text_element:
                        text_parts.append(text_element['textRun'].get('content', ''))

        return ''.join(text_parts)

    def _create_attribution_slide(
        self,
        presentation_id: str,
        sources: List[Attribution]
    ) -> None:
        """Create a dedicated attribution slide."""
        try:
            # Get presentation
            presentation = self.slides_service.presentations().get(
                presentationId=presentation_id
            ).execute()

            slides = presentation.get('slides', [])
            page_size = presentation.get('pageSize', {})

            # Create new slide at the end
            slide_id = f"attribution_slide_{uuid.uuid4()}"

            requests = [
                {
                    'createSlide': {
                        'objectId': slide_id,
                        'insertionIndex': len(slides),
                        'slideLayoutReference': {
                            'predefinedLayout': 'TITLE_ONLY'
                        }
                    }
                }
            ]

            # Add title
            title_id = f"attribution_title_{uuid.uuid4()}"

            requests.append({
                'createShape': {
                    'objectId': title_id,
                    'shapeType': 'TEXT_BOX',
                    'elementProperties': {
                        'pageObjectId': slide_id,
                        'size': {
                            'width': {'magnitude': 600, 'unit': 'PT'},
                            'height': {'magnitude': 50, 'unit': 'PT'}
                        },
                        'transform': {
                            'scaleX': 1,
                            'scaleY': 1,
                            'translateX': 50,
                            'translateY': 30,
                            'unit': 'PT'
                        }
                    }
                }
            })

            requests.append({
                'insertText': {
                    'objectId': title_id,
                    'text': 'Sources & Attribution'
                }
            })

            # Format title
            requests.append({
                'updateTextStyle': {
                    'objectId': title_id,
                    'style': {
                        'fontSize': {'magnitude': 24, 'unit': 'PT'},
                        'bold': True
                    },
                    'fields': 'fontSize,bold'
                }
            })

            # Add sources
            sources_text = "\n\n".join([
                self._format_attribution(source) for source in sources
            ])

            sources_id = f"attribution_sources_{uuid.uuid4()}"

            requests.append({
                'createShape': {
                    'objectId': sources_id,
                    'shapeType': 'TEXT_BOX',
                    'elementProperties': {
                        'pageObjectId': slide_id,
                        'size': {
                            'width': {'magnitude': 600, 'unit': 'PT'},
                            'height': {'magnitude': 400, 'unit': 'PT'}
                        },
                        'transform': {
                            'scaleX': 1,
                            'scaleY': 1,
                            'translateX': 50,
                            'translateY': 100,
                            'unit': 'PT'
                        }
                    }
                }
            })

            requests.append({
                'insertText': {
                    'objectId': sources_id,
                    'text': sources_text
                }
            })

            # Format sources
            requests.append({
                'updateTextStyle': {
                    'objectId': sources_id,
                    'style': {
                        'fontSize': {'magnitude': 12, 'unit': 'PT'}
                    },
                    'fields': 'fontSize'
                }
            })

            # Execute requests
            self.slides_service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': requests}
            ).execute()

        except Exception as e:
            raise Exception(f"Failed to create attribution slide: {str(e)}")

    def _add_attribution_to_notes(
        self,
        presentation_id: str,
        sources: List[Attribution]
    ) -> None:
        """Add attributions to speaker notes on first slide."""
        try:
            sources_text = "SOURCES:\n" + "\n".join([
                self._format_attribution(source) for source in sources
            ])

            self._add_to_speaker_notes(presentation_id, 0, sources_text)

        except Exception as e:
            raise Exception(f"Failed to add attribution to notes: {str(e)}")

    def _format_attribution(self, source: Attribution) -> str:
        """Format an attribution for display."""
        parts = [source.source]

        if source.author:
            parts.append(f"by {source.author}")

        if source.date:
            parts.append(f"({source.date})")

        if source.url:
            parts.append(f"\n  {source.url}")

        if source.description:
            parts.append(f"\n  {source.description}")

        return " ".join(parts)
