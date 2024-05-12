"""
This module contains utility functions for working with files.
"""
import os

standard_tools = [
        {"type": "code_interpreter"},
        {
          "type": "function",
          "function": {
            "name": "write_to_file",
            "description": "Write the content to a file",
            "parameters": {
              "type": "object",
              "properties": {
                "file_name": {
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
                "name": "get_my_own_code",
                "description": "Retrieve or read my own code, so that I can analyze the code behind how I was designed",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_name": {
                            "type": "string",
                            "description": "The name of the source code file to read."
                        }
                    },
                    "required": []
                }
            }
        }
      ]

def current_directory() -> str:
    current_file = os.path.realpath(__file__)
    current_dir = os.path.dirname(current_file)
    parent_dir = os.path.dirname(current_dir)
    return current_dir


if __name__ == "__main__":
    from . import logger
    print(write_to_file("test.deleteme", "Hello, world!"))