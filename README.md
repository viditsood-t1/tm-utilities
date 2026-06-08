# TM-Utilities

A lightweight Python logging utility that provides:

* Automatic daily log file creation
* Monthly log folder organization
* IST (Indian Standard Time) timestamps
* Console and file logging simultaneously
* Simple section separators for cleaner logs
* Minimal configuration

## Features

✅ Automatic log directory creation

✅ Monthly log organization

✅ Daily log rotation by filename

✅ IST timezone support

✅ Console + file logging

✅ Configurable log levels

✅ Section separators for structured logging

---

## Installation

```bash
pip install tm-utilities
```

---

## Quick Start

```python
from tm_logger import logger

logger.info("Application started")
logger.warning("This is a warning")
logger.error("Something went wrong")
```

### Output

```text
2026-06-08 14:35:12,451 - INFO - app - main - Application started
2026-06-08 14:35:12,452 - WARNING - app - main - This is a warning
2026-06-08 14:35:12,453 - ERROR - app - main - Something went wrong
```

---

## Custom Logger Configuration

You can create a logger with a custom log directory and log level.

```python
from tm_logger import setup_logger

logger = setup_logger(
    log_dir="custom_logs",
    debug=True
)

logger.info("Custom logger initialized")
```

### Parameters

| Parameter | Type            | Description                                                  |
| --------- | --------------- | ------------------------------------------------------------ |
| `log_dir` | `str` or `Path` | Directory where logs will be stored                          |
| `debug`   | `bool`          | Enables DEBUG logging when `True`, INFO logging when `False` |

---

## Log Directory Structure

Logs are automatically organized by month and date.

```text
logs/
└── Jun_2026/
    └── 08-06-2026.log
```

A new monthly folder is created automatically, and each day receives its own log file.

---

## Default Configuration

The package ships with the following defaults:

```python
DEBUG = True
LOG_DIR = Path.cwd() / "logs"
```

Meaning:

* Logs are stored inside a `logs/` folder in the current working directory.
* Debug logging is enabled by default.

---

## IST Timezone Support

All timestamps are generated in **Indian Standard Time (IST)**:

```text
UTC +05:30
```

This is useful for applications deployed primarily in India without requiring additional timezone configuration.

---

## License

MIT License

---

## Author

TM Utilities

Built for simple, structured Python logging with minimal setup.
