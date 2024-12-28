"""Core Agent Class code for OpenAI"""
import os
import json
import re
import sys
import time
from datetime import datetime
import contextlib
from openai import OpenAI, AzureOpenAI
import yaml
from ..config import config
from . import msg_logger, BaseAgent
from .agent_defs import standard_tools


class OpenAI_Agent(BaseAgent):
    """
    The OpenAI_Agent class represents an agent that interacts with the OpenAI API to perform various tasks using the OpenAI Assistant.

    Attributes:
        assistant (None): The OpenAI Assistant object.
        run (None): The OpenAI Run object.
        thread (None): The OpenAI Thread object.
        tools (None): The tools used by the agent.
        proj_dir (None): The project directory.
        llm_client (None): The OpenAI client.
        model (str): The model used by the agent.
        name (str): The name of the agent.

    Methods:
        __init__(self, agent_name: str): Initializes the OpenAI_Agent object.
        do_job(self, task: str = None) -> dict: Performs a job using the OpenAI Assistant.
        __str__(self): Allows printing of the agent's source code.
        __repr__(self): Allows printing of the agent's source code.
        my_own_code(self): Returns the agent's own source code.
        write_to_file(self, filepath: str, text: str) -> str: Writes text to a file.
        get_human_input(self, prompt: str = None) -> str: Helps the AI get user input.

    Example::
        >>> agent = OpenAI_Agent("pm", agent_config={"instruction": "You are a helpful assistant."})
        >>> agent.config.instruction
        'You are a helpful assistant.'

    """

    def __init__(self, agent_config: BaseAgent.AgentConfig = {}) -> None:
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
        """
        self.performance_factor = 1
        agent_name = agent_config.get("name", "noname")
        super().__init__(agent_name)
        self.logger.info(f"Initializing agent {agent_name}")
        self.name = agent_name
        self.threads = []

        self.config = self.AgentConfig(agent_config)

        self.temperature = self.config.temperature
        self.config.tools.extend(standard_tools)
        self.config.tools.extend([{"type": "code_interpreter"},
                                  {"type": "file_search"}])
        chat_function_tools = [tool for tool in self.config.tools
                               if tool['type'] == "function" and
                               tool['function']['name'] ==
                               "chat_with_other_agent"]
        try:
            if self.name in chat_function_tools[0]['function']['parameters']['properties']['agent_name']['enum']:
                chat_function_tools[0]['function']['parameters']['properties']['agent_name']['enum'].remove(
                    self.name)
        except KeyError as e:
            self.logger.warning(
                f"<{self.name}> - chat_with_other_agent tools function does not have agent_name parameter. Please check: {e}")
        except Exception as e:
            self.logger.warning(
                f"<{self.name}> - error setting other_agent_list in chat_with_other_agent tools function. Please check: {e}")
        if (config.USE_AZURE):
            self.model = config.AZURE_OPENAI_DEPLOYMENT_NAME
        else:
            self.model = config.OPENAI_MODEL

    def __enter__(self):
        """
        Enter the context manager.

        Returns:
            None
        """
        try:
            if (config.USE_AZURE):
                if config.AZURE_OPENAI_API_KEY is None:
                    self.logger.fatal(
                        f"Please provide AZURE_OPENAI_API_KEY as environment variable.  Cannot continue without AZURE_OPENAI_API_KEY.")
                    exit()
                self.logger.info("Using Azure OpenAI API")
                self.llm_client = AzureOpenAI(
                    api_key=config.AZURE_OPENAI_API_KEY)
            else:
                if config.OPENAI_API_KEY is None:
                    self.logger.fatal(
                        f"Please provide OPENAI_API_KEY as environment variable.  Cannot continue without OPENAI_API_KEY.")
                    exit()
                self.llm_client = OpenAI(api_key=config.OPENAI_API_KEY)
        except Exception as e:
            self.logger.fatal(
                f"Failed to establish OpenAI client with error {e}.")
            exit()

        try:
            # Try find assistant with this name (latest first)
            assistants = self.llm_client.beta.assistants.list(order="desc")
            for assistant in assistants:
                if (assistant.name == self.name
                        and assistant.model == self.model
                        and assistant.instructions == self.config.instruction):
                    self.assistant = self.llm_client.beta.assistants.retrieve(
                        assistant_id=assistant.id)
                    self.logger.debug(f"Found existing assistant {self.name}")
                    break
            else:
                self.assistant = self.llm_client.beta.assistants.create(
                    name=self.name,
                    instructions=self.config.instruction,
                    model=self.model,
                    tools=self.config.tools,
                    temperature=self.config.temperature * self.performance_factor
                )
                self.logger.debug(f"Created new assistant {self.name}")

            self.thread = self.llm_client.beta.threads.create(
                metadata={"issue": "generic"})
            self.threads.append(self.thread)
        except Exception as e:
            self.logger.fatal(
                f"Failed to create OPENAI Assistant, received Error {e}.")
            exit()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.debug(f"<{self.name}> - Exiting agent ...")
        if not self.llm_client is None:
            try:
                for thread in self.threads:
                    self.llm_client.beta.threads.delete(thread_id=thread.id)
            except Exception as e:
                self.logger.warning(
                    f"<{self.name}> - deleting thread received Error: {e}")
            try:
                self.llm_client.beta.assistants.delete(
                    assistant_id=self.assistant.id)
            except Exception as e:
                self.logger.warning(
                    f"<{self.name}> - deleting assistant received Error: {e}")

    def __str__(self) -> str:
        """Allow printing of myself (source code)

        Example::
            >>> agent = OpenAI_Agent("pm")
            >>> print(agent)
            <Agent: pm>
        """
        return f"<Agent: {self.name}>"

    # the following are function tools for OpenAI assistants.
    def ed_text_file(self, filepath: str, ed_script: str, return_content: bool = True) -> str:
        """Update a text to a file

        Args:
            filepath (str): The name of the file to write to
            text (str): The text to write to the file

        Returns:
            str: A message indicating success or failure

        """
        import re
        self.logger.debug(
            f"<{self.name}> - ed_text_file {filepath} - using script {ed_script}")
        try:
            with open(config.DIR_STRUCTURE_YAML, "r", encoding="utf-8") as f:
                dir_structure = yaml.safe_load(f.read())
            # reverse_dir_dict = {v: k for k, v in enumerate(list(dir_st.keys())[0] for dir_st in dir_structure)}
            # if filepath.startswith("/"):
            #     dir_structure = dir_structure[reverse_dir_dict['/']]['/']
            # elif not filepath.startswith("./"):
            #     dir_structure = dir_structure[reverse_dir_dict['.']]['.']
            # for dn in filepath.split('/'):
            #     reverse_dir_dict = {v: k for k, v in enumerate(list(dir_st.keys())[0] if isinstance(dir_st, dict) else dir_st for dir_st in dir_structure)}
            #     dir_structure = dir_structure[reverse_dir_dict[dn]][dn]
            # if not isinstance(dir_structure, str):
            #     result = f"Error: {filepath} in {config.DIR_STRUCTURE_YAML} is listed as a directory, you should not update a dir using ed_text_file tool."
            #     return result
            if not filepath.removeprefix('./') in [next(iter(dir_st.keys())).removeprefix('./') for dir_st in dir_structure]:
                result = f"Error: {filepath} in {
                    config.DIR_STRUCTURE_YAML} is not listed as a file, you should not update a file using ed_text_file tool."
                return result

        except KeyError as e:
            if filepath == config.DIR_STRUCTURE_YAML:
                self.logger.debug(f"<{self.name}> - ed_text_file - updating {
                    config.DIR_STRUCTURE_YAML} for the first time...")
            else:
                self.logger.error(f"<{self.name}> - ed_text_file Failed to read config file {
                    config.DIR_STRUCTURE_YAML}, received Error {e}.")
                result = f"Error: {filepath} is not listed in the {
                    config.DIR_STRUCTURE_YAML} dir structure file, you should not update a file before you design the directory structure and make sure with each file needed."
                return result
        except Exception as e:
            self.logger.error(f"<{self.name}> - ed_text_file Failed to read config file {
                config.DIR_STRUCTURE_YAML}, received Error {e}.")
            return f"Error: Cannot read configured directory structure file {config.DIR_STRUCTURE_YAML} ____ {e}"

        if os.path.exists(filepath):
            self.logger.debug(f"<{self.name}> - ed_text_file file {
                filepath} already exists, reading in to be changed")
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.readlines()
        else:
            self.logger.debug(
                f"<{self.name}> - ed_text_file file {filepath} does not exist, creating new")
            content = []
        old_content_lines = len(content)
        expect_line_cmd_spec = True
        for script_line in ed_script.split("\n"):
            if expect_line_cmd_spec:
                if not script_line:
                    continue
                match = re.match(r'(\d+|\$)?,?(\d+|\$)?([acd])$', script_line)
                if match:
                    command = match.group(3)
                    start_line = int(match.group(1).replace(
                        '$', str(old_content_lines)) if match.group(1) else 1) - (command != 'a')
                    end_line = int(match.group(2).replace('$', str(old_content_lines))) if match.group(
                        2) else start_line + (command != 'a')
                    new_lines = []
                    if command == 'd':
                        content[start_line:end_line] = new_lines
                    else:
                        expect_line_cmd_spec = False
                else:
                    self.logger.error(
                        f"<{self.name}> - ed_text_file wrongly formed ed_script ")
                    return f"ed_text_file: wrongly formed ed_script command: {script_line}. Only accept proper ed script in the format generated by diff -e. for example ``37,$d\n`, `25,31c\nchange to new line\n.\n`, or 0a\nAdd a line\n.\n`. Later change blocks should be provided first so that the line specifiers are not affected by the changes."
            else:
                if script_line.strip() == '.':
                    content[start_line:end_line] = new_lines
                    expect_line_cmd_spec = True
                    continue
                if command == 'a' or command == 'c':
                    new_lines.append(script_line + '\n')

        try:
            match filepath:
                case fn if fn.endswith(".yaml") or fn.endswith(".yml"):
                    self.logger.debug(
                        f"<{self.name}> - ed_text_file updating yaml file {filepath}")
                    yaml.safe_load("\n".join(content))
                case fn if fn.endswith(".json"):
                    self.logger.debug(
                        f"<{self.name}> - ed_text_file updating json file {filepath}")
                    json.loads("\n".join(content))
            directory = os.path.dirname(filepath)
            if directory:
                os.makedirs(directory, exist_ok=True)

            with open(filepath, 'w', encoding="utf-8") as f:
                f.writelines(content)

            self.logger.info(
                f"<{self.name}> - ed_text_file {filepath} successfully.")
        except yaml.YAMLError as e:
            self.logger.debug(f"<{self.name}> - the update resulted in corrupted yaml file {
                filepath}, please read the file first, and make proper changes. Error {e}")
            result = f"<{
                self.name}> - the update resulted in corrupted yaml file {filepath}, Error: {e}"
        except json.JSONDecodeError as e:
            self.logger.debug(f"<{self.name}> - the update resulted in corrupted json file {
                filepath}, please read the file first, and make proper changes. Error {e}")
            result = f"<{
                self.name}> - the update resulted in corrupted json file {filepath}, Error: {e}"
        except Exception as e:
            self.logger.error(
                f"<{self.name}> - ed_text_file Failed to write to file {filepath}, received Error {e}.")
            result = f"<{
                self.name}> - ed_text_file Failed to write to file {filepath}, Error: {e}"
        else:
            result = {"filepath": filepath,
                      "status": "update successful", "new content": content}
        return json.dumps(result)

    def perform_task(self, task: str = None, from_: str = "Unknown", context: dict = {}) -> str:
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
        retry_count = config.RETRY_COUNT
        self.logger.info(f"<{self.name}> TASK:BEGIN from:{from_} - task:{task} - "
                         f"context:{context} retries left:{retry_count}")
        if not task:
            task = self.config.instruction
        try:
            issue_no = str(context.get('issue', ''))
            sorted_threads = sorted(self.threads, key=lambda x: len(x.metadata.get('issue', ''))
                                    - len(x.metadata.get('issue',
                                          '').removeprefix(issue_no)),
                                    reverse=True)
            thread = sorted_threads[0]
            if issue_no and thread.metadata.get('issue', '') == 'generic':
                thread = self.llm_client.beta.threads.create(
                    metadata={"issue": issue_no})
                self.threads.append(thread)

            # making sure wait until other runs are no longer active before creating new one
            wait_other_runs_timeout = 300
            for run_ in self.llm_client.beta.threads.runs.list(thread_id=thread.id):
                while run_.status in ['active'] and (wait_other_runs_timeout := wait_other_runs_timeout - 1) > 0:
                    self.logger.debug(
                        f"<{self.name}> TASK:PREP - {thread.id} - {run_.id} - {run_.status}")
                    time.sleep(1)
            current_message = self.llm_client.beta.threads.messages.create(
                thread_id=thread.id,
                role='user',
                content=task
            )
            self.run = self.llm_client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=self.assistant.id,
                tool_choice=self.config.tool_choice,
                additional_instructions=self.additional_instructions,
                temperature=self.temperature * self.performance_factor,
                timeout=300
            )
        except Exception as e:
            self.logger.warning(
                f"<{self.name}> TASK:STEP - tool func perform_task run into error {e}")
            return f"{e}"
        msg_logger.info(f"{from_} >> {self.name} - {task}")
        result = []
        while self.run.status in ["queued", "in_progress", "requires_action"]:
            self.logger.debug(f"<{self.name}>-{self.run.status=}")
            if self.run.status == "requires_action":
                try:
                    required_actions = self.run.required_action.submit_tool_outputs.model_dump()
                    self.logger.debug(
                        f"<{self.name}> TASK:STEPs -tool_calls: {required_actions}")
                    tools_output = []
                    for action in required_actions['tool_calls']:
                        func_name = action['function']['name']
                        try:
                            arguments = json.loads(
                                action['function']['arguments'])
                            func_names = [item['function']['name']
                                          for item in self.config.tools if item['type'] == "function"]
                            msg_logger.info(
                                f"{self.name} -> {func_name} {json.dumps(arguments, indent=2)}")
                            self.logger.debug(
                                f"<{self.name}> TASK:STEP-{action['id']} - {func_name} {arguments}")
                            if func_name in func_names:
                                # prevent chat back to the person already in a chat:
                                if func_name == "chat_with_other_agent" and "agent_name" in arguments and arguments['agent_name'] == from_:
                                    output = f"You are already chatting with {
                                        from_}, please reply to them instead of starting a new chat."
                                else:
                                    func = getattr(self, func_name, None)
                                    self.logger.debug(f"<{self.name}> TASK:STEP-{action['id']} -calling tool {
                                        func_name} with arguments {arguments}")
                                    output = func(**arguments)
                                self.logger.debug(
                                    f"<{self.name}> TASK:STEP-{action['id']} -called tool {func_name} returned {output}")
                                if output is not None:  # Check if output is not None
                                    tools_output.append({
                                        'tool_call_id': action['id'],
                                        'output': f"{output}"
                                    })
                                else:
                                    self.logger.warning(
                                        f"<{self.name}> TASK:STEP-{action['id']} -Function {func_name} returned None")
                            elif func_name == "multi_tool_use.parallel":
                                multi_tool_use_output = ''
                                for tool_use in arguments.get('tool_uses', []):
                                    tool_use_func_name = tool_use.get(
                                        'recipient_name', "").removeprefix("functions.")
                                    tool_use_func_args = tool_use.get(
                                        'parameters', {})
                                    if tool_use_func_name in func_names:
                                        func = getattr(
                                            self, tool_use_func_name, None)
                                        self.logger.debug(f"<{self.name}> TASK:STEP- sub-step of multi_tool_use.parallel -calling tool {
                                            tool_use_func_name} with arguments {tool_use_func_args}")
                                        output = func(**tool_use_func_args)
                                        self.logger.debug(f"<{self.name}> TASK:STEP- sub-step of multi_tool_use.parallel -{
                                            tool_use_func_name} returned {output}")
                                        if output is not None:  # Check if output is not None
                                            multi_tool_use_output += f"Output of {tool_use.get('recipient_name', "")}:\n{
                                                output}\n\n"
                                        else:
                                            self.logger.warning(
                                                f"<{self.name}> TASK:STEP- sub-step of multi_tool_use.parallel -Function {func_name} returned None")

                                tools_output.append({
                                    'tool_call_id': action['id'],
                                    'output': multi_tool_use_output
                                })
                            else:
                                self.logger.warning(
                                    f"<{self.name}> TASK:STEP-{action['id']} -Function {func_name} not a configured tool.")
                                tools_output.append({
                                    'tool_call_id': action['id'],
                                    'output': f"Function {func_name} not a configured tool."
                                })
                        except Exception as e:
                            tools_output.append({
                                'tool_call_id': action['id'],
                                'output': f"Error: calling tool {func_name}, received error {e}"
                            })

                    if tools_output:
                        tools_output_head = ''
                        tools_output_1st = tools_output[0]
                        if "output" in tools_output_1st:
                            tools_output_head = tools_output_1st['output']
                        else:
                            tools_output_head = tools_output_1st
                        self.logger.debug(
                            f"<{self.name}> TASK:STEPs -Function(s) returned {str(tools_output_head)}")
                        self.logger.info(
                            f"<{self.name}> TASK:STEPs -Function(s) returned {str(tools_output_head):.32s}...")
                        submit_retry_left = 2
                        while submit_retry_left := submit_retry_left - 1 > 0:
                            try:
                                self.run = self.llm_client.beta.threads.runs.submit_tool_outputs_and_poll(
                                    thread_id=thread.id,
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
                                        self.logger.warn(
                                            f"<{self.name}> TASK:STEPs -Failed to submit tool outputs:{e}, recreating the run to retry.")
                                        if self.run.status in ["expired", "failed"]:
                                            self.run = self.llm_client.beta.threads.runs.create(
                                                thread_id=thread.id,
                                                tool_choice=self.config.tool_choice,
                                                assistant_id=self.assistant.id,
                                                timeout=300
                                            )
                                            self.logger.debug(
                                                f"<{self.name}> TASK:STEPs -Recreated run: {self.run.id}, new status: {self.run.status}")
                                    except Exception as err:
                                        self.logger.error(f"<{self.name}> TASK:STEPs -Failed to recreate run: {
                                            err} -after- submitting tool_output receiving {e}.")
                                else:
                                    self.logger.error(
                                        f"<{self.name}> TASK:STEPs -Failed to submit tool outputs:{e}")
                                msg_logger.error(
                                    f"{self.name} <- {func_name} - {json.dumps(tools_output, indent=2)} !!!received!!! {e}")
                            else:
                                self.logger.info(
                                    f"<{self.name}> TASK:STEPs -Tool outputs submitted successfully.")
                                msg_logger.info(
                                    f"{self.name} <- {func_name} - {json.dumps(tools_output, indent=2)} ")
                                submit_retry_left = 0
                except Exception as e:
                    self.logger.error(
                        f"<{self.name}> TASK:STEP - require action Error: {e} at {e.__traceback__.tb_lineno}")
                    if retry_count < 0:
                        self.logger.fatal(
                            f"<{self.name}> TASK:STEP - require action exceeded max retry_count. exiting...")
                        sys.exit(1)
                    else:
                        retry_count -= 1
                        self.logger.warning(
                            f"<{self.name}> TASK:STEP - retry_count remaining: {retry_count} -retrying...")

            time.sleep(0.5)
            self.run = self.llm_client.beta.threads.runs.retrieve(
                thread_id=self.run.thread_id,
                run_id=self.run.id,
            )
            if self.run.status in ["expiried", "failed"]:
                retry_count -= 1
                if retry_count > 0:
                    self.logger.warning(f"<{self.name}> TASK: thread.run status is "
                                        f"{self.run.status}, retry_count remaining: "
                                        f"{retry_count} -retrying...")
                    self.logger.debug(f"<{self.name}> run received: "
                                      f"{self.run.last_error!r}")
                    if (last_error := getattr(self.run, 'last_error', {})) and (error_code := getattr(last_error, 'code', {})):
                        self.logger.warning(
                            f"<{self.name}> TASK: thread.run returned error {error_code}")
                        if error_code == 'rate_limit_exceeded':
                            match = None
                            if (last_error_message := getattr(last_error,
                                                              "message", '')):
                                match = re.search(r'Try again in (\d+) seconds',
                                                  last_error_message)
                            wait_seconds = int(match.group(1)) if match else 15
                            self.logger.warning(
                                f"<{self.name}> TASK: thread.run received 'rate_limit_exceeded', waiting for {wait_seconds} sec before retrying...")
                            time.sleep(wait_seconds)
                    self.run = self.llm_client.beta.threads.runs.create(
                        thread_id=thread.id,
                        tool_choice=self.config.tool_choice,
                        assistant_id=self.assistant.id,
                        timeout=300
                    )
                else:
                    self.logger.error(f"<{self.name}> TASK: thread.run status is "
                                      f"{self.run.status}, this is unexpected. "
                                      "max_retry count reached. exiting...")
                    return f"Task was not completed, it reported status {self.run.status}."

        self.logger.debug(f"<{self.name}> : - TASKs all processed - run "
                          f"{self.run.id} status is:{self.run.status}, token_count: {self.run.usage}")
        if self.run.status == 'completed':
            messages = self.llm_client.beta.threads.messages.list(
                thread_id=self.run.thread_id,
                order='desc'
            )
            for msg in messages.data:
                role = self.name if msg.role == 'assistant' else (
                    from_ if msg.role == 'user' else msg.role)
                content = msg.content[0].text.value if msg.content else ""
                self.logger.debug(f"<{self.name}> : -run {self.run.id} - examine messages: {
                    msg.id} -{role.capitalize()}: {content}")
                result.insert(0, {'role': role, 'content': content})
                if msg.id == current_message.id:
                    # messages is last entry first, if we hit current_message which is the prompt, don't need to go further back.
                    break
        else:
            self.logger.warning(f"OpenAI run returned status {
                self.run.status} which is unexpected at this stage.")
            result.append(
                {"content": f"Task was not completed, the assistant reported run status {self.run.status}."})

        self.logger.info(f"<{self.name}> TASK:END - reply to {from_}: {[r.get('role', "unknown").upper(
        ) + ': ' + r.get('content', "").strip() for r in result if r.get('role', "unknow") != from_]}")

        return json.dumps(result, indent=4)

    def evaluate_agent(self, agent_name: str, score: int = 0, additional_instructions: str = "") -> str:
        """Provide evaluation of the response by an agent
        Args:
            agent_name: the name of the agent to evaluate
            score: positive if agent response meet expectation, netagive if did not
            additional_instructions: how can the agent improve in the future
        Returns:
            status of the evaluation
        """
        self.logger.debug(
            f"<{self.name}> - evaluate_agent({agent_name},{score},{additional_instructions})")
        other_agents = [a for a in BaseAgent.instances(
            True) if a.name == agent_name]
        if other_agents:
            the_other_agent = other_agents[0]
        else:
            self.logger.warning(
                f"<{self.name}> - evaluate_agent does not recognize {agent_name} as a valid agent.")
            return f"<{self.name}> - evaluate_agent does not recognize {agent_name} as a valid agent."
        if the_other_agent:
            the_other_agent.performance_factor *= 1 + max(score, 10) / 100
            if additional_instructions:
                the_other_agent.additional_instructions = additional_instructions
            agent_dir = os.path.join(os.path.dirname(__file__), "agents")
            new_eval = {"timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f"),
                        "evaluated by": self.name,
                        "score": score,
                        "additional_instructions": additional_instructions
                        }
            new_eval_yaml = yaml.dump(
                [new_eval], default_flow_style=False, sort_keys=False)
            with open(os.path.join(agent_dir, agent_name + ".feedback.yaml"), 'a+') as yamlfile:
                yamlfile.write("\n" + new_eval_yaml)
            self.logger.debug(f"<{self.name}> - evaluate_agent, agent {agent_name}"
                              f" new performance score is {the_other_agent.performance_factor}.")
            return "Thanks for your feedback"
        else:
            self.logger.warning(f"<{self.name}> - evaluate_agent, unknown agent "
                                f"{agent_name}, can't evaluate, skipping...")
            return f"Agent {agent_name} was not found, can't evaluate."

    def chat_with_other_agent(self, agent_name: str, message: str, issue: str = '') -> str:
        """Chat with another agent

        Args:
            agent_name: the name of the agent to chat with
            message: the message to send to the agent

        Returns:
            str: the response from the agent
        """
        self.logger.debug(
            f"<{self.name}> - chat_with_other_agent({agent_name},{message},{issue})")
        the_other_agent = [a for a in BaseAgent.instances(
            True) if a.name == agent_name][0]
        if the_other_agent:
            chat_result = the_other_agent.perform_task(
                message, self.name, {"issue": issue})
            return f"{chat_result}."
        else:
            raise Exception(f"Agent {agent_name} not found")

    def upload_issues_as_vector_store(self, issue_number: str = None) -> str:
        import os
        ISSUE_VECTOR_STORE_NAME = "issues"
        # Create a vector store caled "Financial Statements"
        try:
            existing_vector_stores = self.llm_client.beta.vector_stores.list()
            for existing_vector_store in existing_vector_stores.data:
                if existing_vector_store.name == ISSUE_VECTOR_STORE_NAME:
                    self.issue_vector_store = existing_vector_store
                    break
            else:
                self.issue_vector_store = self.llm_client.beta.vector_stores.create(
                    name=ISSUE_VECTOR_STORE_NAME)

            uploaded_issue_file_ids = self.llm_client.beta.vector_stores.files.list(
                vector_store_id=self.issue_vector_store.id)

            uploaded_issues = []
            try:
                for f in uploaded_issue_file_ids.data:
                    uploaded_issues.append(
                        self.llm_client.files.retrieve(f.id))
            except Exception as e:
                self.logger.warning(
                    f"<{self.name}> - some files in the vec store cannot be retrieved.")

            issue_files_to_upload = []
            issue_files = [os.path.join(root, file) for root, _, files in os.walk(
                "issue_board") for file in files if file.endswith(".json")]
            for issue_file in issue_files:
                last_uploaded_at = max(
                    [upliss.created_at for upliss in uploaded_issues if upliss.filename == os.path.basename(issue_file)], default=0)
                if os.stat(issue_file).st_mtime > last_uploaded_at:
                    issue_files_to_upload.append(issue_file)
                else:
                    continue
            if issue_files_to_upload:
                with contextlib.ExitStack() as stack:
                    file_streams = [stack.enter_context(
                        open(path, "rb")) for path in issue_files_to_upload]
                    file_batch = self.llm_client.beta.vector_stores.file_batches.upload_and_poll(
                        vector_store_id=self.issue_vector_store.id, files=file_streams
                    )
            else:
                file_batch = {
                    "status": "success - no new files to upload",
                    "file_ids": [],
                }
        except Exception as e:
            self.logger.error(
                f"<{self.name}> - upload files received error {e} - line {e.__traceback__.tb_lineno}")
        else:
            self.logger.debug(f"<{self.name}> - uploaded files for vector store {
                self.issue_vector_store.id}: {file_batch!r}")

        self.assistant = self.llm_client.beta.assistants.update(
            assistant_id=self.assistant.id,
            tool_resources={"file_search": {
                "vector_store_ids": [self.issue_vector_store.id]}},
        )
        for agt in BaseAgent.instances(True):
            agt.assistant = agt.llm_client.beta.assistants.update(
                assistant_id=agt.assistant.id,
                tool_resources={"file_search": {
                    "vector_store_ids": [self.issue_vector_store.id]}},
            )
        return "success"

    def write_all_files_to_temp_dir(self, thread: str, output_path: str = "tmp"):
        """save OpenAI tools_resources files locally"""
        file_ids = [
            file_id
            for m in self.llm_client.beta.threads.messages.list(thread_id=thread.id)
            for file_id in m.file_ids
        ]
        for file_id in file_ids:
            file_data = self.llm_client.files.content(file_id)
            file_data_bytes = file_data.read()
            with open(output_path + "/" + file_id, 'wb') as file:
                file.write(file_data_bytes)


if __name__ == "__main__":
    """quick test of the pm class"""
    import doctest
    doctest.testmod()
