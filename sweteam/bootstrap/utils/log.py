"""code setting up logger using context manager"""

import logging
import logging.handlers
from contextlib import contextmanager
from typing import Generator
import os


def get_logger(name: str, stream: str | bool = 'INFO', file: str | bool = '',
               *, log_file: str = '', level: str = 'DEBUG') -> logging.Logger:
    """configure a logger with multiple handlers

    Args:
        name: the name of the logger that will be shown in the logs
        stream: set stream log level, default is 'INFO'
        file: set rotating file log level, default is OFF
        level: the logger's own level, default is 'DEBUG'

    Yields:
        logger: the logger object with name and handler set up
    """
    LOG_LEVEL = {
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "CRITICAL": logging.CRITICAL
    }
    logger_ = logging.getLogger(name)
    logger_.setLevel(LOG_LEVEL[level] if level in LOG_LEVEL else logging.DEBUG)

    console_handler = logging.StreamHandler()
    if stream in LOG_LEVEL and (console_handler.__class__ not in
                                {h.__class__ for h in logger_.handlers}):
        console_handler.setLevel(LOG_LEVEL[stream])
        c_format = logging.Formatter("#%(levelname)9s - %(name)s - %(filename)s:%(lineno)d"
                                     " %(funcName)s() - %(message)s")
        console_handler.setFormatter(c_format)
        logger_.addHandler(console_handler)

    log_file = log_file or f"{__file__[:-3]}.log"
    file_handler_class = logging.handlers.RotatingFileHandler
    if file in LOG_LEVEL:
        if (file_handler_class in {h.__class__ for h in logger_.handlers}):
            logger_.warning("Setting logging-to-file to level %s but Logger %s already has a file handler,"
                            " skipping...", file, name)
        else:
            file_handler = file_handler_class(
                log_file, maxBytes=10485760, backupCount=9, encoding='utf-8')
            file_handler.setLevel(LOG_LEVEL[file])
            f_format = logging.Formatter("%(asctime)s %(levelname)s - %(name)s "
                                        "- %(filename)s:%(lineno)d  "
                                        "%(module)s.%(funcName)s() - %(message)s")
            file_handler.setFormatter(f_format)
            logger_.addHandler(file_handler)

    if not logger_.hasHandlers():
        logger_.addHandler(logging.NullHandler())

    return logger_


@contextmanager
def logging_context(*args, **kwargs) -> Generator[logging.Logger, None, None]:
    """use contextmanager to setup/shutdown logging"""
    logger_ = None
    try:
        logger_ = get_logger(*args, **kwargs)
        yield logger_
    finally:
        try:
            if isinstance(logger_, logging.Logger):
                logger_.info("shutting down the logging facility...")
        except Exception as e:
            print(f"Can't log final message to logger, {e=}"
                  "shutting down the logging facility...")
        logging.shutdown()
