"""Support for Fibaro sensors."""
from __future__ import annotations

from contextlib import suppress

from homeassistant.components.sensor import (
    DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    ENERGY_KILO_WATT_HOUR,
    LIGHT_LUX,
    PERCENTAGE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import convert

from . import FIBARO_DEVICES, FibaroDevice

SENSOR_TYPES = {
    "com.fibaro.temperatureSensor": [
        "Temperature",
        None,
        None,
        SensorDeviceClass.TEMPERATURE,
    ],
    "com.fibaro.smokeSensor": [
        "Smoke",
        CONCENTRATION_PARTS_PER_MILLION,
        "mdi:fire",
        None,
    ],
    "CO2": [
        "CO2",
        CONCENTRATION_PARTS_PER_MILLION,
        None,
        None,
        SensorDeviceClass.CO2,
    ],
    "com.fibaro.humiditySensor": [
        "Humidity",
        PERCENTAGE,
        None,
        SensorDeviceClass.HUMIDITY,
    ],
    "com.fibaro.lightSensor": ["Light", LIGHT_LUX, None, SensorDeviceClass.ILLUMINANCE],
}


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Fibaro controller devices."""
    if discovery_info is None:
        return

    entities: list[SensorEntity] = []
    for device in hass.data[FIBARO_DEVICES]["sensor"]:
        entities.append(FibaroSensor(device))
    for device_type in ("cover", "light", "switch"):
        for device in hass.data[FIBARO_DEVICES][device_type]:
            if "energy" in device.interfaces:
                entities.append(FibaroEnergySensor(device))

    add_entities(entities, True)


class FibaroSensor(FibaroDevice, SensorEntity):
    """Representation of a Fibaro Sensor."""

    def __init__(self, fibaro_device):
        """Initialize the sensor."""
        self.current_value = None
        self.last_changed_time = None
        super().__init__(fibaro_device)
        self.entity_id = f"{DOMAIN}.{self.ha_id}"
        if fibaro_device.type in SENSOR_TYPES:
            self._unit = SENSOR_TYPES[fibaro_device.type][1]
            self._icon = SENSOR_TYPES[fibaro_device.type][2]
            self._device_class = SENSOR_TYPES[fibaro_device.type][3]
        else:
            self._unit = None
            self._icon = None
            self._device_class = None
        with suppress(KeyError, ValueError):
            if not self._unit:
                if self.fibaro_device.properties.unit == "lux":
                    self._unit = LIGHT_LUX
                elif self.fibaro_device.properties.unit == "C":
                    self._unit = TEMP_CELSIUS
                elif self.fibaro_device.properties.unit == "F":
                    self._unit = TEMP_FAHRENHEIT
                else:
                    self._unit = self.fibaro_device.properties.unit

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.current_value

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    def update(self):
        """Update the state."""
        with suppress(KeyError, ValueError):
            self.current_value = float(self.fibaro_device.properties.value)


class FibaroEnergySensor(FibaroDevice, SensorEntity):
    """Representation of a Fibaro Energy Sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR

    def __init__(self, fibaro_device):
        """Initialize the sensor."""
        super().__init__(fibaro_device)
        self.entity_id = f"{DOMAIN}.{self.ha_id}_energy"
        self._name = f"{fibaro_device.friendly_name} Energy"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.fibaro_device.unique_id_str}_energy"

    def update(self):
        """Update the state."""
        with suppress(KeyError, ValueError):
            self._attr_native_value = convert(
                self.fibaro_device.properties.energy, float
            )
