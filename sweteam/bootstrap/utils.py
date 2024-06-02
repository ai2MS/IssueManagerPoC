"""
This module contains utility functions for working with files.

Usage:
    python -m utils [update_agent]
"""

import os
import re
import yaml
import json
from datetime import datetime

if __package__:
    from . import logger, agents
    from .defs import standard_tools, new_instructions
else:
    from __init__ import logger
    from defs import standard_tools, new_instructions
project_name = ''


def issue_manager(action: str, issue: str = '', only_in_state: list = [], content: str = None, assignee: str = None, caller: str = "manually"):
    """Manage issues: list, create, read, update, assign
    Example::
    >>> issue_manager("list", "0")
    issue(s) :
    - issue  : 0            priority: 0            status : completed    assignee: unknown      title  : initial bootstrap code 
    """
    ISSUE_BOARD_DIR = "issue_board"
    content_obj = {}
    logger.debug(f"<issue_manager> - entering - issue_manager({action}, {issue}, {only_in_state}, {content})")
    if isinstance(content, str):
        try:
            content_obj = json.loads(content.replace("\n", "\\n")) #correct one of the most common json string error - newline instead of \\n in it.
        except Exception as e:
            logger.warning(f"<issue_manager> - issue_manager {action} cannot parse content as json -{content}.")
            try:
                yaml_obj = yaml.safe_load(content)
                for k, v in yaml_obj.items():
                    if k.lower() in ["title", "description", "details", "priority", "status", "assignee", "updated_by", "updated_at", "created_at"]:
                        content_obj[k.lower()] = v.lower()
                    else:
                        if content_obj.get("details", None):
                            content_obj["details"].append({k.lower(): v})
                        else:
                            content_obj["details"] = [{k.lower(): v}]
            except Exception as e:
                logger.warning(f"<issue_manager> - issue_manager {action} cannot parse content as yaml either -{content}... Will use it as str.")
                if action == "create":
                    content_obj = {"title":f"{content:.24s}","description": content}
                elif action == "update":
                    content_obj = {"details": content}
    else:
        content_obj = content
    logger.debug(f"<issue_manager> - issue_manager, {type(content_obj)}, {content_obj}")
    match action:
        case 'list':
            issue_dir = os.path.join(ISSUE_BOARD_DIR, issue)
            results = []
            for root, dirs, files in os.walk(issue_dir):
                for file in files:
                    issue_number = root.removeprefix(ISSUE_BOARD_DIR+'/')
                    if file==f"{issue_number.replace('/','.')}.json":
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r') as f:
                                data = json.load(f)
                            updates = data.get('updates', [])
                            updates.sort(key=lambda x: x.get('updated_at',0))
                            if updates:
                                latest_status = [u for u in updates if u.get('status', "")] 
                                status = latest_status[-1].get('status', "unknown") if latest_status else "new"
                                latest_priority = [u for u in updates if u.get('priority', "")] 
                                priority = latest_priority[-1].get('priority', "5 - unknown") if latest_status else "4 - Low"
                                latest_updated_by = [u for u in updates if u.get('updated_by', "")] 
                                updated_by = latest_updated_by[-1].get('updated_by', "unknown") if latest_updated_by else "unknown"
                                latest_assignee = [u for u in updates if u.get('assignee', "")] 
                                assigned_to = latest_assignee[-1].get('assignee', updated_by) if latest_assignee else updated_by
                            else:
                                status = data.get('status', "new")
                                priority = data.get('priority', "4 - Low")
                                updated_by = data.get('updated_by', "unknown")
                                assigned_to = data.get('assignee', updated_by)
                            if only_in_state and "in progress" in only_in_state:
                                # sometimes AI will use "in process" instead of "in progress", we will try to accommodate that.s
                                only_in_state.append("in process")
                            if only_in_state and status not in only_in_state:
                                continue
                            if assignee and assignee != assigned_to:
                                continue
                            if priority.lower().strip() in ["low", "medium", "high", "urgent"]:
                                pri_rank = {"low": 4, "medium": 3, "high": 2, "critical":1, "urgent": 0}
                                priority = f"{pri_rank[priority.lower()]} - {priority.capitalize()}"
                            results.append({'issue':issue_number, 'priority':priority, 'status':status, 'assignee': assigned_to, 'title': data.get('title', "no title")})
                        except json.JSONDecodeError:
                            logger.error(f"<issue_manager> - issue_manager/list - issue#{issue_number} - Error decoding JSON from file: {file_path}")
                            results.append({'issue':issue_number, 'status':f"Error Decoding Json"})
                        except FileNotFoundError:
                            logger.error(f"<issue_manager> - issue_manager/list - issue#{issue_number} - Error file not found: {file_path}")
                            results.append({"issue":issue_number, "status":f"Error file not found"})
                        except Exception as e:
                            logger.error(f"<issue_manager> - issue_manager/list - issue#{issue_number} - Error decoding JSON from file: {file_path}")
                            results.append({"issue":issue_number, "status":f"Error {e}"})

            logger.debug(f"<issue_manager> - issue_manager({action}, {issue}...) returned {results}")
            return json.dumps(results)
        case "create":
            try:
                issue_dir = os.path.join(ISSUE_BOARD_DIR, issue)
                if not os.path.exists(issue_dir):
                    os.makedirs(issue_dir, exist_ok=True)
                existing_sub_issues = [int(entry.name) for entry in os.scandir(issue_dir) 
                                    if entry.is_dir() 
                                    and entry.name.isdigit() 
                                    and os.path.exists(os.path.join(issue_dir, entry.name, f"{os.path.join(issue, entry.name).replace('/','.')}.json"))] 
                new_sub_issue_number = f"{max([issue_no for issue_no in existing_sub_issues], default=0) + 1}"
                new_issue_dir = os.path.join(issue_dir, new_sub_issue_number)
                new_issue_number = os.path.join(issue, new_sub_issue_number)

                if 'created_at' not in content_obj:
                    content_obj['created_at'] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
                if 'updates' not in content_obj or not content_obj['updates']:
                    content_obj['updates'] = [{}]
                if 'updated_by' not in content_obj['updates'][-1]:
                    content_obj['updates'][-1]['updated_by'] = caller
                if 'updated_at' not in content_obj['updates'][-1]:
                    content_obj['updates'][-1]['updated_at'] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
                if 'priority' not in content_obj['updates'][-1]:
                    content_obj['updates'][-1]['priority'] = "4 - Low"
                if 'assignee' not in content_obj['updates'][-1]:
                    content_obj['updates'][-1]['assignee'] = assignee if assignee else caller if caller else "unknown"
                if 'status' not in content_obj['updates'][-1]:
                    content_obj['updates'][-1]['status'] = "new"
                
                if not os.path.exists(new_issue_dir):
                    os.makedirs(new_issue_dir, exist_ok=True)

                new_issue_file = os.path.join(new_issue_dir,f"{new_issue_number.replace('/','.')}.json")
                with open(new_issue_file, 'w') as ifh:
                    result = json.dump(content_obj,ifh)
                    result = f"Issue {new_issue_number} created."
            except Exception as e:
                logger.error(f"<issue_manager> issue_manager/create issue {new_issue_number} error {e}: lineno:{e.__traceback__.tb_lineno}")
                result = f"Error creating issue {new_issue_number}. Error: {e}"

            logger.debug(f"<issue_manager> - issue_manager({action}, {issue}...) returned {result}")
            return result
        case "read":
            try:
                issue_dir = os.path.join(ISSUE_BOARD_DIR, issue)
                issue_file = os.path.join(issue_dir, f"{issue.replace('/','.')}.json")
                result={'issue#': issue}
                with open(issue_file, 'r') as jsonfile:
                    data = json.load(jsonfile)
                    updates = data.get('updates', [])
                    result['latest_status'] = max(updates, 
                            key=lambda x: ('status' in x, x.get('updated_at','2000-01-01T00:00:00.000')), default={}).get('status', "new")
                    result['latest_priority'] = max(updates, 
                            key=lambda x: ('priority' in x, x.get('updated_at','2000-01-01T00:00:00.000')), default={}).get('priority',"4 - Low")
                    result['latest_updated_by'] = max(updates, 
                            key=lambda x: ('updated_by' in x, x.get('updated_at','2000-01-01T00:00:00.000')), default={}).get('updated_by', "unknown")
                    result['latest_assignee'] = max(updates, 
                            key=lambda x: ('assignee' in x, x.get('updated_at','2000-01-01T00:00:00.000')), default={}).get('assignee', "unknown")
                    result.update(data)
            except Exception as e:
                logger.error(f"<issue_manager> issue_manager/read issue {issue} error {e}: s{e.__traceback__.tb_lineno}")
                result = f"Error Reading issue {issue} - Error: {e}"
            logger.debug(f"<issue_manager> - issue_manager({action}, {issue}...) returned {result}")
            return json.dumps(result)
        case "update":
            try:
                if content_obj and "updated_at" not in content_obj:
                    content_obj['updated_at'] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
                if content_obj and "updated_by" not in content_obj:
                    content_obj['updated_by'] = caller
                if content_obj and "assignee" not in content_obj:
                    content_obj['assignee'] = caller

                issue_dir = os.path.join(ISSUE_BOARD_DIR, issue)
                issue_file = os.path.join(issue_dir, f"{issue.replace('/','.')}.json")
                with open(issue_file, 'r') as ifile:
                    issue_content = json.load(ifile)
                issue_updates = issue_content.get("updates", [])
                if max([issue_updates], key=lambda x: x.get('updated_at',0),default={}).get('status',"new") == "completed":
                    result = f"Error updating issue {issue}, it is already completed. Please create a new sub issue if you have additional actions needed to be taken on this issue."
                    return result
                if issue_content and "updates" in issue_content:
                    issue_content['updates'].append(content_obj)
                else:
                    issue_content['updates'] = [content_obj]
                with open(issue_file, 'w') as ifile:
                    result = json.dump(issue_content, ifile)
                    result = f"Issue {issue} updated successfully."
            except Exception as e:
                logger.error(f"<issue_manager> issue_manager/update issue {issue} error {e}: {e.__traceback__.tb_lineno}")
                result = f"Error Updating issue {issue} - Error: {e}"
            logger.debug(f"<issue_manager> - issue_manager({action}, {issue}...) returned {result}")
            return result
        case "assign":
            try:
                issue_dir = os.path.join(ISSUE_BOARD_DIR, issue)
                issue_file = os.path.join(issue_dir, f"{issue.replace('/','.')}.json")
                with open(issue_file, 'r') as ifile:
                    issue_content = json.load(ifile)
                if not content:
                    content_obj = {}
                if "updated_at" not in content_obj:
                    content_obj['updated_at'] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
                if "updated_by" not in content_obj:
                    content_obj['updated_by'] = caller
                if "details" not in content_obj:
                    content_obj['details'] = f"assign {issue} to {assignee}."
                if assignee:
                    if assignee in [agt.name for agt in agents]:
                        content_obj['assignee'] = assignee
                    else:
                        return f"Assignee {assignee} is not a valid agent, please only assign to one of the following agents: {[agt.name for agt in agents]}."
                else:
                    content_obj['assignee'] = caller
                if issue_content and "updates" in issue_content:
                    issue_content['updates'].append(content_obj)
                else:
                    issue_content['updates'] = [content_obj]
                with open(issue_file, 'w') as ifile:
                    result = json.dump(issue_content, ifile)
                    result = f"Assigned {issue} to {assignee} successfully."
            except Exception as e:
                logger.error(f"<issue_manager> issue_manager/update issue {issue} error {e}: s{e.__traceback__.tb_lineno}")
                result = f"Error Updating issue {issue} - Error: {e}"

            logger.debug(f"<issue_manager> - exiting - issue_manager({action}, {issue}...) returned {result}")
            return result

        case _:
            logger.warn(f"<issue_manager> - exiting - issue_manager({action}, ...) {action} is not a valid action.")
            return (f"Invalid action: {action}. Only 'list', 'create', 'read', 'update', 'assign' are valid actions")
 

