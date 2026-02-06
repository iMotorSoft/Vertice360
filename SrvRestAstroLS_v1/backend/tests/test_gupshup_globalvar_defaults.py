from __future__ import annotations

import importlib
import os

from backend import globalVar as globalVar_module


def test_gupshup_base_url_default() -> None:
    original_dev = os.environ.get("GUPSHUP_BASE_URL_DEV")
    original_pro = os.environ.get("GUPSHUP_BASE_URL_PRO")

    try:
        os.environ.pop("GUPSHUP_BASE_URL_DEV", None)
        os.environ.pop("GUPSHUP_BASE_URL_PRO", None)

        importlib.reload(globalVar_module)

        assert globalVar_module.GUPSHUP_BASE_URL_DEV == "https://api.gupshup.io"
        assert globalVar_module.GUPSHUP_BASE_URL == "https://api.gupshup.io"
    finally:
        if original_dev is None:
            os.environ.pop("GUPSHUP_BASE_URL_DEV", None)
        else:
            os.environ["GUPSHUP_BASE_URL_DEV"] = original_dev

        if original_pro is None:
            os.environ.pop("GUPSHUP_BASE_URL_PRO", None)
        else:
            os.environ["GUPSHUP_BASE_URL_PRO"] = original_pro

        importlib.reload(globalVar_module)
