from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WaterSaverCoordinator, WaterSaverData


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: WaterSaverCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        WaterSaverHourActive(coordinator),
        WaterSaverLeak12h(coordinator),
        WaterSaverTodayHigh(coordinator),
        WaterSaverAlert(coordinator),
    ])


class _Base(CoordinatorEntity[WaterSaverCoordinator], BinarySensorEntity):
    _attr_has_entity_name = False

    def __init__(self, coordinator: WaterSaverCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self.coordinator.entry.entry_id)}}

    @property
    def available(self) -> bool:
        return self.coordinator.data.available


class WaterSaverHourActive(_Base):
    _attr_unique_id = "water_saver_hour_active"
    _attr_name = "Water Saver Hour Active"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.hour_active

    @property
    def icon(self) -> str:
        return "mdi:water-alert" if self.is_on else "mdi:water-check"


class WaterSaverLeak12h(_Base):
    _attr_unique_id = "water_saver_leak_12h"
    _attr_name = "Water Saver Leak 12h"
    _attr_device_class = BinarySensorDeviceClass.MOISTURE

    @property
    def is_on(self) -> bool:
        d = self.coordinator.data
        if not d.leak_enabled or not d.alert_enabled:
            return False
        if d.snoozed:
            return False
        return d.leak_detected

    @property
    def icon(self) -> str:
        return "mdi:water-alert" if self.is_on else "mdi:water-check"

    @property
    def extra_state_attributes(self):
        d = self.coordinator.data
        return {
            "consecutive_flow_hours": d.consecutive_flow_hours,
            "leak_detected_raw": d.leak_detected,
            "enabled": d.leak_enabled,
            "snoozed": d.snoozed,
            "snooze_until": d.snooze_until,
        }


class WaterSaverTodayHigh(_Base):
    _attr_unique_id = "water_saver_today_high"
    _attr_name = "Water Saver Today High"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        d = self.coordinator.data
        if not d.today_high_enabled or not d.alert_enabled:
            return False
        if d.snoozed:
            return False
        return d.today_high

    @property
    def icon(self) -> str:
        return "mdi:alert" if self.is_on else "mdi:check"

    @property
    def extra_state_attributes(self):
        d = self.coordinator.data
        return {
            "today_high_raw": d.today_high,
            "day_l": d.day_l,
            "excluded_today_l": d.excluded_today_l,
            "effective_day_l": round(max(0.0, d.day_l - d.excluded_today_l), 1),
            "exclude_active": d.exclude_active,
            "exclude_window_open": d.exclude_window_open,
            "avg_day_14d": d.avg_day_14d,
            "enabled": d.today_high_enabled,
            "snoozed": d.snoozed,
            "snooze_until": d.snooze_until,
        }


class WaterSaverAlert(_Base):
    _attr_unique_id = "water_saver_alert"
    _attr_name = "Water Saver Alert"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        d = self.coordinator.data
        if not d.alert_enabled:
            return False
        if d.snoozed:
            return False
        leak_on = d.leak_detected and d.leak_enabled
        high_on = d.today_high and d.today_high_enabled
        return leak_on or high_on

    @property
    def icon(self) -> str:
        return "mdi:alert" if self.is_on else "mdi:check"

    @property
    def extra_state_attributes(self):
        d = self.coordinator.data
        return {
            "leak_12h": d.leak_detected and d.leak_enabled,
            "today_high": d.today_high and d.today_high_enabled,
            "snoozed": d.snoozed,
            "snooze_until": d.snooze_until,
        }
