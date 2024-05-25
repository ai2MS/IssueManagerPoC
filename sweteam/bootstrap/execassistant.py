"""The executive assistant agent logic
This is the agent to ensure every step follows software development process. 
The goal of this agent is not to innovate, rather, you check other agent's responses, and make sure they adhere to required process.
"""

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
                    for a in agents:
                        if a.name == open_issue.get("assignee"):
                            agt = a
                            break
                    else:
                        logger.error(f"<{self.name}> - No agent found with name {open_issue.get('assignee')}")

                    ea_to_agt_prompt = f"\nIssue {open_issue.get('issue')} is still in {open_issue.get('status')} status, it is about {open_issue.get('title')}. Can you complete it? If not, What do you need to complete it?"
                    agt_reply = agt.perform_task(ea_to_agt_prompt, "Executive Assistent")
                    self.upload_issues_as_vector_store()
                    test_result = self.execute_command("sh", "run.sh")
                    ea_reply = self.perform_task(f"regarding issue {open_issue.get('issue')}, {agt.name} had responded with \"{agt_reply}\". the current run.sh result is {test_result}."
                                f"Q1, check the issue_vecotr_store using file_search tool, is this reply a good update to the issue? If so, please help update the issue, or create a new sub issue if updating status of {open_issue.get('status')} is not a good idea."
                                f"Q2, based on this response, who should continue working on this issue? Please use issue_manager() tool to assign this issue to the appropriate agent."
                                f"Q3, is this a good response per the instruction {agt.instruction}? Please use evaluate_agent() tool to evaluate this response."
                                , f"Executive Assistant check {agt.name} reply.")
                    print("**********************")
                    print(f"EA to {agt.name} prompt: {ea_to_agt_prompt}")
                    print(f"{agt.name} to EA reply: {ea_reply}")
                    print("**********************")
                    ea_reply = self.perform_task(f"The {agt.name}'s current additional_instructions are {agt.additional_instructions}. How can this be updated to help {agt.name} complete the issue better?"
                                    , f"Executive Assistant update {agt.name} additional instructions")
                    agt.additional_instructions = ea_reply

                    
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
        # Create a vector store caled "Financial Statements"
        try:
            self.issue_vector_store = self.llm_client.beta.vector_stores.create(name="issues")
            
            # Ready the files for upload to OpenAI
            issue_files = [os.path.join(root, file) for root, _, files in os.walk("issue_board") for file in files]
            file_streams = [open(path, "rb") for path in issue_files]
            
            # Use the upload and poll SDK helper to upload the files, add them to the vector store,
            # and poll the status of the file batch for completion.
            file_batch = self.llm_client.beta.vector_stores.file_batches.upload_and_poll(
            vector_store_id=self.issue_vector_store.id, files=file_streams
            )
        except Exception as e:
            logger.error(f"<{self.name}> - upload files received error {e}")
        else:
            logger.debug(f"<{self.name}> - uploaded files for vector store {self.issue_vector_store.id}: {file_batch.status}")

        self.assistant = self.llm_client.beta.assistants.update(
            assistant_id=self.assistant.id,
            tool_resources={"file_search": {"vector_store_ids": [self.issue_vector_store.id]}},
        )


    def test(self):
        import doctest
        doctest.testmod()


if __name__ == "__main__":
    import doctest
    doctest.testmod()
