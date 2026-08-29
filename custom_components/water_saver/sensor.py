from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
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

    # Original device-bound sensors (has_entity_name = True)
    entities: list[SensorEntity] = [
        WaterSaverTotalM3Sensor(coordinator),
        WaterSaverLastSeenMinSensor(coordinator),
        WaterSaverBatteryYSensor(coordinator),
        WaterSaverRssiSensor(coordinator),
    ]

    # Computed sensors (has_entity_name = False for entity_id compatibility)
    entities.extend(_build_computed_sensors(coordinator))

    async_add_entities(entities)


# =====================================================================
# Original device-bound sensors
# =====================================================================


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

    @property
    def available(self) -> bool:
        return self.coordinator.data.available


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
    def available(self) -> bool:
        # Always available — useful precisely when device is unavailable
        return True

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


# =====================================================================
# Computed sensors (entity_id compatible with former YAML entities)
# =====================================================================


class _Computed(CoordinatorEntity[WaterSaverCoordinator], SensorEntity):
    """Base for sensors replacing YAML template/utility_meter entities."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: WaterSaverCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self.coordinator.entry.entry_id)}}

    @property
    def available(self) -> bool:
        return self.coordinator.data.available


def _build_computed_sensors(coord: WaterSaverCoordinator) -> list[SensorEntity]:
    """Build all computed sensors from descriptor dicts."""
    sensors: list[SensorEntity] = []

    # --- Period consumption sensors ---
    period_defs = [
        ("water_saver_total_liters", "Water Saver Total Liters", "L", "water", SensorStateClass.TOTAL_INCREASING, lambda d: d.total_l),
        ("water_saver_hour_l", "water_saver_hour_l", "L", "water", SensorStateClass.TOTAL_INCREASING, lambda d: d.hour_l),
        ("water_saver_day_l", "water_saver_day_l", "L", "water", SensorStateClass.TOTAL_INCREASING, lambda d: d.day_l),
        ("water_saver_week_l", "water_saver_week_l", "L", "water", SensorStateClass.TOTAL_INCREASING, lambda d: d.week_l),
        ("water_saver_month_l", "water_saver_month_l", "L", "water", SensorStateClass.TOTAL_INCREASING, lambda d: d.month_l),
        ("water_saver_year_l", "water_saver_year_l", "L", "water", SensorStateClass.TOTAL_INCREASING, lambda d: d.year_l),
    ]

    for uid, name, unit, dev_cls, state_cls, value_fn in period_defs:
        sensors.append(_make_sensor(coord, uid, name, unit, dev_cls, state_cls, value_fn))

    # --- Period sensors: extra attributes (last_period, last_valid_state) ---
    # hour_l and day_l get extra attributes for compatibility
    for s in sensors:
        if s.unique_id == "water_saver_hour_l":
            s._extra_attr_fn = lambda d: {  # type: ignore[attr-defined]
                "status": "collecting",
                "last_period": d.last_hour_l,
                "last_valid_state": d.total_l,
            }
        elif s.unique_id == "water_saver_day_l":
            s._extra_attr_fn = lambda d: {  # type: ignore[attr-defined]
                "status": "collecting",
                "last_period": d.last_day_l,
                "last_valid_state": d.total_l,
            }

    # --- Average sensors ---
    avg_defs = [
        ("water_saver_avg_hour_24h", "Water Saver Avg Hour 24h", "L", None, SensorStateClass.MEASUREMENT, lambda d: d.avg_hour_24h, "mdi:calculator"),
        ("water_saver_avg_day_14d", "Water Saver Avg Day 14d", "L", None, SensorStateClass.MEASUREMENT, lambda d: d.avg_day_14d, "mdi:calculator"),
        ("water_saver_avg_month_12m", "Water Saver Avg Month 12m", "L", None, SensorStateClass.MEASUREMENT, lambda d: d.avg_month_12m, "mdi:calculator"),
    ]
    for uid, name, unit, dev_cls, state_cls, value_fn, icon in avg_defs:
        sensors.append(_make_sensor(coord, uid, name, unit, dev_cls, state_cls, value_fn, icon=icon))

    # --- Display sensors (rounded, no state_class) ---
    display_defs = [
        ("water_saver_display_total", "Water Saver Display Total", lambda d: _round_or_none(d.total_l)),
        ("water_saver_display_hour", "Water Saver Display Hour", lambda d: _round_or_none(d.hour_l)),
        ("water_saver_display_today", "Water Saver Display Today", lambda d: _round_or_none(d.day_l)),
        ("water_saver_display_week", "Water Saver Display Week", lambda d: _round_or_none(d.week_l)),
        ("water_saver_display_month", "Water Saver Display Month", lambda d: _round_or_none(d.month_l)),
        ("water_saver_display_year", "Water Saver Display Year", lambda d: _round_or_none(d.year_l)),
        ("water_saver_display_avg_14d", "Water Saver Display Avg 14d", lambda d: _round_or_none(d.avg_day_14d)),
        ("water_saver_display_avg_12m", "Water Saver Display Avg 12m", lambda d: _round_or_none(d.avg_month_12m)),
    ]
    for uid, name, value_fn in display_defs:
        sensors.append(_make_sensor(coord, uid, name, "L", None, None, value_fn))

    # --- Comparison sensors ---
    comparison_defs = [
        ("water_saver_today_delta_avg_14d", "Water Saver Today Delta Avg 14d", "L", SensorStateClass.MEASUREMENT,
         lambda d: _delta(d.day_l, d.avg_day_14d)),
        ("water_saver_today_percent_avg_14d", "Water Saver Today Percent Avg 14d", "%", SensorStateClass.MEASUREMENT,
         lambda d: _percent(d.day_l, d.avg_day_14d)),
        ("water_saver_month_delta_avg_12m", "Water Saver Month Delta Avg 12m", "L", SensorStateClass.MEASUREMENT,
         lambda d: _delta(d.month_l, d.avg_month_12m)),
        ("water_saver_month_over_avg_12m", "Water Saver Month Over Avg 12m", "L", SensorStateClass.MEASUREMENT,
         lambda d: _clamp_positive(_delta(d.month_l, d.avg_month_12m))),
        ("water_saver_month_under_avg_12m", "Water Saver Month Under Avg 12m", "L", SensorStateClass.MEASUREMENT,
         lambda d: _clamp_positive(_neg_delta(d.month_l, d.avg_month_12m))),
    ]
    for uid, name, unit, state_cls, value_fn in comparison_defs:
        sensors.append(_make_sensor(coord, uid, name, unit, None, state_cls, value_fn))

    # --- Leak status text sensor ---
    sensors.append(_make_sensor(
        coord,
        "water_saver_leak_status",
        "Water Saver Leak Status",
        None, None, None,
        lambda d: _leak_status_text(d),
        icon_fn=lambda d: "mdi:water-alert" if d.leak_detected else "mdi:water-check",
    ))

    return sensors


# =====================================================================
# Sensor factory
# =====================================================================


def _make_sensor(
    coord: WaterSaverCoordinator,
    unique_id: str,
    name: str,
    unit: str | None,
    device_class: str | None,
    state_class: SensorStateClass | str | None,
    value_fn,
    icon: str | None = None,
    icon_fn=None,
) -> _Computed:
    sensor = _FactorySensor(coord)
    sensor._attr_unique_id = unique_id
    sensor._attr_name = name
    sensor._attr_native_unit_of_measurement = unit
    if device_class:
        sensor._attr_device_class = device_class
    if state_class:
        sensor._attr_state_class = state_class
    if icon:
        sensor._attr_icon = icon
    sensor._value_fn = value_fn  # type: ignore[attr-defined]
    sensor._icon_fn = icon_fn  # type: ignore[attr-defined]
    sensor._extra_attr_fn = None  # type: ignore[attr-defined]
    return sensor


class _FactorySensor(_Computed):
    _value_fn = None
    _icon_fn = None
    _extra_attr_fn = None

    @property
    def native_value(self):
        if self._value_fn is None:
            return None
        return self._value_fn(self.coordinator.data)

    @property
    def icon(self) -> str | None:
        if self._icon_fn is not None:
            return self._icon_fn(self.coordinator.data)
        return self._attr_icon if hasattr(self, "_attr_icon") else None

    @property
    def extra_state_attributes(self):
        if self._extra_attr_fn is not None:
            return self._extra_attr_fn(self.coordinator.data)
        return None


# =====================================================================
# Value helpers
# =====================================================================


def _round_or_none(v) -> int | None:
    if v is None:
        return None
    return round(v)


def _delta(current: float, avg: float | None) -> int | None:
    if avg is None:
        return None
    return round(current - avg)


def _neg_delta(current: float, avg: float | None) -> int | None:
    if avg is None:
        return None
    return round(avg - current)


def _percent(current: float, avg: float | None) -> int | None:
    if avg is None or avg <= 0:
        return None
    return round((current / avg) * 100)


def _clamp_positive(v: int | None) -> int:
    if v is None:
        return 0
    return max(0, v)


def _leak_status_text(d: WaterSaverData) -> str:
    if d.leak_detected:
        return "Leak"
    if d.today_high:
        return "High"
    return "OK"
