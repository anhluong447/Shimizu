import logging
import os
import sys
from logging.handlers import RotatingFileHandler

def setup_logger(name="Shimizu"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Format
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'bot.log'),
        maxBytes=5*1024*1024, # 5MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

log = setup_logger()