def initialize_package(package_dir: str = None) -> str:
    """Initialize the __init__.py and __manin__.py files of a package.

    Args:
      package_dir: the path to the package, default is the namesake of the project

    Returns:
      the status of the package initializatio
    """
    if package_dir is None:
        # the default package dir is a namesake of the project under the project_dir
        package_dir = os.path.join(os.getcwd(), os.path.basename(os.getcwd))
    base_main = '''\
"""Project base package.

Example::
    >>> print("Hello World!")
    Hello World!
"""
def test() -> str:
    import doctest
    doctest.testmod()

if __name__ == "__main__":
    test()
'''
    try:
        main_file_path = os.path.join(package_dir, "__main__.py")
        with open(main_file_path, "w") as mf:
            mf.write(base_main)
    except Exception as e:
        return f"<Init package> received Error: {e}"
    else:
        return f"<Init package> successful."

def initialize_Dockerfile(project_name: str = None, dockerfile_path: str = None) -> str:
    """Initialize the Dockerfile in the given directory
    """
    base_Dockerfile = f"""\
# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install Poetry
RUN pip install poetry

# Copy pyproject.toml and poetry.lock files to the container
COPY pyproject.toml poetry.lock ./

# Install the project dependencies
RUN poetry install --no-root

# Copy the rest of the application code to the container
COPY . .

# Specify the command to run your application
CMD ["poetry", "run", "python", "-m", "{project_name}"]
"""
    if project_name is None:
        project_name = os.path.basename((os.getcwd()))
    if dockerfile_path is None:
        dockerfile_path = os.path.join(os.getcwd(), "Dockerfile")
    base_Dockerfile.replace("{project_name}", project_name)
    if os.path.exists(dockerfile_path):
        result = (f"<init Dockerfile> {dockerfile_path} already exist, will not overwrite it, exiting...\n")
    else:
        try:
            with open(dockerfile_path, "w") as df:
                df.write(base_Dockerfile)
        except Exception as e:
            result = f"<init Dockerfile> got an Error: {e}\n"
        else:
            result = f"<init Dockerfile> {dockerfile_path} for {project_name} has been successfully initialized.\n"
    base_docker_compose = f"""\
services:
  {project_name}:
    build: .
    command: poetry run python -m {project_name}
    ports:
      - "${{SERVER_PORT:-8080}}:8080"
    restart: always
"""
    docker_compose_path = os.path.join(os.path.dirname((dockerfile_path)), "docker-compose.yaml")
    if os.path.exists(docker_compose_path):
        result += (f"<init Dockerfile> {docker_compose_path} already exist, will not overwrite it, exiting...")
    else:
        try:
            with open(docker_compose_path, "w") as df:
                df.write(base_docker_compose)
        except Exception as e:
            result += f"<init Dockerfile> got an Error: {e}"
        else:
            result += f"<init Dockerfile> {docker_compose_path} for {project_name} has been successfully initialized."
    return result

