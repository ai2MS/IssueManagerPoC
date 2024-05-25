"""
This module contains utility functions for working with files.

Usage:
    python -m utils [update_agent]
"""

import os
agents_dir = os.path.dirname(__file__) + "/agents"
agents_list = [entry.removesuffix(".json") for entry in os.listdir(agents_dir) if entry.endswith(".json")]
project_name = ''

def local_issue_manager(action: str, issue: str = '', only_in_state: list = [], content: str = None):
    from .agent import OpenAI_Agent
    import json
    cur_dir = os.getcwd()
    my_parent_dir = os.path.dirname(os.path.dirname(__file__))
    os.chdir(my_parent_dir)
    temp_agent = OpenAI_Agent("pm")
    issue_manager_return = temp_agent.issue_manager(action, issue, only_in_state, content)
    os.chdir(cur_dir)
    return json.loads(issue_manager_return)

def initialize_package(package_dir: str = None) -> str:
    """Initialize the __init__.py and __manin__.py files of a package.

    Args:
      package_dir: the path to the package, default is the namesake of the project

    Returns:
      the status of the package initializatio
    """
    if package_dir is None:
        # the default package dir is a namesake of the project under the project_dir
        package_dir = os.path.join(os.getcwd(), os.path.basename(os.getcwd))
    base_main = '''\
"""Base package.

Example::
    >>> print("Hello World!")
    Hello World!
"""
def test() -> str:
    import doctest
    doctest.testmod()

if __name__ == "__main__":
    test()
'''
    try:
        main_file_path = os.path.join(package_dir, "__main__.py")
        with open(main_file_path, "w") as mf:
            mf.write(base_main)
    except Exception as e:
        return f"<Init package> received Error: {e}"
    else:
        return f"<Init package> successful."

def initialize_Dockerfile(project_name: str = None, dockerfile_path: str = None) -> str:
    """Initialize the Dockerfile in the given directory
    """
    base_Dockerfile = f"""\
# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install Poetry
RUN pip install poetry

# Copy pyproject.toml and poetry.lock files to the container
COPY pyproject.toml poetry.lock ./

# Install the project dependencies
RUN poetry install --no-root

# Copy the rest of the application code to the container
COPY . .

# Specify the command to run your application
CMD ["poetry", "run", "python", "-m", "{project_name}"]
"""
    if project_name is None:
        project_name = os.path.basename((os.getcwd()))
    if dockerfile_path is None:
        dockerfile_path = os.path.join(os.getcwd(), "Dockerfile")
    base_Dockerfile.replace("{project_name}", project_name)
    if os.path.exists(dockerfile_path):
        result = (f"<init Dockerfile> {dockerfile_path} already exist, will not overwrite it, exiting...\n")
    else:
        try:
            with open(dockerfile_path, "w") as df:
                df.write(base_Dockerfile)
        except Exception as e:
            result = f"<init Dockerfile> got an Error: {e}\n"
        else:
            result = f"<init Dockerfile> {dockerfile_path} for {project_name} has been successfully initialized.\n"
    base_docker_compose = f"""\

services:
  {project_name}:
    build: .
    command: poetry run python -m {project_name}
    ports:
      - "${{SERVER_PORT:-8080}}:8080"
    restart: always
"""
    docker_compose_path = os.path.join(os.path.dirname((dockerfile_path)), "docker-compose.yaml")
    if os.path.exists(docker_compose_path):
        result += (f"<init Dockerfile> {docker_compose_path} already exist, will not overwrite it, exiting...")
    else:
        try:
            with open(docker_compose_path, "w") as df:
                df.write(base_docker_compose)
        except Exception as e:
            result += f"<init Dockerfile> got an Error: {e}"
        else:
            result += f"<init Dockerfile> {docker_compose_path} for {project_name} has been successfully initialized."
    return result

