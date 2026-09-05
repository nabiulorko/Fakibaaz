# 🔌 One-time setup: connect Fakibaaz to Google Sheets

Your data now lives in a Google Sheet instead of a local CSV. This means:
- It survives Streamlit restarts, redeploys, and sleep cycles.
- Opening the app on your laptop **or** phone and typing the same Student ID
  (e.g. `2202195`) shows the same saved sessions.

Do this once. It takes about 5 minutes.

## 1. Create the Google Sheet
1. Go to [sheets.google.com](https://sheets.google.com) and create a new blank sheet.
2. Name it anything, e.g. `Fakibaaz Data`.
3. Copy the **Sheet ID** from its URL:
   `https://docs.google.com/spreadsheets/d/`**`THIS_LONG_ID_PART`**`/edit`

## 2. Create a Google Cloud service account (a robot login for the app)
1. Go to [console.cloud.google.com](https://console.cloud.google.com) → create a project (any name).
2. Enable the **Google Sheets API** for that project (search "Google Sheets API" → Enable).
3. Go to **APIs & Services → Credentials → Create Credentials → Service Account**.
   Give it any name, click through the defaults.
4. Open the new service account → **Keys** tab → **Add Key → Create new key → JSON**.
   A `.json` file downloads — keep it private, don't commit it anywhere public.
5. Inside that JSON, find the `"client_email"` value (looks like
   `something@your-project.iam.gserviceaccount.com`).

## 3. Share the Sheet with the service account
1. Open your Google Sheet from step 1 → **Share**.
2. Paste the `client_email` from step 2, give it **Editor** access, send.
   (It's a robot account, not a real inbox — this just grants access.)

## 4. Add credentials to Streamlit secrets
Create a file `.streamlit/secrets.toml` next to `study_planner_app.py` (locally),
or paste the same content into **Settings → Secrets** if deployed on Streamlit
Community Cloud:

```toml
sheet_id = "PASTE_YOUR_SHEET_ID_HERE"

[gcp_service_account]
type = "service_account"
project_id = "PASTE_FROM_JSON"
private_key_id = "PASTE_FROM_JSON"
private_key = "-----BEGIN PRIVATE KEY-----\nPASTE_FULL_KEY_FROM_JSON\n-----END PRIVATE KEY-----\n"
client_email = "PASTE_FROM_JSON"
client_id = "PASTE_FROM_JSON"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "PASTE_FROM_JSON"
```

Every field above is copied straight out of the downloaded JSON file — same key
names, just moved into `.toml` format. Keep the `\n` characters inside
`private_key` exactly as they appear in the JSON (as literal `\n`, on one line,
wrapped in quotes).

## 5. Run it
```bash
streamlit run study_planner_app.py
```
Enter your Student ID (e.g. `2202195`) in the sidebar. The app creates a
`StudyData` tab in your Sheet automatically on first run and starts saving
every finished session there, tagged with your ID.

## Notes
- The ID is a **lookup key, not a password** — anyone who types the same ID
  sees that ID's data. Fine for personal use across your own devices; don't
  share your ID publicly if the sheet contains anything sensitive.
- If you ever want to peek at or back up your raw data, just open the Google
  Sheet directly — it's a normal spreadsheet.