def initialize_startup_script(project_dir: str = None) -> str:
    """Initialize the startup shell script
    """
    if project_dir is None:
        project_dir = os.getcwd()
    project_name = os.path.basename(project_dir)
    script_path = os.path.join(project_dir, "run.sh")
    base_script = f"""\
#!/bin/bash

# Function to display usage
usage() {{
    echo "Usage: $0 [-t test_name] [-k]"
    exit 1
}}

# Parse command line options
while getopts ":t:k" opt; do
  case $opt in
    t )
      test_name=$OPTARG
      ;;
    k )
      kill_docker=true
      ;;
    \? )
      usage
      ;;
  esac
done

# Check if both -t and -k are provided
if [[ ! -z "$test_name" && ! -z "$kill_docker" ]]; then
    echo "Error: -t and -k options cannot be used together."
    usage
fi

# Execute the appropriate command based on the options
if [ ! -z "$test_name" ]; then
    echo "(re)starting docker compose"
    docker-compose up -d
    echo "Running python -m $test_name"
    python -m "$test_name"
elif [ ! -z "$kill_docker" ]; then
    echo "Running docker-compose down"
    docker-compose down
else
    docker-compose up -d
    docker-compose logs
fi
"""
    if os.path.exists(script_path):
        return (f"<init startup script> {script_path} already exist, will not overwrite it, exiting...")
    else:
        try:
            with open(script_path, "w") as df:
                df.write(base_script)
            current_permissions = os.stat(script_path).st_mode
            os.chmod(script_path, current_permissions | 0o111)
        except Exception as e:
            return f"<init startup script> got an Error: {e}"
        else:
            return f"<init startup script> {script_path} for {project_name} has been successfully initialized."
    

