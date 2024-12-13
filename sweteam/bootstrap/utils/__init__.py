"""
This module contains utility functions for working with files.

Usage:
    python -m utils [update_agent]
"""

import os
import subprocess
import re
import yaml
import json
from datetime import datetime
from .log import get_logger as plain_get_logger, logging
from ..config import config


def get_logger(name: str = '', stream: str | bool | None = None, file: str | bool | None = None,
               *, log_file: str | None = None, level: str | None = None) -> logging.Logger:
    logger_name = config.PROJECT_NAME if name is None else name
    stream_level = config.LOG_LEVEL_CONSOLE if stream is None else stream
    file_level = config.LOG_LEVEL if file is None else file
    log_level = config.LOG_LEVEL if level is None else level
    log_filename = ((config.PROJECT_NAME or os.path.basename(os.getcwd())) + ".log") if log_file is None else log_file

    return plain_get_logger(logger_name, stream_level, file_level, log_file=log_filename, level=log_level)


logger = get_logger((__package__ or __name__ or ""))
from .file_utils import dir_structure


def issue_manager(action: str, issue: str = '', only_in_state: list = [],
                  content: str | None = None, assignee: str | None = None, caller: str = "manually") -> dict | list:
    """Manage issues: list, create, read, update, assign
    Example::
    >>> issue_manager("list", "0")
    '[{"issue": "0", "priority": "0", "status": "completed", "assignee": "unknown", "title": "initial bootstrap code"}]'
    """
    content_obj: dict = {}
    logger.debug("entering...%s",
                 f"{action=}, {issue=}, {only_in_state=}, {content=})")
    if isinstance(content, str):
        try:
            # correct one of the most common json string error - newline instead of \\n in it.
            content_obj = json.loads(content.replace("\n", "\\n"))
        except Exception as e:
            logger.warning(
                f"<issue_manager> - issue_manager {action} cannot parse content as json -{content}.")
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
                logger.warning(f"<issue_manager> - issue_manager {
                    action} cannot parse content as yaml either -{content}... Will use it as str.")
                if action == "create":
                    content_obj = {"title": f"{content:.24s}",
                                   "description": content}
                elif action == "update":
                    content_obj = {"details": content}
    else:
        content_obj = content or {}

    logger.debug(
        "%s %s - content parsed: %s, '%s'", action, issue, type(content_obj), content_obj)

    match action:
        case 'list':
            issue_dir = os.path.join(config.ISSUE_BOARD_DIR, issue)
            results = []
            for root, dirs, files in os.walk(issue_dir):
                for file in files:
                    issue_number = root.removeprefix(config.ISSUE_BOARD_DIR + '/')
                    if file == f"{issue_number.replace('/', '.')}.json":
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r') as f:
                                data = json.load(f)
                            updates = data.get('updates', [])
                            updates.sort(key=lambda x: x.get('updated_at', 0))
                            if updates:
                                latest_status = [
                                    u for u in updates if u.get('status', "")]
                                status = latest_status[-1].get(
                                    'status', "unknown") if latest_status else "new"
                                latest_priority = [
                                    u for u in updates if u.get('priority', "")]
                                priority = latest_priority[-1].get(
                                    'priority', "5 - unknown") if latest_status else "4 - Low"
                                latest_updated_by = [
                                    u for u in updates if u.get('updated_by', "")]
                                updated_by = latest_updated_by[-1].get(
                                    'updated_by', "unknown") if latest_updated_by else "unknown"
                                latest_assignee = [
                                    u for u in updates if u.get('assignee', "")]
                                assigned_to = latest_assignee[-1].get(
                                    'assignee', updated_by) if latest_assignee else updated_by
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
                                pri_rank = {"low": 4, "medium": 3,
                                            "high": 2, "critical": 1, "urgent": 0}
                                priority = f"{
                                    pri_rank[priority.lower()]} - {priority.capitalize()}"
                            results.append({'issue': issue_number, 'priority': priority, 'status': status,
                                           'assignee': assigned_to, 'title': data.get('title', "no title")})
                        except json.JSONDecodeError as e:
                            logger.error("%s - could not list %s due to %s", action, issue, e, exc_info=e)
                            results.append(
                                {'issue': issue_number, 'status': f"Error Decoding Json"})
                        except FileNotFoundError as e:
                            logger.error("%s - could not list %s due to %s. file_path=%s",
                                         action, issue, e, file_path, exc_info=e)
                            results.append(
                                {"issue": issue_number, "status": f"Error, issue {issue_number} does not exist."})
                        except Exception as e:
                            logger.error("%s - could not list %s due to %s. file_path=%s",
                                         action, issue, e, file_path, exc_info=e)
                            results.append(
                                {"issue": issue_number, "status": f"Error reading {issue_number} due to {e}"})
            result = results

        case "create":
            issue_dir = os.path.join(config.ISSUE_BOARD_DIR, issue)
            if not os.path.exists(issue_dir):
                os.makedirs(issue_dir, exist_ok=True)
            existing_sub_issues = [int(entry.name) for entry in os.scandir(issue_dir)
                                   if entry.is_dir()
                                   and entry.name.isdigit()
                                   and os.path.exists(os.path.join(issue_dir, entry.name, f"{os.path.join(issue, entry.name).replace('/', '.')}.json"))]
            new_sub_issue_number = f"{
                max([issue_no for issue_no in existing_sub_issues], default=0) + 1}"
            new_issue_dir = os.path.join(issue_dir, new_sub_issue_number)
            new_issue_number = os.path.join(issue, new_sub_issue_number)

            try:
                if content_obj:
                    content_obj.setdefault('created_at', datetime.now().strftime(
                        "%Y-%m-%dT%H:%M:%S.%f"))
                    last_update: dict = content_obj.setdefault('updates', [{}])[-1]
                    last_update.setdefault('updated_by', caller)
                    last_update.setdefault('updated_at', datetime.now().strftime(
                        "%Y-%m-%dT%H:%M:%S.%f"))
                    last_update.setdefault('priority', "4 - Low")
                    last_update.setdefault('assignee', assignee if assignee else
                                           caller if caller else "unknown")
                    last_update.setdefault('status', "new")

                if not os.path.exists(new_issue_dir):
                    logger.debug("%s issue %s dir does not exist, creating %s ....",
                                 action, issue, new_issue_dir)
                    os.makedirs(new_issue_dir, exist_ok=True)

                new_issue_file = os.path.join(
                    new_issue_dir, f"{new_issue_number.replace('/', '.')}.json")
                with open(new_issue_file, 'w') as ifh:
                    logger.debug("%s issue %s, writing contents to %s", action, new_issue_number, new_issue_file)
                    json.dump(content_obj, ifh)
                result = {"issue": new_issue_number, "status": "success",
                          "message": f"issue {new_issue_number} created successfully."}
            except Exception as e:
                logger.error("%s issue %s failed because error %s",
                             new_issue_number, e, exc_info=e)
                result = {"issue": new_issue_number,
                          "status": "Error", "message": e}

        case "read":
            try:
                issue_dir = os.path.join(config.ISSUE_BOARD_DIR, issue)
                issue_file = os.path.join(
                    issue_dir, f"{issue.replace('/', '.')}.json")
                result = {'issue#': issue}
                with open(issue_file, 'r') as jsonfile:
                    data = json.load(jsonfile)
                    updates = data.get('updates', [])
                    result['latest_status'] = max(updates,
                                                  key=lambda x: ('status' in x, x.get('updated_at', '2000-01-01T00:00:00.000')), default={}).get('status', "new")
                    result['latest_priority'] = max(updates,
                                                    key=lambda x: ('priority' in x, x.get('updated_at', '2000-01-01T00:00:00.000')), default={}).get('priority', "4 - Low")
                    result['latest_updated_by'] = max(updates,
                                                      key=lambda x: ('updated_by' in x, x.get('updated_at', '2000-01-01T00:00:00.000')), default={}).get('updated_by', "unknown")
                    result['latest_assignee'] = max(updates,
                                                    key=lambda x: ('assignee' in x, x.get('updated_at', '2000-01-01T00:00:00.000')), default={}).get('assignee', "unknown")
                    result.update(data)
            except Exception as e:
                logger.error("Cannot %s issue %s because %s", action,
                             issue, e, exc_info=e)
                result = {"issue": issue, "status": "Error", "message": f"Cannot read issue {issue} because {e}"}

        case "update":
            if content_obj and "updated_at" not in content_obj:
                content_obj['updated_at'] = datetime.now().strftime(
                    "%Y-%m-%dT%H:%M:%S.%f")
            if content_obj and "updated_by" not in content_obj:
                content_obj['updated_by'] = caller
            if content_obj and "assignee" not in content_obj:
                content_obj['assignee'] = caller

            issue_dir = os.path.join(config.ISSUE_BOARD_DIR, issue)
            issue_file = os.path.join(
                issue_dir, f"{issue.replace('/', '.')}.json")
            try:
                with open(issue_file, 'r') as ifile:
                    issue_content = json.load(ifile)
                issue_updates = issue_content.get("updates", [])
                if max(issue_updates, key=lambda x: ('status' in x, x.get('updated_at', 0)), default={}).get('status', "new") == "completed":
                    result = {"issue": issue, "status": "error",
                              "message": "This issue is already completed. Please create a new sub issue if you have additional actions needed to be taken on this issue."}
                    return result
                if issue_content and "updates" in issue_content:
                    issue_content['updates'].append(content_obj)
                else:
                    issue_content['updates'] = [content_obj]
                with open(issue_file, 'w') as ifile:
                    json.dump(issue_content, ifile)
                result = {"issue": issue, "status": "success"}
            except FileNotFoundError as e:
                logger.error("%s issue %s failed due to error %s. issue_file=%s",
                             action, issue, e, issue_file, exc_info=e)
                result = {"issue": issue, "status": f"Error, issue {issue} does not exist."}
            except Exception as e:
                logger.error("Cannot {action} issue %s because %s",
                             issue, e, exc_info=e)
                result = {"issue": issue, "status": "Error", "message": f"Cannot update {issue} because {e}"}

        case "assign":
            issue_dir = os.path.join(config.ISSUE_BOARD_DIR, issue)
            issue_file = os.path.join(
                issue_dir, f"{issue.replace('/', '.')}.json")
            try:
                with open(issue_file, 'r') as ifile:
                    issue_content = json.load(ifile)
                if not content:
                    content_obj = {}
                if content_obj and not hasattr(content_obj, "updated_at"):
                    content_obj['updated_at'] = datetime.now().strftime(
                        "%Y-%m-%dT%H:%M:%S.%f")
                if "updated_by" not in content_obj:
                    content_obj['updated_by'] = caller
                if "details" not in content_obj:
                    content_obj['details'] = f"assign {issue} to {assignee}."
                if assignee:
                    agents_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agents")
                    print(f"{agents_dir=}")
                    agents_list = [entry.removesuffix(".json") for entry in os.listdir(
                        agents_dir) if entry.endswith(".json")]
                    if assignee in agents_list:
                        content_obj['assignee'] = assignee
                    else:
                        result = {"issue": issue, "status": "error", "message": f"Assignee {
                            assignee} is not a valid agent, please only assign to one of the following agents: {[agents_list]}."}
                        return result
                else:
                    content_obj['assignee'] = caller
                if issue_content and "updates" in issue_content:
                    issue_content['updates'].append(content_obj)
                else:
                    issue_content['updates'] = [content_obj]
                with open(issue_file, 'w') as ifile:
                    json.dump(issue_content, ifile)
                result = {"issue": issue, "status": "success",
                          "message": f"Assigned to {assignee} successfully."}
            except FileNotFoundError as e:
                logger.error("%s issue %s failed due to error %s. issue_file=%s",
                             action, issue, e, issue_file, exc_info=e)
                result = {"issue": issue, "status": f"Error, issue {issue} does not exist."}
            except Exception as e:
                logger.error("%s issue %s failed due to error %s. issue_file=%s", action,
                             issue, e, issue_file, exc_info=e)
                result = {"issue": issue, "status": "Error", "message": e}

        case _:
            logger.warning(
                "%s is not a valid action for issue_manager, please only use list/create/update/assign.", action)
            result = {"status": "Error", "message":
                      f"{action} is not known action. Only 'list', 'create', 'read', 'update', 'assign' are valid actions"}

    logger.debug("exiting %s %s - result: %s", action, issue, result)
    return result


