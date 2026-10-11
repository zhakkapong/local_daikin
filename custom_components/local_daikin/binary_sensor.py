from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.device_registry import DeviceInfo
import logging

from .entity import DaikinClimateFollower

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    ip = entry.data["ip_address"]
    async_add_entities([
        DaikinCompressorRunningSensor(hass, entry.entry_id, ip),
    ])


class DaikinCompressorRunningSensor(DaikinClimateFollower, BinarySensorEntity):
    """Reads cached diagnostics from the climate entity (no extra HTTP calls)."""

    def __init__(self, hass, entry_id, ip):
        self._hass = hass
        self._entry_id = entry_id
        self._ip = ip
        self._state = None
        self._attr_name = f"Daikin Compressor Running ({ip})"
        self._attr_unique_id = f"daikin_compressor_running_{ip}"
        self._attr_device_class = BinarySensorDeviceClass.RUNNING

    def _get_climate_entity(self):
        data = self._hass.data.get("local_daikin", {}).get(self._entry_id, {})
        return data.get("climate_entity")

    @property
    def available(self) -> bool:
        entity = self._get_climate_entity()
        return entity is not None and entity.available and self._state is not None

    def update(self):
        entity = self._get_climate_entity()
        if entity is None:
            return
        self._state = entity.diagnostics.get("compressor_running")

    @property
    def is_on(self):
        return self._state

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={("local_daikin", self._ip)},
            name="Local Daikin AC",
            manufacturer="Daikin"
        )
