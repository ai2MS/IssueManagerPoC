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
sweteam:
  - sweteam:
    - bootstrap:
        - __init__.py
        - __main__.py
        - agent.py
        - utils.py
        - agents:
          - pm.json
          - architect.json
          - developer.json
          - tester.json
        - issue_board:
          - 0.json
        - docs:
        - README.md

### Additional Considerations
- The __main__.py script will check if itself runs as bootstrap, if so, it creates the {project}_team directory, and copy the code from the bootstrap, but is expected to evolve from there. 
In the future, one can invoke python -m project_team to continue the project without the bootstrap.

The bootstrap include agent.py and utils.py files, and an agents directory.  