def initialize_package(package_dir: str | None = None) -> str:
    """Initialize the __init__.py and __manin__.py files of a package.

    Args:
      package_dir: the path to the package, default is the namesake of the project

    Returns:
      the status of the package initializatio
    """
    if package_dir is None:
        # the default package dir is a namesake of the project under the project_dir
        package_dir = os.path.join(os.getcwd(), os.path.basename(os.getcwd()))
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


def initialize_Dockerfile(project_name: str | None = None, dockerfile_path: str | None = None) -> str:
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
        result = (f"<init Dockerfile> {
                  dockerfile_path} already exist, will not overwrite it, exiting...\n")
    else:
        try:
            with open(dockerfile_path, "w") as df:
                df.write(base_Dockerfile)
        except Exception as e:
            result = f"<init Dockerfile> got an Error: {e}\n"
        else:
            result = f"<init Dockerfile> {dockerfile_path} for {
                project_name} has been successfully initialized.\n"
    base_docker_compose = f"""\
services:
  {project_name}:
    build: .
    command: poetry run python -m {project_name}
    ports:
      - "${{SERVER_PORT:-8080}}:8080"
    restart: always
"""
    docker_compose_path = os.path.join(os.path.dirname(
        (dockerfile_path)), "docker-compose.yaml")
    if os.path.exists(docker_compose_path):
        result += (f"<init Dockerfile> {
                   docker_compose_path} already exist, will not overwrite it, exiting...")
    else:
        try:
            with open(docker_compose_path, "w") as df:
                df.write(base_docker_compose)
        except Exception as e:
            result += f"<init Dockerfile> got an Error: {e}"
        else:
            result += f"<init Dockerfile> {docker_compose_path} for {
                project_name} has been successfully initialized."
    return result


