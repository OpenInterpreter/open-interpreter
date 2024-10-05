
import logging
import json
from datetime import datetime

class ErrorHandler:
    def __init__(self, log_file='error_log.json'):
        logging.basicConfig(level=logging.INFO)
        self.log_file = log_file

    def log(self, level, message, error=None):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': level,
            'message': message,
            'error': str(error) if error else None
        }
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

        # Log to the console as well
        if level == 'INFO':
            logging.info(message)
        elif level == 'WARNING':
            logging.warning(message)
        elif level == 'ERROR':
            logging.error(message)

    def info(self, message):
        self.log('INFO', message)

    def warning(self, message):
        self.log('WARNING', message)

    def error(self, message, error=None):
        self.log('ERROR', message, error)

# Example usage:
# error_handler = ErrorHandler()
# error_handler.error("An unexpected error occurred", Exception("Some exception"))
