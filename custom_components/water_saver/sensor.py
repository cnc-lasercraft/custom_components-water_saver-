from __future__ import annotations

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.config_entries import ConfigEntry

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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator: WaterSaverCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [WaterSaverSensor(coordinator, key, name, unit, dev_class, state_class) for key, name, unit, dev_class, state_class in SENSORS]
    async_add_entities(entities)


class WaterSaverSensor(Entity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: WaterSaverCoordinator, key: str, name: str, unit: str | None, dev_class: str | None, state_class: str | None):
        self.coordinator = coordinator
        self.key = key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_native_unit_of_measurement = unit
        if dev_class:
            self._attr_device_class = dev_class
        if state_class:
            self._attr_state_class = state_class

    async def async_added_to_hass(self):
        @callback
        def _updated():
            self.async_write_ha_state()

        self.coordinator.add_listener(_updated)

    @property
    def native_value(self):
        return getattr(self.coordinator.data, self.key)

    @property
    def extra_state_attributes(self):
        # expose some raw fields on the "Total" sensor
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
