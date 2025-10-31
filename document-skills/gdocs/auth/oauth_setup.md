# Google Docs API - OAuth 2.0 Setup Guide

This guide will walk you through setting up OAuth 2.0 authentication for the Google Docs skill.

## Prerequisites

- A Google Account
- Python 3.7 or higher
- Internet connection

## Step 1: Create a Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a project** → **New Project**
3. Enter a project name (e.g., "Claude Skills - Google Docs")
4. Click **Create**
5. Wait for the project to be created, then select it

## Step 2: Enable Required APIs

1. In the Google Cloud Console, navigate to **APIs & Services** → **Library**
2. Search for and enable the following APIs:
   - **Google Docs API**
     - Click on it → Click **Enable**
   - **Google Drive API**
     - Click on it → Click **Enable**

## Step 3: Configure OAuth Consent Screen

1. Navigate to **APIs & Services** → **OAuth consent screen**
2. Select **External** user type (unless you have a Google Workspace account)
3. Click **Create**
4. Fill in the required fields:
   - **App name:** Claude Skills - Google Docs
   - **User support email:** Your email address
   - **Developer contact information:** Your email address
5. Click **Save and Continue**
6. On the **Scopes** page:
   - Click **Add or Remove Scopes**
   - Search for and select:
     - `https://www.googleapis.com/auth/documents`
     - `https://www.googleapis.com/auth/drive.file`
   - Click **Update**
   - Click **Save and Continue**
7. On the **Test users** page:
   - Click **Add Users**
   - Add your email address
   - Click **Save and Continue**
8. Review the summary and click **Back to Dashboard**

## Step 4: Create OAuth 2.0 Credentials

1. Navigate to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. Select **Desktop app** as the application type
4. Enter a name: "Claude Skills Desktop Client"
5. Click **Create**
6. Click **Download JSON** to download the credentials file
7. Rename the downloaded file to `credentials.json`
8. Move `credentials.json` to the `auth/` directory:
   ```bash
   mv ~/Downloads/credentials.json document-skills/gdocs/auth/credentials.json
   ```

## Step 5: Install Python Dependencies

```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

## Step 6: Test Authentication

Run the test script to verify everything is set up correctly:

```bash
cd document-skills/gdocs
python examples/test_auth.py
```

This will:
1. Open a browser window
2. Ask you to grant permissions to the app
3. Save your credentials to `~/.claude-skills/gdocs/tokens.json`
4. Display your Google account information

**Important:** The first time you run this, Google will show a warning that the app is not verified. This is expected for apps in testing mode. Click **Advanced** → **Go to [App Name] (unsafe)** to proceed.

## Troubleshooting

### "The OAuth client was not found"
- Make sure you've enabled both Google Docs API and Google Drive API
- Verify that `credentials.json` is in the `auth/` directory
- Check that the credentials file hasn't been corrupted

### "Access blocked: This app's request is invalid"
- Ensure you've configured the OAuth consent screen
- Verify that you've added yourself as a test user
- Check that you've selected the correct scopes

### "invalid_grant: Token has been expired or revoked"
- Delete `~/.claude-skills/gdocs/tokens.json`
- Run the authentication flow again

### Browser doesn't open automatically
- The script will print a URL
- Copy and paste the URL into your browser manually
- Complete the OAuth flow
- Copy the authorization code back to the terminal

## Security Notes

- **Never commit `credentials.json` to version control** (it's in `.gitignore`)
- **Never share `credentials.json` with others**
- Tokens are stored in `~/.claude-skills/gdocs/tokens.json` (also never commit)
- You can revoke access anytime at https://myaccount.google.com/permissions

## Publishing Your App (Optional)

If you want to use this without the "unsafe app" warning:

1. Navigate to **OAuth consent screen**
2. Click **Publish App**
3. Submit for verification (requires additional steps and review)

For personal use, keeping the app in testing mode is perfectly fine.

## Next Steps

Once authentication is working, you can:
- Read Google Docs: `python examples/read_document.py`
- Test document analysis: `python examples/analyze_structure.py`
- Try the full skill workflow
