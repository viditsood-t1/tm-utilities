from tm_logger.logger import setup_logger

def test_logger_creation():
    logger = setup_logger()
    assert logger is not None