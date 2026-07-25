"""Shared fixtures for the Home Assistant integration tests.

These need `pytest-homeassistant-custom-component`; the bare
`tests/test_rhythm.py` self-check deliberately does not.

`enable_custom_integrations` is requested per-test rather than autouse: it
pulls in `hass`, and the recorder fixtures insist on being resolved before
`hass` exists.
"""
import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def _recorder_db_first(recorder_db_url):
    """Resolve the recorder database before this test's `hass` is built.

    `recorder_db_url` asserts no Home Assistant instance exists yet. Autouse
    fixtures are set up before explicitly requested ones, which is the only
    reliable way to win that race.
    """
    yield
