import os
from typing import Optional
from ..globalVar import MLFLOW_TRACKING_URI as GLOBAL_TRACKING_URI, APP_NAME

try:
   # Try to read env vars first, then fallback to globalVar
   MLFLOW_ENABLED = os.environ.get("MLFLOW_ENABLED", "0") in ("1", "true", "True")
   MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI") or GLOBAL_TRACKING_URI
   MLFLOW_EXPERIMENT = os.environ.get("MLFLOW_EXPERIMENT", "vertice360")
   PRODUCT_NAME = APP_NAME
except ImportError:
   # Fallback if globalVar cannot be imported (unlikely in this repo structure)
   MLFLOW_ENABLED = False
   MLFLOW_TRACKING_URI = None
   MLFLOW_EXPERIMENT = "vertice360"
   PRODUCT_NAME = "Vertice360"
