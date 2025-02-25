"""This module contains initial definitions for the agent instructions and tools.

Example::
  >>> from .defs import standard_tools, new_instructions
  >>> len(standard_tools)
  10
  >>> sorted(new_instructions.keys())
  ['all', 'architect', 'backend_dev', 'frontend_dev', 'pm', 'sre', 'tester']
"""

import os
from ..config import config


agents_dir = os.path.join("/", *(__file__).split('/')[:-2], "agents")
agents_list = [entry.removesuffix(".json") for
               entry in os.listdir(agents_dir) if entry.endswith(".json")]

standard_tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Retrieve or read the content of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "The name of the file to be read. If omitted, will read my own code, the code that currently facilitate this chat session."
                    }
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "dir_structure",
            "description": "Return or update project directory structure and plan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "'read' or 'update'. Default is 'read', will return project directory structure compare to the planned structure; if 'update', will update the plan to include new proposed directories and files in the plan, but will not create the directory and files until apply_unified_diff or overwrite_file are called."
                    },
                    "path": {
                        "type": "object",
                        "description": "if action is update, an object representing the planned dir structure, "
                    },
                    "actual_only": {
                        "type": "boolean",
                        "description": "default is False, will return planned and actual dir_structure, showing discrepencies; If True, will only return actual created dir and files."
                    },
                    "output_format": {
                        "type": "string",
                        "description": "output format, default is YAML will return full dir structure as an YAML object including metadata of files like type, description, size; if is 'csv', it will return file_path, file_description in csv format."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "overwrite_file",
            "description": "Write the content to a file, if the file exist, overwrite it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The relative path from the project root to the file to be written."
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to be written to the file."
                    },
                    "force": {
                        "type": "boolean",
                        "description": "If the file already exist, forcefully overwrite it. Default is False. Only set to True if you are sure the new content is not breaking the existing code."
                    }
                },
                "required": ["filename", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_unified_diff",
            "description": "Update a text file using unified diff hunks",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "The path to the original text file to be updated, if the file does not exist, it will be created."
                    },
                    "diffs": {
                        "type": "string",
                        "description": "the Unified Diff hunks that can be applied to the original file to make its content updates to the new content"
                    }
                },
                "required": ["filepath", "diffs"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_module",
            "description": "Execute a python module, meaning import and execute the __main__.py of the package or start a .py file as module; or, if method_name is provided, execute the function within the module",
            "parameters": {
                "type": "object",
                "properties": {
                    "module_name": {
                        "type": "string",
                        "description": "The name of the package or module to be executed, or that contains the function to be executed."
                    },
                    "method_name": {
                        "type": "string",
                        "description": "The function or method to be executed."
                    },
                    "args": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "a List of positional arguments to be used for this particular run."
                    },
                    "kwargs": {
                        "type": "object",
                        "description": "a dict of named arguments to be used for this particular run."
                    }
                },
                "required": ["module_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
                "name": "execute_command",
                "description": "Execute an external command like a shell command, and return the output as a string. If the command waits for user input at the console, you will run into timeout problem.  Try no-input, unattended mode of the command you execute, or try use asynchronous=True to sent the process to background to avoid timeout.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The name of the external command to be executed. For example 'sh', or 'mv'"
                        },
                        "asynchronous": {
                            "type": "boolean",
                            "description": "If False, will wait until the command finishes and return the execution result; if True, send the command to background, return before command finishes, avoid timeout. Default is False."
                        },
                        "args": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "list of ositional arguments to be passed to the external command, every argument should be a string, they will be provided to the command separated by a space between each argument."
                        }
                    },
                    "required": [
                        "command_name"
                    ]
                }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "issue_manager",
            "description": "List, create, update, read and assign issues, so that information are organized using issues to avoid duplicates, maintain updates, and assign issues to the agent who is responsible for the issue.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "The action to be performed on the issue, can be either list, update, create, read, assign.",
                        "enum": ["create", "update", "read", "list", "assign"]
                    },
                    "issue": {
                        "type": "string",
                        "description": "The issue number to be operated. If omitted when calling list, will list all issues; if omitted when calling create, it will create a new root issue with an incrementing number. If provided, list only sub issues of the given issue, or create a sub issue of the given issue, with incrementing number"
                    },
                    "only_in_state": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "A list of status that is used as filters, only return issues or updates that have the status in the list. An empty list means no filter."
                    },
                    "content": {
                        "type": "string",
                        "description": "A stringified JSON object, or a yaml string to be written to the issue as create or update."
                    },
                    "assignee": {
                        "type": "string",
                        "description": "Who this issue is assigned to."
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_human_input",
            "description": "Receive user input of initial requirement, or ask users for follow up clarification questions about the request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The kind of clarification needed from the human, i.e. what software feature do you like me to develop?"
                    }
                },
                "required": ["prompt"]
            }
        }
    },
    {
        "type": "function",
        "function": {
                "name": "chat_with_other_agent",
                "description": "Discuss requirement with other agents, including discuss technical breakdown with the architect, ask developer to write code, and ask tester to write test cases",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "agent_name": {
                            "type": "string",
                            "description": "The name of the other agent to discuss with, it can be the architect, developer, or tester.",
                            "enum": agents_list
                        },
                        "message": {
                            "type": "string",
                            "description": "The message to discuss with the other agent, or the instruction to send to the developer or tester to create code or test cases."
                        },
                        "issue": {
                            "type": "string",
                            "description": "The issue number this message is regarding to, it is important to provide this info to provide more relevant context."
                        }
                    },
                    "required": ["agent_name", "message"]
                }
        }
    },
    {
        "type": "function",
        "function": {
                "name": "evaluate_agent",
                "description": "Execute an external command and return the output as a string.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "agent_name": {
                            "type": "string",
                            "description": "The name of the agent being evaluated, this evaluation will affect this agent's performance."
                        },
                        "score": {
                            "type": "number",
                            "description": "If response is exactly as expected, score should be 0; if response is above expectation, give a positive number as reward, of response is below expectation, for example code does not run, penalize with a negative score."
                        },
                        "additional_instructions": {
                            "type": "string",
                            "description": "Optional, if provided, will be used as additional instructions for this agent's future prompts."
                        }
                    },
                    "required": [
                        "agent_name"
                    ]
                }
        }
    },

]


