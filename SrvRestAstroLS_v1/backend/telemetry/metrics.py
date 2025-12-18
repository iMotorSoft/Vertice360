import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

def inc(name: str, tags: Optional[Dict[str, str]] = None) -> None:
    """
    Increment a counter metric.
    Stub implementation: logs the metric.
    """
    logger.debug(f"[METRIC] INC {name} tags={tags}")

def observe(name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
    """
    Observe a value (histogram/gauge).
    Stub implementation: logs the metric.
    """
    logger.debug(f"[METRIC] OBS {name}={value} tags={tags}")
