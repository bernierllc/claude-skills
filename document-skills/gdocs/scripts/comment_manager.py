#!/usr/bin/env python3
"""
Comment Manager for Google Docs.

Handles reading and creating comments via Google Drive API.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Comment:
    """Represents a comment on a Google Doc."""
    comment_id: str
    content: str
    author: str
    created_time: datetime
    modified_time: datetime
    resolved: bool
    anchor: Optional[str] = None  # The text this comment is attached to
    replies: List['CommentReply'] = None

    def __post_init__(self):
        if self.replies is None:
            self.replies = []


@dataclass
class CommentReply:
    """Represents a reply to a comment."""
    reply_id: str
    content: str
    author: str
    created_time: datetime
    modified_time: datetime


class CommentManager:
    """Manages comments on Google Docs via Drive API."""

    def __init__(self, drive_service):
        """
        Initialize the comment manager.

        Args:
            drive_service: Authenticated Google Drive API service object
        """
        self.drive_service = drive_service

    def get_comments(self, doc_id: str, include_resolved: bool = False) -> List[Comment]:
        """
        Get all comments from a Google Doc.

        Args:
            doc_id: Google Docs document ID
            include_resolved: Whether to include resolved comments (default: False)

        Returns:
            List of Comment objects

        Example:
            >>> comments = comment_mgr.get_comments('DOC_ID')
            >>> for comment in comments:
            ...     print(f"{comment.author}: {comment.content}")
        """
        try:
            # Get comments from Drive API
            results = self.drive_service.comments().list(
                fileId=doc_id,
                fields='comments(id,content,author,createdTime,modifiedTime,resolved,anchor,quotedFileContent,replies)',
                includeDeleted=False
            ).execute()

            comments = []
            for comment_data in results.get('comments', []):
                # Skip resolved comments if requested
                if not include_resolved and comment_data.get('resolved', False):
                    continue

                # Parse comment
                comment = self._parse_comment(comment_data)
                comments.append(comment)

            return comments

        except Exception as e:
            raise RuntimeError(f"Failed to get comments: {e}")

    def _parse_comment(self, comment_data: Dict[str, Any]) -> Comment:
        """
        Parse comment data from API response.

        Args:
            comment_data: Raw comment data from API

        Returns:
            Comment object
        """
        # Parse author
        author_data = comment_data.get('author', {})
        author_name = author_data.get('displayName', 'Unknown')

        # Parse timestamps
        created_time = self._parse_timestamp(comment_data.get('createdTime'))
        modified_time = self._parse_timestamp(comment_data.get('modifiedTime'))

        # Get anchor text (the text the comment is attached to)
        anchor = None
        quoted_content = comment_data.get('quotedFileContent', {})
        if quoted_content:
            anchor = quoted_content.get('value', '')

        # Parse replies
        replies = []
        for reply_data in comment_data.get('replies', []):
            reply = self._parse_reply(reply_data)
            replies.append(reply)

        return Comment(
            comment_id=comment_data.get('id'),
            content=comment_data.get('content', ''),
            author=author_name,
            created_time=created_time,
            modified_time=modified_time,
            resolved=comment_data.get('resolved', False),
            anchor=anchor,
            replies=replies
        )

    def _parse_reply(self, reply_data: Dict[str, Any]) -> CommentReply:
        """
        Parse reply data from API response.

        Args:
            reply_data: Raw reply data from API

        Returns:
            CommentReply object
        """
        author_data = reply_data.get('author', {})
        author_name = author_data.get('displayName', 'Unknown')

        created_time = self._parse_timestamp(reply_data.get('createdTime'))
        modified_time = self._parse_timestamp(reply_data.get('modifiedTime'))

        return CommentReply(
            reply_id=reply_data.get('id'),
            content=reply_data.get('content', ''),
            author=author_name,
            created_time=created_time,
            modified_time=modified_time
        )

    @staticmethod
    def _parse_timestamp(timestamp_str: Optional[str]) -> Optional[datetime]:
        """
        Parse ISO 8601 timestamp string.

        Args:
            timestamp_str: ISO 8601 timestamp string

        Returns:
            datetime object or None
        """
        if not timestamp_str:
            return None

        try:
            # Remove 'Z' and parse
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1] + '+00:00'
            return datetime.fromisoformat(timestamp_str)
        except Exception:
            return None

    def create_comment(self, doc_id: str, content: str, anchor_text: Optional[str] = None) -> str:
        """
        Create a new comment on a Google Doc.

        Args:
            doc_id: Google Docs document ID
            content: Comment text
            anchor_text: Optional text to anchor the comment to

        Returns:
            Comment ID of the created comment

        Example:
            >>> comment_id = comment_mgr.create_comment('DOC_ID', 'Great point!')
        """
        comment_body = {
            'content': content
        }

        # Add anchor if provided (not implemented yet - needs quotedFileContent)
        # This will be enhanced in Phase 4

        try:
            result = self.drive_service.comments().create(
                fileId=doc_id,
                body=comment_body,
                fields='id'
            ).execute()

            return result.get('id')

        except Exception as e:
            raise RuntimeError(f"Failed to create comment: {e}")

    def reply_to_comment(self, doc_id: str, comment_id: str, content: str) -> str:
        """
        Reply to an existing comment.

        Args:
            doc_id: Google Docs document ID
            comment_id: ID of the comment to reply to
            content: Reply text

        Returns:
            Reply ID

        Example:
            >>> reply_id = comment_mgr.reply_to_comment('DOC_ID', 'comment_123', 'I agree!')
        """
        reply_body = {
            'content': content
        }

        try:
            result = self.drive_service.replies().create(
                fileId=doc_id,
                commentId=comment_id,
                body=reply_body,
                fields='id'
            ).execute()

            return result.get('id')

        except Exception as e:
            raise RuntimeError(f"Failed to create reply: {e}")

    def resolve_comment(self, doc_id: str, comment_id: str):
        """
        Mark a comment as resolved.

        Args:
            doc_id: Google Docs document ID
            comment_id: Comment ID to resolve

        Example:
            >>> comment_mgr.resolve_comment('DOC_ID', 'comment_123')
        """
        try:
            self.drive_service.comments().update(
                fileId=doc_id,
                commentId=comment_id,
                body={'resolved': True}
            ).execute()

        except Exception as e:
            raise RuntimeError(f"Failed to resolve comment: {e}")

    def format_comments_summary(self, comments: List[Comment]) -> str:
        """
        Format comments into a readable summary.

        Args:
            comments: List of Comment objects

        Returns:
            Formatted string with comment summary
        """
        if not comments:
            return "No comments found."

        lines = []
        lines.append(f"\nFound {len(comments)} comment(s):\n")
        lines.append("=" * 60)

        for i, comment in enumerate(comments, 1):
            lines.append(f"\n{i}. Comment by {comment.author}")
            lines.append(f"   Created: {comment.created_time.strftime('%Y-%m-%d %H:%M') if comment.created_time else 'Unknown'}")

            if comment.anchor:
                lines.append(f"   On text: \"{comment.anchor[:50]}{'...' if len(comment.anchor) > 50 else ''}\"")

            lines.append(f"   Content: {comment.content}")

            if comment.replies:
                lines.append(f"   Replies ({len(comment.replies)}):")
                for reply in comment.replies:
                    lines.append(f"      → {reply.author}: {reply.content}")

            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)

    # =========================================================================
    # Phase 4: Comment Creation & Management
    # =========================================================================

    def create_comment(
        self,
        doc_id: str,
        content: str
    ) -> str:
        """
        Create a new document-level comment.

        Note: Google Drive API's anchor field for Google Docs is not reliably
        supported by the Google Docs editor. Comments created via API are
        treated as document-level comments, not anchored to specific text.

        For text-level comments, users should add them manually in the UI.

        Args:
            doc_id: Google Doc ID
            content: Comment text

        Returns:
            Comment ID of created comment

        Raises:
            HttpError: If API call fails

        Example:
            >>> manager = CommentManager(drive_service)
            >>> comment_id = manager.create_comment(
            ...     doc_id='ABC123',
            ...     content='📝 Added from team meeting on 2025-10-31'
            ... )
        """
        from googleapiclient.errors import HttpError

        try:
            comment_body = {
                'content': content
            }

            result = self.drive_service.comments().create(
                fileId=doc_id,
                body=comment_body,
                fields='id,content,author,createdTime'
            ).execute()

            return result.get('id')

        except HttpError as e:
            print(f"Error creating comment: {e}")
            raise

    def reply_to_comment(
        self,
        doc_id: str,
        comment_id: str,
        content: str
    ) -> str:
        """
        Reply to an existing comment.

        Args:
            doc_id: Google Doc ID
            comment_id: ID of comment to reply to
            content: Reply text

        Returns:
            Reply ID

        Raises:
            HttpError: If API call fails

        Example:
            >>> manager = CommentManager(drive_service)
            >>> reply_id = manager.reply_to_comment(
            ...     doc_id='ABC123',
            ...     comment_id='XYZ789',
            ...     content='This has been addressed'
            ... )
        """
        from googleapiclient.errors import HttpError

        try:
            reply_body = {
                'content': content
            }

            result = self.drive_service.replies().create(
                fileId=doc_id,
                commentId=comment_id,
                body=reply_body,
                fields='id,content,author,createdTime'
            ).execute()

            return result.get('id')

        except HttpError as e:
            print(f"Error replying to comment: {e}")
            raise

    def resolve_comment(
        self,
        doc_id: str,
        comment_id: str
    ) -> bool:
        """
        Mark a comment as resolved.

        Args:
            doc_id: Google Doc ID
            comment_id: ID of comment to resolve

        Returns:
            True if successful

        Example:
            >>> manager = CommentManager(drive_service)
            >>> success = manager.resolve_comment(
            ...     doc_id='ABC123',
            ...     comment_id='XYZ789'
            ... )
        """
        from googleapiclient.errors import HttpError

        try:
            # Get the existing comment first (API requires content field)
            comment = self.drive_service.comments().get(
                fileId=doc_id,
                commentId=comment_id,
                fields='content'
            ).execute()

            # Update with existing content + resolved flag
            self.drive_service.comments().update(
                fileId=doc_id,
                commentId=comment_id,
                body={
                    'content': comment.get('content'),
                    'resolved': True
                },
                fields='id,resolved'
            ).execute()

            return True

        except HttpError as e:
            print(f"Error resolving comment: {e}")
            return False

    def create_comment_with_context(
        self,
        doc_id: str,
        content: str,
        search_text: str,
        occurrence: int = 0
    ) -> Optional[str]:
        """
        Create a comment with rich context near specific text.

        This searches the document for the specified text and creates a comment
        that includes paragraph number and excerpt for context. Note: Per Google's
        documentation, comments created via API are treated as "unanchored" in
        Google Docs UI, but the comment body will contain location info.

        Args:
            doc_id: Google Doc ID
            content: Base comment text
            search_text: Text to search for in document
            occurrence: Which occurrence to target (0 = first match)

        Returns:
            Comment ID if successful, None if text not found

        Example:
            >>> manager = CommentManager(drive_service)
            >>> comment_id = manager.create_comment_with_context(
            ...     doc_id='ABC123',
            ...     content='📊 Synthesized from meeting on 10/31/25',
            ...     search_text='Recent customer research validates',
            ...     occurrence=0
            ... )
        """
        from googleapiclient.errors import HttpError

        try:
            # Import here to avoid circular dependency
            from .gdocs_editor import GoogleDocsEditor

            # Get document content via Docs API
            # We need a docs_service - let's build one from our drive creds
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            # Use the same credentials from drive_service
            creds = self.drive_service._http.credentials
            docs_service = build('docs', 'v1', credentials=creds)

            # Get document structure
            doc = docs_service.documents().get(documentId=doc_id).execute()

            # Search for text in document
            matches = self._find_text_in_document(doc, search_text)

            if not matches:
                print(f"Warning: Text '{search_text[:50]}...' not found in document")
                return None

            # Pick the requested occurrence
            if occurrence >= len(matches):
                occurrence = len(matches) - 1

            match = matches[occurrence]

            # Build rich comment with context
            contextual_content = (
                f"{content}\n\n"
                f"📍 Location: Paragraph #{match['paragraph_index']}\n"
                f"📝 Context: \"...{match['excerpt']}...\""
            )

            # Create comment (will be unanchored in UI per Google's docs)
            comment_body = {
                'content': contextual_content
            }

            result = self.drive_service.comments().create(
                fileId=doc_id,
                body=comment_body,
                fields='id,content,author,createdTime'
            ).execute()

            return result.get('id')

        except HttpError as e:
            print(f"Error creating contextual comment: {e}")
            return None

    def _find_text_in_document(self, doc: dict, search_text: str) -> list:
        """
        Find all occurrences of text in document.

        Args:
            doc: Document resource from Docs API
            search_text: Text to search for

        Returns:
            List of dicts with keys: paragraph_index, doc_start, excerpt
        """
        matches = []
        para_idx = -1
        lower_search = search_text.lower()

        body = doc.get('body', {})
        for content_elem in body.get('content', []):
            paragraph = content_elem.get('paragraph')
            if not paragraph:
                continue

            para_idx += 1

            # Concatenate all text runs in this paragraph
            text_parts = []
            start_index = None

            for element in paragraph.get('elements', []):
                if 'startIndex' in element and start_index is None:
                    start_index = element['startIndex']

                text_run = element.get('textRun')
                if text_run and 'content' in text_run:
                    text_parts.append(text_run['content'])

            if not text_parts:
                continue

            full_text = ''.join(text_parts)
            lower_text = full_text.lower()

            # Find all occurrences in this paragraph
            pos = 0
            while True:
                idx = lower_text.find(lower_search, pos)
                if idx == -1:
                    break

                # Calculate document-absolute position
                doc_start = (start_index or 1) + idx

                # Extract excerpt (40 chars before and after)
                excerpt_start = max(0, idx - 40)
                excerpt_end = min(len(full_text), idx + len(search_text) + 40)
                excerpt = full_text[excerpt_start:excerpt_end].replace('\n', ' ').strip()

                matches.append({
                    'paragraph_index': para_idx,
                    'doc_start': doc_start,
                    'length': len(search_text),
                    'excerpt': excerpt
                })

                pos = idx + len(search_text)

        return matches

    def delete_comment(
        self,
        doc_id: str,
        comment_id: str
    ) -> bool:
        """
        Delete a comment.

        Args:
            doc_id: Google Doc ID
            comment_id: ID of comment to delete

        Returns:
            True if successful

        Example:
            >>> manager = CommentManager(drive_service)
            >>> success = manager.delete_comment(
            ...     doc_id='ABC123',
            ...     comment_id='XYZ789'
            ... )
        """
        from googleapiclient.errors import HttpError

        try:
            self.drive_service.comments().delete(
                fileId=doc_id,
                commentId=comment_id
            ).execute()

            return True

        except HttpError as e:
            print(f"Error deleting comment: {e}")
            return False
