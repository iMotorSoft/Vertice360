import logging
import sys
from .context import get_request_id, get_correlation_id

class ContextFilter(logging.Filter):
    """
    This is a filter which injects request_id and correlation_id into the logRecord.
    """
    def filter(self, record):
        record.request_id = get_request_id() or "-"
        record.correlation_id = get_correlation_id() or "-"
        return True

def setup_logging(level=logging.INFO):
    """
    Configures standard logging to include telemetry context.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers to avoid duplication if called multiple times or by other libs
    if root_logger.handlers:
        root_logger.handlers = []

    handler = logging.StreamHandler(sys.stdout)
    
    # Custom format including context vars
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] [req:%(request_id)s] [corr:%(correlation_id)s] %(name)s - %(message)s'
    )
    
    handler.setFormatter(formatter)
    
    # Add filter to handler (or logger) to inject values
    ctx_filter = ContextFilter()
    handler.addFilter(ctx_filter)
    
    root_logger.addHandler(handler)

    # Set some noisy libraries to warning
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
