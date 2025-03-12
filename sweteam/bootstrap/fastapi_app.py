from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
import sys
import os
import json
from typing import List, Optional
from datetime import datetime

from sweteam.bootstrap.utils.log import get_default_logger

from .utils.issue_management import IssueManager
from .config import config

logger = get_default_logger(__name__)

app = FastAPI()

# Mount static files directory
app.mount("/static", StaticFiles(directory="sweteam/bootstrap/static"), name="static")

# Set up Jinja2 templates
templates = Jinja2Templates(directory="sweteam/bootstrap/templates")

# Initialize the IssueManager
issue_manager = IssueManager()

# Sample data for demonstration (replace with actual data from IssueManager)

def issue_list() -> list:
    issues = issue_manager.get_cached_doc_metadata() or issue_manager.source.get_all_metadata()
    issues_list = []
    for k, v in issues.items():
        issues_list.append({'id': v.get(f"{issue_manager.namespace}id", k),
                            'title': (v.get('title') or v.get(f'{issue_manager.namespace}title'))[:80]})
    return issues_list

class ChatMessage(BaseModel):
    message: str
    issue_id: str


class UserInput(BaseModel):
    input_text: str


@app.get("/", response_class=HTMLResponse)
async def get_issue_chat_page(request: Request):
    """
    Serve the issue chat page.

    Args:
        request (Request): The FastAPI request object.

    Returns:
        TemplateResponse: The rendered HTML template with issue data.

    Example:
        >>> from fastapi.testclient import TestClient
        >>> client = TestClient(app)
        >>> response = client.get("/")
        >>> response.status_code
        200
    """
    
    issues_list = issue_list()
    return templates.TemplateResponse(
        "issue_chat.html",
        {"request": request, "issues": issues_list}
    )


@app.get("/api/issues/{issue_id}")
async def get_issue(issue_id: str):
    import json
    """
    Get details for a specific issue.

    Args:
        issue_id (str): The ID of the issue to retrieve.

    Returns:
        dict: The issue details.

    Example:
        >>> from fastapi.testclient import TestClient
        >>> client = TestClient(app)
        >>> response = client.get("/api/issues/ISSUE-1")
        >>> response.status_code
        200
        >>> response.json()["id"]
        'ISSUE-1'
    """
    try:
        cached_issues = issue_manager.get_cached_documents([issue_id])
        if cached_issues:
            found_issue_raw = cached_issues[0]
            found_issue_metadata = found_issue_raw["metadata"]
        else:
            found_issues = issue_manager.source.get_documents([issue_id])
            found_issue_raw = dict(found_issues[0]) if found_issues else {}
            found_issue_metadata = found_issue_raw["metadata"]

        if "text" in found_issue_raw:
            # if this is direct loaded from file by SimpleDirectoryReader .etc
            found_issue = json.loads(found_issue_raw.get("text"))
        else:
            # if this is created by Document(...)
            found_issue = json.loads(found_issue_raw.get("text_resource"))
    
        if found_issue:
            issue = {}
            issue["id"] = issue_id
            issue["title"] = found_issue_metadata.get(f"{issue_manager.namespace}title", "no title")
            issue["created"] = found_issue_metadata.get(f"{issue_manager.namespace}created_at", "unknown")
            issue["updated"] = found_issue_metadata.get(f"{issue_manager.namespace}updated_at", "unknown")
            issue["status"] = found_issue_metadata.get(f"{issue_manager.namespace}status", "unknown")
            
            # Get the description or text content
            description = found_issue.get("description") or found_issue.get("text", 'n/a')
            # If the description is a string that looks like JSON, try to parse it
            if isinstance(description, str):
                try:
                    # Try to parse as JSON
                    import json
                    json_data = json.loads(description)
                    issue["description"] = json_data
                except json.JSONDecodeError:
                    # If not valid JSON, keep as string
                    issue["description"] = description
            else:
                issue["description"] = description

            # Get the comment
            comments = found_issue.get("comment") or found_issue.get("comments", 'n/a')
            # If the comment is a string that looks like JSON, try to parse it
            if isinstance(comments, str):
                try:
                    # Try to parse as JSON
                    import json
                    json_data = json.loads(comments)
                    issue["comments"] = json_data
                except json.JSONDecodeError:
                    # If not valid JSON, keep as string
                    issue["comments"] = comments
            else:
                issue["comments"] = comments

            # Get the changelog
            changelog = found_issue.get("changelog") or found_issue.get("updates", 'n/a')
            # If the changelog is a string that looks like JSON, try to parse it
            if isinstance(changelog, str):
                try:
                    # Try to parse as JSON
                    import json
                    json_data = json.loads(changelog)
                    issue["changelog"] = json_data
                except json.JSONDecodeError:
                    # If not valid JSON, keep as string
                    issue["changelog"] = changelog
            else:
                issue["changelog"] = changelog

            # everything other than [description], [comments], [changelog]
            # goes to attributes
            # everything other than [description], [comments], [changelog]
            # goes to attributes
            issue["attributes"] = {}
            for key, value in found_issue.items():
                if key not in ["description", "comments", "changelog"]:
                    issue["attributes"][key] = value            

            return issue
    except Exception as e:
        logger.warning("Error retrieving document %s from the source, due to %s", issue_id, e, exc_info=e)
        return {"error": "Issue not found"}, 404


