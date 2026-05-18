import os
import logging

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Configure the logger
logger = logging.getLogger("prodigal_agent")
logger.setLevel(logging.INFO)

# File handler
file_handler = logging.FileHandler("logs/agent.log")
file_handler.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] %(message)s", 
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(formatter)

# Add handler to logger
# Prevent adding multiple handlers if logger is imported multiple times
if not logger.handlers:
    logger.addHandler(file_handler)
    # Ensure it doesn't propagate to the root logger to keep console clean
    logger.propagate = False