def initialize_agent_files(agent_parent_dir: str = None) -> str:
    """Initialize the agent files
    """
    logger.debug(f"<Initializing> - updating agents instructions as part of project setup. Should not be used in production")
    import os
    import json

    agents_dir = agent_parent_dir if agent_parent_dir else os.path.dirname(__file__) + "/agents"
    agents_list = [entry.removesuffix(".json") for entry in os.listdir(agents_dir) if entry.endswith(".json")]
    for agent_name in agents_list:
        config_json = os.path.join(agents_dir, f"{agent_name}.json")
        if new_instructions.get(agent_name):
            with open(config_json, "r") as f:
                agent_config = json.load(f)

            agent_config["instruction"] = new_instructions[agent_name] + new_instructions["all"]
            with open(config_json, "w") as f:
                json.dump(agent_config, f, indent=4)
    logger.info(f"<Initializing> - updated {len(agents_list)} agents instructions")

def dir_tree(path_: str) -> str:
    """Print the directory tree
    """
    def extract_desc(file_path: str) -> str:
        """Extract the description from the file
        """
        READLINES_HINT = 128
        EXTRACT_RULES = [{"type":"README.md", "filename_pattern":r"README.md$","comment_prefix":"#"},
            {"type":"Python", "filename_pattern":r".*\.py$", "comment_prefix":"\"\"\""}, 
            {"type":"Dockerfile", "filename_pattern":r"Dockerfile$", "comment_prefix":"#"}, 
            {"type":"Docker-compose", "filename_pattern":r"docker-compose.ya?ml$", "comment_prefix":""},
            {"type":"Javascript", "filename_pattern":r".*\.(js|ts)$", "comment_prefix":"/**"},
            ]
        comment = ""
        file_name = os.path.basename(file_path)
        for rule in EXTRACT_RULES:
            rule_re = re.compile(rule["filename_pattern"])
            if os.path.isfile(file_path) and rule_re.match(file_name):
                with open(file_path, "r") as f:
                    lines = f.readlines(READLINES_HINT)
                for line in lines:
                    if line.strip().startswith(rule["comment_prefix"]):
                        comment=line.strip().removeprefix(rule["comment_prefix"]).removesuffix("\n").strip()
                    if comment:
                        break                   
            if comment:
                break
        return comment


    if not os.path.exists(path_):
        return f"{path_} does not exist."
    dir_desc_file_patterns = [r'README.md', r'__init__.py', r'index.js', r'Dockerfile', r'docker-compose.ya?ml']
    exclude_patterns = [r'.*/node_modules/.*', r'.*/.venv/.*', r'.*/.pytest_cache/.*', r'.*/__pycache__/.*', r'.*/issue_board/.*']
    tree = []
    d = tree
    for (root, dirs, files) in os.walk(path_):
        if any(re.match(pattern, (root+'/')) for pattern in exclude_patterns):
            continue
        for dirpart in root.split('/'):
            if not dirpart:
                dirpart='/'
            endr = {key_: idx for idx,v in enumerate(d) for key_ in v if key_ == dirpart}
            if endr:
                d=d[endr[dirpart]][dirpart]
            else:
                d_i = {dirpart:[]}
                d.append(d_i)
                d = d_i[dirpart]
        for ddesc_pattern in dir_desc_file_patterns:
            descfile = [fl for fl in files if re.match(ddesc_pattern, fl)]
            if descfile:
                d.append({descfile[0]:extract_desc(os.path.join(root, descfile[0]))})
                break
        else:
                if re.match(ddesc_pattern, fl):
                    d.append({fl:extract_desc(os.path.join(root, fl))})
        for fl in files:
            cmt=extract_desc(os.path.join(root, fl))
            if {fl:cmt} not in d:
                d.append({fl:cmt})
        d=tree
    return (yaml.dump(tree))


