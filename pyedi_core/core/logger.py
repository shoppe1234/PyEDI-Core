"""
Structured logging module for PyEDI-Core.

Wraps structlog and stamps every log event with correlation_id, file_name,
stage, transaction_type, and processing_time_ms.

Three deployment tiers configured via config.yaml:
- log_level: DEBUG | INFO | WARNING | ERROR
- output: console | file | both
- format: pretty | json
"""

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import structlog
from structlog.stdlib import LoggerFactory

# Global logger instance - configured at startup
_logger: Optional[structlog.BoundLogger] = None

# Configuration defaults
_config: dict = {
    "log_level": "INFO",
    "output": "console",
    "log_file": "./logs/pyedi.log",
    "format": "pretty",
}


def configure(config: dict) -> None:
    """
    Configure the logger from a config dictionary.
    
    Args:
        config: Dictionary with keys: log_level, output, log_file, format
    """
    global _logger, _config
    _config.update(config)
    
    # Set up structlog
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            _get_formatter(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    _logger = structlog.get_logger()


def _get_formatter():
    """Get the appropriate formatter based on config."""
    if _config.get("format") == "json":
        return structlog.processors.JSONRenderer()
    else:
        return structlog.dev.ConsoleRenderer()


def _get_log_level() -> str:
    """Get the configured log level."""
    return _config.get("log_level", "INFO")


def get_logger() -> structlog.BoundLogger:
    """
    Get the configured logger instance.
    
    Returns:
        A structlog BoundLogger with correlation ID support
    """
    global _logger
    if _logger is None:
        configure(_config)
    return _logger


def generate_correlation_id() -> str:
    """
    Generate a new UUID for correlation tracking.
    
    Returns:
        A UUID4 string
    """
    return str(uuid.uuid4())


def bind_logger(**kwargs: Any) -> structlog.BoundLogger:
    """
    Bind context fields to the logger.
    
    Common fields: correlation_id, file_name, stage, transaction_type, processing_time_ms
    
    Args:
        **kwargs: Key-value pairs to bind to the logger context
        
    Returns:
        A bound logger with the provided context
    """
    logger = get_logger()
    return logger.bind(**kwargs)



# Initialize with defaults
configure(_config)


class LoggerMixin:
    """
    Mixin class to add logging capability to any class.
    
    Provides self.logger property that automatically binds correlation_id.
    """
    
    _correlation_id: Optional[str] = None
    
    @property
    def correlation_id(self) -> str:
        """Get or generate correlation ID for this instance."""
        if self._correlation_id is None:
            self._correlation_id = generate_correlation_id()
        return self._correlation_id
    
    @property
    def logger(self) -> structlog.BoundLogger:
        """Get a bound logger with correlation_id."""
        return bind_logger(correlation_id=self.correlation_id)
    
    def set_correlation_id(self, correlation_id: str) -> None:
        """Set a specific correlation ID for this instance."""
        self._correlation_id = correlation_id


# Module-level functions for convenience
def debug(message: str, **kwargs: Any) -> None:
    """Log a debug message."""
    get_logger().debug(message, **kwargs)


def info(message: str, **kwargs: Any) -> None:
    """Log an info message."""
    get_logger().info(message, **kwargs)


def warning(message: str, **kwargs: Any) -> None:
    """Log a warning message."""
    get_logger().warning(message, **kwargs)


def error(message: str, **kwargs: Any) -> None:
    """Log an error message."""
    get_logger().error(message, **kwargs)
