import logging
import contextlib
from typing import Optional, Dict, Any, Generator
from ..globalVar import MLFLOW_ENABLED, MLFLOW_TRACKING_URI, MLFLOW_EXPERIMENT

logger = logging.getLogger(__name__)

# Try to import mlflow
try:
    if MLFLOW_ENABLED:
        import mlflow
        HAS_MLFLOW = True
    else:
        HAS_MLFLOW = False
except ImportError:
    HAS_MLFLOW = False
    logger.warning("MLflow enabled but not installed. Disabling MLflow support.")

class NoOpContextManager:
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

def setup_mlflow():
    if HAS_MLFLOW and MLFLOW_TRACKING_URI:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        mlflow.set_experiment(MLFLOW_EXPERIMENT)
        logger.info(f"MLflow initialized: {MLFLOW_TRACKING_URI}")

@contextlib.contextmanager
def start_run(run_name: Optional[str] = None, tags: Optional[Dict[str, Any]] = None) -> Generator[Any, None, None]:
    if HAS_MLFLOW:
        with mlflow.start_run(run_name=run_name) as run:
            if tags:
                mlflow.set_tags(tags)
            yield run
    else:
        yield NoOpContextManager()

def log_params(params: Dict[str, Any]) -> None:
    if HAS_MLFLOW:
        mlflow.log_params(params)
    else:
        logger.debug(f"[MLFLOW NO-OP] log_params: {params}")

def log_metrics(metrics: Dict[str, float], step: Optional[int] = None) -> None:
    if HAS_MLFLOW:
        mlflow.log_metrics(metrics, step=step)
    else:
        logger.debug(f"[MLFLOW NO-OP] log_metrics: {metrics}")

def log_artifact_text(name: str, content: str) -> None:
    if HAS_MLFLOW:
        mlflow.log_text(content, name)
    else:
        logger.debug(f"[MLFLOW NO-OP] log_artifact_text: {name}")

# Initialize configuration on import if enabled
if HAS_MLFLOW:
    try:
        setup_mlflow()
    except Exception as e:
        logger.error(f"Failed to setup MLflow: {e}")
        HAS_MLFLOW = False
