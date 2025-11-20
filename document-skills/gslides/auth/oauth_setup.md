# Google Slides API - OAuth 2.0 Setup Guide

This guide walks you through setting up OAuth 2.0 authentication for the Google Slides skill.

## Prerequisites

- Google account
- 10-15 minutes

## Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Enter project name (e.g., "Claude Slides Skill")
4. Click "Create"
5. Wait for project creation to complete

## Step 2: Enable Google Slides API and Drive API

1. In Cloud Console, go to "APIs & Services" → "Library"
2. Search for "Google Slides API"
3. Click on it → Click "Enable"
4. Go back to Library
5. Search for "Google Drive API"
6. Click on it → Click "Enable"

**Why Drive API?** The Drive API is needed for:
- Creating comments on presentations
- Managing file permissions
- Accessing shared presentations

## Step 3: Configure OAuth Consent Screen

1. Go to "APIs & Services" → "OAuth consent screen"
2. Select "External" user type → Click "Create"
3. Fill in required fields:
   - **App name**: Claude Slides Skill
   - **User support email**: Your email
   - **Developer contact**: Your email
4. Click "Save and Continue"
5. Click "Add or Remove Scopes"
6. Add these scopes:
   - `.../auth/presentations` (Read and write Google Slides)
   - `.../auth/drive` (Full Drive access for comments)
7. Click "Update" → "Save and Continue"
8. Add yourself as a test user:
   - Click "Add Users"
   - Enter your Gmail address
   - Click "Add"
9. Click "Save and Continue" → "Back to Dashboard"

## Step 4: Create OAuth Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. Select "Desktop app" as application type
4. Enter name: "Claude Slides Desktop Client"
5. Click "Create"
6. Click "Download JSON" (downloads `client_secret_xxx.json`)
7. Rename downloaded file to `credentials.json`
8. Move `credentials.json` to this `auth/` directory

## Step 5: Verify Setup

Your `auth/` directory should now have:

```
auth/
├── .gitignore
├── oauth_setup.md (this file)
├── credentials.json.example
└── credentials.json (your actual credentials)
```

## Step 6: Test Authentication

```bash
cd /path/to/.claude/skills/document-skills/gslides
python examples/test_auth.py
```

This will:
1. Open your browser
2. Ask you to grant permissions
3. Save tokens to `~/.claude-skills/gslides/tokens.json`

## OAuth Scopes Explained

This skill requests these OAuth scopes:

| Scope | Purpose | Why Needed |
|-------|---------|------------|
| `https://www.googleapis.com/auth/presentations` | Read and write Google Slides | Create, read, and update presentations |
| `https://www.googleapis.com/auth/drive` | Full Drive access | Comments, file management, shared presentations |

## Security Notes

### What Gets Stored

- **`credentials.json`**: OAuth client credentials (client ID, client secret)
- **`~/.claude-skills/gslides/tokens.json`**: User access and refresh tokens

### Protection

- Both files are in `.gitignore` and will NEVER be committed to git
- Tokens auto-refresh when expired
- You can revoke access anytime at: https://myaccount.google.com/permissions

### Token Refresh

- Access tokens expire after ~1 hour
- Refresh tokens are used to automatically get new access tokens
- You only need to re-authenticate if:
  - You delete `tokens.json`
  - You revoke app permissions
  - Refresh token fails

## Troubleshooting

### "Error 403: Access denied"

**Problem**: You haven't added yourself as a test user.

**Solution**:
1. Go to "OAuth consent screen"
2. Scroll to "Test users"
3. Click "Add Users"
4. Add your Gmail address

### "Error 400: redirect_uri_mismatch"

**Problem**: OAuth redirect URI doesn't match.

**Solution**: This should not happen with desktop app type. If it does:
1. Go to "Credentials"
2. Click on your OAuth client
3. Ensure "Desktop app" is selected

### "credentials.json not found"

**Problem**: File not in correct location or not named correctly.

**Solution**:
1. Ensure file is named exactly `credentials.json`
2. Ensure it's in the `auth/` directory
3. Check it's not `credentials.json.example`

### "The file was created with a newer version"

**Problem**: Download included incorrect JSON structure.

**Solution**:
1. Delete `credentials.json`
2. Go back to Cloud Console
3. Download JSON again
4. Rename to `credentials.json`

## Next Steps

After successful authentication:
1. Try creating a presentation: `python examples/create_presentation.py`
2. Read the SKILL.md documentation
3. Explore example scripts in `examples/`

## Support

- [Google Slides API Documentation](https://developers.google.com/slides/api)
- [Google Drive API Documentation](https://developers.google.com/drive/api)
- [OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
