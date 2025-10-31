# Quick Start Guide - Google Docs Skill

Get up and running in 10 minutes!

## Step 1: Install Dependencies (1 minute)

```bash
cd document-skills/gdocs
pip install -r requirements.txt
```

## Step 2: Set Up OAuth (5-8 minutes)

### A. Create Google Cloud Project

1. Go to https://console.cloud.google.com/
2. Create new project: "Claude Skills - Google Docs"
3. Enable APIs:
   - **Google Docs API** → Enable
   - **Google Drive API** → Enable

### B. Configure OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**
2. Choose **External** → Create
3. Fill in:
   - App name: "Claude Skills - Google Docs"
   - Support email: your email
   - Developer email: your email
4. Add scopes (click "Add or Remove Scopes"):
   - `https://www.googleapis.com/auth/documents`
   - `https://www.googleapis.com/auth/drive.file`
5. Add test user: your email
6. Save

### C. Create Credentials

1. Go to **APIs & Services** → **Credentials**
2. **Create Credentials** → **OAuth client ID**
3. Application type: **Desktop app**
4. Name: "Claude Skills Desktop"
5. Click **Create**
6. **Download JSON**
7. Save as `auth/credentials.json`

## Step 3: Authenticate (1 minute)

```bash
python examples/test_auth.py
```

- Browser will open
- Grant permissions (ignore "unsafe app" warning - click Advanced → Continue)
- Done! Credentials saved to `~/.claude-skills/gdocs/tokens.json`

## Step 4: Test It! (30 seconds)

```bash
python examples/read_document.py "YOUR_GOOGLE_DOC_URL"
```

Example:
```bash
python examples/read_document.py "https://docs.google.com/document/d/1A2B3C4D5E6F/edit"
```

You should see your document's structure and content!

## Troubleshooting

**"OAuth client was not found"**
→ Make sure `credentials.json` is in `auth/` directory

**"Access blocked: This app's request is invalid"**
→ Check that you added yourself as a test user in OAuth consent screen

**"Permission denied" reading document**
→ Make sure you have at least View access to the document

## Next Steps

- Read full documentation: `SKILL.md`
- Detailed OAuth guide: `auth/oauth_setup.md`
- Wait for Phase 2-6 (content insertion & comments)!

## What's Working Now (Phase 1)

✅ OAuth authentication
✅ Read any Google Doc
✅ Parse document structure
✅ Extract sections and headings
✅ Get plain text content

## Coming Soon

🚧 Insert content into documents
🚧 Add contextual comments
🚧 Merge meeting notes workflow
🚧 Format preservation

---

**Total setup time:** ~10 minutes (one-time)
**Future uses:** Instant (tokens saved!)
