"""initialize a software development project
This is the __main__ file belonging to the bootstrap module. Which is used to kick of a new project.
It is responsible for creating the project directory and initializing it with bootstrap code.

Usage:
    python __main__.py [-p <project_name>] [-n]
    <project_name> is the name of the new project, default project name is "default", or can be set by PROJECT_NAME environment variable.
    -n means start over, it will delete the existing "team" of agents for the project and copy the bootstrap agents over.

"""

import os
import sys
import shutil

def main(project_name: str = 'default_team', start_over: bool = False) -> None:
    """
    Creates a new project directory and initializes it with bootstrap code.

    Args:
        project_name (str, optional): The name of the project. Defaults to 'default_project'.
        start_over (bool, optional): Whether to delete the existing project directory and start over. Defaults to False.

    Returns:
        None

    Raises:
        FileExistsError: If the project directory already exists.
        Exception: If there is an error creating the project directory.
    """
    if __package__ and __package__.endswith("bootstrap"):
        try:
            current_file = os.path.realpath(__file__)
            current_dir = os.path.dirname(current_file)
            parent_dir = os.path.dirname(current_dir)
            project_dir = os.path.join(parent_dir, project_name)
            if start_over:
                shutil.rmtree(project_dir, ignore_errors=True)
            os.makedirs(project_dir, exist_ok=False)
            print(f"New project <{project_name} is created.>")
            copy_directory(current_dir, project_dir)
            print(f"and project <{project_name} is initialized with bootstrap code.>")
        except FileExistsError:
            print(f"Dir <{project_dir}> already exist. Continue project <{project_name}>")
        except Exception as e:
            print(f"Error {e} creating project directory: " + project_dir, "Please check permissions.")
            exit()
        
        import importlib
        sys.path.insert(0, parent_dir)
        actual_project = importlib.import_module(project_name)
        os.chdir(project_dir)
        actual_project.load_agents()
    else:
        # if ppl invoke the project-team instead of the boot strap
        from . import load_agents
        load_agents()


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
    incoming_project_name = os.environ.get("PROJECT_NAME", "default") + "_team"
    incomeing_start_over = True
    for arg in sys.argv:
        if arg == "-p":
            incoming_project_name = sys.argv[sys.argv.index(arg) + 1]
        elif arg == "-n":
            incomeing_start_over = True

    main(incoming_project_name, incomeing_start_over)