def initialize_startup_script(project_dir: str | None = None) -> str:
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
    * )
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


def initialize_agent_files(agent_parent_dir: str | None = None) -> str:
    """Initialize the agent files
    """
    logger.debug(
        f"<Initializing> - updating agents instructions as part of project setup. Should not be used in production")
    import os
    import json
    from ..defs import new_instructions

    agents_dir = os.path.join(
        agent_parent_dir if agent_parent_dir else os.path.dirname(os.path.dirname(__file__)), "agents")
    logger.info(f"updating agent info in {agents_dir=}")
    agents_list = [entry.removesuffix(".json") for entry in os.listdir(
        agents_dir) if entry.endswith(".json")]
    for agent_name in agents_list:
        config_json = os.path.join(agents_dir, f"{agent_name}.json")
        if new_instructions.get(agent_name):
            with open(config_json, "r") as f:
                agent_config = json.load(f)

            agent_config["instruction"] = new_instructions[agent_name] + \
                new_instructions["all"]
            with open(config_json, "w") as f:
                json.dump(agent_config, f, indent=4)
    logger.info(
        f"<Initializing> - updated {len(agents_list)} agents instructions")
    return 'done.'


def execute_module(module_name: str, method_name: str | None = None, args: list = [], **kwargs) -> str:
    """Execute a specified method from a Python module.

    Args:
        module_name: Name of the module to execute.
        method_name: Name of the method to execute.
        args: Arguments for the method.
        kwargs: Keyword arguments for the method.

    Returns: 
        A dictionary with 'output' or 'error' as a key.

    Example::
        >>> agent = OpenAI_Agent("pm")
        >>> agent.execute_module('math', 'sqrt', args=[16]).strip()
        '{"output": 4.0}'
        >>> result = agent.execute_module('os', 'getcwd')
        >>> os.getcwd() in result
        True

    """
    # Prepare the command to execute
    if method_name:
        python_command = f"import json, {module_name};" \
            "output={};" \
            f"output['output'] = getattr({module_name}, '{method_name}')(*{args}, **{kwargs}); " \
            "print(json.dumps(output))"
        python_mode = "-c"
        python_command_args = []
    else:
        python_command = f"{module_name}"
        python_command_args = args
        python_mode = "-m"

    logger.debug(f"execute_module - Executing {python_command}")
    # Execute the command as a subprocess
    try:
        result = subprocess.run(['python', python_mode, python_command, *python_command_args],
                                capture_output=True, text=True, check=False, shell=False, timeout=120)
        if result.returncode == 0:
            logger.debug(
                f"execute_module -Execution returned 0 exit code")
            if method_name:
                return result.stdout
            else:
                return result.stdout.strip()
        else:
            logger.error(f"execute_module -Execution returned non-0 exit code. Output: {
                result.stdout}; Error: {result.stderr}")
            return f'Execution finished with non-0 return code: {result.stderr}, Output: {result.stdout}'
    except subprocess.CalledProcessError as e:
        logger.error(
            f"<execute_module -Execution failed. Error: {e}")
        return f'Execution failed with error: {e}'
    except subprocess.TimeoutExpired:
        logger.error(
            f"<execute_module -Execution failed. Error: timeout")
        return f'Execution timed out, if this happens often, please check if this module execution is hang.'
    except Exception as e:
        logger.error(
            f"<execute_module -Execution failed. Error: {e}")
        return f'Execution failed with error: {e}'


