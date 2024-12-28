"""The Orchestrator agent logic
This is the agent to ensure every step follows software development process. 
The goal of this agent is not to innovate, rather, you check other agent's responses, and make sure they adhere to required process.
"""

import contextlib
import json
from re import A
from pydantic import BaseModel
from . import logger
from .utils import issue_manager
from .defs import BaseAgent, AgentFactory
from .defs import ollama_agent, openai_agent
from .defs.agent_defs import agent_roles


class Orchestrator(BaseAgent):

    def follow_up(self, agent_names: list = [], issue_number: str = '') -> list:
        """
        Follow up on open issues and assign them to appropriate agents.

        This method retrieves open issues, sorts them by priority and issue number, 
        and assigns them to agents based on their current status and assignee. 
        It also evaluates agent responses and updates issue details accordingly.

        Args:
            agent_names (list): List of agent names to filter issues by assignee. 
                                If empty, all open issues are considered.
            issue_number (str): Specific issue number to filter open issues. 
                                If empty, all open issues are considered.

        Returns:
            list: A list of dictionaries representing the open issues.
        """
        def get_open_issues(issue_number: str = '') -> list[dict]:
            self.logger.debug(".get_open_issues(%s)...", issue_number)
            try:
                open_issues = issue_manager(
                    "list", issue=issue_number, only_in_state=["new", "in progress", "open"])
                self.logger.debug(
                    " the current list of open issues are %s", open_issues)
            except Exception as e:
                self.logger.error(" - Error loading open issues: %s", e)
                open_issues = []

            return open_issues if isinstance(open_issues, list) else [open_issues]

        retry_count = 5
        while (open_issues := get_open_issues()) and (retry_count := retry_count - 1) > 0:
            open_issues.sort(key=lambda x: [x.get("priority", "5"), tuple(
                map(int, x.get("issue", "").split("/")))])
            for open_issue in open_issues:
                if not open_issue.get("assignee") or self.name in open_issue.get("assignee", ""):
                    # if not assigned or assigned to myself, try assign it
                    to_self_prompt = f"Issue {open_issue.get('issue')} is assigned to {
                        open_issue.get("assignee", "No One")}, "
                    "please use issue_manager to read the content of it, and determine who should be responsible for continue working on this issue, "
                    "and then use issue_manager(action='assign'...) to assign this issue to the agent according the below rols. "
                    to_self_prompt += agent_roles
                    o_reply = self.perform_task(
                        to_self_prompt, "self(orchestrator)", {'issue': open_issue})
                    if (updated_open_issues := get_open_issues(
                            open_issue.get('issue', ""))):
                        open_issue = updated_open_issues[0]
                        self.logger.info("Issue %s is now assigned to %s", open_issue.get(
                            'issue'), open_issue.get('assignee'))

                if not agent_names or open_issue.get('assignee') in agent_names:
                    # if no specific agent names or the issue is assigned to one of the specified agents
                    agents: list[BaseAgent] = BaseAgent.instances(True)
                    for agt in agents:
                        if agt.name == open_issue.get('assignee'):
                            to_agt_prompt = f"\nIssue {open_issue.get('issue')} is assigned to you "
                            f"and is in {open_issue.get('status')} status, it is about {open_issue.get('title')}. "
                            "Please review the details of this issue using issue_manager and if it is specific enough to be coded, please write the code, "
                            f"If you feel it is not clear and specific enough please analyze how to describe it in more details and create more specific sub issues for coding."
                            agt_reply = agt.perform_task(
                                to_agt_prompt, "Orchestrator", {"issue": open_issue})

                            # review response from agent
                            class Response_Review(BaseModel):
                                response_score: float
                                is_response_satisfactory: bool
                                comment: str

                            response_review_format = Response_Review.model_json_schema()
                            response_review_instruction = ("The user asked the assistant to respond to the given prompt request "
                                                           "and the assistant provided the subsequent response. Please evaluate how well is the "
                                                           "response from the assistant addressed the user request. is the response satifactory? "
                                                           "With a scale of 0 to 10, how do you score the response? ")
                            review_response = self.llm_client.chat(
                                model=self.config.model,
                                messages=[
                                    {'role': 'user', 'content': to_agt_prompt},
                                    {'role': 'assistant', 'content': agt_reply},
                                    {'role': 'user',
                                        'content': response_review_instruction}
                                ],
                                format=response_review_format,
                                options={
                                    'temperature': self.config.temperature}
                            )
                            self.logger.debug("Review response: %s", review_response)

                            test_result = self.execute_command(
                                "bash", ["run.sh"])
                            to_self_prompt = (f"regarding issue {open_issue.get('issue')}, {agt.name} had responded with \"{agt_reply}\". And the current run.sh result is {test_result}."
                                              f"Use your file_search tool to check if the information provided in this reply exist in the issue files in your issues vector_store?"
                                              f"If not please use issue_manager() tool to update relevant issue or create sub issues under the most relevant issue."
                                              )
                            o_reply = self.perform_task(to_self_prompt, f"Orchestrator check if "
                                                        f"{agt.name} complete issue.", {"issue": open_issue.get('issue', 'generic')})
                            logger.debug(
                                f"<{self.name}> - Orchestrator self perform task update issue result:{o_reply}")

                            to_self_prompt = (f"Please use evaluate_agent() tool to evaluate {agt.name}'s response, consider evaluation criteria {agt.config.evaluation_criteria}."
                                              f"If the score is unsatisfactory, please provide additional_instructions argument, it will be used next time the agent is asked to perform a task."
                                              )
                            o_reply = self.perform_task(to_self_prompt, f"Orchestrator update "
                                                        f"{agt.name} additional instructions", {"issue": open_issue})

                            logger.debug(
                                f"<{self.name}> - Orchestrator self perform task update additional instructions result:{o_reply}")
                            break
                    else:
                        logger.warning(
                            f"<{self.name}> - No agent found with name {open_issue.get('assignee')}")
                        to_self_prompt = f"Issue {open_issue.get(
                            'issue')} is not yet assigned to a worker agent, analyze it's description and details, and assign it to the best agent to tackle its current status."
                        o_reply = self.perform_task(
                            to_self_prompt, f"analyze issue {open_issue}", {"issue": open_issue})
                    # self.upload_issues_as_vector_store()

        return get_open_issues()
        # print("***************")
        # for reply in replies:
        #     print(f"===")
        #     for entry in reply:
        #         print(entry.get("role").upper(), ":")
        #         print("  ", entry.get("content"))
        # while agt_to_eval := input("<<Eval>> Which agent would you like to evaluate (blank to skip eval)? "):
        #     eval_score = input(f"<<Eval>> How satisfied are you with the {agt_to_eval}? ")
        #     try:
        #         eval_score = int(eval_score)
        #     except:
        #         eval_score = 0
        #     eval_feedback = input(f"<<Eval>> How can the {agt_to_eval} improve in the future? ")
        #     self.evaluate_agent(agt_to_eval, eval_score, eval_feedback)
        # print("**********************")


