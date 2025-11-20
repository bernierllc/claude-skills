#!/usr/bin/env python3
"""
OAuth 2.0 Authentication Manager for Google Slides API.

Handles the OAuth flow, token storage, and automatic token refresh.
"""

import os
import json
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# OAuth scopes required for the skill
SCOPES = [
    'https://www.googleapis.com/auth/presentations',  # Read and write presentations
    'https://www.googleapis.com/auth/drive',  # Full Drive access (needed for comments and file management)
]


class AuthManager:
    """Manages OAuth 2.0 authentication for Google Slides API."""

    def __init__(self, credentials_path: Optional[str] = None, token_path: Optional[str] = None):
        """
        Initialize the authentication manager.

        Args:
            credentials_path: Path to OAuth client credentials JSON file.
                            Defaults to auth/credentials.json
            token_path: Path to store user tokens.
                       Defaults to ~/.claude-skills/gslides/tokens.json
        """
        # Default credentials path relative to skill directory
        skill_dir = Path(__file__).parent.parent
        self.credentials_path = Path(credentials_path) if credentials_path else skill_dir / 'auth' / 'credentials.json'

        # Default token path in user home directory
        if token_path:
            self.token_path = Path(token_path)
        else:
            token_dir = Path.home() / '.claude-skills' / 'gslides'
            token_dir.mkdir(parents=True, exist_ok=True)
            self.token_path = token_dir / 'tokens.json'

        self.credentials: Optional[Credentials] = None

    def authenticate(self) -> Credentials:
        """
        Authenticate with Google APIs using OAuth 2.0.

        Returns:
            Credentials object for making API calls.

        Raises:
            FileNotFoundError: If credentials.json is not found.
            Exception: If authentication fails.
        """
        # Load existing tokens if available
        if self.token_path.exists():
            self.credentials = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)

        # If credentials are invalid or don't exist, authenticate
        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                # Try to refresh expired credentials
                try:
                    print("Refreshing expired credentials...")
                    self.credentials.refresh(Request())
                    print("✓ Token refreshed successfully")
                except Exception as e:
                    print(f"✗ Token refresh failed: {e}")
                    print("Re-authenticating with OAuth flow...")
                    # Clear credentials to force OAuth flow below
                    self.credentials = None

            # Run OAuth flow if credentials are None or refresh failed
            if not self.credentials:
                if not self.credentials_path.exists():
                    raise FileNotFoundError(
                        f"OAuth credentials not found at {self.credentials_path}\n"
                        f"Please follow the setup guide in auth/oauth_setup.md"
                    )

                print("Starting OAuth authentication flow...")
                print("A browser window will open for you to grant permissions.")

                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), SCOPES
                )
                self.credentials = flow.run_local_server(port=0)

            # Save credentials for future use
            self._save_credentials()

        return self.credentials

    def _save_credentials(self):
        """Save credentials to token file."""
        with open(self.token_path, 'w') as token_file:
            token_file.write(self.credentials.to_json())
        print(f"Credentials saved to {self.token_path}")

    def get_credentials(self) -> Credentials:
        """
        Get valid credentials, authenticating if necessary.

        Returns:
            Valid Credentials object.
        """
        if not self.credentials or not self.credentials.valid:
            return self.authenticate()
        return self.credentials

    def revoke_credentials(self):
        """Revoke current credentials and delete token file."""
        if self.credentials:
            # Revoke the credentials
            import requests
            requests.post(
                'https://oauth2.googleapis.com/revoke',
                params={'token': self.credentials.token},
                headers={'content-type': 'application/x-www-form-urlencoded'}
            )
            self.credentials = None

        # Delete token file
        if self.token_path.exists():
            self.token_path.unlink()
            print(f"Credentials revoked and {self.token_path} deleted")