def execute_command(command_name: str, args: list = [], asynchronous: bool = False) -> str:
    """Execute a specified method from a Python module.

    Args:
        command_name: Name of the module to execute.
        args: Arguments for the method.

    Returns: 
        A dictionary with 'output' or 'error' as a key.

    Example::
        >>> agent = OpenAI_Agent("pm")
        >>> agent.execute_command('echo', args=['hello', 'world'])
        '{"output": "hello world\\\\n"}'
        >>> result = agent.execute_command('pwd')
        >>> import json
        >>> json.loads(result).get('output').strip() == os.getcwd()
        True
        >>> agent.execute_command('ls', args=['non-exist.dir'])
        "execute_command returned non-0 return code. Output:, Error: ls: cannot access 'non-exist.dir': No such file or directory\\n"
    """
    import json
    # Execute the command as a subprocess
    try:
        if asynchronous:
            process = subprocess.Popen([command_name, *args],
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE,
                                       text=True,
                                       shell=False)
            logger.debug(
                f"execute_command - started parallel process: {process.pid}")
            return f"started {command_name} in a parallel process: {process.pid}"
        else:
            result = subprocess.run([command_name, *args],
                                    capture_output=True, text=True, check=False, shell=False, timeout=120)
            logger.debug(
                f"execute_command -returned {result.stdout}.")
            output = {'output': result.stdout}
            if result.returncode == 0:
                return json.dumps(output)
            else:
                logger.error(
                    f"execute_command -Execution returned non-0 exit code. Error: {result.stderr}")
                return f"execute_command returned non-0 return code. Output:{result.stdout}, Error: {result.stderr}"
    except subprocess.CalledProcessError as e:
        logger.error(
            f"execute_command -Execution failed. Error: {e}")
        return f"error: {e}"
    except subprocess.TimeoutExpired:
        logger.error(
            f"execute_command -Execution failed. Error: timeout")
        return f'Execution timed out, if this happens often, please check if this module execution is hang.'
    except Exception as e:
        logger.error(
            f"execute_command -Execution failed. Error: {e}")
        return f'Execution failed with error: {e}'