def initialize_startup_script(project_dir: str = None) -> str:
    """Initialize the startup shell script
    """
    if project_dir is None:
        project_dir = os.getcwd()
    project_name = os.path.basename(project_dir)
    script_path = os.path.join(project_dir, "run.sh")
    base_script = f"""\
#!/bin/bash

# Function to display usage
usage() {{
    echo "Usage: $0 [-t test_name] [-k]"
    exit 1
}}

# Parse command line options
while getopts ":t:k" opt; do
  case $opt in
    t )
      test_name=$OPTARG
      ;;
    k )
      kill_docker=true
      ;;
    \? )
      usage
      ;;
  esac
done

# Check if both -t and -k are provided
if [[ ! -z "$test_name" && ! -z "$kill_docker" ]]; then
    echo "Error: -t and -k options cannot be used together."
    usage
fi

# Execute the appropriate command based on the options
if [ ! -z "$test_name" ]; then
    echo "(re)starting docker compose"
    docker-compose up -d
    echo "Running python -m $test_name"
    python -m "$test_name"
elif [ ! -z "$kill_docker" ]; then
    echo "Running docker-compose down"
    docker-compose down
else
    docker-compose up -d
    docker-compose logs
fi
"""
    if os.path.exists(script_path):
        return (f"<init startup script> {script_path} already exist, will not overwrite it, exiting...")
    else:
        try:
            with open(script_path, "w") as df:
                df.write(base_script)
            current_permissions = os.stat(script_path).st_mode
            os.chmod(script_path, current_permissions | 0o111)
        except Exception as e:
            return f"<init startup script> got an Error: {e}"
        else:
            return f"<init startup script> {script_path} for {project_name} has been successfully initialized."
    