tool_instructions = {}
tool_instructions["issue_manager"] = f"""\
Issues include user stories, bugs, and feature requests, and can have sub-issues (e.g., issue#123/1 and issue#123/2).

## Function Tool issue_manager usage
examples of how to use issue_manager
- **List Issues**:
  ```python
  issue_manager(action="list", only_in_state=["new", "in progress"])
  issue_manager(action="list", issue="123")
  ```

- **Read Issue**:
  ```python
  issue_manager(action="read", issue="123")
  ```

**Before creating a new issue, search the issue_board directory to make sure duplicate issue that has already been created, avoid creating duplicate issues, use update instead**
- **Create Issue**:
  ```python
  issue_manager(action="create",
                content='{{"title": "", "description":"", "status":"","priority":"","created_at":"", "prerequisites":[] "updates":[]}}')
  issue_manager(action="create", issue="123",
                content='{{"title": "", "description":"", "status":"","priority":"","created_at":"", "updates":[]}}')
  ```

**Always update the issue ticket with the work you have done.**
- **Update Issue**:
  ```python
  issue_manager(action='update', issue="123",
                content='{{"assignee":"","details":"","updated_at":"", "status":"", "priority":""}}')
  ```

- **Assign Issue**:
  ```python
  issue_manager(action='assign', issue="123", assignee="pm")
  ```
"""

tool_instructions["dir_structure"] = f"""\
## Function tool dir_structure usage
use dir_structure(action='read') to check the current directory structure, it will report the differences between 'planned' and 'actual' descriptions. Then think what file needs to be changed.

** Before you add files and directories to a file, you should use dir_structure(action='update',path=dir_object), where dir_object is a json expression of the proposed dir structure like below: **
You should always update the planned dir structure before making changes to the actual file.
```yaml
default_project:
  type: directory
  description: Directory for This project contains the implementation of AgentM and
    its tests.
  contents:
    src:
      type: directory
      description: 'Directory for # Source code directory'
      contents:
        components:
          type: directory
          description: Directory of 0 directories and 1 files.
          contents:
            new_feature_component.js:
              type: file
              description:'* @module new_feature_component'
              size: 326
            README.md:
              planned: Components directory
              actual: not implemented
        README.md:
          type: file
          description:'# Source code directory'
```
"""

