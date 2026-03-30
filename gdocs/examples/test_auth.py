#!/usr/bin/env python3
"""
Test OAuth authentication setup.

This script verifies that OAuth credentials are properly configured
and allows you to authenticate for the first time.
"""

import sys
from pathlib import Path

# Add parent directory to path to import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.auth_manager import AuthManager


def main():
    print("="*60)
    print("Google Docs API - OAuth Authentication Test")
    print("="*60)
    print()

    # Initialize auth manager
    auth_manager = AuthManager()

    print(f"Looking for credentials at: {auth_manager.credentials_path}")
    print(f"Tokens will be saved to: {auth_manager.token_path}")
    print()

    # Attempt authentication
    try:
        creds = auth_manager.authenticate()
        print("\n✓ Authentication successful!")
        print(f"\n✓ Access token obtained (expires in ~1 hour)")
        print(f"✓ Refresh token saved to: {auth_manager.token_path}")
        print("\n✓ You're ready to use the Google Docs skill!")
        print("\nNext steps:")
        print("  1. Try: python examples/read_document.py <doc_url>")
        print("  2. Or read the SKILL.md documentation")

    except FileNotFoundError as e:
        print(f"\n✗ Error: {e}")
        print("\nPlease follow the setup guide:")
        print("  1. Read auth/oauth_setup.md")
        print("  2. Create credentials.json in the auth/ directory")
        sys.exit(1)

    except Exception as e:
        print(f"\n✗ Authentication failed: {e}")
        print("\nTroubleshooting:")
        print("  1. Check that you've enabled Google Docs API and Drive API")
        print("  2. Verify OAuth consent screen is configured")
        print("  3. Ensure you've added yourself as a test user")
        print("  4. See auth/oauth_setup.md for detailed instructions")
        sys.exit(1)


if __name__ == '__main__':
    main()
