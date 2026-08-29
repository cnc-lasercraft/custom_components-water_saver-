from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WaterSaverCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: WaterSaverCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        WaterSaverAlarmSwitch(coordinator, "alert", "Water Saver Alert Enabled", "mdi:shield-alert"),
        WaterSaverAlarmSwitch(coordinator, "leak", "Water Saver Leak Enabled", "mdi:water-alert"),
        WaterSaverAlarmSwitch(coordinator, "today_high", "Water Saver Today High Enabled", "mdi:chart-bell-curve"),
    ])


class WaterSaverAlarmSwitch(CoordinatorEntity[WaterSaverCoordinator], SwitchEntity):
    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: WaterSaverCoordinator,
        switch_key: str,
        name: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator)
        self._switch_key = switch_key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"water_saver_{switch_key}_enabled"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self.coordinator.entry.entry_id)}}

    @property
    def is_on(self) -> bool:
        d = self.coordinator.data
        if self._switch_key == "leak":
            return d.leak_enabled
        if self._switch_key == "today_high":
            return d.today_high_enabled
        if self._switch_key == "alert":
            return d.alert_enabled
        return True

    async def async_turn_on(self, **kwargs) -> None:
        self.coordinator.set_switch(self._switch_key, True)

    async def async_turn_off(self, **kwargs) -> None:
        self.coordinator.set_switch(self._switch_key, False)
