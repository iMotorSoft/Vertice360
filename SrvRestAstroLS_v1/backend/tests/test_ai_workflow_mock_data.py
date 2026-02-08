from __future__ import annotations

from backend.modules.vertice360_ai_workflow_demo import mock_data


def test_caballito_three_rooms_returns_two_options():
    filters = {
        "city": "CABA",
        "neighborhood": "Caballito",
        "rooms": 3,
        "currency": "USD",
    }
    options = mock_data.get_recommended_options(filters)

    assert set(options.keys()) == {"optionA", "optionB"}
    option_a = options["optionA"]
    option_b = options["optionB"]
    assert option_a.get("unitCode") != option_b.get("unitCode")

    for option in (option_a, option_b):
        assert option.get("city") == "CABA"
        assert option.get("neighborhood") == "Caballito"
        assert option.get("rooms") == 3


def test_get_recommended_options_is_deterministic():
    filters = {
        "city": "CABA",
        "neighborhood": "Caballito",
        "rooms": 3,
        "max_price": 210000,
        "currency": "USD",
    }

    mock_data.reset_mock_data()
    first = mock_data.get_recommended_options(filters)
    mock_data.reset_mock_data()
    second = mock_data.get_recommended_options(filters)

    assert first == second
