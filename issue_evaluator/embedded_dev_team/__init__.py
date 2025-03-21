"""
This is the entry point of a software engineering project. 

The new piradigm is to have new software all "self-writen" and evolve by itself.
This means software are going to update themselves to evolve instead of relying on
some other agents human or AI developers. 

This module has two models, when called as Bootstrap, it creates a new software engineering project. 
when called as a project/team it continue an existing software project.

Usage:
    python -m sweteam.bootstrap [-p project_name] [-n]
    project_name is what the actual project should be called, if not provided, its "default", you can also set PROJECT_NAME environment variable for this
    -n will remove old project dir and start a new one with that name, so be careful using this option.

    or 

    python -m default_project.team
    all arguments are ignored, this will continue the previously setup project
"""

import logging
import logging.handlers
import os
from .config import config
from .utils.log import logger

my_name = (config.PROJECT_NAME or os.path.basename(os.getcwd()))
