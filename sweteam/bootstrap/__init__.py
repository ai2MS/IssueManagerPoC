"""
Bootstrap a new software engineering project.

This is the initial point of a software engineering project. 
The new piradigm is to have new software all "self-writen" and evolve by itself.
This means software are going to update themselves to evolve instead of relying on
some other agents human or AI developers. 
This in turn means this piece of software will evolve the software development 
capabilities that only needed by this project, instead of having to acquire full
software development capability. 
"""

import logging
import os

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
    from . import agent
    agents_dir = os.path.join(os.path.dirname(__file__), 'agents')
    logger.debug(f"package name: {__package__}")
    if (my_name != 'bootstrap'):
        agents_list = [entry for entry in os.listdir(agents_dir) if entry.endswith(".json")]
        for agt in agents_list:
            agents.append(agent.OpenAI_Agent(agt.removesuffix(".json"), agents_dir))

        pm = [a for a in agents if a.name=="pm"][0]
        if not pm:
            pm = agents[0]
        
        if pm:
            pm.perform_task("Start a new software project by asking the user to provide new requirements.")