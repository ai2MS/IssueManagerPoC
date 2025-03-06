# Issue Management Assistant

This application provides a split-screen interface for viewing and interacting with issue management tickets (like Jira or GitHub issues). The left panel displays the issue details, while the right panel provides a chat interface to interact with an AI assistant about the issue.

## Features

- View issue details including title, description, status, and comments
- Select different issues from a dropdown menu
- Chat with an AI assistant about the selected issue
- Responsive design that works on both desktop and mobile devices

## Running the Application

To run the application, execute the following command from the project root:

```bash
python -m sweteam.bootstrap.fastapi_app
```

Then open your browser and navigate to:

```
http://localhost:8000
```

## How It Works

1. The application uses FastAPI to serve the web interface and API endpoints
2. The IssueManager class from `issue_management.py` is used to query and retrieve issue information
3. The frontend is built with HTML, CSS, and JavaScript, with a responsive split-screen layout
4. The chat functionality uses AJAX to communicate with the backend without page reloads

## API Endpoints

- `GET /`: Serves the main split-screen interface
- `GET /api/issues`: Lists all available issues
- `GET /api/issues/{issue_id}`: Gets details for a specific issue
- `POST /api/chat`: Processes a chat message and returns an AI response

## Customization

To use with your actual issue data instead of the sample data:

1. Modify the `get_issue`, `list_issues`, and `chat` endpoints in `fastapi_app.py` to use your actual issue data source
2. Update the IssueManager integration to properly query your issues

## Requirements

- Python 3.9+
- FastAPI
- Uvicorn
- Jinja2
- The dependencies required by the IssueManager class