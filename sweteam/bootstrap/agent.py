
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
    procs = []
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
            agent_dir = os.path.join(os.path.dirname(__file__), "agents")
        try:
            config_json = os.path.join(agent_dir, f"{agent_name}.json")
            agent_config = json.load(open(config_json))
            self.instruction = agent_config.get('instruction', "")
            self.tools = standard_tools.copy()
            self.tools.extend(agent_config.get('tools'))
            chat_function_tools = [tool for tool in self.tools if tool['type'] == 'function' and tool['function']['name'] == 'chat_with_other_agent']
            try:
                chat_function_tools[0]['function']['parameters']['properties']['agent_name']['enum'].remove(self.name)
            except KeyError as e:
                logger.warning(f"<{self.name}> - chat_with_other_agent tools function does not have agent_name parameter. Please check: {e}")
            except Exception as e:
                logger.warning(f"<{self.name}> - error setting other_agent_list in chat_with_other_agent tools function. Please check: {e}")
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

    # method to list/read/write issues
    def issue_manager(self, action: str, issue: str = '', only_in_state: list = [], content: str = None):
        ISSUE_BOARD_DIR = "issue_board"
        content_obj = {}
        if content:
            try:
                content_obj = json.loads(content)
            except Exception as e:
                return ("Error parsing {content}, please make sure content is a proper json object.")
        match action:
            case "list":
                issue_dir = os.path.join(ISSUE_BOARD_DIR, issue)
                results = []
                for root, dirs, files in os.walk(issue_dir):
                    for file in files:
                        if file=='issue.json':
                            file_path = os.path.join(root, file)
                            issue_number = root.removeprefix(ISSUE_BOARD_DIR+'/')
                            try:
                                with open(file_path, 'r') as f:
                                    data = json.load(f)
                                updates = data.get('updates', [])
                                updates.sort(key=lambda x: x.get('update at',0), reverse=True)
                                if updates:
                                    status = updates[0].get('status', 'new')
                                    priority = updates[0].get('priority', '0')
                                else:
                                    status = data.get('status', 'new')
                                    priority = data.get('priority', '0')
                                if only_in_state and status not in only_in_state:
                                    continue
                                results.append({'issue':issue_number, 'priority':priority, 'status':status})
                            except json.JSONDecodeError:
                                logger.error(f"<{self.name}> - issue_manager/list - issue#{issue_number} - Error decoding JSON from file: {file_path}")
                                results.append({"issue":issue_number, "status":f"Error Decoding Json"})
                            except FileNotFoundError:
                                logger.error(f"<{self.name}> - issue_manager/list - issue#{issue_number} - Error file not found: {file_path}")
                                results.append({"issue":issue_number, "status":f"Error file not found"})
                            except Exception as e:
                                logger.error(f"<{self.name}> - issue_manager/list - issue#{issue_number} - Error decoding JSON from file: {file_path}")
                                results.append({"issue":issue_number, "status":f"Error {e}"})
                return f"{results}"
            case "create":
                try:
                    issue_dir = os.path.join(ISSUE_BOARD_DIR, issue)
                    if not os.path.exists(issue_dir):
                        os.makedirs(issue_dir, exist_ok=True)
                    existing_sub_issues = [int(entry.name) for entry in os.scandir(issue_dir) 
                                        if entry.is_dir() 
                                        and entry.name.isdigit() 
                                        and os.path.exists(os.path.join(issue_dir, entry.name,'issue.json'))] 
                    new_issue_number = f"{max([issue_no for issue_no in existing_sub_issues], default=0) + 1}"
                    if 'created_at' not in content_obj:
                        content_obj['created_at'] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
                    issue_file = os.path.join(issue_dir, new_issue_number,'issue.json')
                    result = self.write_to_file(issue_file, json.dumps(content_obj))
                except Exception as e:
                    logger.error(f"<{self.name}> issue_manager/create issue {new_issue_number} error {e}: s{e.__traceback__.tb_lineno}")
                    return f"Error creating issue {new_issue_number}. Error: {e}"
                return "issue" + result.removesuffix('.json*').removeprefix(f"File {ISSUE_BOARD_DIR}") + " created"
            case "read":
                try:
                    issue_dir = os.path.join(ISSUE_BOARD_DIR, issue)
                    issue_file = os.path.join(issue_dir, 'issue.json')
                    read_result = json.loads(self.read_from_file(issue_file))
                    if 'content' in read_result:
                        result = read_result.get("content", "")
                    else:
                        result = ""
                except Exception as e:
                    logger.error(f"<{self.name}> issue_manager/read issue {issue} error {e}: s{e.__traceback__.tb_lineno}")
                    result = f"Error Reading issue {issue} - Error: {e}"
                return result
            case "update":
                try:
                    issue_dir = os.path.join(ISSUE_BOARD_DIR, issue)
                    issue_file = os.path.join(issue_dir, 'issue.json')
                    issue_read = json.loads(self.read_from_file(issue_file))
                    issue_content = json.loads(issue_read.get("content","{}"))
                    if content_obj and "updated_at" not in content_obj:
                        content_obj["updated_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
                    if content_obj and "author" not in content_obj:
                        content_obj["author"] = self.name
                    if issue_content and "updates" in issue_content:
                        issue_content["updates"].append(content_obj)
                    else:
                        issue_content["updates"] = [content_obj]
                    result = self.write_to_file(issue_file, json.dumps(issue_content))
                except Exception as e:
                    logger.error(f"<{self.name}> issue_manager/update issue {issue} error {e}: s{e.__traceback__.tb_lineno}")
                    return f"Error Updating issue {issue} - Error: {e}"
                return f"issue {issue} updated"
            case _:
                return (f"Invalid action: {action}")
            
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
            logger.info(f"<{self.name}> - read_from_file {filename} successfully.")
            result = {
                "filename": filename,
                "content": content,
            }
        except Exception as e:
            logger.warning(f"<{self.name}> -read_from_file Failed to read file {filename}, received Error {e}.")
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

            logger.info(f"<{self.name}> - write_to_file {filename} successfully.")
            return f"File {filename} has been written successfully."
        except Exception as e:
            logger.error(f"<{self.name}> - write_to_file Failed to write to file {filename}, received Error {e}.")
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
            >>> agent.list_dir(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),"issue_board"), True).split('\\n')[:4]
            ["'0':", '  issue.json:', '    attributes:', '      mode: 0o100644']
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
            logger.warning(f"<{self.name}> - list_dir run into FileNotFoundError {e}")
            return f"{e}"
        except PermissionError as e:
            logger.warning(f"<{self.name}> - list_dir run into PermissionError {e}")
            return f"{e}"
        
        if return_yaml:
            return yaml.dump(contents, default_flow_style=False)
        else:
            return contents

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
        current_message = None
        retry_count = int(os.environ.get("RETRY_COUNT", 3))
        logger.info(f"<{self.name}> TASK:BEGIN from:{from_} - task:{task} - retries left:{retry_count}")
        if not task:
            task = self.instruction
        try:
            # making sure wait until other runs are no longer active before creating new one
            wait_other_runs_timeout = 300
            for run_ in self.llm_client.beta.threads.runs.list(thread_id=self.thread.id):
                while run_.status in ['active'] and (wait_other_runs_timeout := wait_other_runs_timeout - 1) > 0:
                    logger.debug(f"<{self.name}> TASK:PREP - {self.thread.id} - {run_.id} - {run_.status}")
                    time.sleep(1)

            current_message = self.llm_client.beta.threads.messages.create(
                thread_id=self.thread.id,
                role="user",
                content=task
                )
            self.run = self.llm_client.beta.threads.runs.create(
                thread_id=self.thread.id,
                assistant_id=self.assistant.id,
                timeout=300
            )
        except Exception as e:
            logger.warning(f"<{self.name}> TASK:STEP - tool func perform_task run into error {e}")
            return f"{e}"
        msg_logger.info(f"{from_} >> {self.name} - {task}")
        result = []
        while self.run.status in ["queued", "in_progress", "requires_action"]:
            logger.debug(f"<{self.name}>-{self.run.status=}")
            if self.run.status == "requires_action":
                try:
                    required_actions = self.run.required_action.submit_tool_outputs.model_dump()
                    logger.debug(f"<{self.name}> TASK:STEPs -tool_calls: {required_actions}")
                    tools_output = []
                    for action in required_actions["tool_calls"]:
                        func_name = action["function"]["name"]
                        arguments = json.loads(action["function"]["arguments"])
                        func_names = [item['function']['name'] for item in self.tools if item['type'] == 'function']
                        msg_logger.info(f"{self.name} -> {func_name} {arguments}")
                        logger.debug(f"<{self.name}> TASK:STEP-{action['id']} - {func_name} {arguments}")
                        if func_name in func_names:
                            func = getattr(self, func_name, None)
                            logger.debug(f"<{self.name}> TASK:STEP-{action['id']} -calling tool {func_name} with arguments {arguments}")
                            output = func(**arguments)
                            logger.debug(f"<{self.name}> TASK:STEP-{action['id']} {func_name} returned {output}")
                            if output is not None:  # Check if output is not None
                                tools_output.append({
                                    "tool_call_id": action["id"],
                                    "output": output
                                })
                            else:
                                logger.warning(f"<{self.name}> TASK:STEP-{action['id']} -Function {func_name} returned None")
                        elif func_name == "multi_tool_use.parallel":
                            for tool_use in arguments.get("tool_uses", []):
                                tool_use_func_name = tool_use.get("receipient_name","").removeprefix("functions")
                                tool_use_func_args = tool_use.get("parameters", {})
                                if tool_use_func_name in func_names:
                                    func = getattr(self, tool_use_func_name, None)
                                    logger.debug(f"<{self.name}> TASK:STEP- sub-step of multi_tool_use.parallel -calling tool {tool_use_func_name} with arguments {tool_use_func_args}")
                                    output = func(**tool_use_func_args)
                                    logger.debug(f"<{self.name}> TASK:STEP- sub-step of multi_tool_use.parallel -{tool_use_func_name} returned {output}")
                                    if output is not None:  # Check if output is not None
                                        tools_output.append({
                                            "tool_call_id": action["id"],
                                            "output": output
                                        })
                                    else:
                                        logger.warning(f"<{self.name}> TASK:STEP- sub-step of multi_tool_use.parallel -Function {func_name} returned None")
                                pass
                        else:
                            logger.warning(f"<{self.name}> TASK:STEP-{action['id']} -Function {func_name} not a configured tool.")
                            tools_output.append({
                                "tool_call_id": action["id"],
                                "output": f"Function {func_name} not a configured tool."
                            })
                        
                    if tools_output:
                        tools_output_head = ''
                        tools_output_1st = tools_output[0]
                        if 'output' in tools_output_1st:
                            tools_output_head = tools_output_1st['output']
                        else:
                            tools_output_head = tools_output_1st
                        logger.info(f"<{self.name}> TASK:STEPs -Function(s) returned {str(tools_output_head):.32s}...")
                        submit_retry_left = 2
                        while submit_retry_left:=submit_retry_left-1 > 0:
                            try:
                                self.run = self.llm_client.beta.threads.runs.submit_tool_outputs_and_poll(
                                thread_id=self.thread.id,
                                run_id=self.run.id,
                                tool_outputs=tools_output
                                )
                            except Exception as e:
                                if submit_retry_left > 0:
                                    try:
                                        self.run = self.llm_client.beta.threads.runs.retrieve(
                                            thread_id=self.run.thread_id,
                                            run_id=self.run.id,
                                        )                   
                                        logger.warn(f"<{self.name}> TASK:STEPs -Failed to submit tool outputs:{e}, recreating the run to retry.")
                                        if self.run.status in ["expired", "failed"]:
                                            self.run = self.llm_client.beta.threads.runs.create(
                                                thread_id=self.thread.id,
                                                assistant_id=self.assistant.id,
                                                timeout=300
                                            )
                                            logger.debug(f"<{self.name}> TASK:STEPs -Recreated run: {self.run.id}, new status: {self.run.status}")
                                    except Exception as err:
                                        logger.error(f"<{self.name}> TASK:STEPs -Failed to recreate run: {err} -after- submitting tool_output receiving {e}.")
                                else:
                                    logger.error(f"<{self.name}> TASK:STEPs -Failed to submit tool outputs:{e}")
                                msg_logger.error(f"{func_name} -> {self.name} - {tools_output} !!!received!!! {e}")
                            else:
                                logger.info(f"<{self.name}> TASK:STEPs -Tool outputs submitted successfully.")
                                msg_logger.info(f"{func_name} -> {self.name} - {tools_output}")
                                submit_retry_left = 0
                except Exception as e:
                    logger.error(f"<{self.name}> TASK:STEP - require action Error: {e} at {e.__traceback__.tb_lineno}")

            time.sleep(0.5)
            self.run = self.llm_client.beta.threads.runs.retrieve(
                thread_id=self.run.thread_id,
                run_id=self.run.id,
            )
            if self.run.status in ["expiried", "failed"]:
                logger.warning(f"<{self.name}> TASK: run status is {self.run.status}, this is unexpected. retrying...")
                retry_count -= 1
                if retry_count > 0:
                    self.run = self.llm_client.beta.threads.runs.create(
                        thread_id=self.thread.id,
                        assistant_id=self.assistant.id,
                        timeout=300
                    )
        logger.debug(f"<{self.name}> : - terminal run status is:{self.run.status=}, token_count: {self.run.usage}")
        if self.run.status == 'completed':
            messages = self.llm_client.beta.threads.messages.list(
                thread_id=self.run.thread_id,
                order='desc'
            )
            for msg in messages.data:
                role = self.name if msg.role == 'assistant' else (from_ if msg.role == 'user' else msg.role)
                content = msg.content[0].text.value
                logger.debug(f"<{self.name}> : -run.status is completed - examine messages: {msg.id} -{role.capitalize()}: {content}")
                result.insert(0,{"role":role, "content":content})
                if msg.id == current_message.id:
                    #messages is last entry first, if we hit current_message which is the prompt, don't need to go further back.
                    break
        else: 
            logger.warning(f"OpenAI run returned status {self.run.status} which is unexpected at this stage. next round will recreate a run.")

        logger.info(f"<{self.name}> TASK:END - reply to:{from_} -result:{[r.get('role','unknown').upper()+': '+r.get('content','').strip() for r in result]}")

        return json.dumps(result, indent=4) 

    def evaluate_agent(self, agent_name: str, score: int = 0, feedback: str = ''):
        """Provide evaluation of the response by an agent
        Args:
            agent_name: the name of the agent to evaluate
            score: positive if agent response meet expectation, netagive if did not
            feedback: how can the agent improve in the future
        Returns:
            None
        """
        logger.debug(f"<{self.name}> - evaluate_agent({agent_name},{score},{feedback})")
        the_other_agent = [a for a in agents if a.name==agent_name][0]
        if the_other_agent:
            the_other_agent.assistant.metadata["performance"] += score
            agent_dir = os.path.join(os.path.dirname(__file__), "agents")
            with open(os.path.join(agent_dir,agent_name+".feedback.json"), "a") as ff:
                json.dump({"timestamp":datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f"),"score":score, "feedback":feedback}, ff)
            return None
        else:
            logger.warn(f"<{self.name}> - evaluate_agent, unknown agent {agent_name}, can't evaluate, skipping...")
            raise Exception(f"Agent {agent_name} not found")

    def get_human_input(self, prompt: str = None) -> str:
        """Help AI get user input
        
        Args:
            prompt: the message shows to the user regarding what the question is about.
            
        Returns:
            str that the user entered into the input() function
        """
        logger.debug(f"<{self.name}> - get_human_input({prompt})")
        if prompt:
            result = input(f"\n***************<{self.name}> Needs User Input***************\n{prompt}:")
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
        logger.debug(f"<{self.name}> - chat_with_other_agent({agent_name},{message})")
        the_other_agent = [a for a in agents if a.name==agent_name][0]
        if the_other_agent:
            chat_result = the_other_agent.perform_task(message, self.name)

            return f"{chat_result}. Please use evaluate_agent tool to evaluate my response."
        else:
            raise Exception(f"Agent {agent_name} not found")

    def execute_module(self, module_name: str, method_name: str = None, args: list = [], **kwargs) -> dict[str, any]:
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
            >>> agent.execute_module('math', 'sqrt', args=[16]).strip()
            '{"output": 4.0}'
            >>> result = agent.execute_module('os', 'getcwd')
            >>> os.getcwd() in result
            True

        """
        # Prepare the command to execute
        if method_name:
            python_command = f"import json, {module_name};" \
                              "output={};" \
                             f"output['output'] = getattr({module_name}, '{method_name}')(*{args}, **{kwargs}); " \
                             "print(json.dumps(output))"
            python_mode = "-c"
            python_command_args = []
        else:
            python_command =  f"{module_name}"
            python_command_args = args
            python_mode = "-m"

        logger.debug(f"<{self.name}> execute_module - Executing {python_command}")
        # Execute the command as a subprocess
        try:
            result = subprocess.run(['python', python_mode, python_command, *python_command_args],
                                    capture_output=True, text=True, check=False, shell=False, timeout=120)
            if result.returncode == 0:
                logger.debug(f"<{self.name}> execute_module -Execution returned 0 exit code")
                if method_name:
                    return result.stdout
                else:
                    return result.stdout.strip()
            else:
                logger.error(f"<{self.name}> execute_module -Execution returned non-0 exit code. Output: {result.stdout}; Error: {result.stderr}")
                return f'Execution finished with error: {result.stderr}, Output: {result.stdout}'
        except subprocess.CalledProcessError as e:
            logger.error(f"<{self.name}> execute_module -Execution failed. Error: {e}")
            return f'Execution failed with error: {e}'
        except subprocess.TimeoutExpired:
            logger.error(f"<{self.name}> execute_module -Execution failed. Error: timeout")
            return f'Execution timed out, if this happens often, please check if this module execution is hang.'
        except Exception as e:
            logger.error(f"<{self.name}> execute_module -Execution failed. Error: {e}")
            return f'Execution failed with error: {e}'

    def execute_command(self, command_name: str, args: list = [], asynchronous: bool = False) -> dict[str]:
        """Execute a specified method from a Python module.

        Args:
            command_name: Name of the module to execute.
            args: Arguments for the method.
        
        Returns: 
            A dictionary with 'output' or 'error' as a key.

        Example::
            >>> agent = OpenAI_Agent("tester")
            >>> agent.execute_command('echo', args=['hello', 'world'])
            'hello world\\n'
            >>> result = agent.execute_command('pwd')
            >>> result == os.getcwd() + '\\n'
            True
            >>> agent.execute_command('ls', args=['non-exist.dir'])
            "Error: ls: cannot access 'non-exist.dir': No such file or directory\\n"
        """

        # Execute the command as a subprocess
        try:
            if asynchronous:
                process = subprocess.Popen([command_name, *args],
                                           stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE,
                                           text=True,
                                           shell=False,
                                           timeout=1200)
                self.procs.append(process)
                logger.debug(f"<{self.name}> - execute_command - started parallel process: {process.pid}")
            else:
                result = subprocess.run([command_name, *args],
                                        capture_output=True, text=True, check=False, shell=False, timeout=120)
                logger.debug("<{self.name}> - execute_command -returned {result}.")
                if result.returncode == 0:
                    return result.stdout
                else:
                    logger.error(f"<{self.name}> execute_command -Execution returned non-0 exit code. Error: {result.stderr}")
                    return f"Error: {result.stderr}"
        except subprocess.CalledProcessError as e:
            logger.error(f"<{self.name}> execute_command -Execution failed. Error: {e}")
            return f"error: {e.stderr}"
        except subprocess.TimeoutExpired:
            logger.error(f"<{self.name}> execute_command -Execution failed. Error: timeout")
            return f'Execution timed out, if this happens often, please check if this module execution is hang.'
        except Exception as e:
            logger.error(f"<{self.name}> execute_command -Execution failed. Error: {e}")
            return f'Execution failed with error: {e}'


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
