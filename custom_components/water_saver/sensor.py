from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WaterSaverCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: WaterSaverCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            WaterSaverTotalM3Sensor(coordinator),
            WaterSaverLastSeenMinSensor(coordinator),
            WaterSaverBatteryYSensor(coordinator),
            WaterSaverRssiSensor(coordinator),
        ]
    )


class _Base(CoordinatorEntity[WaterSaverCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: WaterSaverCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.entry.entry_id)},
            "name": self.coordinator.name,
            "manufacturer": "wmbusmeters",
            "model": "MQTT water meter",
        }


class WaterSaverTotalM3Sensor(_Base):
    _attr_name = "Total"
    _attr_unique_id = "water_saver_total_m3"
    _attr_native_unit_of_measurement = "m³"
    _attr_device_class = "water"
    _attr_state_class = "total_increasing"

    @property
    def native_value(self):
        return self.coordinator.data.total_m3

    @property
    def extra_state_attributes(self):
        d = self.coordinator.data
        return {
            "meter_id": d.meter_id,
            "status": d.status,
            "power_mode": d.power_mode,
            "telegram_timestamp": d.telegram_timestamp,
            "rssi_dbm": d.rssi_dbm,
            "battery_y": d.battery_y,
        }


class WaterSaverLastSeenMinSensor(_Base):
    _attr_name = "Last seen"
    _attr_unique_id = "water_saver_last_seen_min"
    _attr_native_unit_of_measurement = "min"
    _attr_state_class = "measurement"

    @property
    def native_value(self):
        return self.coordinator.data.last_seen_min


class WaterSaverBatteryYSensor(_Base):
    _attr_name = "Battery"
    _attr_unique_id = "water_saver_battery_y"
    _attr_native_unit_of_measurement = "y"
    _attr_state_class = "measurement"

    @property
    def native_value(self):
        return self.coordinator.data.battery_y


class WaterSaverRssiSensor(_Base):
    _attr_name = "RSSI"
    _attr_unique_id = "water_saver_rssi_dbm"
    _attr_native_unit_of_measurement = "dBm"
    _attr_state_class = "measurement"

    @property
    def native_value(self):
        return self.coordinator.data.rssi_dbm
