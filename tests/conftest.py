"""Shared pytest fixtures for the Alexa Bridge Manager test suite."""
import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Make custom_components/ importable as if installed, for every test."""
    yield