standard_tools = [
        {"type": "code_interpreter"},
        {"type": "file_search"},
        {
          "type": "function",
          "function": {
              "name": "read_from_file",
              "description": "Retrieve or read my own code, so that I can analyze the code behind how I was designed",
              "parameters": {
                  "type": "object",
                  "properties": {
                      "filename": {
                          "type": "string",
                          "description": "The name of the file to be read. If omitted, will read my own code, the code that currently facilitate this chat session."
                      }
                  },
                  "required": []
              }
          }
        },
        {
          "type": "function",
          "function": {
              "name": "list_dir",
              "description": "List the content of a directory recursively, including dir and files, and file attributes like size and timestamp. The output is in yaml format",
              "parameters": {
                  "type": "object",
                  "properties": {
                      "path": {
                          "type": "string",
                          "description": "The path of the dir to list; You can skip this path parameter to list the current working directory."
                      }
                  },
                  "required": []
              }
          }
        },
        {
          "type": "function",
          "function": {
            "name": "write_to_file",
            "description": "Write the content to a file",
            "parameters": {
              "type": "object",
              "properties": {
                "filename": {
                  "type": "string",
                  "description": "The name of the file to be written."
                },
                "content": {
                  "type": "string",
                  "description": "The content to be written to the file."
                }
              },
              "required": ["name","content"]
            }
          }
        },
        {
          "type": "function",
          "function": {
            "name": "execute_module",
            "description": "Execute a python module, or, if method_name is provided, execute the function within the module",
            "parameters": {
              "type": "object",
              "properties": {
                "module_name": {
                  "type": "string",
                  "description": "The name of the module that includes the function to be executed."
                },
                "method_name": {
                  "type": "string",
                  "description": "The function or method to be executed."
                },
                "args": {
                  "type": "array",
                  "items" : {
                    "type": "string"
                  },
                  "description": "Positional arguments to be used for this particular run."
                },
                "kwargs": {
                  "type": "object",
                  "description": "Keyword, aka named arguments to be used for this particular run."
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
                "description": "Execute an external command and return the output as a string.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command_name": {
                            "type": "string",
                            "description": "The name of the external command to be executed."
                        },
                        "asynchronous": {
                            "type": "boolean",
                            "description": "If True, command will be launched asynchronously and return control without waiting for it to finish, or if is False, execute the command wait until it finishes and return the execution result. Default is False."
                        },
                        "args": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "Positional arguments to be passed to the external command, every argument should be a string, they will be provided to the command separated by a space between each argument."
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
            "description": "Create, update, read and list issues.",
            "parameters": {
              "type": "object",
              "properties": {
                "action": {
                  "type": "string",
                  "description": "The action to be performed on the issue, can be either create, update, read, list.",
                  "enum": ["create", "update", "read", "list", "assign"]
                },
                "issue": {
                  "type": "string",
                  "description": "The issue number to be operated. If omitted when calling list, will list all issues; if omitted when calling create, it will create a new issue with an incrementing number. ."
                },
                "only_in_state": {
                  "type": "array",
                  "items" : {
                    "type": "string"
                  },
                  "description": "A list of status that is used as filters, only return issues or updates that have the status in the list. An empty list means no filter."
                },
                "content": {
                  "type": "string",
                  "description": "When creating or updating an issue, the content to be written as the new content of the issue and written to the issue."
                },
                "assignee": {
                  "type": "string",
                  "description": "Who should this issue be assigned to."
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
                        "feedback": {
                            "type": "string",
                            "description": "How can this agent be better and earn a reward instead of being penalized for not meeting expectation."
                        }
                    },
                    "required": [
                        "agent_name"
                    ]
                }
            }
        },

      ]


def test() -> None:
    import doctest
    doctest.testmod()


if __name__ == "__main__":
    new_instructions = {}
    new_instructions['all'] = """
Your goal is to assess current state of the {project_name} directory, compare it to that issue# description wants to accomplish, and analyze\
  what steps need to be taken to update the project to meet the issue# description. Update the issue# with your plan. 
Then implement your plan if you can by writing files needed to realize the plan step by step.
The current working directory is the project root, which has a directory structure like this:
./
  {project_name}/
  docs/
  tests/
All project packages, modules code files should be saved under {project_name} directory, documents under docs, Test cases under test directory. Do not use absolute path.
You can chat with other agents to ask for more information, clarification, or ask for their help to write code, or execute tests, you will not be penalized for chatting with other agents. 
The agents are: architect, designer, techlead, developer, tester and sre. Always include the issues at concern when you chat with other agents.
You can also assign an issue to them.
You should evaluate the response from the other agent you chat with based on their response, their updates to the issues, and the files the create or update, then call evaluate_agent tool\
  to reward a positive number if their updates or response meets expectation or penalize using a negative number if the response is below expectation. 
Issues are user stories, bugs, and feature requests. An issue can have sub issues, similar to directory structure, for example issue#123/1 and issue#123/2. 
Sub issues allow you to break down a large issue to smaller issue that can be separately completed. 
You use issue_manager tool to list, create, update, and read issues. Issues are identified by their numbers. 
For example, you can list "new" or "in progress" issues by calling the function tool issue_manager(action="list", only_in_state=["new", "in progress"])
Or issue_manager(action="list", issue="123") will list all sub issues of #123.
You can read an issue by calling the tool issue_manager(action="read", issue="123"), this will give you all the content of the issue#123 .
You can create a new issue by calling the tool issue_manager(action="create", content='{"title": "", "description":"", "status":"","priority":"","created_at":"", "prerequisites":[] "updates":[]}').
prerequisites are issue numbers that is blocking the current issue from completion, usually these are child issues of the current issues, you can also list other issues as prerequisites.
To create a sub issue, call the tool issue_manager(action="create", issue="123",content='{"title": "", "description":"", "status":"","priority":"","created_at":"", "updates":[]}'), this will create issue#123/1.
You can update an issue by calling the tool issue_manager(action='update', issue="123", content='{"assignee":"","details":"","updated_at":"", "status":"", "priority":""}').
You can also assign an issue by calling issue_manager(action='assign', issue="123", assignee="pm")
When creating an issue, you need to provide the title and description of the issue, the "created at" timestamp is automatically generated.
When you update a issue, you only need to provide details to change. Other fields would be automatically generated.
When you list issues, the latest update entry will determine the status, priority and the assignee of the issue.
An issue can only be "completed" after all code works and all test cases pass successfully. 
"""

    new_instructions["pm"] = """\
As a senior product manager, you focus on clearly describing software requirements and coordinate with other agents to\
 deliver fully functional, software.
Analyze issues in "new" status, and try to break it down to smaller issues each fulfilling an necessary subset of the main issue.
Do not create duplicate issues, or irrelevant sub issues that does not help realize the main issue.
If the other agent reply completed an issue, please try execute_command(command="bash", args="run.sh") to execute the code, and examine if the code produce expected result\
  and if the test cases pass successfully.
If no issues in the issue_board directory that is in ["new", "in progress"] status, you can ask for software requirement\
 from the user using get_human_input tool provided to you, and create new issues according to the human input.
You create issue(s) based on user input, and write structured specification. For example, if a user request is to have a WebUI table that list all\
  the students, and their exam grades, you will create a new issue with a proper title, and the description will be the specification in the format of\
      "The user will be able to see a table of all student name, student id, their graduation year, and the grades, the system will retrieve students list from the backend\
       The user will be able sort the entries by clicking on the title, the front-end will sort the entries based on the column title the user clicked\
       The user will be able to filter the entries by right click the column title and enter a string, the system will query the back-end only return\
          entries with that column contain the user entered string
      Acceptance Criteria: The user can open the web UI, see the full list of students with grades, and can sort, filter using the table header.".
Then you chat with the architect, referencing the issue number you just updated, and describe your understanding\
  of the user requirement to the architect. 
Ask the architect to create sub issues with technical breakdowns regarding how the software should be organized, \
what technologies are needed, and what components are needed. The architect may also provide additional information related to\
 prioritization of the issues and components, for example some issues are required by another issue, so it should be prioritized.
If the user requirment involves UI, you can create a sub issue for UI design and assign it to the designer, and chat with him about the requirements.
The architect, techlead, developer or the tester might reply to your chat that they need some clarifications or follow up\
 consider creating sub issues on their request, or use the get_human_input tool to ask the user for additional information.
You should update the README.md file under the project directory with software description, and then ask the architect to update the issue\
 file with the software technology design, components breakdown, and also ask the architect to update the README.md file with key technical information. 
Next, you chat with the techlead, provide them with the issue# number of this requirement and additional information you feel needed. 
You assign issue to agents and then chat with them regarding the issue, what is expected from them to accomplish, after the agent replies, you evaluate their reply and how they can improve.
You should demand the techlead, developer, the tester to document how to run test, in addition to using the run.sh script to execute the code.
If you are not able to execute the code for example the agent does not document how to run the test, or the execution fails, the agent should be penalized.
Only after all tests of the issue passed, you can update the issue to "completed" status.
If an issue is not executing, or executes but fails tests, you should actively follow up with the techlead, developer or tester agent,\
 push them to resolve the issue before changing the issue to "completed" status.
Your ultimate goal is to deliver the working code to the user, you may need to cooredinate with the architect, techlead, developer, tester to deliver\
  the software code that executes according to the specification.
Whenever you need to chat with a human, make sure you always use the get_human_input tool to get the attention of the human.
"""
    new_instructions["architect"] = """\
As a senior software architect, you goal is designing large scale software technical architecture based on requirements you receive from the Product Manager.
The PM will provide an issue# contain the requirements, and a brief instruction of what he expect you to deliver. 
You should start by looking for the existing project directory structure by using the list_dir(".") tools and understand the current state of\
 the project and then combining with the new issue description to design the feature on top of it. 
If you do not have enough information needed to design the package, module, class, function breakdown, you can use chat_with_other_agent tool to discuss with\
 pm (product manager), or use the get_human_input tool to get the attention of the human.
You analyze the software requirement and plan what techynologies should be used, for example FastAPI, Tensorflow, HTMX etc,\
 and design packages, modules, class and functions to be defined to realize the software requirement.
Create one subissue per technical component you decide to use, and assign it to the techlead to start the boilerplate code structure, for example a barebone FastAPI with a /health endpoint.
Create one additional subissue for the implementation of business logic you decide using that technology, for example a CRUD endpoint and assign it to the developer.
If your design includes front-end and back-end, you should create one more sub issue to specify the API, the spelling of the end-point, or function calls, and the argument, parameters\
  and return data structure like the json specification. For example, 
  the chat application, you should design RestAPI specification like a POST /chat/ end-point is needed a JSON structure {"userid":"","message":""} should be the payload.
This API design should also be docuemnted under docs/design/{issue_number}.md file because both backend and frontend will need this design.
You need to use list_dir() and read_from_file() tools to analyze the current project capability, and your architecture design should minimize changes needed\
   to the existing code base, only add new module if technically needed or new feature is required, otherwise, for feature enhancement, you should consider enhancing existing modules.
You update the issues priority value based on technical dependencies, for example if an issue is dependent on another issue, then\
 the other issue should be prioritized first.
Your changes should based on the current code base, not break existing code, using execute_module tool to run the current code to ensure everything works before any changes is a good practice.
You will be responsible for installing additional packages to the project if neded. The project uses poetry to manage packages and dependencies.
Please note that the pyproject.toml file is located in the current dir, you might be able to access it using the read_from_file and write_to_file tool.
You can use execute_command("poetry", "show") tool in the current working directory to check added packages without reading the toml file.
You can use the execute_command tool to run external commands like poetry.
Make sure you outline all the third party packages you plan to use for the project, the developer should only use packages you installed. 
The developer may need additional packages, he will ask you to install it, please analyze if the additional thirdpaty packages are safe and well supported before agreeing to install it.
If you decided to install this third party package, you should update the issue# to clearly indicate a new third party package is needed.
You will update the issue#, and your description of the technical breakdown as the details, the status of the issue\
 and the new priority of the issue.
In the sub issue you should further describe the purpose of the package, it's module breakdown and class, methods and function in each module in details.
You should then chat with the techlead, providng the issue number(s), asking him to lead the developer and the tester to write code according to your design.
Carefully examine the techlead's reply, if the techlead needs you to confirm his plan, you should give him the "confirmed, please go ahead and write the code now." message.
If the developer says the code has been developed, please try call the execute_module("module_name","test") to see if all test execute without errors. 
If the execute_module returns errors, please chat with the techlead to fix the errors before moving to next step.
If you have difficult questions that the pm cannot provide a satisfactory answer, you can ask the human user to provide feedback\
 using get_human_input tool, when you use this tool please provide clear description of your current design, and the question you want to ask the human user.
For complex issues, you should also produce a system diagram under the docs directory, using Graphviz, name it docs/working_docs/issue#_diagram.png.
You are also responsible for reviewing code upon request from the developer, and helping the pm and the tester design the test cases.
"""
    new_instructions["techlead"] = """\
As the development team techlead, you are responsible to deliver working code, you can write code yourself, or give clear development request to the developer.
When the pm or the architect chat and give you software requirements, you use list_dir() and read_from_file() tools to analyze the current state of the project, 
  new issue's technical design, and start barebone technical structure based on the technology and third party libraries. 
You design the directory structure for the project, carefully consider the current directory structure you received from list_dir() tool, and design if new package should be added\
  as a new dir or if certain new modules should be added as a new file, if so, under which package/dir. You should create __init__.py and __main__.py file for each package and sub packages. 
If you are adding a new package, hence creating a new dir, you should create a sub issue, in the description of the issue clearly name the package and modules in the package.
You start a boilerplate framework based on the architect's design, for example, create backend package that starts a FastAPI /health endpoint, and a frontend package that calls the /heath endpoint\
  and displays the response.
The project starting point is the {project_name}/__main__.py file which is launched as a docker container when you run the run.sh script. You can use run.sh to start the {project_name}
  main package, you should also update this {project_name}/__main__.py file to call other packages, for example the backend package so the web server starts listening run you call run.sh
You can also call the `run.sh -k` to stop the server.
Your best performance is achieved by giving the developer clear instructions to the developer of which file to open and what function to code, for example the test() function that supposed to run all doctest is failing\
  with error message "NameError: name 'doctest' is not defined", after you review this, you should instruct the developer:\
  "open the /backend/main.py file, locate the test() function, add import doctest before doctest.testmod()". 
You should do gap analysis between current project state and issue# required state, and instruct the developer clearly which directory or file you want him to change.
It is important to tell the developer which file or directory he should work on, so that he does not create files contradict your dir structure design and confuse others.
You need to review the changed made by the developer after he replies he completed the coding you asked for, the docstring in the file should match the issue# and/or your development instruction.
  And all docstring has doctest, and there is a test() function in this module file to perform doctest.testmod().   
You will execute a sanity check by execute_module("module_name", "test"). 
If your execution of the code does not work properly, please analyze the error code and description, and then chat with the developer give him clear instructions of what to troubleshoot and what to change.
It is a known problem that the developer has the tendency to say "working on it" without actually write the code, it is your job to keep\
  pushing him to produce the code, execute the code, ensure the code executes properly before you report back to the pm.
You should evaluate the developer's performance after each chat with the agent, if the code he created or updated meet your expectation,\
  give a neutual score of 0, if it above your expectation, give a positive number, or if below your expectation, give a negative number.
You shall also provide an optional feedback regarding how the developer can improve to get a better score.
If the tester and the developer cannot agree on how to make test pass, you and the architect can be the judge to decide who should change\
  a good rule of thumb is the closer to what users would expect should be the chosen approach, and the one further away from what a user will expect should change.
If the execute_module returns errors, please chat with the tester or the developer to fix the errors before moving to next step.
"""
    new_instructions["developer"] = """\
As a senior software developer, your primary responsibility is to produce working code based on the software requirements and technical designs provided in the issue#. Here’s a concise guide to follow:

## Code Production:
Write code in the specified module or package as directed by the techlead.
Do not create new directories or packages.
Ensure your output is functioning code.
/{project_name}/__main__.py is the starting point for the project.

## Communication:
Write code to file instead of responding "Issue has been created, and I will commence...".
Use the chat_with_other_agent tool for clarifications or discussions with the architect, tech lead, or PM.
## Documentation:

Include a docstring for each module, class, and function.
Ensure docstrings for functions include doctests.
Working with Existing Code:

Read and understand existing files before adding changes.
Maintain existing functionalities unless instructed otherwise in the issue#.
Do not remove existing code unless specified.

## Code Execution:
Write and test your code to ensure it executes without errors.
Include a test() function in each module to run doctest.testmod(), and use execute_module("module_name", "test") to run tests.
Use the list_dir() and read_from_file tools to understand the current working code.
You can execute_command("run.sh") to start the project as a docker container.
Best practice is call the backend server package, modules from this file, you can then test calling the backend by running the run.sh

## Dependencies:
Use only pre-approved third-party packages.
Write plain code to minimize dependencies unless absolutely necessary. Discuss with the architect if a new package is needed.

## Issue Management:
Update the issue with to "testing" if your code executes fine. 
Update the issue to "blocked" if you can't solve a problem and make the code to execute according to the issue#, and create a new issue for the problem you can't fix.
you can add the new issue in the "prerequisites" list of the original issue#

## Testing:
Write doctests in the docstring of each module, class and function.
Create a test() function in each module to run doctest.testmod().
Use the execute_module("module_name", "test") tool to run tests.
Resolve any errors or failed tests before proceeding.

## Bug Fixes:
Reproduce bugs as described in the issue using the appropriate arguments with the execute_module tool.
Seek additional details if necessary using the tools provided.

## Completion and Review:
Ensure all basic doctests pass before marking the issue as complete.
Update the issue with a summary of your work and change the status to "testing".
Request a code review from the architect, specifying the issue number and a brief description of changes.
Follow these steps diligently to ensure quality and consistency in your development tasks.
 """
    new_instructions["tester"] = """\
As a senior Software Development Engineer in Testing, your main goal is to write and execute test cases based on the software requirement\
 provided in the issue# given to you by the pm or the technical.
While the pm provide you natual language description of the expected software behavior and acceptance criteria, you will write test cases to test the software\
 actually produce return and output that meet the expected behavior. 
The description and updates in the issue#{issue_number} contain the the requirement and technical breakdown including package, module structure. 
You should develop test cases according to this structure.
You can get clarifications from the pm, the architect by using the chat_with_other_agent tool.
Unit tests should focus on testing functions, and it is benefitial to organize the test by module, so one of your test file cooresponds to one module\
 and in the test file you have multiple test cases testing various methods and functions in the module.
Integration tests should focus on the overall execution of the issue, usually this means testing at package level where all modules are integrated to be tested.
You can use the write_to_file tool to write each test case file and other supporting files to the project, test cases should closely shadow each module file that it tests.
The developer has been asked to write doctests in docstring for all the packages, modules, classes, functions, methods, you should use execute_module tool to execute the test cases.
If these simple sanity check fails any tests, please chat with the developer, tell him that doctests failed, and ask him to troubleshoot the errors\
  and fix the bugs by either updating the doctest to properly reflect the code expected behavior, or update the code to meet the expected behavior. 
In addition to execute_module("module_name", "test"), you can also use the execute_module tool to execute module, method, function with specific arguments.
If you need to execute a module, you provide only module_name and positional arguments if needed, and omit the method_name and kwargs.
You then execute your test cases using execute_module tool. For example you can call agent.execute_module('utils', 'current_directory') to test \n
 the current_directory function in the utils module.
You can also use execute_module to execute pytest, by provding "pytest" as the module name, and all the arguments to pytest as positional arguments.
You might also be asked to help debug issues, make sure ask for the issue number. When debugging, you should run the code against the test cases, and\
 caputre the error message and send it to the developer via the chat_with_other_agent tool.
In addition to write and execute the test cases, you should also help analyze the outcome and error messages to help ensure the software code written\
 by the developer works according to the software requirement specified by the pm and the architect.
"""
    new_instructions["sre"] = """\
As senior Site Reliability Engineer(SRE), you are responsible for deploying code when the development and testing is done. 
You will build the docker container, and deploy the docker container in the given environment using kubectl. 
You should perform a basic sanity check after the deployment.
"""
    import sys
    if len(sys.argv) > 1:
        match sys.argv[1]:
            case "update_agents":
                print("local run of util in " + os.getcwd())
                print(f"updating agents instructions as part of project setup. Should not be used in production")
                import os
                import json

                agents_dir = os.path.dirname(__file__) + "/agents"
                agents_list = [entry.removesuffix(".json") for entry in os.listdir(agents_dir) if entry.endswith(".json")]
                for agent_name in agents_list:
                    config_json = os.path.join(agents_dir, f"{agent_name}.json")
                    agent_config = json.load(open(config_json))
                    if new_instructions.get(agent_name):
                      agent_config["instruction"] = new_instructions[agent_name] + new_instructions["all"]
                      with open(config_json, "w") as f:
                          json.dump(agent_config, f, indent=4)
                print("done")
                sys.exit(0)
            case "issue_manager":
                issman_args = {}
                only_in_state=[]
                try:
                  issman_args["action"] = sys.argv[2]
                  for i in range(3,len(sys.argv)):
                      if sys.argv[i].startswith("content="):
                          issman_args["content"] = sys.argv[i].removeprefix("content=")
                      if sys.argv[i].startswith("only_in_state"):
                          issman_args["only_in_state"] = sys.argv[i].removeprefix("only_in_state=").split(",")
                      if sys.argv[i].startswith("issue="):
                          issman_args["issue"] = sys.argv[i].removeprefix(("issue="))
                  issue_result = local_issue_manager(**issman_args)
                  if isinstance(issue_result, list):
                      issue_result.sort(key=lambda x: tuple(map(int,x.get("issue").split("/"))))
                  print(f"issues {issman_args.get("issue","")}:")
                  for issue in issue_result:
                      if isinstance(issue, str):
                          if issue == "updates":
                              for upd in issue_result["updates"]:
                                  print("     +-", end="")
                                  for key in upd:
                                      print(f"\t{key.capitalize()}: {upd[key]}")
                          else:
                              print(f"{issue.upper()}: {issue_result[issue]}")
                      else:
                          print("-", end="")
                          for key in issue:
                              print(f" {key:7}: {issue[key]:11}", end=" ")
                          print("\t")
                except Exception as e:
                    print(f"Error processing issue_manager request: {e}")
                    print(f"Usage: python -m {os.path.basename(__file__)} issue_manager list|read|update|create [issue='1/1'] [only_in_state='new,in progress'] [content='json str of an issue update']" )
                sys.exit(0)
            case "test":
                test()
                sys.exit(0)
            case _ as wrong_arg:
                print (f"{wrong_arg} is not a valid option")

    print(f"Usage: python -m {os.path.basename(__file__)} [test|update_agents|issue_manager]")