def test() -> None:
    import doctest
    doctest.testmod()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        match sys.argv[1]:
            case "update_agents":
                if os.path.exists(os.path.join(os.getcwd(), "agents")):
                    agent_parent_dir = os.getcwd()
                    print("local run of util in " + os.getcwd())
                else:
                    agent_parent_dir = os.path.dirname(__file__)
                    print("local run of util on " + os.path.dirname(__file__))
                    
                initialize_agent_files(agent_parent_dir)
                sys.exit(0)
            case "issue_manager":
                issman_args = {}
                only_in_state=[]
                try:
                  issman_args["action"] = sys.argv[2]
                  for i in range(3,len(sys.argv)):
                      if sys.argv[i].startswith("content="):
                          issman_args["content"] = sys.argv[i].removeprefix("content=")
                      if sys.argv[i].startswith("only_in_state"):
                          issman_args["only_in_state"] = sys.argv[i].removeprefix("only_in_state=").split(",")
                      if sys.argv[i].startswith("issue="):
                          issman_args["issue"] = sys.argv[i].removeprefix(("issue="))
                  issue_result = json.loads(issue_manager(**issman_args))
                  if isinstance(issue_result, list):
                      issue_result.sort(key=lambda x: tuple(map(int,x.get("issue").split("/"))))
                  for key_ in issue_result:
                      if isinstance(key_, str):
                          if key_ == "updates":
                              print(f"{key_.upper()}:")
                              for upd in issue_result[key_]:
                                  upd_len = len(upd)
                                  for seq, key in enumerate(upd):
                                      match seq:
                                          case 0:
                                              border_char=f"{0x2514:c}{0x252c:c}{0x2500:c}"
                                          case n if n == upd_len-1:
                                              border_char=f" {0x2514:c}{0x2500:c}"
                                          case _:
                                              border_char=f" {0x251c:c}{0x2500:c}"
                                      print(f"    {border_char}\t{key.capitalize()}: {upd[key]}")
                          else:
                              print(f"{key_.upper()}: {issue_result[key_]}")
                      else:
                          print("-", end="")
                          for key in key_:
                              print(f" {key:7}: {key_[key]:11}", end=" ")
                          print("\t")
                except Exception as e:
                    print(f"Error processing issue_manager request: {e}, at line {e.__traceback__.tb_lineno}")
                    print(f"Usage: python -m {os.path.basename(__file__)} issue_manager list|read|update|create [issue='1/1'] [only_in_state='new,in progress'] [content='json str of an issue update']" )
                sys.exit(0)
            case "test":
                test()
                sys.exit(0)
            case _ as wrong_arg:
                print (f"{wrong_arg} is not a valid option")

    print(f"Usage: python -m {os.path.basename(__file__)} [test|update_agents|issue_manager]")
