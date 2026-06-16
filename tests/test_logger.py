import logging
from datetime import timedelta
from pathlib import Path

import pytest

from tm_utility.loggerService.logs import (
    DEBUG,
    ist_time,
    logger_title,
    setup_logger,
)


@pytest.fixture
def clean_logger():
    """
    Ensure tm_logs loggerService has no handlers before and after each test.
    """
    log = logging.getLogger("tm_logs")

    for handler in log.handlers[:]:
        handler.close()
        log.removeHandler(handler)

    yield log

    for handler in log.handlers[:]:
        handler.close()
        log.removeHandler(handler)


def test_ist_time_returns_timetuple():
    result = ist_time()

    assert hasattr(result, "tm_year")
    assert hasattr(result, "tm_mon")
    assert hasattr(result, "tm_mday")


def test_setup_logger_creates_log_directory_and_file(clean_logger, tmp_path):
    logger = setup_logger(log_dir=tmp_path)

    month_folder = Path(tmp_path) / Path(
        next(tmp_path.iterdir()).name
    )

    assert month_folder.exists()
    assert month_folder.is_dir()

    log_files = list(month_folder.glob("*.log"))
    assert len(log_files) == 1

    assert logger.name == "tm_logs"


def test_setup_logger_default_debug_level(clean_logger, tmp_path):
    logger = setup_logger(log_dir=tmp_path)

    expected_level = logging.DEBUG if DEBUG else logging.INFO
    assert logger.level == expected_level


def test_setup_logger_debug_false_sets_info_level(clean_logger, tmp_path):
    logger = setup_logger(log_dir=tmp_path, debug=False)

    assert logger.level == logging.INFO


def test_setup_logger_debug_true_sets_debug_level(clean_logger, tmp_path):
    logger = setup_logger(log_dir=tmp_path, debug=True)

    assert logger.level == logging.DEBUG


def test_setup_logger_adds_two_handlers(clean_logger, tmp_path):
    logger = setup_logger(log_dir=tmp_path)

    assert len(logger.handlers) == 2

    assert any(isinstance(h, logging.FileHandler) for h in logger.handlers)
    assert any(isinstance(h, logging.StreamHandler) for h in logger.handlers)


def test_setup_logger_does_not_duplicate_handlers(clean_logger, tmp_path):
    logger1 = setup_logger(log_dir=tmp_path)
    handler_count = len(logger1.handlers)

    logger2 = setup_logger(log_dir=tmp_path)

    assert logger1 is logger2
    assert len(logger2.handlers) == handler_count


def test_logger_title_with_section_name(monkeypatch):
    messages = []

    class DummyLogger:
        def info(self, message):
            messages.append(message)

    monkeypatch.setattr("tm_utility.loggerService.logs.logger", DummyLogger())

    logger_title(
        section_name="TEST SECTION",
        char="-",
        line_length=20,
        spacer_lines=0,
    )

    assert messages == [
        "-" * 20,
        "TEST SECTION".center(20),
        "-" * 20,
    ]


def test_logger_title_without_section_name(monkeypatch):
    messages = []

    class DummyLogger:
        def info(self, message):
            messages.append(message)

    monkeypatch.setattr("tm_utility.loggerService.logs.logger", DummyLogger())

    logger_title(section_name=None, char="*", line_length=10)

    assert messages == [
        "*" * 10,
    ]


def test_logger_title_with_spacer_lines(monkeypatch):
    messages = []

    class DummyLogger:
        def info(self, message):
            messages.append(message)

    monkeypatch.setattr("tm_utility.loggerService.logs.logger", DummyLogger())

    logger_title(
        section_name="TITLE",
        char="=",
        line_length=10,
        spacer_lines=2,
    )

    assert messages == [
        " ",
        " ",
        "=" * 10,
        "TITLE".center(10),
        "=" * 10,
        " ",
        " ",
    ]


def test_handlers_use_formatter(clean_logger, tmp_path):
    logger = setup_logger(log_dir=tmp_path)

    for handler in logger.handlers:
        assert handler.formatter is not None
        assert "%(asctime)s" in handler.formatter._fmt
        assert "%(levelname)s" in handler.formatter._fmt
        assert "%(message)s" in handler.formatter._fmt