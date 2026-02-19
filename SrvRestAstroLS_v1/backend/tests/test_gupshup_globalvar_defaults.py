from __future__ import annotations

import importlib

from backend import globalVar as globalVar_module


def test_gupshup_base_url_default(monkeypatch) -> None:
    with monkeypatch.context() as m:
        m.delenv("GUPSHUP_BASE_URL_DEV", raising=False)
        m.delenv("GUPSHUP_BASE_URL_PRO", raising=False)

        importlib.reload(globalVar_module)

        assert globalVar_module.GUPSHUP_BASE_URL_DEV == "https://api.gupshup.io"
        assert globalVar_module.GUPSHUP_BASE_URL == "https://api.gupshup.io"

    # Ensure globals are reloaded with restored environment.
    importlib.reload(globalVar_module)
