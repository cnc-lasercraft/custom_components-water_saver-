from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WaterSaverCoordinator


SENSORS = [
    ("total_l", "Total", "L", "water", "total_increasing"),
    ("hour_l", "Stunde", "L", "water", "measurement"),
    ("day_l", "Heute", "L", "water", "measurement"),
    ("week_l", "Woche", "L", "water", "measurement"),
    ("month_l", "Monat", "L", "water", "measurement"),
    ("year_l", "Jahr", "L", "water", "measurement"),
    ("last_seen_min", "Letzte Meldung", "min", None, "measurement"),
    ("battery_y", "Batterie", "y", None, "measurement"),
    ("rssi_dbm", "RSSI", "dBm", None, "measurement"),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: WaterSaverCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            WaterSaverSensor(coordinator, key, name, unit, dev_class, state_class)
            for key, name, unit, dev_class, state_class in SENSORS
        ]
    )


class WaterSaverSensor(CoordinatorEntity[WaterSaverCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WaterSaverCoordinator,
        key: str,
        name: str,
        unit: str | None,
        dev_class: str | None,
        state_class: str | None,
    ) -> None:
        super().__init__(coordinator)
        self.key = key

        # Entity naming / IDs
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"

        # Units/classes
        self._attr_native_unit_of_measurement = unit
        if dev_class:
            self._attr_device_class = dev_class
        if state_class:
            self._attr_state_class = state_class

    @property
    def native_value(self):
        return getattr(self.coordinator.data, self.key)

    @property
    def extra_state_attributes(self):
        # Put rich attributes on "Total"
        if self.key != "total_l":
            return None
        d = self.coordinator.data
        return {
            "meter_id": d.meter_id,
            "status": d.status,
            "power_mode": d.power_mode,
            "payload_timestamp": d.last_payload_ts,
            "target_date": d.target_date,
            "target_l": d.target_l,
        }

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.entry.entry_id)},
            "name": self.coordinator.name,
            "manufacturer": "wmbusmeters",
            "model": "MQTT water meter",
        }
