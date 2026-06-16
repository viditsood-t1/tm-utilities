import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone


# Default settings
DEBUG = True
LOG_DIR = Path.cwd() / "logs"


# Function to create IST timezone
def ist_time(*args):
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist).timetuple()


def logger_title(section_name=None, char="*", line_length=50, spacer_lines=0):
    blank_line = " "
    separator_line = char * line_length

    for _ in range(spacer_lines):
        logger.info(blank_line)

    logger.info(separator_line)

    if section_name:
        logger.info(f"{section_name.center(line_length)}")
        logger.info(separator_line)

    for _ in range(spacer_lines):
        logger.info(blank_line)


def setup_logger(log_dir=None, debug=None):

    log_dir = Path(log_dir) if log_dir else LOG_DIR
    debug = DEBUG if debug is None else debug

    # Create logs directory
    log_dir.mkdir(parents=True, exist_ok=True)

    # Create monthly folder
    month_folder = datetime.now().strftime("%b_%Y")
    month_path = log_dir / month_folder
    month_path.mkdir(parents=True, exist_ok=True)

    # Daily log file
    log_file = month_path / f"{datetime.now().strftime('%d-%m-%Y')}.log"

    log_level = logging.DEBUG if debug else logging.INFO

    logger = logging.getLogger("tm_logs")
    logger.setLevel(log_level)

    # Prevent duplicate handlers
    if not logger.handlers:

        file_handler = logging.FileHandler(log_file, mode="a")
        console_handler = logging.StreamHandler()

        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s"
        )
        formatter.converter = ist_time

        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


# Default logger
logger = setup_logger()