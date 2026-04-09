"""
Google Tasks MCP Server
=======================
A remote MCP (Model Context Protocol) server that wraps the Google Tasks API.
It lets Claude list, create, complete, and delete tasks on your behalf.

Transport: Streamable HTTP (so it works as a Claude remote MCP connector).
Auth:      Uses a long-lived Google OAuth 2.0 refresh token from env vars.
"""

import os
import datetime

# ---------------------------------------------------------------------------
# Google API client setup
# ---------------------------------------------------------------------------
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ---------------------------------------------------------------------------
# MCP SDK imports
# ---------------------------------------------------------------------------
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Read Google OAuth credentials from environment variables.
# These are set once on the server (e.g. in Render's dashboard).
# ---------------------------------------------------------------------------
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN", "")


def _get_tasks_service():
    """
    Build and return an authenticated Google Tasks API client.

    We create fresh credentials from the refresh token each time.
    The Google library automatically refreshes the access token
    when needed, so the server stays authenticated forever.
    """
    credentials = Credentials(
        token=None,  # will be fetched automatically
        refresh_token=GOOGLE_REFRESH_TOKEN,
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
    )
    # 'tasks' is the API name, 'v1' is the version
    return build("tasks", "v1", credentials=credentials)


# ---------------------------------------------------------------------------
# Create the MCP server
# ---------------------------------------------------------------------------
# The `name` shows up in Claude's UI when the connector is registered.
# Use the PORT environment variable (Render sets this automatically).
port = int(os.environ.get("PORT", 8000))

mcp = FastMCP(
    name="Google Tasks",
    instructions=(
        "Manage Google Tasks. You can list task lists, view tasks, "
        "create new tasks, mark tasks complete, and delete tasks."
    ),
    host="0.0.0.0",
    port=port,
)


# ===========================================================================
# Tool 1: list_task_lists
# ===========================================================================
@mcp.tool()
def list_task_lists() -> list[dict]:
    """
    List all Google Task lists for the user.

    Returns a list of task lists, each with 'id', 'title', and 'updated'.
    The default list is usually called "My Tasks".
    """
    service = _get_tasks_service()

    # Google's API paginates, so we loop to get everything
    all_lists = []
    page_token = None

    while True:
        response = (
            service.tasklists()
            .list(maxResults=100, pageToken=page_token)
            .execute()
        )
        for tl in response.get("items", []):
            all_lists.append(
                {
                    "id": tl["id"],
                    "title": tl["title"],
                    "updated": tl.get("updated", ""),
                }
            )
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return all_lists


# ===========================================================================
# Tool 2: list_tasks
# ===========================================================================
@mcp.tool()
def list_tasks(
    task_list_id: str = "@default",
    show_completed: bool = False,
    max_results: int = 100,
) -> list[dict]:
    """
    List tasks in a specific task list.

    Args:
        task_list_id: The ID of the task list. Use "@default" for "My Tasks".
        show_completed: If True, also include completed tasks.
        max_results: Maximum number of tasks to return (1-100).
    """
    service = _get_tasks_service()

    all_tasks = []
    page_token = None

    while True:
        response = (
            service.tasks()
            .list(
                tasklist=task_list_id,
                maxResults=min(max_results, 100),
                showCompleted=show_completed,
                showHidden=show_completed,  # hidden = completed + cleared
                pageToken=page_token,
            )
            .execute()
        )
        for task in response.get("items", []):
            all_tasks.append(
                {
                    "id": task["id"],
                    "title": task.get("title", ""),
                    "notes": task.get("notes", ""),
                    "status": task.get("status", ""),  # "needsAction" or "completed"
                    "due": task.get("due", ""),  # RFC 3339 date
                    "updated": task.get("updated", ""),
                }
            )
        page_token = response.get("nextPageToken")
        if not page_token or len(all_tasks) >= max_results:
            break

    return all_tasks[:max_results]


# ===========================================================================
# Tool 3: create_task
# ===========================================================================
@mcp.tool()
def create_task(
    title: str,
    notes: str = "",
    due_date: str = "",
    task_list_id: str = "@default",
) -> dict:
    """
    Create a new task.

    Args:
        title: The task title (required).
        notes: Optional extra details / description.
        due_date: Optional due date in YYYY-MM-DD format (e.g. "2025-03-15").
        task_list_id: Which task list to add it to. "@default" = "My Tasks".
    """
    service = _get_tasks_service()

    # Build the request body
    body: dict = {"title": title}

    if notes:
        body["notes"] = notes

    if due_date:
        # Google Tasks expects an RFC 3339 timestamp for the due date.
        # We append T00:00:00.000Z so it's treated as an all-day date.
        body["due"] = f"{due_date}T00:00:00.000Z"

    result = (
        service.tasks().insert(tasklist=task_list_id, body=body).execute()
    )

    return {
        "id": result["id"],
        "title": result.get("title", ""),
        "notes": result.get("notes", ""),
        "due": result.get("due", ""),
        "status": result.get("status", ""),
    }


# ===========================================================================
# Tool 4: complete_task
# ===========================================================================
@mcp.tool()
def complete_task(
    task_id: str,
    task_list_id: str = "@default",
) -> dict:
    """
    Mark a task as completed.

    Args:
        task_id: The ID of the task to complete.
        task_list_id: The task list the task belongs to. "@default" = "My Tasks".
    """
    service = _get_tasks_service()

    # We need to patch the task's status to "completed"
    body = {
        "id": task_id,
        "status": "completed",
    }

    result = (
        service.tasks()
        .patch(tasklist=task_list_id, task=task_id, body=body)
        .execute()
    )

    return {
        "id": result["id"],
        "title": result.get("title", ""),
        "status": result.get("status", ""),
        "completed": result.get("completed", ""),
    }


# ===========================================================================
# Tool 5: delete_task
# ===========================================================================
@mcp.tool()
def delete_task(
    task_id: str,
    task_list_id: str = "@default",
) -> str:
    """
    Delete a task permanently.

    Args:
        task_id: The ID of the task to delete.
        task_list_id: The task list the task belongs to. "@default" = "My Tasks".
    """
    service = _get_tasks_service()

    service.tasks().delete(tasklist=task_list_id, task=task_id).execute()

    return f"Task {task_id} deleted successfully."


# ===========================================================================
# Start the server
# ===========================================================================
if __name__ == "__main__":
    # Run with streamable-http transport so Claude can connect remotely.
    mcp.run(transport="streamable-http")
