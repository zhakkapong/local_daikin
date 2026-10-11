from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable, Optional
from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfTemperature,
    PERCENTAGE,
    UnitOfTime,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
)
from homeassistant.helpers.device_registry import DeviceInfo
import logging

from .dsiot import compressor_load_percent, percent_of

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)

async def async_setup_entry(hass, entry, async_add_entities):
    ip = entry.data["ip_address"]
    async_add_entities([
        DaikinOutdoorTempSensor(hass, entry.entry_id, ip),
        DaikinEnergyTodaySensor(hass, entry.entry_id, ip),
        DaikinCurrentHumiditySensor(hass, entry.entry_id, ip),
        DaikinIndoorTempSensor(hass, entry.entry_id, ip),
        DaikinRuntimeTodaySensor(hass, entry.entry_id, ip),
        DaikinTargetTempSensor(hass, entry.entry_id, ip),
        *(DaikinDiagnosticSensor(hass, entry.entry_id, ip, description) for description in DIAGNOSTIC_SENSORS),
    ])


class BaseDaikinSensor(SensorEntity):
    """Base sensor that reads cached state from the climate entity (no extra HTTP calls)."""

    def __init__(self, hass, entry_id, ip, name_suffix, unique_id_suffix):
        self._hass = hass
        self._entry_id = entry_id
        self._ip = ip
        self._state = None
        self._attr_name = f"Daikin {name_suffix} ({ip})"
        self._attr_unique_id = f"daikin_{unique_id_suffix}_{ip}"

    def _get_climate_entity(self):
        data = self._hass.data.get("local_daikin", {}).get(self._entry_id, {})
        return data.get("climate_entity")

    @property
    def available(self) -> bool:
        entity = self._get_climate_entity()
        return entity is not None and entity.available

    def update(self):
        """Read cached values from climate entity — do NOT call entity.update()."""
        entity = self._get_climate_entity()
        if entity is None:
            return
        self._read_state(entity)

    def _read_state(self, entity):
        """Override in subclasses to read the relevant value."""
        pass

    @property
    def native_value(self):
        return self._state

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={("local_daikin", self._ip)},
            name="Local Daikin AC",
            manufacturer="Daikin"
        )


class DaikinOutdoorTempSensor(BaseDaikinSensor):
    def __init__(self, hass, entry_id, ip):
        super().__init__(hass, entry_id, ip, "Outside Temp", "outside_temp")
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def _read_state(self, entity):
        self._state = entity.extra_state_attributes.get("outside_temperature")


class DaikinEnergyTodaySensor(BaseDaikinSensor):
    def __init__(self, hass, entry_id, ip):
        super().__init__(hass, entry_id, ip, "Energy Today", "energy_today")
        self._attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_should_poll = True

    def _read_state(self, entity):
        self._state = entity.extra_state_attributes.get("energy_today")


class DaikinCurrentHumiditySensor(BaseDaikinSensor):
    def __init__(self, hass, entry_id, ip):
        super().__init__(hass, entry_id, ip, "Current Humidity", "current_humidity")
        self._attr_native_unit_of_measurement = PERCENTAGE

    def _read_state(self, entity):
        self._state = entity.current_humidity


class DaikinIndoorTempSensor(BaseDaikinSensor):
    def __init__(self, hass, entry_id, ip):
        super().__init__(hass, entry_id, ip, "Indoor Temp", "indoor_temp")
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def _read_state(self, entity):
        self._state = entity.current_temperature


class DaikinRuntimeTodaySensor(BaseDaikinSensor):
    def __init__(self, hass, entry_id, ip):
        super().__init__(hass, entry_id, ip, "Runtime Today", "runtime_today")
        self._attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def _read_state(self, entity):
        self._state = entity.extra_state_attributes.get("runtime_today")


class DaikinTargetTempSensor(BaseDaikinSensor):
    def __init__(self, hass, entry_id, ip):
        super().__init__(hass, entry_id, ip, "Target Temp", "target_temp")
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def _read_state(self, entity):
        self._state = entity.target_temperature


@dataclass(frozen=True, kw_only=True)
class DaikinDiagnosticSensorDescription(SensorEntityDescription):
    """`key` is used in the unique_id; the value comes from climate.diagnostics."""

    value_fn: Callable[[dict], Any]
    # Diagnostics key holding the model's maximum; adds max_rpm/percent attributes.
    max_key: Optional[str] = None


DIAGNOSTIC_SENSORS = (
    DaikinDiagnosticSensorDescription(
        key="compressor_frequency",
        name="Compressor Frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("compressor_frequency"),
    ),
    DaikinDiagnosticSensorDescription(
        key="compressor_load",
        name="Compressor Load",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: compressor_load_percent(d.get("compressor_frequency")),
    ),
    DaikinDiagnosticSensorDescription(
        # Not "power": keep it distinct from the Power switch's unique_id.
        key="power_consumption",
        name="Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("power"),
    ),
    DaikinDiagnosticSensorDescription(
        key="current",
        name="Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("current"),
    ),
    DaikinDiagnosticSensorDescription(
        key="supply_voltage",
        name="Supply Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("supply_voltage"),
    ),
    DaikinDiagnosticSensorDescription(
        key="indoor_fan_speed",
        name="Indoor Fan Speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("indoor_fan_speed"),
        max_key="indoor_fan_speed_max",
    ),
    DaikinDiagnosticSensorDescription(
        key="outdoor_fan_speed",
        name="Outdoor Fan Speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("outdoor_fan_speed"),
        max_key="outdoor_fan_speed_max",
    ),
    DaikinDiagnosticSensorDescription(
        key="indoor_coil_temp",
        name="Indoor Coil Temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("indoor_coil_temp"),
    ),
    DaikinDiagnosticSensorDescription(
        key="outdoor_coil_temp",
        name="Outdoor Coil Temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("outdoor_coil_temp"),
    ),
    DaikinDiagnosticSensorDescription(
        key="control_target_temp",
        name="Control Target Temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("control_target_temp"),
    ),
    DaikinDiagnosticSensorDescription(
        key="eev_position",
        name="EEV Position",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("eev_position"),
    ),
)


class DaikinDiagnosticSensor(BaseDaikinSensor):
    """Sensor for a value decoded by dsiot.extract_diagnostics()."""

    entity_description: DaikinDiagnosticSensorDescription

    def __init__(self, hass, entry_id, ip, description: DaikinDiagnosticSensorDescription):
        super().__init__(hass, entry_id, ip, description.name, description.key)
        self.entity_description = description
        self._attributes = None

    @property
    def available(self) -> bool:
        # Models without this path report None; show unavailable rather than unknown.
        return super().available and self._state is not None

    def _read_state(self, entity):
        diagnostics = entity.diagnostics
        self._state = self.entity_description.value_fn(diagnostics)
        max_key = self.entity_description.max_key
        if max_key is not None:
            max_rpm = diagnostics.get(max_key)
            self._attributes = {"max_rpm": max_rpm, "percent": percent_of(self._state, max_rpm)}

    @property
    def extra_state_attributes(self):
        return self._attributes
