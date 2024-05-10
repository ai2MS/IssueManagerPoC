"""Kick of a new software project

Usage:
    python -m bootstrap [project_name]
"""

import os
import sys
import shutil

def main(project_name: str = 'default_project') -> None:
    try:
        current_file = os.path.realpath(__file__)
        current_dir = os.path.dirname(current_file)
        parent_dir = os.path.dirname(current_dir)
        project_dir = os.path.join(parent_dir, project_name)
        os.makedirs(project_dir, exist_ok=False)
        print(f"New project <{project_name} is created.>")
    except FileExistsError:
        print(f"Dir <{project_dir}> already exist. Continue project <{project_name}>")
    except Exception as e:
        print(f"Error {e} creating project directory: " + project_dir, "Please check permissions.")
        exit()
    
    copy_directory(current_dir, project_dir)
    
    import importlib
    sys.path.insert(0, parent_dir)
    actual_project = importlib.import_module(project_name)
    actual_project.load_agents()


def copy_directory(src_dir, dst_dir):
    os.makedirs(dst_dir, exist_ok=True)
    for item in os.listdir(src_dir):
        src_item = os.path.join(src_dir, item)
        dst_item = os.path.join(dst_dir, item)
        if os.path.isdir(src_item):
            copy_directory(src_item, dst_item)
        else:
            shutil.copy2(src_item, dst_item)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        main()
