"""
This module contains utility functions for working with files.

Usage:
    python -m utils [update_agent]
"""

from .file_utils import dir_structure
from typing import Callable, Any
import os
import subprocess
from enum import Enum
import yaml
import json
from datetime import datetime
from .initialize_project import initialize_package, initialize_Dockerfile, initialize_startup_script
from .log import logger
from ..config import config

def get_dot_notation_value(dict_obj, dot_path, default=None):
    """
    Access nested dictionary values using dot notation
    
    Args:
        dict_obj (dict): The dictionary to search
        dot_path (str): Path to value using dot notation (e.g. "status.name")
        default (any): value to return if the key is not found, None if ommited
    Returns:
        The value if found, None if not found
    """
    try:
        parts = dot_path.split('.')
        value = dict_obj
        for part in parts:
            value = value[part]
        return value
    except (KeyError, TypeError):
        return default

def timed_execution(f: Callable, *args, **kwargs) -> Any:
    import time
    method_name=f.__self__.__class__.__name__ + "." + f.__name__ if hasattr(f, '__self__') else f.__name__
    logger.info("Start timed execution of %s...", method_name)
    start_time = time.time()
    return_value = f(*args, **kwargs)
    end_time = time.time()
    elapsed_time = end_time - start_time
    logger.info("Timed Execution of %s completed in %.2f seconds", method_name, elapsed_time)
    return return_value

async def timed_async_execution(f: Callable, *args, **kwargs) -> Any:
    import time
    method_name=f.__self__.__class__.__name__ + "." + f.__name__ if hasattr(f, '__self__') else f.__name__
    logger.info("Start timed Async execution of %s...", method_name)
    start_time = time.time()
    return_value = await f(*args, **kwargs)
    end_time = time.time()
    elapsed_time = end_time - start_time
    logger.info("Timed Async Execution of %s completed in %.2f seconds", method_name, elapsed_time)
    return return_value


class Action(Enum):
    """Action Enum for the agent to take."""
    LIST = "list"
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    ASSIGN = "assign"

def issue_manager(action: str, issue: str = '', only_in_state: list = [],
                  content: str | None = None, assignee: str | None = None, caller: str = "unknown") -> dict | list:
    """Manage issues: list, create, read, update, assign
    Example::
    >>> issue_manager("list", "0")
    '[{"issue": "0", "priority": "0", "status": "completed", "assignee": "unknown", "title": "initial bootstrap code"}]'
    """
    content_obj: dict = {}
    logger.debug("entering...%s",
                 f"{action=}, {issue=}, {only_in_state=}, {content=}, {assignee=}, {caller=})")
    if isinstance(content, str):
        try:
            # correct one of the most common json string error - newline instead of \\n in it.
            content_obj = json.loads(content.replace("\n", "\\n"))
        except Exception as e:
            logger.warning(
                "%s cannot parse content '%s' as JSON.", action, content)
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
                logger.warning(
                    "%s cannot parse content '%s' as YAML either... Will use it as str.", action, content)
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
                    issue_number = root.removeprefix(
                        config.ISSUE_BOARD_DIR + '/')
                    if file == f"{issue_number.replace('/', '.')}.json":
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r') as f:
                                data = json.load(f)
                            updates: list = data.get('updates', [])
                            logger.debug("before sorting: %s", updates)
                            if updates:
                                updates.sort(key=lambda x: x.get('updated_at', ""))
                                logger.debug("after sorting: %s", updates)
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
                            logger.error(
                                "%s - could not list %s due to %s", action, issue, e, exc_info=e)
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
                    last_update: dict = content_obj.setdefault(
                        'updates', [{}])[-1]
                    last_update.setdefault('updated_by', caller)
                    last_update.setdefault('updated_at', datetime.now().strftime(
                        "%Y-%m-%dT%H:%M:%S.%f"))
                    last_update.setdefault('priority', "4 - Low")
                    last_update.setdefault('assignee', assignee if assignee else
                                           caller if caller else "unknown")
                    last_update.setdefault('status', "new")
                    last_update.setdefault('details', "create new issue.")

                if not os.path.exists(new_issue_dir):
                    logger.debug("%s issue %s dir does not exist, creating %s ....",
                                 action, issue, new_issue_dir)
                    os.makedirs(new_issue_dir, exist_ok=True)

                new_issue_file = os.path.join(
                    new_issue_dir, f"{new_issue_number.replace('/', '.')}.json")
                with open(new_issue_file, 'w') as ifh:
                    logger.debug("%s issue %s, writing contents to %s",
                                 action, new_issue_number, new_issue_file)
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
                result = {"issue": issue, "status": "Error",
                          "message": f"Cannot read issue {issue} because {e}"}

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
                result = {"issue": issue, "status": f"Error, issue {
                    issue} does not exist."}
            except Exception as e:
                logger.error("Cannot {action} issue %s because %s",
                             issue, e, exc_info=e)
                result = {"issue": issue, "status": "Error",
                          "message": f"Cannot update {issue} because {e}"}

        case "assign":
            issue_dir = os.path.join(config.ISSUE_BOARD_DIR, issue)
            issue_file = os.path.join(
                issue_dir, f"{issue.replace('/', '.')}.json")
            try:
                with open(issue_file, 'r') as ifile:
                    issue_content = json.load(ifile)
                if not content:
                    content_obj = {}
                if "updated_at" not in content_obj:
                    content_obj['updated_at'] = datetime.now().strftime(
                        "%Y-%m-%dT%H:%M:%S.%f")
                if "updated_by" not in content_obj:
                    content_obj['updated_by'] = caller
                if "details" not in content_obj:
                    content_obj['details'] = f"assign #{issue} to {assignee}."
                if assignee:
                    agents_dir = os.path.join(os.path.dirname(
                        os.path.dirname(__file__)), "agents")
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
                logger.debug("assigning %s to %s, details: %s", issue, assignee, content_obj)
                with open(issue_file, 'w') as ifile:
                    json.dump(issue_content, ifile)
                result = {"issue": issue, "status": "success",
                          "message": f"Assigned to {assignee} successfully."}
            except FileNotFoundError as e:
                logger.error("%s issue %s failed due to error %s. issue_file=%s",
                             action, issue, e, issue_file, exc_info=e)
                result = {"issue": issue, "status": f"Error, issue {
                    issue} does not exist."}
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
