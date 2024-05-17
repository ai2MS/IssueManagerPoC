"""
This is the entry point of a software engineering project. 

The new piradigm is to have new software all "self-writen" and evolve by itself.
This means software are going to update themselves to evolve instead of relying on
some other agents human or AI developers. 

This module has two models, when called as Bootstrap, it creates a new software engineering project. 
when called as a project/team it continue an existing software project.

Usage:
    python -m sweteam.bootstrap [-p project_name] [-n]
    project_name is what the actual project should be called, if not provided, its "default", you can also set PROJECT_NAME environment variable for this
    -n will remove old project dir and start a new one with that name, so be careful using this option.

    or 

    python -m default_project.team
    all arguments are ignored, this will continue the previously setup project
"""

import logging
import os
import contextlib

logger = logging.getLogger(__name__)
match os.environ.get("LOG_LEVEL"):
    case "DEBUG":
        logger.setLevel(logging.DEBUG)
    case "INFO"|"LOG":
        logger.setLevel(logging.INFO)
    case "WARN"|"WARNING":
        logger.setLevel(logging.WARN)
    case "ERROR":
        logger.setLevel(logging.ERROR)
    case _:
        logger.setLevel(logging.INFO)
        
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
c_format = logging.Formatter('%(levelname)s - %(name)s - %(message)s')
console_handler.setFormatter(c_format)
logger.addHandler(console_handler)


my_name = __package__.split(".")[0]
file_handler = logging.FileHandler(f"{my_name}.log")
f_format = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
file_handler.setFormatter(f_format)
logger.addHandler(file_handler)

msg_logger = logging.getLogger("message_log")
if __package__ and not __package__.startswith("sweteam"):
    msg_file_handler = logging.FileHandler(f"{my_name}_messages.log")
    msg_file_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    msg_file_handler.setFormatter(msg_file_format)
    msg_logger.addHandler(msg_file_handler)
    msg_logger.setLevel(logging.INFO)

agents = []

# load agents
def load_agents():
    global agents
    from . import agent
    if __package__.startswith("sweteam"):
        print(f"Warning, Current package name: {__package__}")
    agents_dir = os.path.join(os.path.dirname(__file__), 'agents')
    logger.debug(f"package name: {__package__}")
    if (my_name != 'bootstrap'):
        agents_list = [entry.removesuffix(".json") for entry in os.listdir(agents_dir) if entry.endswith(".json")]
        with contextlib.ExitStack() as stack:
            # for agt in agents_list:
            #     agents.append(agent.OpenAI_Agent(agt.removesuffix(".json"), agents_dir))
            agents.extend([stack.enter_context(agent.OpenAI_Agent(agt, agents_dir)) for agt in agents_list])

            pm = [a for a in agents if a.name=="pm"][0]
            if not pm:
                pm = agents[0]
            
            prompt = "Check the issue_board directory for issues with status in ['new', 'in progress'], and analyze them, prioritize, then continue work on them. Or, if no issues currently have new status, Start a new software project by asking the user to provide new requirements."
            round_name = "Initializing"
            while pm and prompt:
                pm.perform_task(prompt, round_name)
                prompt = input("\n***Please follow up, or just press enter to finish this session:\n")
                round_name = "Continuing"