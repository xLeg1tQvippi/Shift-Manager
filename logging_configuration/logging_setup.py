import logging.config
import yaml
from lexicon_folder.lexicon import LOGGING

def setup_logging():
    with open(LOGGING['config_path'], 'r') as f:
        config = yaml.safe_load(f)
        logging.config.dictConfig(config)
        
    queue_handler = logging.getHandlerByName("queue_handler")
    if queue_handler and hasattr(queue_handler, 'listener'):
        queue_handler.listener.start()