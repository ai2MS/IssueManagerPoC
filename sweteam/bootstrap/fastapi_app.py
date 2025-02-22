from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn
import sys

app = FastAPI()


class UserInput(BaseModel):
    input_text: str


@app.get("/", response_class=HTMLResponse)
async def get_input_page():
    """
    Serve the input page.

    Returns:
        HTMLResponse: The HTML content of the input page.

    Example:
        >>> from fastapi.testclient import TestClient
        >>> client = TestClient(app)
        >>> response = client.get("/")
        >>> response.status_code
        200
        >>> "Enter your input:" in response.text
        True
    """
    html_content = """
    <html>
        <head>
            <title>Agent Input</title>
        </head>
        <body>
            <h1>Agent Input</h1>
            <form action="/submit" method="post">
                <label for="input_text">Enter your input:</label>
                <input type="text" id="input_text" name="input_text" required>
                <button type="submit">Submit</button>
            </form>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.post("/submit")
async def submit_input(input_text: str = Form(...)):
    """
    Process the submitted input.

    Args:
        input_text (str): The input text submitted by the user.

    Returns:
        dict: A dictionary containing a message and the input text.

    Example:
        >>> from fastapi.testclient import TestClient
        >>> client = TestClient(app)
        >>> response = client.post("/submit", data={"input_text": "test input"})
        >>> response.status_code
        200
        >>> response.json()
        {'message': 'Input received', 'input_text': 'test input'}
    """
    # Here, you can process the input_text as needed
    return {"message": "Input received", "input_text": input_text}

if __name__ == "__main__":
    if "--test" in sys.argv:
        print("Running doctests...")
        import doctest
        doctest.testmod()
    else:
        uvicorn.run(app, host="0.0.0.0", port=8000)

