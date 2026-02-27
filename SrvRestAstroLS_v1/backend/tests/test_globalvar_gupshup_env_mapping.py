from __future__ import annotations

import importlib

from backend import globalVar as globalVar_module


def test_gupshup_enabled_with_canonical_env_only(monkeypatch) -> None:
    with monkeypatch.context() as m:
        m.setenv("VERTICE360_ENV", "dev")

        # Canonical runtime env only.
        m.setenv("GUPSHUP_APP_NAME", "vertice360dev")
        m.setenv("GUPSHUP_API_KEY", "test-key-dev")
        m.setenv("GUPSHUP_WA_SENDER", "14386196758")

        # Ensure env-specific aliases are not needed by Python runtime.
        m.delenv("GUPSHUP_APP_NAME_DEV", raising=False)
        m.delenv("GUPSHUP_API_KEY_DEV", raising=False)
        m.delenv("GUPSHUP_SRC_NUMBER_DEV", raising=False)

        importlib.reload(globalVar_module)

        assert globalVar_module.GUPSHUP_APP_NAME == "vertice360dev"
        assert globalVar_module.GUPSHUP_API_KEY == "test-key-dev"
        assert globalVar_module.get_gupshup_wa_sender_e164() == "+14386196758"
        assert globalVar_module.gupshup_whatsapp_enabled() is True

    importlib.reload(globalVar_module)


def test_gupshup_env_specific_aliases_do_not_autowire_runtime(monkeypatch) -> None:
    with monkeypatch.context() as m:
        m.setenv("VERTICE360_ENV", "dev")

        # Env-specific aliases present...
        m.setenv("GUPSHUP_APP_NAME_DEV", "vertice360dev")
        m.setenv("GUPSHUP_API_KEY_DEV", "test-key-dev")
        m.setenv("GUPSHUP_SRC_NUMBER_DEV", "14386196758")

        # ...but canonical vars missing.
        m.delenv("GUPSHUP_APP_NAME", raising=False)
        m.delenv("GUPSHUP_API_KEY", raising=False)
        m.delenv("GUPSHUP_WA_SENDER", raising=False)

        importlib.reload(globalVar_module)

        assert globalVar_module.GUPSHUP_APP_NAME == ""
        assert globalVar_module.GUPSHUP_API_KEY == ""
        assert globalVar_module.get_gupshup_wa_sender_e164() == ""
        assert globalVar_module.gupshup_whatsapp_enabled() is False

    importlib.reload(globalVar_module)