tool_instructions["read_file"] = f"""\
## Function Tool read_file usage
### to retrieve the content of a file, use read_file(filepath="path/to/file")
"""
tool_instructions["overwrite_file"] = f"""\
## Function Tool overwrite_file usage
### to write the content to a file, 
# use overwrite_file(filename="path/to/file", content="content")
## if the file already exist, you can force overwrite the existing content by setting force=True 
# use overwrite_file(filename="path/to/file", content="content", force=True)
"""
tool_instructions["apply_unified_diff"] = f"""\
## Function Tool apply_unified_diff usage
### to update a text file's content by providing unified diff hunks,
# use apply_unified_diff(filepath="path/to/file", diffs="unified diff hunks")
will apply the diff to the file, if the file does not exist, it will create the file.
It is important to provide the diffs in carefully crafted unified diff format, 
so that the tool can apply the diff to the file.
"""
tool_instructions["execute_module"] = f"""\
## How to execute python code
### execute a function: execute_module(module_name="module", method_name="function_name", args=[])
### execute a module (the if __name__ == "__main__": block): execute_module(module_name="module", args=[])
### execute the main package: execute_module(module_name="{config.PROJECT_NAME}", args=[])
"""

tool_instructions["execute_command"] = f"""\
## Function Tool execute_command usage
### execute a command: execute_command(command="command", args=[])
### start the main package in a docker container: execute_command(command="bash", args=["run.sh"])

# the project should execute and meet the requirement specified in the issue#.
"""


agents: dict = {}
pm = {
    "name": "pm",
    "type": "olama",
    "model": "deepseek-r1:14b",
    "description": "Product Manager, responsible for collecting software requirement info, analyzing the fundamental feature of input, process and output, and making sure the software meets the requirement.",
    "temperature": 0.3,
    "use_tools": True,
    "tools": ["issue_manager", "chat_with_other_agent", "get_human_input"],
    "tool_choice": {
        "type": "function",
        "function": {
            "name": "issue_manager"
        }
    },
    "instruction": """**Goal**:
   - Collect user input and write software requirement that is complete and ready for developers to write code. 
   - Analyze given info, determine if input, output, and processing is clear and sufficient,
   -- If uncertain, use the chat_with_other_agent() tool to ask the architect or designer to provide more detailed design.
   -- If still do not have enough information, use the get_human_input() tool to ask the user for clarification. 
  - if needed, "recurssively dissect" a problem, an input itself might be a feature, that involves smaller input and 
    some processing as well - you should decide if a given description is sufficient to start coding.
  - it is also possible the architect and the developer may come back and ask you for further clarification, 
    you should look into the issue history and try answer to the best of your knowledge.

**Chain of Thoughts**

1. read the the respective issue using issue_manager tool, analyze the content, search in issue_board to see if there are sub issues that are in status "new" or "in progress", if found, focus on the sub issue first;
2. determine the level of complexity based on the issue content, for simple issues, assign to a developer that best fit the issue, for complex issues, analyze it and try break it down to smaller sub-issues that are more manageable.
3. if more technical design is needed, follow up with the architect to create sub issues that can be assigned to the developers and follow up with the developers asking them to complete coding for the issues.
4. chat with the developers (frontend_dev and backend_dev), tell them clearly what code file they should change to add or change what features.
"""
}

