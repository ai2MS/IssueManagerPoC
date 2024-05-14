
import os
import json
import time
from datetime import datetime
import subprocess
import ollama
from openai import OpenAI, AzureOpenAI
import yaml

if __package__:
    from .utils import current_directory, standard_tools
    from . import logger, agents, msg_logger
else:
    print("Not running as a package, importing from current directory.")
    from utils import current_directory, standard_tools
    from __init__ import logger, agents, msg_logger

class Ollama_Agent:
    llm_service = ollama
    model = "gpt-4-turbo-2024-04-09"
    name = ""
    def __init__(self) -> None:          
        modelfile = (f"FROM llama3\n"
            f"SYSTEM {self.instruction}\n")
        response = self.llm_service.create(model=self.model, modelfile=modelfile, stream=False)
        logger.info(f"creating ollama model {self.model}: {response}")
        # todo: need a compatibility layer to make this ollama model work similar to openai's assistant API
        # currently ollama model won't work

class OpenAI_Agent:
    """
    The OpenAI_Agent class represents an agent that interacts with the OpenAI API to perform various tasks using the OpenAI Assistant.

    Attributes:
        assistant (None): The OpenAI Assistant object.
        run (None): The OpenAI Run object.
        thread (None): The OpenAI Thread object.
        tools (None): The tools used by the agent.
        proj_dir (None): The project directory.
        llm_client (None): The OpenAI client.
        llm_service (ollama): The Ollama service.
        model (str): The model used by the agent.
        name (str): The name of the agent.

    Methods:
        __init__(self, agent_name: str): Initializes the OpenAI_Agent object.
        do_job(self, task: str = None) -> dict: Performs a job using the OpenAI Assistant.
        __str__(self): Allows printing of the agent's source code.
        __repr__(self): Allows printing of the agent's source code.
        my_own_code(self): Returns the agent's own source code.
        write_to_file(self, filename: str, text: str) -> str: Writes text to a file.
        get_human_input(self, prompt: str = None) -> str: Helps the AI get user input.
    
    Example::
        >>> agent = OpenAI_Agent("tester")

    """
    assistant = None
    run = None
    thread = None
    tools = None
    llm_client = None
    llm_service = ollama
    model = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME","gpt-4-turbo-2024-04-09")
    name = ""
    def __init__(self, agent_name: str, agent_dir: str = None):
        """
        Initialize the OpenAI_Agent object.

        Args:
            agent_name (str): The name of the agent.

        Raises:
            json.decoder.JSONDecodeError: If the agent's JSON configuration file is not valid JSON.
            FileNotFoundError: If the agent's JSON configuration file is not found.
            KeyError: If the agent's JSON configuration file does not contain an 'instruction' key.

        Returns:
            None

        Example::
            >>> agent = OpenAI_Agent("tester")

        """
        useAzureOpenAI = os.environ.get("USE_AZURE") == "True"
        logger.info(f"Initializing agent {agent_name}")
        self.file_name = __file__
        self.name = agent_name
        if agent_dir is None:
            agent_dir = os.path.join(current_directory(), "agents")
        try:
            config_json = os.path.join(agent_dir, f"{agent_name}.json")
            agent_config = json.load(open(config_json))
            self.instruction = agent_config.get('instruction', "")
            self.tools = standard_tools.copy()
            self.tools.extend(agent_config.get('tools'))
            other_agent_list = [agt.name for agt in agents if agt.name != self.name]
            chat_function_tools = [tool for tool in self.tools if tool['type'] == 'function' and tool['function']['name'] == 'chat_with_other_agents']
            try:
                chat_function_tools[0]['function']['parameters']['properties']['agent_name']['enum'] = other_agent_list
            except KeyError as e:
                logger.warning(f"<{self.name}> - chat_with_other_agent tools function does not have agent_name parameter. Please check: {e}")
            except Exception:
                pass
            if (useAzureOpenAI):
                self.model = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME",None)
                #Azure does not support #self.tools.append({"type":"retrieval"})
            else:
                self.model = os.environ.get("OPENAI_MODEL",None)
                self.tools.append({"type":"file_search"})
        except json.decoder.JSONDecodeError:
            logger.fatal(f"{agent_name}m.json file is not valid JSON. Please fix the pm.json file.")
            exit()
        except FileNotFoundError:
            logger.fatal(f"{agent_name}.json file not found. Please create a pm.json file in the current directory.")
            exit()
        except KeyError:
            logger.fatal(f"{agent_name}.json file does not contain an 'instruction' key. Please add an 'instruction' key to the pm.json file.")
            exit()

    def __enter__(self):
        """
        Enter the context manager.

        Returns:
            None
        """
        useAzureOpenAI = os.environ.get("USE_AZURE") == "True"
        try:
            if (useAzureOpenAI):
                azure_openai_api_key=os.environ.get("AZURE_OPENAI_API_KEY", None)
                if azure_openai_api_key is None:
                    logger.fatal(f"Please provide AZURE_OPENAI_API_KEY as environment variable.  Cannot continue without AZURE_OPENAI_API_KEY.")
                    exit()
                logger.info("Using Azure OpenAI API")
                self.llm_client = AzureOpenAI(api_key=os.environ.get("AZURE_OPENAI_API_KEY"))
            else:
                openai_api_key=os.environ.get("OPENAI_API_KEY", None)
                if openai_api_key is None:
                    logger.fatal(f"Please provide OPENAI_API_KEY as environment variable.  Cannot continue without OPENAI_API_KEY.")
                    exit()
                self.llm_client = OpenAI(api_key=openai_api_key)
        except Exception as e:
            logger.fatal(f"Failed to establish OpenAI client with error {e}.")
            exit()

        try:
            # Try find assistant with this name (latest first)
            assistants = self.llm_client.beta.assistants.list(order="desc")
            for assistant in assistants:
                if (assistant.name == self.name
                        and assistant.model == self.model 
                        and assistant.instructions == self.instruction):
                    self.assistant = self.llm_client.beta.assistants.retrieve(assistant_id=assistant.id)
                    logger.debug(f"Found existing assistant {self.name}")
                    break
            else:
                self.assistant = self.llm_client.beta.assistants.create(
                    name=self.name,
                    instructions=self.instruction,
                    model=self.model, 
                    tools=self.tools,
                )
                logger.debug(f"Created new assistant {self.name}")

            self.thread = self.llm_client.beta.threads.create()
        except Exception as e:
            logger.fatal(f"Failed to create OPENAI Assistant, received Error {e}.")
            exit()
            
        return self


    def __exit__(self, exc_type, exc_val, exc_tb):
        logger.debug(f"Exiting agent {self.name}")
        self.llm_client.beta.threads.delete(thread_id=self.thread.id)
        self.llm_client.beta.assistants.delete(assistant_id=self.assistant.id)



    def __str__(self) -> str:
        """Allow printing of myself (source code)

        Example::
            >>> agent = OpenAI_Agent("tester")
            >>> print(agent)
            <Agent: tester>
        """
        return f"<Agent: {self.name}>"
    def __repr__(self) -> str:
        """Allow printing of myself (source code)"""
        return f"<Agent: {self.name}>" #json.dumps(self.my_own_code())

    # the following are function tools for OpenAI assistants.
    def read_from_file(self, filename: str = None) -> str:
        """Return the content of a given file.

        Args:
            filename (str, optional): The name of the file to be read. Defaults to None, which means read my own code

        Returns:
            str: The json dumps of the {filename: filename, content: content} dictionary. 
            If there is an error, the json dumps of {filename: filename, error: error} of the file.

        Raises:
            Exception: If there is an error reading the file.

        Example::
            >>> agent = OpenAI_Agent("tester")
            >>> print(agent.read_from_file("non-existant.file"))
            {"filename": "non-existant.file", "error": "[Errno 2] No such file or directory: 'non-existant.file'"}
        """
        if not filename:
            filename = self.file_name
    
        logger.debug(f"<{self.name}> - read_from_file {filename}")
        try:
            with open(filename, "r") as f:
                content = f.read()
            logger.info(f"<{self.name}> - read {filename}")
            result = {
                "filename": filename,
                "content": content,
            }
        except Exception as e:
            logger.error(f"<{self.name}> - Failed to read file {filename}, received Error {e}.")
            content = f"{e}"
            result = {
                "filename": filename,
                "error": f"{e}",
            }
        return json.dumps(result)
        
    def write_to_file(self, filename: str, content: str) -> str:
        """Write text to a file

        Args:
            filename (str): The name of the file to write to
            text (str): The text to write to the file

        Returns:
            str: A message indicating success or failure

        Example::
            >>> agent = OpenAI_Agent("tester")
            >>> print(agent.write_to_file("deleteme.test", "This is a test, please delete me."))
            File deleteme.test has been written successfully.
        """
        logger.debug(f"<{self.name}> - write_to_file {filename} - {content}")
        try:
            directory = os.path.dirname(filename)
            if directory:
                os.makedirs(directory, exist_ok=True)

            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)

            logger.info(f"<{self.name}> -wrote {filename}")
            return f"File {filename} has been written successfully."
        except Exception as e:
            return f"Error: {str(e)} ____ {e}"

    def list_dir(self, path: str = None, return_yaml: bool = True) -> str|object:
        """
        Recursively lists directory contents and organizes them in a nested dictionary
        format suitable for YAML output, including file size and timestamp.

        Args:
            path: the path to list, if this path is invalid, it will trigger an error
            return_yaml: if True, return a YAML string, if False, return an object
        
        Returns:
            either a YAML string or an object
        
        Example::
            >>> agent = OpenAI_Agent("tester")
            >>> print(agent.list_dir(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),"issue_board"), True).split()[0])
            0.json:

        """
        contents = {}
        if not path:
            path = os.getcwd()
        try:
            for entry in os.scandir(path):
                if entry.is_dir(follow_symlinks=False):
                    # Recursively list subdirectories
                    contents[entry.name] = self.list_dir(entry.path, False)
                else:
                    # Get file details
                    stat = entry.stat()
                    contents[entry.name] = {
                        'size': stat.st_size,
                        'timestamp': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        'attributes': {
                            'mode': oct(stat.st_mode),
                        }
                    }
        except FileNotFoundError as e:
            logger.warning(f"<{self.name}> TASK:STEP - tool func list_dir run into error {e}")
            return f"{e}"
        except PermissionError as e:
            logger.warning(f"<{self.name}> TASK:STEP - tool func list_dir run into error {e}")
            return f"{e}"
        
        if return_yaml:
            return yaml.dump(contents, default_flow_style=False)
        else:
            contents

    def perform_task(self, task: str = None, from_: str = "Unknown") -> dict:
        """
        Perform a job using the OpenAI Assistant.

        Args:
            task (str, optional): The task to be performed. If not provided, the instruction from the agent's JSON configuration file will be used. Defaults to None.

        Returns:
            dict: A dictionary containing the results of the job. The keys of the dictionary represent the roles (e.g., 'User', 'Assistant') and the values represent the corresponding messages.

        Raises:
            None

        """
        retry_count = int(os.environ.get("RETRY_COUNT", 3))
        logger.info(f"<{self.name}> TASK:BEGIN -{task}")
        if not task:
            task = self.instruction

        message = self.llm_client.beta.threads.messages.create(
            thread_id=self.thread.id,
            role="user",
            content=task
            )
        self.run = self.llm_client.beta.threads.runs.create(
            thread_id=self.thread.id,
            assistant_id=self.assistant.id,
            timeout=300
        )
        msg_logger.info(f"{from_} >> {self.name} - {task}")
        result = {}
        while self.run.status in ["queued", "in_progress", "requires_action"]:
            logger.debug(f"<{self.name}>-{self.run.status=}")
            if self.run.status == "requires_action":
                required_actions = self.run.required_action.submit_tool_outputs.model_dump()
                logger.debug(f"<{self.name}> TASK:STEPs -tool_calls: {required_actions}")
                tools_output = []
                for action in required_actions["tool_calls"]:
                    func_name = action["function"]["name"]
                    arguments = json.loads(action["function"]["arguments"])
                    func_names = [item['function']['name'] for item in self.tools if item['type'] == 'function']
                    msg_logger.info(f"{self.name} -> {func_name} {arguments}")
                    logger.debug(f"<{self.name}> TASK:step -tool_call_id: {action['id']}- {func_name} {arguments}")
                    if func_name in func_names:
                        func = getattr(self, func_name, None)
                        logger.debug(f"<{self.name}> TASK:step -willing tool {func_name} with arguments {arguments}")
                        output = func(**arguments)
                        logger.debug(f"<{self.name}> TASK:step-tool {func_name} returned {output}")
                        if output is not None:  # Check if output is not None
                            tools_output.append({
                                "tool_call_id": action["id"],
                                "output": output
                            })
                        else:
                            logger.warning(f"<{self.name}> TASK:STEP -Function {func_name} returned None")
                    else:
                        logger.warning(f"<{self.name}> TASK:STEP -Function not found")
                    
                if tools_output:
                    tools_output_head = ''
                    tools_output_1st = tools_output[0]
                    if 'output' in tools_output_1st:
                        tools_output_head = tools_output_1st['output']
                    else:
                        tools_output_head = tools_output_1st
                    logger.info(f"<{self.name}> TASK:STEP -Function {func_name} returned {str(tools_output_head):.32s}...")
                    try:
                        self.run = self.llm_client.beta.threads.runs.submit_tool_outputs_and_poll(
                        thread_id=self.thread.id,
                        run_id=self.run.id,
                        tool_outputs=tools_output
                        )
                    except Exception as e:
                        logger.error(f"<{self.name}> TASK:STEPs -Failed to submit tool outputs:{e}")
                        msg_logger.error(f"{func_name} -> {self.name} - {tools_output} !!!received!!! {e}")
                    else:
                        logger.info(f"<{self.name}> TASK:STEPs -Tool outputs submitted successfully.")
                        msg_logger.info(f"{func_name} -> {self.name} - {tools_output}")

            time.sleep(0.5)
            self.run = self.llm_client.beta.threads.runs.retrieve(
                thread_id=self.run.thread_id,
                run_id=self.run.id,
            )
            if self.run.status in ["expiried", "failed"]:
                logger.warning(f"<{self.name}> TASK:END -run.status is {self.run.status}. retrying...")
                retry_count -= 1
                if retry_count > 0:
                    self.run = self.llm_client.beta.threads.runs.create(
                        thread_id=self.thread.id,
                        assistant_id=self.assistant.id,
                        timeout=300
                    )
        logger.debug(f"<{self.name}> : -after while wait ... {self.run.status=}")
        if self.run.status == 'completed':
            messages = self.llm_client.beta.threads.messages.list(
                thread_id=self.run.thread_id
            )
            for msg in sorted(messages.data, key=lambda x: x.role, reverse=True):
                role = msg.role
                content = msg.content[0].text.value
                logger.debug(f"<{self.name}> : -run.status is completed - msg is -{role.capitalize()}: {content}")
                result[role.capitalize()]=content
        else: 
            logger.warning(f"OpenAI run returned status {self.run.status} which is unexpected at this stage.")

        logger.info(f"<{self.name}> TASK:END -result:{json.dumps(result, indent=4)}")

        return result and result.get("Assistant")

    def get_human_input(self, prompt: str = None) -> str:
        """Help AI get user input
        
        Args:
            prompt: the message shows to the user regarding what the question is about.
            
        Returns:
            str that the user entered into the input() function
        """
        logger.debug(f"get_human_input {prompt}")
        if prompt:
            result = input(f"\n***************User Input Needed***************\n{prompt}:")
        else:
            result = input("The AI needs some input from you:")
        return result
    
    def chat_with_other_agent(self, agent_name: str, message: str) -> str:
        """Chat with another agent
        
        Args:
            agent_name: the name of the agent to chat with
            message: the message to send to the agent
        
        Returns:
            str: the response from the agent
        """
        logger.debug(f"chat_with_other_agent {agent_name} {message}")
        the_other_agent = [a for a in agents if a.name==agent_name][0]
        if the_other_agent:
            chat_result = the_other_agent.perform_task(message, self.name)
            return chat_result or chat_result['Assistant']
        else:
            raise Exception(f"Agent {agent_name} not found")

    def execute_module(self, module_name: str, method_name: str, *args, **kwargs) -> dict[str, any]:
        """Execute a specified method from a Python module.

        Args:
            module_name: Name of the module to execute.
            method_name: Name of the method to execute.
            args: Arguments for the method.
            kwargs: Keyword arguments for the method.
        
        Returns: 
            A dictionary with 'output' or 'error' as a key.

        Example::
            >>> agent = OpenAI_Agent("tester")
            >>> result = agent.execute_module('math', 'sqrt', 16)
            >>> result['output']
            4.0
            >>> result = agent.execute_module('utils', 'current_directory')
            >>> result['output'] ==  os.getcwd()
            True

        """
        # Prepare the command to execute
        python_command = f"import json, {module_name};" \
                        "output={};" \
                        f"output['output'] = getattr({module_name}, '{method_name}')(*{args}, **{kwargs}); " \
                        "print(json.dumps(output))"
        logger.debug(f"<{self.name}> TASK:STEP -Executing {python_command}")
        # Execute the command as a subprocess
        try:
            result = subprocess.run(['python', '-c', python_command],
                                    capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                logger.error(f"<{self.name}> TASK:STEP -Execution failed. Error: {result.stderr}")
                return {'output':f'Execution finished with error: {e}','error': result.stderr}
        except subprocess.TimeoutExpired:
            logger.error(f"<{self.name}> TASK:STEP -Execution failed. Error: timeout")
            return {'output':f'Execution timed out, if this happens often, please check if this module execution is hang.','error': 'Execution timed out'}
        except Exception as e:
            logger.error(f"<{self.name}> TASK:STEP -Execution failed. Error: {e}")
            return {'output':f'Execution failed with error: {e}','error': str(e)}


    def write_all_files_to_temp_dir(self, thread: str, output_path: str = '/tmp'):
        """save OpenAI tools_resources files locally"""
        file_ids = [
            file_id
            for m in self.llm_client.beta.threads.messages.list(thread_id=thread.id)
            for file_id in m.file_ids
        ]
        for file_id in file_ids:
            file_data = self.llm_client.files.content(file_id)
            file_data_bytes = file_data.read()
            with open(output_path+"/"+file_id, "wb") as file:
                file.write(file_data_bytes)

if __name__ == "__main__":
    """quick test of the pm class"""
    import doctest
    doctest.testmod()
