import logging
import structlog
import sys
from pathlib import Path


def configure_logging(level: str = "INFO", log_dir: str = "logs") -> None:
    """Configure stdlib logging and structlog for JSON-lines output."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "algo_trader"):
    """Return a structlog-backed logger."""
    configure_logging()
    return structlog.get_logger(name)
