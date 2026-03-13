import logging
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra_data"):
            log_entry["data"] = record.extra_data
        return json.dumps(log_entry)


def setup_logger(
    name: str = "sudo-trade",
    level: str = "INFO",
    log_dir: str = "logs",
    json_output: bool = True,
) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if logger.handlers:
        return logger

    # Console handler — always present
    console = logging.StreamHandler(sys.stdout)
    if json_output:
        console.setFormatter(JSONFormatter())
    else:
        console.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(module)s | %(message)s"
        ))
    logger.addHandler(console)

    # File handler — logs to disk
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(
        log_path / f"{name}.log", encoding="utf-8"
    )
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "sudo-trade") -> logging.Logger:
    return logging.getLogger(name)
