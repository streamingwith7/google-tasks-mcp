# Google Tasks MCP Server

A remote [MCP](https://modelcontextprotocol.io) server that lets Claude manage your Google Tasks — from the desktop app, the web, or your phone.

## What it does

Once deployed, Claude can:
- **List your task lists** (e.g. "My Tasks", "Work", "Shopping")
- **List tasks** in any list (with optional completed-task filter)
- **Create tasks** with a title, notes, and due date
- **Mark tasks complete**
- **Delete tasks**

---

## Prerequisites

- **Python 3.11+** installed on your Mac
- A **Google Cloud project** with the Tasks API enabled and OAuth 2.0 credentials (type: "Desktop app")
- A **GitHub account** (with the `gh` CLI installed — `brew install gh`)
- A free **[Render](https://render.com)** account for hosting

---

## Step-by-step setup

### Step 1: Get your Google OAuth refresh token

This is a one-time step you run on your Mac. It opens your browser, asks you to log into Google, and prints a refresh token that the server uses to stay authenticated.

```bash
# Go into the project folder
cd ~/google-tasks-mcp

# Create a virtual environment and activate it
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the OAuth helper script
python get_refresh_token.py
```

The script will ask you to paste your **Client ID** and **Client Secret**, then open your browser. Log in with the Google account whose tasks you want to manage, and click "Allow".

When it finishes, you'll see a line like:

```
SUCCESS! Here is your refresh token:

1//0eXXXXXXXXXXXXXXXXXXXXXXXXXX
```

**Copy that token** and save it somewhere safe (e.g. a note). You'll need it in Step 3.

---

### Step 2: Push to GitHub

If you haven't already, create a GitHub repo and push the code:

```bash
cd ~/google-tasks-mcp
git init
git add .
git commit -m "Initial commit: Google Tasks MCP server"
gh repo create google-tasks-mcp --public --source=. --push
```

---

### Step 3: Deploy to Render

1. Go to [render.com](https://render.com) and sign in.
2. Click **"New +"** → **"Web Service"**.
3. Connect your GitHub account if you haven't, then select the **google-tasks-mcp** repo.
4. Render will auto-detect the settings from `render.yaml`. Verify:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `python server.py`
5. Scroll to **Environment Variables** and add these three:

   | Key                    | Value                        |
   |------------------------|------------------------------|
   | `GOOGLE_CLIENT_ID`     | Your OAuth Client ID         |
   | `GOOGLE_CLIENT_SECRET` | Your OAuth Client Secret     |
   | `GOOGLE_REFRESH_TOKEN` | The token from Step 1        |

6. Click **"Create Web Service"** and wait for the deploy to finish.
7. Copy your service URL — it will look like `https://google-tasks-mcp-xxxx.onrender.com`.

---

### Step 4: Register in Claude as a remote MCP connector

#### Claude Desktop (Mac)

1. Open Claude → **Settings** (gear icon) → **Integrations**.
2. Click **"Add custom integration"**.
3. Set the name to **Google Tasks**.
4. Set the URL to: `https://google-tasks-mcp-xxxx.onrender.com/mcp` (your Render URL + `/mcp`).
5. Click **Save**.

#### Claude Web (claude.ai)

1. Go to [claude.ai](https://claude.ai) → **Settings** → **Integrations**.
2. Follow the same steps as above.

#### Claude Mobile (iOS / Android)

Remote MCP integrations added in desktop or web sync automatically to your mobile app.

---

## Testing it out

Start a new conversation with Claude and try:

> "Show me all my Google task lists."

> "What tasks do I have in My Tasks?"

> "Add a task called 'Buy groceries' with a due date of 2025-04-15."

> "Mark the 'Buy groceries' task as complete."

---

## Running locally (for development)

```bash
cd ~/google-tasks-mcp
source venv/bin/activate

# Set env vars for local testing
export GOOGLE_CLIENT_ID="your-client-id"
export GOOGLE_CLIENT_SECRET="your-client-secret"
export GOOGLE_REFRESH_TOKEN="your-refresh-token"

python server.py
```

The server runs on `http://localhost:8000`. You can point Claude Desktop at `http://localhost:8000/mcp` for local testing.

---

## Troubleshooting

- **"invalid_grant" error:** Your refresh token may have expired. Re-run `python get_refresh_token.py` to get a new one, then update it in Render.
- **"Access Not Configured" error:** Make sure the Google Tasks API is enabled in your Google Cloud project.
- **Server won't start on Render:** Check the Render logs. Usually it's a missing environment variable.
