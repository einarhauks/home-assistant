"""Make sure that existing Koogeek LS1 support isn't broken."""

from datetime import timedelta
from unittest import mock

from aiohomekit.exceptions import AccessoryDisconnectedError, EncryptionError
from aiohomekit.testing import FakePairing
import pytest

from homeassistant.components.light import SUPPORT_BRIGHTNESS, SUPPORT_COLOR
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.homekit_controller.common import (
    DeviceTestInfo,
    EntityTestInfo,
    Helper,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)

LIGHT_ON = ("lightbulb", "on")


async def test_koogeek_ls1_setup(hass):
    """Test that a Koogeek LS1 can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "koogeek_ls1.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id="00:00:00:00:00:00",
            name="Koogeek-LS1-20833F",
            model="LS1",
            manufacturer="Koogeek",
            sw_version="2.2.15",
            hw_version="",
            serial_number="AAAA011111111111",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="light.koogeek_ls1_20833f",
                    friendly_name="Koogeek-LS1-20833F",
                    unique_id="homekit-AAAA011111111111-7",
                    supported_features=SUPPORT_BRIGHTNESS | SUPPORT_COLOR,
                    capabilities={"supported_color_modes": ["hs"]},
                    state="off",
                ),
            ],
        ),
    )


@pytest.mark.parametrize("failure_cls", [AccessoryDisconnectedError, EncryptionError])
async def test_recover_from_failure(hass, utcnow, failure_cls):
    """
    Test that entity actually recovers from a network connection drop.

    See https://github.com/home-assistant/core/issues/18949
    """
    accessories = await setup_accessories_from_file(hass, "koogeek_ls1.json")
    config_entry, pairing = await setup_test_accessories(hass, accessories)

    helper = Helper(
        hass, "light.koogeek_ls1_20833f", pairing, accessories[0], config_entry
    )

    # Set light state on fake device to off
    helper.characteristics[LIGHT_ON].set_value(False)

    # Test that entity starts off in a known state
    state = await helper.poll_and_get_state()
    assert state.state == "off"

    # Set light state on fake device to on
    helper.characteristics[LIGHT_ON].set_value(True)

    # Test that entity remains in the same state if there is a network error
    next_update = dt_util.utcnow() + timedelta(seconds=60)
    with mock.patch.object(FakePairing, "get_characteristics") as get_char:
        get_char.side_effect = failure_cls("Disconnected")

        state = await helper.poll_and_get_state()
        assert state.state == "off"

        chars = get_char.call_args[0][0]
        assert set(chars) == {(1, 8), (1, 9), (1, 10), (1, 11)}

    # Test that entity changes state when network error goes away
    next_update += timedelta(seconds=60)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    state = await helper.poll_and_get_state()
    assert state.state == "on"
