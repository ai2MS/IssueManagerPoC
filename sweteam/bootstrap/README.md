# Software Engineering Team Software Specification Description

### Overview
This repo is a project that orchestrate LLM agents to function as different roles within a software Engineering team, including Product Manager(pm), Architect, Developer, Tester.
It has a bare minimum core that is called bootstrap, this allows the start of a new project team, team and instantiate the four roles.
### Detailed Components
1. **agent.py**: 
The agent.py is the main file that coordinates the creation of the agents, their capabilities like chat_with_other_agent, write_to_file, read_from_file, and get_human_input.

2. **utils.py**: 
The utils.py has some supporting functionalities like the tools definition that can be used by OpenAI assistants to interact with the agents.

3. **agent directory**: 
The agents directory contains the .json definitions of the agents, most importantly, the instruction for each agent. And if needed, it can also define additional agent specific tools that can be used by the specific agent.

### Project Directory Structure
- {project_root}:
  - bootstrap:
    - README.md: Software Engineering Team Software Specification Description
    - execassistant.py: The executive assistant agent logic
    - __main__.py: initialize a software development project
    - defs.py: This module contains initial definitions for the agent instructions
        and tools.
    - config.py: ''
    - agent.py: Core Agent Class code sfor OpenAI"""
    - utils.py: ''
    - __init__.py: ''
    - __pycache__:
      - agent.cpython-312.pyc: ''
      - config.cpython-312.pyc: ''
      - __main__.cpython-312.pyc: ''
      - utils.cpython-312.pyc: ''
      - __main__.cpython-310.pyc: ''
      - defs.cpython-312.pyc: ''
      - __init__.cpython-312.pyc: ''
      - pm.cpython-310.pyc: ''
      - __init__.cpython-310.pyc: ''
      - pm.cpython-312.pyc: ''
    - agents:
      - techlead.json: ''
      - pm.json: ''
      - designer.json: ''
      - tester.json: ''
      - sre.json: ''
      - frontend_dev.json: ''
      - backend_dev.json: ''
      - architect.json: ''


### Additional Considerations
- The __main__.py script will check if itself runs as bootstrap, if so, it creates the {project}_team directory, and copy the code from the bootstrap, but is expected to evolve from there. 
In the future, one can invoke python -m project_team to continue the project without the bootstrap.

The bootstrap include agent.py and utils.py files, and an agents directory.  
