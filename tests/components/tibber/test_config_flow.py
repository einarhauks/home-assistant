"""Tests for Tibber config flow."""
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.tibber.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN

from tests.common import MockConfigEntry, async_init_recorder_component


@pytest.fixture(name="tibber_setup", autouse=True)
def tibber_setup_fixture():
    """Patch tibber setup entry."""
    with patch("homeassistant.components.tibber.async_setup_entry", return_value=True):
        yield


async def test_show_config_form(hass):
    """Test show configuration form."""
    await async_init_recorder_component(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_create_entry(hass):
    """Test create entry from user input."""
    await async_init_recorder_component(hass)

    test_data = {
        CONF_ACCESS_TOKEN: "valid",
    }

    unique_user_id = "unique_user_id"
    title = "title"

    tibber_mock = MagicMock()
    type(tibber_mock).update_info = AsyncMock(return_value=True)
    type(tibber_mock).user_id = PropertyMock(return_value=unique_user_id)
    type(tibber_mock).name = PropertyMock(return_value=title)

    with patch("tibber.Tibber", return_value=tibber_mock):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=test_data
        )

    assert result["type"] == "create_entry"
    assert result["title"] == title
    assert result["data"] == test_data


async def test_flow_entry_already_exists(hass):
    """Test user input for config_entry that already exists."""
    await async_init_recorder_component(hass)

    first_entry = MockConfigEntry(
        domain="tibber",
        data={CONF_ACCESS_TOKEN: "valid"},
        unique_id="tibber",
    )
    first_entry.add_to_hass(hass)

    test_data = {
        CONF_ACCESS_TOKEN: "valid",
    }

    with patch("tibber.Tibber.update_info", return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=test_data
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
