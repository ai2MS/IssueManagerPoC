from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
import sys
import os
import json
from typing import List, Optional, Dict, Any
from datetime import datetime

from sweteam.bootstrap.utils.log import get_default_logger
from .utils.issue_management import IssueManager
from .config import config

class ChatMessage(BaseModel):
    message: str
    issue_id: str


class UserInput(BaseModel):
    input_text: str


class IssueManagementApp:
    def __init__(self):
        self.logger = get_default_logger(self.__class__.__name__)
        self.app = FastAPI()
        self._setup_routes()
        self._setup_static_files()
        self._setup_templates()
        self._setup_issue_manager()

    def _setup_static_files(self):
        """Set up static files directory"""
        self.app.mount("/static", StaticFiles(directory="sweteam/bootstrap/static"), name="static")

    def _setup_templates(self):
        """Set up Jinja2 templates"""
        self.templates = Jinja2Templates(directory="sweteam/bootstrap/templates")

    def _setup_issue_manager(self):
        """Initialize the IssueManager"""
        self.issue_manager = IssueManager()

    def _setup_routes(self):
        """Set up all routes for the application"""
        self.app.get("/")(self.get_issue_chat_page)
        self.app.get("/api/issues/{issue_id}")(self.get_issue)
        self.app.post("/api/chat")(self.chat)
        self.app.get("/api/issues")(self.list_issues)

    def get_issue_list(self) -> list:
        """Get list of all issues with basic information"""
        issues = self.issue_manager.get_cached_doc_metadata() or self.issue_manager.source.get_all_metadata()
        issues_list = []
        for k, v in issues.items():
            issues_list.append({
                'id': v.get(f"{self.issue_manager.namespace}id", k),
                'title': (v.get('title') or v.get(f'{self.issue_manager.namespace}title'))[:80]
            })
        return issues_list

    async def get_issue_chat_page(self, request: Request) -> HTMLResponse:
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
        issues_list = self.get_issue_list()
        return self.templates.TemplateResponse(
            "issue_chat.html",
            {"request": request, "issues": issues_list}
        )


    async def get_issue(self, issue_id: str) -> Dict[str, Any]:
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
            cached_issues = self.issue_manager.get_cached_documents([issue_id])
            if cached_issues:
                found_issue_raw = cached_issues[0]
                found_issue_metadata = found_issue_raw["metadata"]
            else:
                found_issues = self.issue_manager.source.get_documents([issue_id])
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
                issue["title"] = found_issue_metadata.get(f"{self.issue_manager.namespace}title", "no title")
                issue["created"] = found_issue_metadata.get(f"{self.issue_manager.namespace}created_at", "unknown")
                issue["updated"] = found_issue_metadata.get(f"{self.issue_manager.namespace}updated_at", "unknown")
                issue["status"] = found_issue_metadata.get(f"{self.issue_manager.namespace}status", "unknown")
                
                # Process description
                description = found_issue.get("description") or found_issue.get("text", 'n/a')
                issue["description"] = self._parse_json_string(description)

                # Process comments
                comments = found_issue.get("comment") or found_issue.get("comments", 'n/a')
                issue["comments"] = self._parse_json_string(comments)

                # Process changelog
                changelog = found_issue.get("changelog") or found_issue.get("updates", 'n/a')
                issue["changelog"] = self._parse_json_string(changelog)

                # Process additional attributes
                issue["attributes"] = {}
                for key, value in found_issue.items():
                    if key not in ["description", "comments", "changelog"]:
                        issue["attributes"][key] = value            

                return issue
        except Exception as e:
            self.logger.warning("Error retrieving document %s from the source, due to %s", issue_id, e, exc_info=e)
            return {"error": "Issue not found"}, 404

    def _parse_json_string(self, data: Any) -> Any:
        """Helper method to parse JSON strings"""
        if isinstance(data, str):
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return data
        return data


    async def chat(self, message: ChatMessage) -> Dict[str, str]:
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
        try:
            query = f"Regarding issue {message.issue_id}: {message.message}"

            try:
                response = self.issue_manager.aquery(query)
                ai_response = str(response.response)
            except Exception as e:
                ai_response = f"I run into error querying issue manager: {e}"

            return {"response": ai_response}

        except Exception as e:
            self.logger.error(f"Error in chat endpoint: {e}")
            return {"response": "I'm sorry, I encountered an error while processing your request."}


    async def list_issues(self) -> list:
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
        return self.get_issue_list()

    def run(self):
        """Start the FastAPI application server"""
        print("Starting Issue Management Assistant server...")
        print("Access the web interface at http://localhost:8000")
        uvicorn.run(self.app, host="0.0.0.0", port=8000)


def main():
    app = IssueManagementApp()
    app.run()


if __name__ == "__main__":
    if "--test" in sys.argv:
        print("Running doctests...")
        import doctest
        doctest.testmod()
    else:
        main()
