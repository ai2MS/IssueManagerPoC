
import os
import json
import time
import ollama
from openai import OpenAI
from .utils import current_directory, standard_tools
from . import logger, agents

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
    """
    assistant = None
    run = None
    thread = None
    tools = None
    llm_client = None
    llm_service = ollama
    model = "gpt-4-turbo-2024-04-09"
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

        """
        logger.info(f"Initializing agent {agent_name}")
        self.file_name = __file__
        self.name = agent_name
        if agent_dir is None:
            agent_dir = current_directory()
        try:
            config_json = os.path.join(agent_dir, f"{agent_name}.json")
            agent_config = json.load(open(config_json))
            self.instruction = agent_config['instruction']
            self.tools = standard_tools
            self.tools.extend(agent_config['tools'])
        except json.decoder.JSONDecodeError:
            logger.fatal(f"{agent_name}m.json file is not valid JSON. Please fix the pm.json file.")
            exit()
        except FileNotFoundError:
            logger.fatal(f"{agent_name}.json file not found. Please create a pm.json file in the current directory.")
            exit()
        except KeyError:
            logger.fatal(f"{agent_name}.json file does not contain an 'instruction' key. Please add an 'instruction' key to the pm.json file.")
            exit()

        openai_api_key=os.environ.get("OPENAI_API_KEY", None)
        if openai_api_key is None:
            logger.fatal(f"Please provide OPENAI_API_KEY as environment variable.  Cannot continue without OPENAI_API_KEY.")
            exit()

        try:
            self.llm_client = OpenAI(api_key=openai_api_key)
        except Exception as e:
            logger.fatal(f"Failed to establish OPENAI client with error {e}.")
            exit()

        try:
            # Try find assistant with this name (latest first)
            assistants = self.llm_client.beta.assistants.list(order="desc")
            for assistant in assistants:
                if (assistant.name == agent_name
                        and assistant.model == self.model 
                        and assistant.instructions == self.instruction):
                    self.assistant = self.llm_client.beta.assistants.retrieve(assistant_id=assistant.id)
                    logger.debug(f"Found existing assistant {agent_name}")
                    break
            else:
                self.assistant = self.llm_client.beta.assistants.create(
                    name=agent_name,
                    instructions=self.instruction,
                    model=self.model, 
                    tools=self.tools,
                )
                logger.debug(f"Created new assistant {agent_name}")

            self.thread = self.llm_client.beta.threads.create()
        except Exception as e:
            logger.fatal(f"Failed to create OPENAI Assistant, received Error {e}.")
            exit()


    def perform_task(self, task: str = None) -> dict:
        """
        Perform a job using the OpenAI Assistant.

        Args:
            task (str, optional): The task to be performed. If not provided, the instruction from the agent's JSON configuration file will be used. Defaults to None.

        Returns:
            dict: A dictionary containing the results of the job. The keys of the dictionary represent the roles (e.g., 'User', 'Assistant') and the values represent the corresponding messages.

        Raises:
            None

        """
        logger.info(f"TASK:BEGIN <{self.name}>-{task}")
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
        result = {}
        while self.run.status in ["queued", "in_progress", "requires_action"]:
            logger.debug(f"{self.run.status=}")
            if self.run.status == "requires_action":
                required_actions = self.run.required_action.submit_tool_outputs.model_dump()
                logger.info(f"TASK:STEP <{self.name}>-tool_calls: {required_actions}")
                tools_output = []
                for action in required_actions["tool_calls"]:
                    func_name = action["function"]["name"]
                    arguments = json.loads(action["function"]["arguments"])
                    func_names = [item['function']['name'] for item in self.tools if item['type'] == 'function']
                    if func_name in func_names:
                        func = getattr(self, func_name, None)
                        logger.debug(f"will call tool {func_name} with arguments {arguments}")
                        output = func(**arguments)
                        logger.debug(f"tool {func_name} returned {output}")
                        if output is not None:  # Check if output is not None
                            tools_output.append({
                                "tool_call_id": action["id"],
                                "output": output
                            })
                        else:
                            logger.warn(f"Function {func_name} returned None")
                    else:
                        logger.warn("Function not found")
                    
                if tools_output:
                    logger.info(f"TASK:STEP <{self.name}>-tool_outputs: {tools_output}")
                    try:
                        self.run = self.llm_client.beta.threads.runs.submit_tool_outputs_and_poll(
                        thread_id=self.thread.id,
                        run_id=self.run.id,
                        tool_outputs=tools_output
                        )
                    except Exception as e:
                        logger.error("Failed to submit tool outputs:", e)
                    else:
                        logger.info("Tool outputs submitted successfully.")
     
            time.sleep(0.5)
            self.run = self.llm_client.beta.threads.runs.retrieve(
                thread_id=self.run.thread_id,
                run_id=self.run.id,
            )
        logger.debug(f"after while wait ... {self.run.status=}")
        if self.run.status == 'completed':
            messages = self.llm_client.beta.threads.messages.list(
                thread_id=self.run.thread_id
            )
            for msg in messages.data:
                role = msg.role
                content = msg.content[0].text.value
                logger.debug(f"run.status is completed - msg is -{role.capitalize()}: {content}")
                result[role.capitalize()]=content
        else: 
            logger.warn(f"OpenAI run returned status {self.run.status} which is unexpected at this stage.")

        logger.info(f"TASK:END <{self.name}>-result:{result}")
        return result

    def __str__(self):
        """Allow printing of myself (source code)"""
        return json.dumps(self.my_own_code())
    def __repr__(self):
        """Allow printing of myself (source code)"""
        return json.dumps(self.my_own_code())

    def my_own_code(self):
        """Return my own source code.
        This will allow the AI to request my own source code for analyzing and self update.
        """
        logger.debug("my_own_code")
        with open(self.file_name, "r") as f:
            code = f.read()
        return code
    
    def write_to_file(self, filename: str, text: str) -> str:
        """Write text to a file

        Args:
            filename (str): The name of the file to write to
            text (str): The text to write to the file

        Returns:
            str: A message indicating success or failure
        """
        logger.debug(f"write_to_file {filename} {text}")
        try:
            directory = os.path.dirname(filename)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(filename, "w", encoding="utf-8") as f:
                f.write(text)
            logger.info("write"+filename)
            return "File written to successfully."
        except Exception as e:
            return f"Error: {str(e)} ____ {e}"

    def get_human_input(self, prompt: str = None) -> str:
        """Help AI get user input
        
        Args:
            prompt: the message shows to the user regarding what the question is about.
            
        Returns:
            str that the user entered into the input() function
        """
        logger.debug(f"get_human_input {prompt}")
        if prompt:
            result = input(prompt+":")
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
            the_other_agent.perform_task(message)
        else:
            raise Exception(f"Agent {agent_name} not found")


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
    current_dir = current_directory()
    parent_dir = os.path.dirname(current_dir)
    project_dir = os.path.join(parent_dir, 'proj_test')
    print(f"Testing using {project_dir}...")
    os.makedirs(project_dir, exist_ok=False)
    my_pm = OpenAI_Agent("pm")
    my_pm.do_job("Start a new software project by asking the user to provide new requirements.")
    os.removedirs(project_dir)
