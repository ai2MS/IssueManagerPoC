"""initialize a software development project
This is the __main__ file belonging to the bootstrap module. Which is used to kick of a new project.
It is responsible for creating the project directory and initializing it with bootstrap code.

Usage:
    python __main__.py [-p <project_name>] [-n]
    <project_name> is the name of the new project, default project name is "default", or can be set by PROJECT_NAME environment variable.
    -n means start over, it will delete the existing "team" of agents for the project and copy the bootstrap agents over.

"""
from datetime import datetime
import os
import sys
import shutil
import subprocess
from . import logger, utils
from .config import config

def main(project_name: str = 'default_project', overwrite: bool = False) -> None:
    """
    Creates a new project directory and initializes it with bootstrap code.

    Args:
        project_name (str, optional): The name of the project. Defaults to 'default_project'.
        overwrite (bool, optional): Whether to delete the existing project directory and start over. Defaults to False.

    Returns:
        None

    Raises:
        FileExistsError: If the project directory already exists.
        Exception: If there is an error creating the project directory.
    """
    EMBEDDED_DEV_TEAM_NAME = "embedded_dev_team"
    new_branch_name = ''
    if __package__ and __package__.endswith("bootstrap"):
        try:
            current_file = os.path.realpath(__file__)
            current_dir = os.path.dirname(current_file)
            current_parent_dir = os.path.dirname(current_dir)
            project_dir = os.path.join(os.getcwd(), project_name)
            parent_dir = os.path.dirname(project_dir)
            project_team_dir = os.path.join(project_dir, EMBEDDED_DEV_TEAM_NAME)
            try:
                current_git_branch = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True, check=True).stdout.strip()
                logger.debug(f"Currently on branch {current_git_branch}")
                if (current_git_branch in ["main", "master"]):
                    old_branch_name = current_git_branch
                    logger.warn(f"??Currently on branch <{current_git_branch}>, we shall never change it without a PR. creating new branch...")
                    all_branches = subprocess.run(['git', 'branch', '--list'], capture_output=True, text=True).stdout
                    new_branch_name = f"{project_name}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    if new_branch_name in [branch_name.strip() for branch_name in all_branches.split()]:
                        new_branch_name = f"{project_name}-{datetime.now().strftime('%Y%m%d%H%M%S.%f')}"
                    return_text = subprocess.run(['git', 'checkout', '-b', new_branch_name], capture_output=True, text=True).stdout.strip()
                    logger.debug(f"creating new branch {new_branch_name} returned {return_text}")
            except Exception as e:
                logger.fatal(f"Error setting up branch for {project_name}. Can't continue.")
                exit(1)

            if os.path.exists(project_dir):
                os.chdir(project_dir)
                if os.path.exists(os.path.join(project_dir, "pyproject.toml")):
                    poetry_version_result = subprocess.run(['poetry', 'version'], capture_output=True, text=True)
                    poetry_version_result.check_returncode()
                    if poetry_version_result.stdout.split()[0] == project_name.replace("_", "-"):
                        logger.info(f"Project <{project_name}> has already been previously initialized.")
                    else:
                        logger.error(f"Directory {project_dir} already contain a project that is called {poetry_version_result.stdout.split()[0]}, can't initialize it as {project_name}")
                        sys.exit(1)
                else:
                    poetry_init_result = subprocess.run(['poetry', 'init', '--name', project_name, '--no-interaction', project_name], capture_output=True, text=True)
                    poetry_init_result.check_returncode()
                    overwrite = True
                    logger.info(f"New project <{project_name}> is initialized.")
            else:
                poetry_new_result = subprocess.run(['poetry', 'new', '--name', project_name, '--no-interaction', project_name], capture_output=True, text=True)
                poetry_new_result.check_returncode()
                logger.info(f"New project <{project_name}> is created.")
                copy_directory(os.path.join(current_parent_dir,"issue_board"), os.path.join(project_dir, "issue_board"))
                os.chdir(project_dir)
                overwrite = True

            if overwrite:
                copy_directory(current_dir, project_team_dir)
                init_agent_files = utils.initialize_agent_files()
                logger.debug(f"Initializing agent files returned {init_agent_files}")
                init_package_result = utils.initialize_package(os.path.join(project_dir, os.path.basename(project_dir)))
                logger.debug(f"Initializing package returned {init_package_result}")
                init_Dockerfile_result = utils.initialize_Dockerfile(project_name)
                logger.debug(f"Initializing docker returned {init_Dockerfile_result}")
                init_script_result = utils.initialize_startup_script()
                logger.debug(f"Initializing startup script returned {init_script_result}")
                os.makedirs("docs/design", exist_ok=True)
                with open("docs/design/dir_structure.yaml", "w") as dddf:
                    dddf.write(utils.dir_tree("."))
                logger.info(f"and project <{project_name}> is initialized with bootstrap code.")
        except Exception as e:
            logger.fatal(f"Error {e} setting up project: " + project_dir)
            sys.exit(101)
        
        try:
            os.chdir(project_dir)
            # import importlib
            # sys.path.insert(0, project_dir)
            # actual_project_team = importlib.import_module(project_name+"."+EMBEDDED_DEV_TEAM_NAME)
            # actual_project_team.load_agents()
            poetry_result = subprocess.run(['poetry', 'install'], capture_output=True, text=True)
            poetry_result.check_returncode()
            logger.info(f"Project <{project_name} is initialized with bootstrap code. Transferring execution to project <{project_name}>")
            poetry_result = subprocess.run(['poetry', 'run', 'python', '-m', EMBEDDED_DEV_TEAM_NAME, "-p", project_name], check=True)
        except Exception as e:
            logger.error(f"{project_name} agents run into errors {e}. stack: {str(e)}")
            if new_branch_name:
                response = input(f"{project_name} agents run into errors, do you want to drop the new git branch {new_branch_name}?")
                if response.lower() in ["y", "yes"]:
                    subprocess.run(['git', 'reset', '--hard'], capture_output=True, text=True)
                    subprocess.run(['git', 'checkout', old_branch_name], capture_output=True, text=True)
                    subprocess.run(['git', 'branch', '-D', new_branch_name], capture_output=True, text=True)

    elif __package__:
        # if invoke the project.team instead of the bootstrap
        current_file = os.path.realpath(__file__)
        current_dir = os.path.dirname(current_file)
        current_parent_dir = os.path.dirname(current_dir)
        project_dir = current_parent_dir

        try:
            current_git_branch = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True)
            logger.debug(f"Currently on branch {current_git_branch}")
            os.chdir(project_dir)
            if (current_git_branch in ["main", "master"]):
                logger.fatal(f"??Currently on branch <{current_git_branch}>, we shall never change it without a PR. \nPlease create a new branch or switch to one of the following branches...")
                all_branches = subprocess.run(['git', 'branch', '--list'], capture_output=True, text=True)
                for branch in sorted(all_branches, reverse=True):
                    print(f"- {branch}")
                    exit(1)
        except FileNotFoundError:
            logger.fatal(f"It seems git was not installed on this system. Can't continue without git.")
            exit(2)
        except Exception as e:
            logger.fatal(f"Error setting up git env: {e}, can't continue.")
            exit(1)

        from . import load_agents
        logger.debug(f"Invoked as {__package__}, not bootstrap, loading agents")
        load_agents()
    else:
        logger.fatal(f"__main__ can't run as a script, please execute it as a module using python -m {os.path.dirname(__file__)}")
        exit(1)


