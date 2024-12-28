"""Ollama Agent, won't use until local model are possible."""
import os
import json
import yaml
import ollama
from datetime import datetime
from typing import Sequence, Self
from ..config import config
from ..utils import issue_manager, dir_structure, execute_module, execute_command
from .agent_defs import standard_tools
from . import msg_logger, BaseAgent


class Ollama_Agent(BaseAgent):

    def __init__(self, agent_config: BaseAgent.AgentConfig = {}) -> None:
        # use agent_config
        agent_config_dict = agent_config.to_dict()
        agent_config_dict.setdefault("model", agent_config_dict.get("model") or
                                     config.OLLAMA_DEFAULT_BASE_MODEL or "mistral-nemo")
        agent_config_dict.setdefault("name", agent_config_dict.get(
            "name", "noname").replace(" ", "_"))
        super().__init__(agent_config_dict.get("name"))
        self.config = self.AgentConfig(agent_config_dict)
        self.logger.debug("loaded agent %s config from parameter agent_config: %s as %s",
                          self.name, agent_config, self.config)

        self.llm_client = ollama.Client(host=config.OLLAMA_HOST)

        if self.config.use_tools:
            self.tools = self.config.tools
            self.tools.extend(standard_tools)
        else:
            self.tools = []

        # Initialize conversation with a user query
        self.messages = []
        self.model_initialized = False
        self.logger.info("Initializing agent %s", self.name)

    def __enter__(self) -> Self:
        if self.model_initialized:
            return self
        existing_models = self.llm_client.list()
        for model in existing_models.get("models", []):
            model_name = model.get("name") or model.get("model")
            if model_name.partition(":")[0] == self.config.name:
                self.logger.debug(f"found existing model {self.name}")
                break
        else:
            # Note that Ollama uses "model" property to represent roughly an "agent" concept
            # the model name represents an object that is of a certain model type with initial system prompt
            # so the model name in Ollama is not the model type, rather it's an entity that includes system prompt
            modelfile = (f"FROM {self.config.model}\n"
                         f"SYSTEM {self.config.instruction!r}\n"
                         f"PARAMETER temperature {self.config.temperature}")
            self.logger.info("creating ollama model %s", modelfile)
            response = self.llm_client.create(
                model=self.name, modelfile=modelfile)
            self.logger.info("created ollama model received %s", response)
        self.model_initialized = True

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.debug(f"<{self.name}> - Exiting agent ...")
        if not self.llm_client is None:
            try:
                self.llm_client.delete(self.name)
            except Exception as e:
                self.logger.warning(
                    f"<{self.name}> - deleting thread received Error: {e}")

    def __str__(self) -> str:
        """Allow printing of myself (source code)

        """
        return f"<Agent: {self.name}>"

    def messages_append(self, new_message: object):
        new_message_len = len(f"{new_message}")
        while len(f"{self.messages}") + new_message_len > self.config.context_window_size * 1024 * 0.75:
            del self.messages[1]
        self.messages.append(new_message)

    # method to list/read/write issues

    def perform_task(self, task: str = '', from_: str = "Unknown", context: dict = {}) -> str:
        self.__enter__()
        self.messages.append({'role': 'user', 'content': task})
        if self.tools:
            msg_logger.info("%s >> %s - %s (support tools)",
                            from_, self.name, task)
            self.logger.info("%s >> %s - %s (support tools)",
                             from_, self.name, task)
            response = self.llm_client.chat(
                model=self.name, messages=self.messages, tools=self.tools)
        else:
            msg_logger.info("%s >> %s - %s (no tools)", from_, self.name, task)
            self.logger.info("%s >> %s - %s (no tools)",
                             from_, self.name, task)
            response = self.llm_client.chat(
                model=self.name, messages=self.messages)

        # Add the model's response to the conversation history
        self.messages_append(response['message'])

        # Process function calls made by the model
        if response['message'].get('tool_calls'):
            self.logger.debug("<%s> The session is trying to use tools: %s",
                              self.name, response['message']['tool_calls'])
            func_names = [item['function']['name']
                          for item in self.tools if item['type'] == "function"]
            for tool in response['message']['tool_calls']:
                arguments = tool['function']['arguments']
                func_name = tool['function']['name']
                if func_name in func_names:
                    func = getattr(self, func_name, None)
                    try:
                        function_response = func(
                            **arguments) if func else f"Error {func_name} is configured as a tool but is not a method I have."
                        self.logger.debug(
                            "calling <%s> returned: %s", func_name, function_response)
                    except Exception as e:
                        function_response = f"calling {
                            func_name} failed with Error: {e!r}"
                        self.logger.error(
                            "calling <%s(%s)> run into Error: %s", func_name, arguments, e, exc_info=e)
                    # Add function response to the conversation
                    self.messages_append(
                        {
                            'role': 'tool',
                            'content': function_response,
                        }
                    )
                    self.logger.debug(
                        "<%s> - tool %s returned: %s", self.name, func_name, function_response)
                else:
                    self.messages_append(
                        {
                            'role': 'tool',
                            'content': f"{func_name} is not a configured tool."
                        }
                    )
                    # Second API call: Get final response from the model
            final_response = self.llm_client.chat(
                model=self.name, messages=self.messages)
            self.logger.debug(
                f"<{self.name}> - {final_response['message']['content']}")

            return str(final_response['message']['content'])
        else:
            self.logger.debug(f"<{self.name}> The session didn't use tools. Its response was:{
                              response['message']}")
            return response['message']['content']

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


def test():
    with Ollama_Agent("test_agent", agent_config={"base_model": "llama3.2",
                                                  "instruction": "",
                                                  "temperature": 0.25,
                                                  "name": "test_agent",
                                                  "tools": [{
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
                                                  }]
                                                  }) as test_agent:
        test_agent.perform_task(
            input("what do you want to say to the test_agent:"))


if __name__ == "__main__":
    # testing locally
    test()
