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


def test_gupshup_wa_sender_normalizes_to_e164(monkeypatch) -> None:
    with monkeypatch.context() as m:
        m.setenv("GUPSHUP_WA_SENDER", "14386196758")
        importlib.reload(globalVar_module)
        assert globalVar_module.GUPSHUP_WA_SENDER == "+14386196758"
        assert globalVar_module.GUPSHUP_SRC_NUMBER == "14386196758"

    importlib.reload(globalVar_module)


def test_gupshup_wa_sender_accepts_plus(monkeypatch) -> None:
    with monkeypatch.context() as m:
        m.setenv("GUPSHUP_WA_SENDER", "+14386196758")
        importlib.reload(globalVar_module)
        assert globalVar_module.get_gupshup_wa_sender_e164() == "+14386196758"
        assert globalVar_module.get_gupshup_wa_sender_provider_value() == "14386196758"

    importlib.reload(globalVar_module)
