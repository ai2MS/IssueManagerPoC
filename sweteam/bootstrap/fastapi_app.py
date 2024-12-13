from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

app = FastAPI()


class UserInput(BaseModel):
    input_text: str


@app.get("/", response_class=HTMLResponse)
async def get_input_page():
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
    # Here, you can process the input_text as needed
    return {"message": "Input received", "input_text": input_text}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
