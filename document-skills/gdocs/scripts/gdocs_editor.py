#!/usr/bin/env python3
"""
Main Google Docs Editor API.

Provides high-level interface for reading and editing Google Docs.
"""

import re
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .auth_manager import AuthManager
from .comment_manager import CommentManager, Comment


@dataclass
class DocumentAnalysis:
    """Represents the analysis of a Google Doc structure."""
    doc_id: str
    title: str
    content: str
    sections: List[Dict[str, Any]]
    total_chars: int
    comments: List[Comment] = None

    def __post_init__(self):
        if self.comments is None:
            self.comments = []


class GoogleDocsEditor:
    """Main API for reading and editing Google Docs with contextual comments."""

    def __init__(self, credentials_path: Optional[str] = None, token_path: Optional[str] = None):
        """
        Initialize the Google Docs Editor.

        Args:
            credentials_path: Path to OAuth credentials file.
            token_path: Path to store user tokens.
        """
        self.auth_manager = AuthManager(credentials_path, token_path)
        self.docs_service = None
        self.drive_service = None
        self.comment_manager = None

    def _ensure_authenticated(self):
        """Ensure we have valid credentials and service objects."""
        if not self.docs_service or not self.drive_service:
            try:
                creds = self.auth_manager.get_credentials()
                self.docs_service = build('docs', 'v1', credentials=creds)
                self.drive_service = build('drive', 'v3', credentials=creds)
                self.comment_manager = CommentManager(self.drive_service)
            except FileNotFoundError as e:
                # credentials.json not found
                raise FileNotFoundError(
                    f"{e}\n\n"
                    f"To set up OAuth credentials:\n"
                    f"  1. Read: {self.auth_manager.credentials_path.parent}/oauth_setup.md\n"
                    f"  2. Download credentials.json to: {self.auth_manager.credentials_path}"
                )
            except Exception as e:
                # Other authentication errors
                print(f"\n✗ Authentication failed: {e}")
                print(f"\nTo re-authenticate manually:")
                print(f"  1. Delete expired tokens: rm {self.auth_manager.token_path}")
                print(f"  2. Re-run authentication: python examples/test_auth.py")
                raise

    @staticmethod
    def extract_doc_id(doc_url_or_id: str) -> str:
        """
        Extract document ID from URL or return as-is if already an ID.

        Args:
            doc_url_or_id: Google Docs URL or document ID

        Returns:
            Document ID

        Examples:
            >>> extract_doc_id('https://docs.google.com/document/d/ABC123/edit')
            'ABC123'
            >>> extract_doc_id('ABC123')
            'ABC123'
        """
        # Pattern: /d/{DOC_ID}/
        match = re.search(r'/d/([a-zA-Z0-9-_]+)', doc_url_or_id)
        if match:
            return match.group(1)
        # Assume it's already a document ID
        return doc_url_or_id

    @staticmethod
    def extract_tab_id(doc_url: str) -> Optional[str]:
        """
        Extract tab ID from URL query parameter.

        Args:
            doc_url: Google Docs URL

        Returns:
            Tab ID if present in URL, None otherwise

        Examples:
            >>> extract_tab_id('https://docs.google.com/document/d/ABC/edit?tab=t.123')
            't.123'
            >>> extract_tab_id('https://docs.google.com/document/d/ABC/edit')
            None
        """
        match = re.search(r'[?&]tab=([^&]+)', doc_url)
        return match.group(1) if match else None

    @staticmethod
    def find_tab_by_id(tabs: List[dict], tab_id: str) -> Optional[dict]:
        """
        Find tab by ID, searching recursively through child tabs.

        Args:
            tabs: List of tab objects
            tab_id: Tab ID to find (e.g., 't.0', 't.82ynznspwjyi')

        Returns:
            Tab object if found, None otherwise
        """
        for tab in tabs:
            if tab.get('tabProperties', {}).get('tabId') == tab_id:
                return tab

            # Search child tabs recursively
            child_tabs = tab.get('childTabs', [])
            if child_tabs:
                found = GoogleDocsEditor.find_tab_by_id(child_tabs, tab_id)
                if found:
                    return found

        return None

    def get_tab_body(self, document: dict, tab_id: Optional[str] = None) -> dict:
        """
        Get body content from specific tab or first tab.

        Args:
            document: Document resource with tabs
            tab_id: Optional tab ID to target specific tab

        Returns:
            Body content from target tab
        """
        tabs = document.get('tabs', [])

        if not tabs:
            # Legacy: No tabs, use document body
            return document.get('body', {})

        if tab_id:
            # Find specific tab
            target_tab = self.find_tab_by_id(tabs, tab_id)
            if target_tab:
                return target_tab.get('documentTab', {}).get('body', {})

        # Default to first tab
        return tabs[0].get('documentTab', {}).get('body', {})

    def get_document(self, doc_url_or_id: str, include_tabs_content: bool = True) -> Dict[str, Any]:
        """
        Retrieve a Google Doc by URL or ID.

        Args:
            doc_url_or_id: Google Docs URL or document ID
            include_tabs_content: If True, includes all tabs content (recommended)

        Returns:
            Document resource (JSON structure)

        Raises:
            HttpError: If document doesn't exist or user lacks permissions
        """
        self._ensure_authenticated()
        doc_id = self.extract_doc_id(doc_url_or_id)

        try:
            document = self.docs_service.documents().get(
                documentId=doc_id,
                includeTabsContent=include_tabs_content
            ).execute()
            return document
        except HttpError as error:
            if error.resp.status == 404:
                raise ValueError(f"Document not found: {doc_id}. This might be a Word document (.docx), which cannot be edited via the Google Docs API.")
            elif error.resp.status == 400 and "not supported" in str(error).lower():
                raise ValueError(
                    f"This is a Word document (.docx) stored in Google Drive, not a native Google Doc.\n"
                    f"The Google Docs API cannot read or edit .docx files.\n\n"
                    f"Options:\n"
                    f"1. Convert to Google Doc: In Google Drive, right-click → Open with → Google Docs\n"
                    f"2. Use the docx skill instead for Word documents\n"
                    f"3. Download the .docx file and work with it locally"
                )
            elif error.resp.status == 403:
                raise PermissionError(f"No permission to access document: {doc_id}")
            else:
                raise

    def create_document(self, title: str, initial_content: Optional[str] = None) -> Dict[str, str]:
        """
        Create a new Google Doc.

        Args:
            title: Title for the new document
            initial_content: Optional initial content to insert

        Returns:
            Dictionary with 'doc_id' and 'doc_url' keys

        Example:
            >>> editor = GoogleDocsEditor()
            >>> result = editor.create_document('My New Document')
            >>> print(f"Created: {result['doc_url']}")
        """
        self._ensure_authenticated()

        # Create the document
        document = self.docs_service.documents().create(body={
            'title': title
        }).execute()

        doc_id = document.get('documentId')
        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"

        # Add initial content if provided
        if initial_content:
            requests = [{
                'insertText': {
                    'location': {
                        'index': 1,
                    },
                    'text': initial_content
                }
            }]

            self.docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': requests}
            ).execute()

        return {
            'doc_id': doc_id,
            'doc_url': doc_url,
            'title': title
        }

    def analyze_document(self, doc_url_or_id: str, include_comments: bool = True) -> DocumentAnalysis:
        """
        Analyze a Google Doc's structure and content.

        Args:
            doc_url_or_id: Google Docs URL or document ID
            include_comments: Whether to include comments in analysis

        Returns:
            DocumentAnalysis with structure information
        """
        doc = self.get_document(doc_url_or_id, include_tabs_content=True)
        doc_id = self.extract_doc_id(doc_url_or_id)

        # Extract tab ID from URL if present
        tab_id = self.extract_tab_id(doc_url_or_id)

        # Get body from target tab
        body = self.get_tab_body(doc, tab_id)

        title = doc.get('title', 'Untitled')
        content_elements = body.get('content', [])

        # Extract text content and identify sections
        sections = []
        current_section = None
        text_content = []

        for element in content_elements:
            if 'paragraph' in element:
                para = element['paragraph']
                para_style = para.get('paragraphStyle', {})
                named_style = para_style.get('namedStyleType', '')

                # Extract text from paragraph
                para_text = self._extract_paragraph_text(para)
                text_content.append(para_text)

                # Identify headings as section markers
                if named_style.startswith('HEADING_'):
                    if current_section:
                        sections.append(current_section)

                    heading_level = named_style.replace('HEADING_', '')
                    current_section = {
                        'heading': para_text,
                        'level': heading_level,
                        'start_index': element.get('startIndex', 0),
                        'end_index': element.get('endIndex', 0),
                    }
                elif current_section:
                    # Update section end index as we encounter more content
                    current_section['end_index'] = element.get('endIndex', 0)

        # Add final section
        if current_section:
            sections.append(current_section)

        # Calculate total character count
        total_chars = content_elements[-1].get('endIndex', 0) if content_elements else 0

        # Get comments if requested
        comments = []
        if include_comments:
            try:
                comments = self.comment_manager.get_comments(doc_id)
            except Exception as e:
                # Don't fail the whole analysis if comments fail
                print(f"Warning: Could not retrieve comments: {e}")

        return DocumentAnalysis(
            doc_id=doc_id,
            title=title,
            content='\n'.join(text_content),
            sections=sections,
            total_chars=total_chars,
            comments=comments
        )

    @staticmethod
    def _extract_paragraph_text(paragraph: Dict[str, Any]) -> str:
        """
        Extract plain text from a paragraph element.

        Args:
            paragraph: Paragraph element from document

        Returns:
            Plain text content
        """
        elements = paragraph.get('elements', [])
        text_parts = []

        for elem in elements:
            if 'textRun' in elem:
                text_run = elem['textRun']
                text = text_run.get('content', '')
                text_parts.append(text)

        return ''.join(text_parts).rstrip('\n')

    def read_document_text(self, doc_url_or_id: str) -> str:
        """
        Read the plain text content of a Google Doc.

        Args:
            doc_url_or_id: Google Docs URL or document ID

        Returns:
            Plain text content of the document
        """
        analysis = self.analyze_document(doc_url_or_id)
        return analysis.content

    def print_document_structure(self, doc_url_or_id: str):
        """
        Print a formatted overview of the document structure.

        Args:
            doc_url_or_id: Google Docs URL or document ID
        """
        analysis = self.analyze_document(doc_url_or_id)

        print(f"\n{'='*60}")
        print(f"Document: {analysis.title}")
        print(f"ID: {analysis.doc_id}")
        print(f"Total characters: {analysis.total_chars}")
        print(f"{'='*60}\n")

        if analysis.sections:
            print(f"Document Structure ({len(analysis.sections)} sections):\n")
            for i, section in enumerate(analysis.sections, 1):
                indent = '  ' * (int(section['level']) - 1) if section['level'].isdigit() else ''
                print(f"{i}. {indent}[H{section['level']}] {section['heading']}")
                print(f"   {indent}    (chars {section['start_index']}-{section['end_index']})")
        else:
            print("No sections detected (no headings found)")

        # Display comments if available
        if analysis.comments:
            print(f"\n{'='*60}")
            print(f"Comments ({len(analysis.comments)}):")
            print(f"{'='*60}")
            print(self.comment_manager.format_comments_summary(analysis.comments))

        print(f"\n{'='*60}")
        print("Content preview (first 500 chars):")
        print(f"{'='*60}")
        print(analysis.content[:500])
        if len(analysis.content) > 500:
            print(f"\n... ({len(analysis.content) - 500} more characters)")