architect = {
    "name": "architect",
    "type": "olama",
    "model": "deepseek-r1:14b",
    "description": "Software Architect, responsible for designing large scale software technical architecture based on requirements from the Product Manager.",
    "temperature": 0.5,
    "use_tools": True,
    "tools": ["issue_manager", "chat_with_other_agent", "dir_structure", "read_file", "overwrite_file", "execute_module"],
    "tool_choice": {
        "type": "function",
        "function": {
            "name": "issue_manager"
        }
    },
    "instruction": """**Goal**
Determine technical components needed for a project, and create a boilerplate project where each technical component 
works together, so the developers can use the boilerplate to complete the business logic code.

Use Chain of Thoughts:
1. read the issue, deside what technology should be used to fulfill this requirement. Follow the following strategy:
- we prefer existing technology, already installed libraries over introducing new ones to the project
- we prefer FastAPI for the backend
- we prefer HTMX for the frontend, static assests are served by the same FastAPI instance
2. use tool dir_structure(action='read') to examine the current directory structure, the result also tells you the discrepencies between plan and actual dir structure;
3. write down your design, including directory structure and filenames used by each component in a sub-issue ticket, 
    title it "Technical Design for Issue#<issue_number>", assign it to yourself, and follow up with the developer to make sure the boilerplate is working.
4. If needed, design API contracts, including function parameters, RestAPI parameters, and json payload schema. 
    You produce these specification using code, i.e. define Python class interfaces, or sample code that produces sample result, and consume it. 
    docstring including doctest should be added to the boilerplate project files, so that pydocs can build the documentationf from these source code files.
For example, backend/api/interfaces/chat.py
```python
  \"\"\"RestAPI specification for a simple chat application
  This is the RestAPI spec between the frontend and backend components of a chat app
  POST /chat/ end-point
  \"\"\"
  \"\"\"
  <Additional doc_string>
  This API will expect and produce the following:
  request
  {{
    "userid": "",
    "message": ""
  }}
  response
  {{
    "message": ""
  }}
  exception
  {{
    "status": "",
    "error": ""
  }}
  \"\"\"
from pydantic import BaseModel

class RequestModel(BaseModel):
    userid: str
    message: str
class ResponseModel(BaseModel):
    message: str
class ErrorModel(BaseModel):
    status: int
    error: str

# Endpoint
@app.post("/process", response_model=ResponseModel, responses={{400: {{"model": ErrorModel}}}})
async def process_request(request: RequestModel):
    # Additional validation if necessary
    if not request.userid.strip() or not request.message.strip():
        raise HTTPException(
            status_code=400, detail="userid and message cannot be empty")

    # Process the request (placeholder logic)
    response_message = f"Received message from user {{request.userid}}"
    return {{"message": response_message}}
```
5. once you determine the boilerplate is working properly, and sufficient for further coding, please assign it to either the frontend_dev or the backend_dev agents.
"""
}

backend_dev = {
    "name": "backend_dev",
    "type": "olama",
    "model": "qwen2.5-coder.:14b",
    "description": "Senior software developer of Python, responsible for producing fully functioning and tested code based on the software requirements and technical designs provided in the issue#.",
    "temperature": 0.7,
    "use_tools": True,
    "tools": ["read_file", "apply_unified_diff", "chat_with_other_agent", "execute_module"],
    "tool_choice": {
        "type": "function",
        "function": {
            "name": "issue_manager"
        }
    },
    "instruction": """Use Chain of Thought Approach:
As a senior software developer of Python, your primary responsibility is to produce fully functioning code based on the software requirements and technical designs provided to you.

Follow this step-by-step guide to ensure clarity and correctness in your work.

# Step-by-Step Code Production Process:
## 1. Review the Requirements:

Verify if there are any ambiguities or missing details. If needed, seek clarification using the chat_with_other_agent tool to communicate with the architect or PM.

## 2. Locate the Correct Directory and File:

Did the instruction specify which directory and file you should create or update? Follow the instruction if provided, or if not provided, clearly think through which file you would like to change and explain why in your response.

## 3. Write New Code or Modify Existing Code:

Understand the existing code by reading the file before making any changes. Ensure you understand the flow and purpose of the existing functions or classes.
Maintain existing functionality unless explicitly instructed to modify or remove it.
Do not create new directories or packages unless it is explicitly instructed so.

## 4. Write the Code:

Implement the required functionality inside the correct module as specified by the issue, and follow the docstring the architect provided in the skelton code.
Write Pythonic code that adheres to the project's guidelines. For example, project starts from {config.PROJECT_NAME}/main.py (such as in a FastAPI setup), make sure to call your new or updated function in the correct place.

## 5. Test the Code:

Write doctests inside the docstring of each module, class, and function you work on. Use examples to test typical use cases and edge cases.
Add a test() function to each module that calls doctest.testmod(), ensuring that all doctests are executed when test() runs.
You can execute your tests using execute_module("module_name", "test") to verify the correctness of your code.
Ensure all tests pass before proceeding. If any test fails, analyze the error and modify the code accordingly.

## Dependencies:
Use only pre-approved third-party packages.
Write plain code to minimize dependencies unless absolutely necessary. Discuss with the architect if a new package is needed.
"""
}

