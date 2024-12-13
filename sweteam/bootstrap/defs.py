"""This module contains initial definitions for the agent instructions and tools.

Example::
  >>> from .defs import standard_tools, new_instructions
  >>> len(standard_tools)
  12
  >>> sorted(new_instructions.keys())
  ['all', 'architect', 'backend_dev', 'frontend_dev', 'pm', 'sre', 'techlead', 'tester']
"""

import os
import json
import re
from .config import config
from abc import ABC, abstractmethod
from .utils import get_logger
from .utils import issue_manager, execute_module, execute_command
from .utils.file_utils import dir_structure


class BaseAgent(ABC):
    _instances = []

    class AgentConfig:
        model = "mistral-nemo:latest"
        instruction: str = ""
        additional_instructions: str = ""
        temperature: int = 1
        tools: list = []
        tool_choice: str | dict = "auto"
        evaluation_criteria: str = ""
        use_tools: bool = False
        context_window_size: int = 128
        name: str = ''

        def __init__(self, initial_values: dict = {}) -> None:
            for key, value in initial_values.items():
                setattr(self, key, value)

        def __repr__(self) -> str:
            attrs = ', '.join(f"{key}={value!r}" for key, value in self.__dict__.items())
            return f"{self.__class__.__name__}({attrs})"

    class LLMClient(ABC):
        @abstractmethod
        def chat(self, messages: list, **kwargs) -> dict:
            """Abstract chat method.

            Args:
                messages (list): A list of messages comprising the conversation.
                **kwargs: Additional keyword arguments for specific LLM client implementations.

            Returns:
                dict: The chat response from the LLM.
            """
            raise NotImplementedError

        @abstractmethod
        def generate(self, prompt: str, **kwargs) -> dict:
            """Abstract text generation method.

            Args:
                prompt (str): The text prompt for generation.
                **kwargs: Additional keyword arguments for specific LLM client implementations.

            Returns:
                dict: The generation response from the LLM.
            """
            raise NotImplementedError

        @abstractmethod
        def list(self, **kwargs) -> list:  # Or dict, adjust as needed
            """Abstract method to list available models.

            Args:
                **kwargs: Additional keyword arguments for specific LLM client implementations.

            Returns:
                list or dict:  A list or dictionary of available models.
            """
            raise NotImplementedError

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.config!r})"

    def __init__(self, agent_name: str = '') -> None:
        self.name = agent_name
        self.config = self.AgentConfig()
        self.llm_client: self.LLMClient() = None
        self.logger = get_logger(f'{self.__class__.__name__ or ""}[{self.name}]')
        self.__class__._instances.append(self)

    @classmethod
    def instances(cls, include_children: bool = False) -> list:
        if not include_children:
            return cls._instances  # Return the list of all instances for this class
        else:
            temp_instances = []
            # Iterate through all direct child classes
            for subclass in cls.__subclasses__():
                if hasattr(subclass, '_instances'):
                    temp_instances.extend(subclass._instances)
            # Include instances of the current class as well
            if hasattr(cls, '_instances'):
                temp_instances.extend(cls._instances)
            return temp_instances

    # method to list/read/write issues

    def issue_manager(self, action: str, issue: str = '',
                      only_in_state: list = [], content: str = None,
                      assignee: str = None):
        return issue_manager(action, issue, only_in_state, content, assignee, caller=self.name)

    def dir_structure(self, action: str = 'read', path: dict = {}) -> str:
        """update or return project directory structure

        Args:
            action - one of read|delete|update
        """
        self.logger.debug(f"<{self.name}> - calling dir_structure({action=}, {path=})")
        return dir_structure(action=action, path=path)

    def execute_command(self, *args, **kwargs) -> str:
        """"""
        self.logger.debug(f"<{self.name}> - calling execute_command with {kwargs}")
        return execute_command(*args, **kwargs)

    def execute_module(self, *args, **kwargs) -> str:
        self.logger.debug(f"<{self.name}> - calling execute_module with {kwargs}")
        return execute_module(*args, **kwargs)

    def read_file(self, filepath: str = '') -> str:
        """Return the content of a given file.

        Args:
            filepath (str, optional): The name of the file to be read. Defaults to None, which means read my own code

        Returns:
            str: The json dumps of the {filepath: filepath, content: content} dictionary. 
            If there is an error, the json dumps of {filepath: filepath, error: error} of the file.

        Raises:
            Exception: If there is an error reading the file.

        Example::
            >>> agent = OpenAI_Agent("pm")
            >>> print(agent.read_file("non-existant.file"))
            {"filepath": "non-existant.file", "error": "[Errno 2] No such file or directory: 'non-existant.file'"}
        """
        if not filepath:
            filepath = __file__

        self.logger.debug(f"<{self.name}> - read_file {filepath}")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            self.logger.info(
                f"<{self.name}> - read_file {filepath} successfully.")
            result = {
                'filepath': filepath,
                'content': content,
            }
        except Exception as e:
            self.logger.warning(
                f"<{self.name}> -read_file Failed to read file {filepath}, received Error {e}.")
            content = f"{e}"
            result = {
                'filepath': filepath,
                'error': f"{e}",
            }
        return json.dumps(result)

    def overwrite_file(self, filename: str, content: str, force: bool = False) -> str:
        """Write content info to a file, mostly used for binary files

        Args:
            filepath (str): The name of the file to write to
            content (str): The text to write to the file

        Returns:
            str: A message indicating success or failure

        Example::
            >>> agent = OpenAI_Agent("pm")
            >>> print(agent.overwrite_file("deleteme.test", "This is a test, please delete me.", force=True))
            File deleteme.test has been written successfully.
        """
        self.logger.debug(
            f"<{self.name}> - overwrite_file {filename} - {content}")
        if not os.path.exists(filename) or force:
            try:
                directory = os.path.dirname(filename)
                if directory:
                    os.makedirs(directory, exist_ok=True)

                with open(filename, 'w', encoding="utf-8") as f:
                    f.write(content)

                self.logger.info(
                    f"<{self.name}> - overwrite_file {filename} successfully.")
                return f"File {filename} has been written successfully."
            except Exception as e:
                self.logger.error(
                    f"<{self.name}> - overwrite_file Failed to write to file {filename}, received Error {e}.")
                return f"Error: {str(e)} ____ {e}"
        else:
            result = json.loads(self.read_file(filename))
            result['rejection'] = f"file {filename} already exists, "
            "its content is in this message, please make sure the the new "
            "content is not causing existing code to fail, then use "
            "`force=True` to overwrite the existing content."
            return json.dumps(result)

    def apply_unified_diff_to_file(self, filepath: str, diffs: str) -> str:
        """accept unified diff hunks and apply to filepath

        Args:
            filepath - filepath to the original file of which content needs to be updated
            diffs - text of unified diff instructions

        Returns:
            str message of if update was successful.
                Example::
        >>> agent = OpenAI_Agent("pm")
        >>> agent.apply_unified_diff("delete.me", "--- delete.me 2022-02-02 02:02:02\\n+++ new_delete.me 2023-03-03 03:03:03\\n@@ -1,5 +1,5 @@\\n+Line1\\n+Lin2\\n+Line3\\n+Line4\\n+Line5")
        'Successfully updated delete.me.'
        """
        def parse_hunk_header(header) -> tuple[int, int, int, int]:
            # Use regex to correctly parse the hunk header
            match = re.match(
                r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', header)
            if not match:
                raise ValueError(f"Invalid hunk header: {header}")

            old_start = max(int(match.group(1)) - 1, 0)
            # Default to 1 if count is not specified
            old_count = int(match.group(2) or 1)
            new_start = max(int(match.group(3)) - 1, 0)
            # Default to 1 if count is not specified
            new_count = int(match.group(4) or 1)

            return old_start, old_count, new_start, new_count

        original_lines = []
        if os.path.exists(filepath):
            self.logger.debug(f"<{self.name}> - apply_unified_diff() file "
                              f"{filepath} already exists, "
                              "reading in to be changed")
            with open(filepath, "r", encoding="utf-8") as f:
                original_lines = f.readlines()

        updated_lines = original_lines[:]
        update_offset = orig_start = orig_line_cnt = upd_start = upd_line_cnt = 0
        orig_hunk_line_cnt = upd_hunk_line_cnt = 0
        # Skip the file header lines
        diff_lines = (line for line in diffs.splitlines(keepends=True)
                      if not line.startswith(("---", "+++", "diff --git", "new file mode", "index ")))
        for diff_line in diff_lines:
            if diff_line.startswith('@@'):
                orig_start, orig_line_cnt, upd_start, upd_line_cnt = parse_hunk_header(
                    diff_line)
                orig_hunk_line_cnt = upd_hunk_line_cnt = 0
            elif diff_line.startswith('-'):
                # Removal
                line_num = orig_start + update_offset
                if original_lines[line_num:line_num + 1] != [diff_line[1:]]:
                    raise ValueError(f"Can't Delete, Orig_file line #{orig_start + 1} does "
                                     f"not match diff hunk '{
                                         diff_line.strip()}'."
                                     "Try read the content of the file again "
                                     "so you can recreate correct unified diffs.")
                del updated_lines[line_num]
                update_offset -= 1
                orig_hunk_line_cnt += 1
            elif diff_line.startswith('+'):
                # Addition
                line_num = orig_start + update_offset
                updated_lines.insert(line_num, diff_line[1:])
                update_offset += 1
                upd_hunk_line_cnt += 1
            elif diff_line.startswith(' '):
                # Context line
                line_num = orig_start + update_offset
                if updated_lines[line_num:line_num + 1] != [diff_line]:
                    raise ValueError(f"Can't find expected context, "
                                     f"Orig_file line #{line_num + 1} does "
                                     f"not match diff hunk '{diff_line}'."
                                     "Try read the content of the file again "
                                     "so you can recreate correct unified diffs.")
                orig_hunk_line_cnt += 1
                upd_hunk_line_cnt += 1
            else:
                raise ValueError(f"Unexpected diff hunk specification line: "
                                 f"'{diff_line.strip()}'.  Please use strict "
                                 "Unified Diff syntax to specify diffs.")
        if orig_hunk_line_cnt != orig_line_cnt or upd_hunk_line_cnt != upd_line_cnt:
            raise ValueError(f"UniDiff specification invalid, hunk specified "
                             f"{orig_line_cnt} original lines and {upd_line_cnt}"
                             f" updated lines, but the hunk commands were for "
                             f"{orig_hunk_line_cnt} original lines and "
                             f"{upd_hunk_line_cnt} updated lines.")
        self.logger.debug(f"<{self.name}> - apply_unified_diff() writing to file "
                          f"{filepath} ...")

        directory = os.path.dirname(filepath)
        if directory:
            os.makedirs(directory, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(updated_lines)

        return f"Successfully updated {filepath}."

    @abstractmethod
    def perform_task(self, task: str = None, from_: str = "Unknown", context: dict = {}) -> str:
        raise NotImplementedError

    @abstractmethod
    def evaluate_agent(self, agent_name: str, score: int = 0, additional_instructions: str = "") -> str:
        raise NotImplementedError

    @abstractmethod
    def chat_with_other_agent(self, agent_name: str, message: str, issue: str = '') -> str:
        raise NotImplementedError

    def get_human_input(self, prompt: str = None) -> str:
        """Help AI get user input

        Args:
            prompt: the message shows to the user regarding what the question is about.

        Returns:
            str that the user entered into the input() function
        """
        self.logger.debug(f"<{self.name}> - get_human_input({prompt})")
        if prompt:
            result = input(
                f"\n***************<{self.name}> Needs User Input***************\n{prompt}:")
        else:
            result = input("The AI needs some input from you:")
        return result


agents_dir = os.path.dirname(__file__) + "/agents"
agents_list = [entry.removesuffix(".json") for entry in os.listdir(
    agents_dir) if entry.endswith(".json")]
project_name = config.PROJECT_NAME
agent_roles: str = """\
pm: analyze software feature requirements from the user, break down the issue to smaller, more specific\
 sub issues that are sub-components of the requirements, including requirement refinement, architecture\
 UI design, coding backend and frontend, and build containerized packages and deploy.
architect: based on the given issue, design the technology to be used, and directory structure of what files\
 should be create or updated to realize the feature; if the issue description is not specific enough yet\
 help the pm to further break down the issue to multiple more specific sub-issues.
backend_dev: develop backend code that serve the API and realize core business functionalities\
 including business logic, and data preservation code.
front_end_dev: develop web frontend code that serve the user interface, and calling the backend API\
 to delegate user's interaction to be fulfilled by the backend.
designer: design UI and UX for the web frontend, create wireframe designs and progress to css implementation of the UI
sre: build Dockerfile to package the software as container, test the containerized package and deploy to production\
 as the sub issue specified.
"""
standard_tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Retrieve or read my own code, so that I can analyze the code behind how I was designed",
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


new_instructions = {}
new_instructions["all"] = f"""\
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

**Before creating a new issue, search the issue_board directory to make sure dupliate issue that has already been created, avoid creating duplicate issues, use update instead**
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
## How to execute python code
### execute a function: execute_module(module_name="module", method_name="function_name", args=[])
### execute a module (the if __name__ == "__main__": block): execute_module(module_name="module", args=[])
### execute the main package: execute_module(module_name="{config.PROJECT_NAME}", args=[])

### execute a command: execute_command(command="command", args=[])
### start the main package in a docker container: execute_command(command="bash", args=["run.sh"])

# the project should execute and meet the requirement specified in the issue#.
"""

new_instructions["pm"] = f"""\
**Goal**:
   - Collect software requirement info. For a given software requirement, analyze the fundamental feature of input, process and output:
    - what type of input is expected to be processed
    - what processing is expected on the input data
    - how to provide the output to the party using this feature
  - it is possible to "recurssively dissect" a problem, an input itself might be a feature, that involves smaller input and some processing as well - you should decide if a given description is sufficient to start coding.
  - it is also possible the architect and the developer may come back and ask you for further clarification, you should look into the issue history and try answer to the best of your knowledge.

**Chain of Thoughts**

1. read the the respective issue using issue_manager, analyze the content, search in issue_board to see if there are sub issues that are in status "new" or "in progress", if found, focus on the sub issue first;
2. for new issues that has no architect sub issues, create a sub issue for architecture, assign it to architect, and ask the architect to create a boilerplate project with the technology and third party packages install and working;
3. follow up with the architect until the boiler plate is working, check for sub issues that are assigned to the developers and follow up with the developers asking them to complete coding for the issues.
4. if the specification is not clear enough, search in issue_board directory to check related or similar issues, do they provide enough information, if so assign those issue ticket to the developer;
5. if cannot find relevant issue tickets in issue_board directory, create a new sub issue using issue_manager, with clear instruction of what code to write, then assign it to developer, and ask them to compelte the issue;
6. follow up with the developer to make sure them are writing working code, if they are unable to produce working code, try break down the issue ticket to more specific smaller issues that are more tengible.
7. chat with the developers (frontend_dev and backend_dev), tell them clearly what code file they should change to add or change what features.

### Notes

- **Completion**: An issue can only be marked as "completed" after all code works and all test cases pass.
"""
new_instructions["architect"] = f"""\
As a software architect, you goal is designing large scale software technical architecture based on requirements you receive from the Product Manager. Your deliverables are boilerplate executable project structure that has all the technical component you envision the project will need, including all the packages, use `poetry` to install if a third party package does not yet exist.
**Goal**
Your goal is to create a boilerplate project where each technical component works smoothly with each other. You don't need to implement specific business logic, insteadd you assign the follow up ticket to a developer to use the boilerplate to complete the business logic code.

Use Chain of Thoughts:
1. read the issue, deside what technology should be used to fulfill this requirement. We follow the following strategy:
- we prefer existing technology, third party libraries over introducing new ones to the project
- we prefer FastAPI for the backend
- we prefer HTMX for the frontend, static assests are served by the same FastAPI instance
- we prefer files over database, unless throughput and volume justifies database
2. use dir_structure(action='read') to examine the current directory structure, the result also tells you the discrepencies between plan and actual dir structure;
3. use dir_structure(action='update', path=dir_object) to update the plan, the dir_object should represent a dir structure in which dir and file hierachy is represented in dictionary object hierachy, and "description" property should be used to indicate the purpose of each file.
4. You are also responsible to chose directory and file structure for data files, or database schema if you choose to use it (remember we prefer files over database). You specify filesystem structure also using function tool dir_structure.
5. design API contracts, including function parameters, RestAPI parameters, and json payload schema. You produce these specification using code, i.e. define Python class interfaces, or sample code that produces sample result, and consume it. Text specification of the items you are designing should be added as docstring or additional_docstring to the source code files of the boilerplate you create, so that pydocs can build the documentationf from these source code files.
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
        raise HTTPException(status_code=400, detail="userid and message cannot be empty")

    # Process the request (placeholder logic)
    response_message = f"Received message from user {{request.userid}}"
    return {{"message": response_message}}
```
6. once you determine the boilerplate is working properly, and sufficient for further coding, please assign it to either the frontend_dev or the backend_dev agents.
7. If you do not have enough information needed to design the package, module, class, function breakdown, you can use chat_with_other_agent tool to discuss with pm (product manager), or use the get_human_input tool to get the attention of the human.
Your design should be based on the current code base, do **not** break existing code, using execute_module tool to run the current code to ensure everything works before any changes is a good practice.
8. You can use the execute_command tool to run external commands like poetry.
For example, execute_command(command="poetry", args=["show"]) to check added packages without reading the pyproject.toml file.
"""

new_instructions["backend_dev"] = f"""\
System Prompt with Chain of Thought Approach:
As a senior software developer of Python, your primary responsibility is to produce fully functioning and tested code based on the software requirements and technical designs provided in the issue#.

Follow this step-by-step guide to ensure clarity and correctness in your work.

# Step-by-Step Code Production Process:
## 1. Review the Requirements:

Begin by reading and understanding the issue# and the corresponding requirements.
Verify if there are any ambiguities or missing details. If needed, seek clarification using the chat_with_other_agent tool to communicate with the architect or PM.

## 2. Locate the Correct Directory and File:

Use the dir_structure(action='read') tool to inspect the existing directory structure, pay attention to the discrepency between the planned and actual status;
Review and make sure you are changing the correct files according to planned purpose. Do not create a new file while there is already an existing file for the same purpose.

## 3. Write New Code or Modify Existing Code:

Understand the existing code by reading the file before making any changes. Ensure you understand the flow and purpose of the existing functions or classes.
Maintain existing functionality unless explicitly instructed to modify or remove it.
Do not create new directories or packages unless it is explicitly mentioned in the issue#.

## 4. Write the Code:

Implement the required functionality inside the correct module as specified by the issue#.
Write Pythonic code that adheres to the project's guidelines. If the project starts from {project_name}/main.py (such as in a FastAPI setup), make sure to call your new or updated function in the correct place.
If any external dependencies are needed, ensure they are pre-approved and minimal.

## 5. Test the Code:

Write doctests inside the docstring of each module, class, and function you work on. Use examples to test typical use cases and edge cases.
Add a test() function to each module that calls doctest.testmod(), ensuring that all doctests are executed when test() runs.
Execute your tests using execute_module("module_name", "test") to verify the correctness of your code.
Ensure all tests pass before proceeding. If any test fails, analyze the error and modify the code accordingly.

## 6. Run the Project to Test Execution:

Start the project by running execute_command(command="bash", args=["run.sh"]) to launch the backend (for example, starting a FastAPI server on port 8080).
Interact with the running backend using frontend code or test API calls via tools like curl.
Ensure the system runs without runtime errors and behaves as expected.

## 7. Update the issue using issue_manager to keep track of what you have done to improve the code to meet the requirements.

## Dependencies:
Use only pre-approved third-party packages.
Write plain code to minimize dependencies unless absolutely necessary. Discuss with the architect if a new package is needed.

"""

new_instructions["frontend_dev"] = f"""\
As a senior frontend software developer, your primary responsibility is to produce working code for web UI based on the software requirements and technical designs provided in the issue#.
Your goal is to produce working WebUI front-end that works:

## Code Production:
Write HTML, CSS, and JavaScript code in the specified directory or file by the architect. We prefer HTMX as frontend framework, if the design requires, we can fall back to React.
You read result of function tool dir_structure, and confirm the dir and file you work on exist in this file already, and the description of each dir and file should match what you will be working on.
If not, check with the techlead that the design is correct that you should work on this file.
Do not create new directories or packages unless specified in the issue#.
If you create new directory or files, you need to first update dir_structure function tool to reflect the new directory or file.
Ensure your output is functioning code.
If you need to test frontend code, use execute_command(command="bash", args=["run.sh"]) to start the project backend as a server first then run your test cases.

## Communication:
Write code to file using update_test_file toolinstead of responding "Issue has been created, and I will commence...".
Use the chat_with_other_agent tool for clarifications or discussions with the architect, tech lead, or PM.

## JSDoc:
Include a JSDoc for each module, class, and function.

#Working with Existing Code:
Important: Read and understand existing file content then make small and efficient changes.
Maintain existing functionalities unless instructed otherwise in the issue#.
Do not remove existing code unless specified.

## Code Execution:
Write and test your code to ensure it executes without errors. Use Selenium to test your code.
You can execute_command(command="bash",args=["run.sh"]) to start the project backend as a docker container.
Best practice is start the backend server using run.sh, then test interacting with your backend using frontend code or curl.

## Dependencies:
Use only pre-approved third-party packages. If you need packages that are not installed, use chat_with_other_agent tool to discuss with the techlead.
Write plain code to minimize dependencies unless absolutely necessary. Discuss with the architect if a new package is needed.

## Testing:
### Unit testing:
Write unit test test cases for your html, css and js files, they shoul run locally without errors.
Use Selenium to test your web UI.

## Bug Fixes:
Reproduce bugs as described in the issue using the appropriate arguments with the execute_module tool.
Seek additional details if necessary using the tools provided.

## Completion and Review:
Update the issue with a summary of your work and change the status to "testing".
Request a code review from the architect, specifying the issue number and a brief description of changes.
Follow these steps diligently to ensure quality and consistency in your development tasks.
"""


new_instructions["tester"] = f"""\
As a senior Software Development Engineer in Testing, your main goal is to write and execute intergration testing.
While the pm provide you natual language description of the expected software behavior and acceptance criteria, you will write test cases to test the software\
 actually produce return and output that meet the expected behavior.
Writing test code is also development, so you should focus on coding the write logic. You will write both python tests and jest tests.
Your test code should be in the tests/ direcotry.
#<issue_number> contain the the requirement and technical breakdown including package, module structure.
The description and updates in the issue
You can get clarifications from the pm, the architect by using the chat_with_other_agent tool.
You can use the ed_text_file tool to write each test case file and other supporting files to the project, test cases should closely shadow each module file that it tests.
The developer has been asked to write unit tests for all their code, you can use execute_module tool to execute the test cases.
If these simple sanity check fails any tests, please chat with the developer, tell him that doctests failed, and ask him to troubleshoot the errors\
  and fix the bugs by either updating the doctest to properly reflect the code expected behavior, or update the code to meet the expected behavior.
In addition to execute_module("module_name", "test"), you can also use the execute_module tool to execute module, method, function with specific arguments.
If you need to execute a module, you provide only module_name and positional arguments if needed, and omit the method_name and kwargs.
You then execute your test cases using execute_module tool. For example you can call agent.execute_module('utils', 'current_directory') to test \n
 the current_directory function in the utils module.
You can also use execute_module to execute pytest, by provding "pytest" as the module name, and all the arguments to pytest as positional arguments.
You might also be asked to help debug issues, make sure ask for the issue number. When debugging, you should run the code against the test cases, and\
 caputre the error message and send it to the developer via the chat_with_other_agent tool.
If test returns non-zero return code, and some test fails, start from the first error, anf focus on solve the one error before moving on to the next error.
Carefully analyze the error, ask "what would cause this error message", then locate the line of code that caused the error, read the lines before this line to diagnose.
Then change your testing code, or propose changes to the actual code to meet the expected behavior.
"""
new_instructions["sre"] = f"""\
As senior Site Reliability Engineer(SRE), you are responsible for deploying code when the development and testing is done.
You will build the docker container, and deploy the docker container in the given environment using kubectl.
To execute backend server, you can use execute_command(command="sh", args=["npm", "start"], asynchronous=True), this runs npm start in the background.
Analyze command output and error messages, determine if you can fix it, if not chat with the parties you believe is responsible and say "the code is producing the error and output ..., please analyze and fix"
"""


def test() -> None:
    import doctest
    doctest.testmod()


if __name__ == "__main__":
    test()
