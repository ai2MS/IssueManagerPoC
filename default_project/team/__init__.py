"""
Bootstrap a new software engineering project.

This is the initial point of a software engineering project. 
The new piradigm is to have new software all "self-writen" and evolve by itself.
This means software are going to update themselves to evolve instead of relying on
some other agents human or AI developers. 
This in turn means this piece of software will evolve the software development 
capabilities that only needed by this project, instead of having to acquire full
software development capability. 

Usage:
    python -m sweteam.bootstrap [-p project_name] [-n]
    project_name is what the actual project should be called, if not provided, its "default", you can also set PROJECT_NAME environment variable for this
    -n will remove old project dir and start a new one with that name, so be careful using this option.

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
c_format = logging.Formatter('%(levelname)s - %(name)s - %(message)s')
console_handler.setFormatter(c_format)
logger.addHandler(console_handler)

my_name = __package__.split(".")[-1]
file_handler = logging.FileHandler(f"{my_name}.log")
f_format = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
file_handler.setFormatter(f_format)
logger.addHandler(file_handler)

agents = []

# load agents
def load_agents():
    global agents
    from . import agent
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
            
            prompt = "Check the issue_board directory for issues with status in ['new', 'work in progress'], and analyze them, prioritize, then continue work on them. Or, if no issues currently have new status, Start a new software project by asking the user to provide new requirements."
            while pm and prompt:
                pm.perform_task(prompt)
                prompt = input("\n***Please follow up, or just press enter to finish this session:\n")