"""The executive assistant agent logic
This is the agent to ensure every step follows software development process. 
The goal of this agent is not to innovate, rather, you check other agent's responses, and make sure they adhere to required process.
"""

import contextlib
import json
if __package__:
    from . import agent, logger, agents
else:
    import agent
    from __init__ import logger, agents


class ExecutiveAssistant(agent.OpenAI_Agent):
    """The Executive Assistant
    Example::
        >>> with ExecutiveAssistant() as ea:
        ...     ea.name
        'ea'
    
    """
    issue_vector_store = None
    def __init__(self):
        self_config = {
            "instruction": "You are an Executive Assistant, you follow rules and ensure other agents perform tasks, updating issue#, and produce working documents or working code.",
            "temperature": 0.5,
            "tools": [
                {"type": "file_search"}
            ]
        }
        super().__init__("ea", agent_config=self_config)  # Call the constructor of the base class


    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.issue_vector_store:
            self.llm_client.beta.vector_stores.delete(self.issue_vector_store.id)
        try:
            existing_vector_stores = self.llm_client.beta.vector_stores.list()
            for vs in [ vs for vs in existing_vector_stores.data if vs.name == "issues"]:
                try:
                    self.llm_client.beta.vector_stores.delete(vs.id)
                except Exception as err:
                    logger.warning(f"<{self.name}> - EA trying to delete vector_store {vs.id} received Error: {e}")
        except Exception as e:
            logger.warning(f"<{self.name}> - EA trying to remove vector store received Error: {e}")
        try:
            # for agt in agents:
            #     self.llm_client.beta.assistants.delete(agt.assistant.id)
            existing_assistants = self.llm_client.beta.assistants.list()
            for ast in [ast for ast in existing_assistants.data if ast.name in [agt.name for agt in agents]]:
                try: 
                    self.llm_client.beta.assistants.delete(ast.id)
                except Exception as err:
                    logger.warning(f"<{self.name}> - EA trying to remove assistant {ast.name}, received Error: {err}")
            for f in self.llm_client.files.list().data:
                self.llm_client.files.delete(f.id)
        except Exception as e:
            logger.error(f"<{self.name}> - EA trying to find and remove orphan assistants, received Error: {e}")
        super().__exit__(exc_type, exc_val, exc_tb)

    def follow_up(self, agent_name: list = None, issue_number: str = '') -> str:
        def get_open_issues():
            try:
                open_issues = json.loads(self.issue_manager("list", issue=issue_number, only_in_state=["new","in progress", "open"]))
                logger.debug(f"<{self.name}> - the pm finished one round, the current list of open issues are {open_issues}")
            except Exception as e:
                logger.error(f"<{self.name}> - Error loading open issues: {e}")
                open_issues = []

            return open_issues
        
        retry_count = 5
        while (open_issues := get_open_issues()) and (retry_count := retry_count - 1) > 0:
            open_issues.sort(key=lambda x: [x.get("priority", "5"), tuple(map(int,x.get("issue").split("/")))])
            for open_issue in open_issues:
                if not agent_name or open_issue.get("assignee") in agent_name:
                    for agt in agents:
                        if agt.name == open_issue.get("assignee"):
                            ea_to_agt_prompt = f"\nIssue {open_issue.get('issue')} is still in {open_issue.get('status')} status, it is about {open_issue.get('title')}. Can you complete it? If not, What do you need to complete it?"
                            agt_reply = agt.perform_task(ea_to_agt_prompt, "Executive Assistent")

                            test_result = self.execute_command("bash",["run.sh"])
                            ea_self_prompt = (f"regarding issue {open_issue.get('issue')}, {agt.name} had responded with \"{agt_reply}\". And the current run.sh result is {test_result}."
                                    f"Use your file_search tool to check if the information provided in this reply exist in the issue files in your issues vector_store? If not please use issue_manager() tool to update relevant issue or or create sub issues under the most relevant issue."
                            )
                            ea_reply = self.perform_task(ea_self_prompt, f"Executive Assistant check if {agt.name} updated issue.")
                            logger.debug(f"<{self.name}> - EA self perform task update issue result:{ea_reply}")

                            ea_self_prompt = f"The instruction to {agt.name} is {agt.instruction}? Please use evaluate_agent() tool to evaluate this response."
                            ea_reply = self.perform_task(ea_self_prompt, f"Executive Assistant evaluate {agt.name} reply")
                            logger.debug(f"<{self.name}> - EA self perform task evaluate agent result:{ea_reply}")

                            ea_self_prompt = f"The {agt.name}'s current additional_instructions are {agt.additional_instructions}. Please give me an updated additional instruction that can help {agt.name} complete the issue better?"
                            ea_reply = self.perform_task(ea_self_prompt, f"Executive Assistant update {agt.name} additional instructions")
                            ea_reply_obj = [msg for msg in (json.loads(ea_reply)) if msg.get("role") == self.name]
                            add_inst = "\n".join([msg["content"] for msg in ea_reply_obj])
                            agt.additional_instructions = add_inst
                            logger.debug(f"<{self.name}> - EA self perform task update additional instructions result:{ea_reply}")
                            break
                    else:
                        logger.warning(f"<{self.name}> - No agent found with name {open_issue.get('assignee')}")
                        ea_self_prompt = f"Issue {open_issue.get('issue')} is not yet assigned to a worker agent, analyze it's description and details, and assign it to the best agent to tackle its current status."
                        ea_reply = self.perform_task(ea_self_prompt, f"ea analyze issue {open_issue}")
                    self.upload_issues_as_vector_store()

                    
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
                self.issue_vector_store = self.llm_client.beta.vector_stores.create(name=ISSUE_VECTOR_STORE_NAME)

            uploaded_issues = self.llm_client.beta.vector_stores.files.list(vector_store_id=self.issue_vector_store.id)

            issue_files = [os.path.join(root, file) for root, _, files in os.walk("issue_board") for file in files if file.endswith(".json")]

            issue_files_to_upload = []
            for issue_file in issue_files:
                already_uploaded = [upliss for upliss in uploaded_issues.data if upliss['name'] == issue_file]
                if already_uploaded and os.stat(issue_file).st_mtime < already_uploaded[0].get('created_at', 0):
                    continue
                else:
                    issue_files_to_upload.append(issue_file)
            with contextlib.ExitStack() as stack:  
                file_streams = [stack.enter_context(open(path, "rb")) for path in issue_files_to_upload]
                file_batch = self.llm_client.beta.vector_stores.file_batches.upload_and_poll(
                    vector_store_id=self.issue_vector_store.id, files=file_streams
                )
        except Exception as e:
            logger.error(f"<{self.name}> - upload files received error {e} - line {e.__traceback__.tb_lineno}")
        else:
            logger.debug(f"<{self.name}> - uploaded files for vector store {self.issue_vector_store.id}: {file_batch.status}")

        self.assistant = self.llm_client.beta.assistants.update(
            assistant_id=self.assistant.id,
            tool_resources={"file_search": {"vector_store_ids": [self.issue_vector_store.id]}},
        )
        for agt in agents:
            agt.assistant = agt.llm_client.beta.assistants.update(
                assistant_id=agt.assistant.id,
                tool_resources={"file_search": {"vector_store_ids": [self.issue_vector_store.id]}},
        )
        return "success"

    def test(self):
        import doctest
        doctest.testmod()


if __name__ == "__main__":
    import doctest
    doctest.testmod()