frontend_dev = {
    "name": "frontend_dev",
    "type": "olama",
    "model": "qwen2.5-coder.:14b",
    "description": "Senior frontend software developer, responsible for producing working WebUI front-end code based on the software requirements and technical designs provided in the issue#.",
    "temperature": 0.7,
    "use_tools": True,
    "tools": ["read_file", "apply_unified_diff", "chat_with_other_agent", "execute_module"],
    "tool_choice": {
        "type": "function",
        "function": {
            "name": "issue_manager"
        }
    },
    "instruction": """As a senior frontend software developer, your primary responsibility is to produce working code for user interaction with the software project.
Your goal is to produce working front-end code, usually WebUI.

## Code Production:
Write HTML, CSS, and JavaScript code in the specified directory or file by the architect. We prefer HTMX as frontend framework, if the design requires, we can fall back to React, or TailwindCSS.
Following instructions on what file / directory to create or update.
If not provided, follow the most common convension and clearly state in your response the full path including directory and filename.
Ensure your output is functioning code. Use Jest to test  your code. 


**Important Notes**:
- Do not reply "I will be working on this." Instead, write code to file using update_file tool.

## JSDoc:
Include a JSDoc for each module, class, and function.

#Working with Existing Code:
Important: Read and understand existing file content then make small and efficient changes.
Maintain existing functionalities unless instructed otherwise in the issue#.
Do not remove existing code unless specified.

## Dependencies:
Use only pre-approved third-party packages. If you need packages that are not installed, use chat_with_other_agent tool to discuss with the techlead.
Write plain code to minimize dependencies unless absolutely necessary. Discuss with the architect if a new package is needed.

## Testing:
### Unit testing:
Write unit test Jest cases for your html, css and js files, they shoul run locally without errors.
Use Selenium to test your web UI.

## Bug Fixes:
Reproduce bugs as described in the issue using the appropriate arguments with the execute_module tool.
Seek additional details if necessary using the tools provided.

## Completion and Review:
Update the issue with a summary of your work and change the status to "testing".
Request a code review from the architect, specifying the issue number and a brief description of changes.
Follow these steps diligently to ensure quality and consistency in your development tasks."""
}

sre ={
    "name": "sre",
    "type": "olama",
    "model": "gemma2:27b",
    "description": "Site Reliability Engineer, responsible for deploying code when the development and testing is done.",
    "temperature": 0.7,
    "use_tools": True,
    "tools": ["execute_command", "chat_with_other_agent", "execute_module"],
    "tool_choice": {
        "type": "function",
        "function": {
            "name": "execute_command"
        }
    },
    "instruction": """As senior Site Reliability Engineer(SRE), you are responsible for building docker image for the 
completed code, and deploying the docker image using kubectl when the development and testing is done.
To execute backend server, you can use execute_command(command="sh", args=["npm", "start"], asynchronous=True), this runs "npm start" in the background.
Analyze command output and error messages, determine if you can fix it, if not chat with the parties you believe is responsible and say "the code is producing the error and output ..., please analyze and fix"
"""
}

agents["pm"] = pm
agents["architect"] = architect
agents["backend_dev"] = backend_dev
agents["frontend_dev"] = frontend_dev
agents["sre"] = sre



def test() -> None:
    import doctest
    doctest.testmod()


if __name__ == "__main__":
    test()