def copy_directory(src_dir, dst_dir):
    """
    Copy a directory and its contents to a new location.

    Args:
        src_dir (str): The path of the source directory to be copied.
        dst_dir (str): The path of the destination directory where the source directory and its contents will be copied to.

    Returns:
        None

    Raises:
        None
    """
    os.makedirs(dst_dir, exist_ok=True)
    for item in os.listdir(src_dir):
        src_item = os.path.join(src_dir, item)
        dst_item = os.path.join(dst_dir, item)
        if os.path.isdir(src_item):
            copy_directory(src_item, dst_item)
        else:
            shutil.copy2(src_item, dst_item)


if __name__ == "__main__":
    match __package__:
        case s if s.endswith("bootstrap"):
            try:
                utils.project_name = config.PROJECT_NAME
                overwrite = False
                for arg in sys.argv:
                    if arg == "-p":
                        utils.project_name = sys.argv[sys.argv.index(arg) + 1]
                    elif arg == "-o":
                        overwrite = sys.argv[sys.argv.index(arg) + 1] == "True"
            except IndexError:
                logger.fatal(f"Error parsing arguments.\nUsage:\npython -m {os.path.basename(os.path.dirname(__file__))} [-p project_name] [-o True|False]\n")
                sys.exit(1)
            except Exception as e:
                logger.fatal(f"Error parsing arguments: {e}")
                sys.exit(1)
        case ''|None:
            logger.fatal(f"__main__ can't run as a script, please execute it as a module using python -m {os.path.basename(os.path.dirname(__file__))}")
            exit(1)
        case _:
            utils.project_name = os.path.basename(os.getcwd())
            overwrite = False

    main(utils.project_name, overwrite)