@app.post("/api/chat")
async def chat(message: ChatMessage):
    """
    Process a chat message and return an AI response.

    Args:
        message (ChatMessage): The chat message and associated issue ID.

    Returns:
        dict: The AI response.

    Example:
        >>> from fastapi.testclient import TestClient
        >>> client = TestClient(app)
        >>> response = client.post("/api/chat", json={"message": "What's the status?", "issue_id": "ISSUE-1"})
        >>> response.status_code
        200
        >>> "response" in response.json()
        True
    """
    # In a real implementation, you would use the IssueManager to query the issue
    # and generate a response based on the message and issue context

    try:
        # Get the issue details

        # Use the IssueManager to query for a response
        # This is a simplified example - in a real implementation, you would
        # use the issue details and the message to generate a more contextual response
        query = f"Regarding issue {message.issue_id}: {message.message}"

        # Try to use the issue_manager to get a response
        try:
            response = issue_manager.query(query)
            ai_response = str(response.response)
        except Exception as e:
            # Fallback to a simple response if the query fails
            ai_response = (f"I run into error querying issue manager: {e}")

            # Generate a simple response based on the issue details
            # if "status" in message.message.lower():
            #     ai_response = f"The current status of this issue is: {issue['status']}"
            # elif "description" in message.message.lower() or "about" in message.message.lower():
            #     ai_response = f"This issue is about: {issue['description']}"
            # elif "comment" in message.message.lower():
            #     ai_response = f"There are {len(issue['comments'])} comments on this issue."
            # else:
            #     ai_response = f"I'm analyzing issue {issue['id']}: {issue['title']}. It's currently {issue['status']} and was created on {issue['created']}. How can I help you with this issue?"

        return {"response": ai_response}

    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        return {"response": "I'm sorry, I encountered an error while processing your request."}


@app.get("/api/issues")
async def list_issues():
    """
    List all available issues.

    Returns:
        list: A list of issues with basic information.

    Example:
        >>> from fastapi.testclient import TestClient
        >>> client = TestClient(app)
        >>> response = client.get("/api/issues")
        >>> response.status_code
        200
        >>> isinstance(response.json(), list)
        True
    """
    # In a real implementation, you would fetch issues from the IssueManager
    # For now, we'll use sample data
    issues_list = issue_list()
    return issues_list


def main():
    print("Starting Issue Management Assistant server...")
    print("Access the web interface at http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    if "--test" in sys.argv:
        print("Running doctests...")
        import doctest
        doctest.testmod()
    else:
        pass
        # main()