class OllamaOrchestrator(ollama_agent.Ollama_Agent, Orchestrator):
    """the Orchestrator based on Ollama

    The Orchestrator needs to be a model that supports tools usage.
    It will evaluate the response from other agents, and update files if needed.
    """

    def __init__(self):
        self_config = self.AgentConfig({
            "name": "orchestrator",
            "use_tools": True,
            "tools": [],
            "model": "mistral-nemo",#"qwq",
            "instruction": "You are an Orchestrator, you coordinate with other agents and ensure they follow their instructions. Sometimes, other agents may reply to your ask by giving you an answer as if this is a chat session, in those cases, they may provide you with markdown, including code snipets marks with ``` and ```, please help them save these answers to files according to the filenames specified in their answers.  Your main goal is to ensure the other agents' answer will result in useful file updates, if needed you help save their answers to the files using overwrite_file or ed_text_file tools.",
            "temperature": 0.1,
        })
        # Call the constructor of the base class
        super().__init__(agent_config=self_config)


class OpenAIOrchestrator(openai_agent.OpenAI_Agent, Orchestrator):
    """The Orchestrator
    Example::
        >>> with Orchestrator() as orchestrator:
        ...     orchestrator.name
        'orchestrator'

    """
    issue_vector_store = None

    def __init__(self):
        self_config = self.AgentConfig({
            "name": "orchestrator",
            "instruction": "You are an Orchestrator, you coordinate with other agents and ensure they follow their instructions. Sometimes, other agents may reply to your ask by giving you an answer as if this is a chat session, in those cases, they may provide you with markdown, including code snipets marks with ``` and ```, please help them save these answers to files according to the filenames specified in their answers.  Your main goal is to ensure the other agents' answer will result in useful file updates, if needed you help save their answers to the files using overwrite_file or ed_text_file tools.",
            "temperature": 0.5,
            "tools": [
                {"type": "file_search"}
            ]
        })
        # Call the constructor of the base class
        super().__init__(agent_config=self_config)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.issue_vector_store:
            self.llm_client.beta.vector_stores.delete(
                self.issue_vector_store.id)
        try:
            existing_vector_stores = self.llm_client.beta.vector_stores.list()
            for vs in [vs for vs in existing_vector_stores.data if vs.name == "issues"]:
                try:
                    self.llm_client.beta.vector_stores.delete(vs.id)
                except Exception as err:
                    logger.warning(
                        f"<{self.name}> - Orchestrator trying to delete vector_store {vs.id} received Error: {err}")
        except Exception as e:
            logger.warning(
                f"<{self.name}> - Orchestrator trying to remove vector store received Error: {e}", exc_info=e)
        try:
            # for agt in agents:
            #     self.llm_client.beta.assistants.delete(agt.assistant.id)
            existing_assistants = self.llm_client.beta.assistants.list()
            for ast in [ast for ast in existing_assistants.data if ast.name in [agt.name for agt in BaseAgent.instances(True)]]:
                try:
                    self.llm_client.beta.assistants.delete(ast.id)
                except Exception as err:
                    logger.warning(
                        f"<{self.name}> - Orchestrator trying to remove assistant {ast.name}, received Error: {err}")
            for f in self.llm_client.files.list().data:
                self.llm_client.files.delete(f.id)
        except Exception as e:
            logger.error(
                f"<{self.name}> - Orchestrator trying to find and remove orphan assistants, received Error: {e}", exc_info=e)
        super().__exit__(exc_type, exc_val, exc_tb)


if __name__ == "__main__":
    import doctest
    doctest.testmod()
