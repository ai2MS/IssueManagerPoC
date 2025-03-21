from .base_agent import BaseAgent, AgentFactory
import logging

msg_logger = logging.getLogger("message_log")
if __package__ and not __package__.endswith("bootstrap"):
    msg_file_handler = logging.FileHandler(f"{__package__}_messages.log")
    msg_file_format = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s')
    msg_file_handler.setFormatter(msg_file_format)
    msg_logger.addHandler(msg_file_handler)
    msg_logger.setLevel(logging.INFO)
