from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORE_KEY, STORE_VERSION


@dataclass
class PeriodState:
    # Period start total_l values
    start_total_l_hour: float | None = None
    start_total_l_day: float | None = None
    start_total_l_week: float | None = None
    start_total_l_month: float | None = None
    start_total_l_year: float | None = None

    # Timestamps of last period boundaries (ISO format, local time)
    last_hour_boundary: str | None = None
    last_day_boundary: str | None = None
    last_week_boundary: str | None = None
    last_month_boundary: str | None = None
    last_year_boundary: str | None = None

    # Rolling history buffers for averages
    hourly_history: list[float] = field(default_factory=list)   # last 24
    daily_history: list[float] = field(default_factory=list)    # last 14
    monthly_history: list[float] = field(default_factory=list)  # last 12

    # Leak detection
    consecutive_flow_hours: int = 0

    # Last known total_l (survives unavailable periods)
    last_total_l: float | None = None

    # Switch states (persisted)
    leak_enabled: bool = True
    today_high_enabled: bool = True
    alert_enabled: bool = True

    # Snooze (ISO timestamp when snooze expires, None = not snoozed)
    snooze_until: str | None = None

    # Liters consumed today during excluded windows (lawn/pool) — subtracted
    # from day_l before today-high evaluation. Resets at the day boundary.
    excluded_today_l: float = 0.0

    # UTC ISO timestamp until which the exclusion window stays "open" (grace
    # period after the last active lawn/pool moment). None = window closed.
    exclude_grace_until: str | None = None

    # True from the moment a lawn/pool draw goes inactive until one telegram
    # has been booked against it. Keeps the exclusion window open across a
    # meter reporting interval that is longer than the grace period, so the
    # tail of the draw still gets subtracted. Cleared on a day rollover.
    exclude_settle_pending: bool = False


class WaterSaverStore:
    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, STORE_VERSION, STORE_KEY)

    async def async_load(self) -> PeriodState:
        data = await self._store.async_load()
        if not data:
            return PeriodState()
        return _migrate(data)

    async def async_save(self, state: PeriodState) -> None:
        await self._store.async_save(_serialize(state))


def _migrate(data: dict[str, Any]) -> PeriodState:
    """Migrate from any older storage format to current PeriodState."""
    # v1 only had the 5 start_total_l_* fields
    # v2 adds everything else — missing keys get defaults
    defaults = PeriodState()
    return PeriodState(
        start_total_l_hour=data.get("start_total_l_hour", defaults.start_total_l_hour),
        start_total_l_day=data.get("start_total_l_day", defaults.start_total_l_day),
        start_total_l_week=data.get("start_total_l_week", defaults.start_total_l_week),
        start_total_l_month=data.get("start_total_l_month", defaults.start_total_l_month),
        start_total_l_year=data.get("start_total_l_year", defaults.start_total_l_year),
        last_hour_boundary=data.get("last_hour_boundary"),
        last_day_boundary=data.get("last_day_boundary"),
        last_week_boundary=data.get("last_week_boundary"),
        last_month_boundary=data.get("last_month_boundary"),
        last_year_boundary=data.get("last_year_boundary"),
        hourly_history=data.get("hourly_history", []),
        daily_history=data.get("daily_history", []),
        monthly_history=data.get("monthly_history", []),
        consecutive_flow_hours=data.get("consecutive_flow_hours", 0),
        last_total_l=data.get("last_total_l"),
        leak_enabled=data.get("leak_enabled", True),
        today_high_enabled=data.get("today_high_enabled", True),
        alert_enabled=data.get("alert_enabled", True),
        snooze_until=data.get("snooze_until"),
        excluded_today_l=data.get("excluded_today_l", 0.0),
        exclude_grace_until=data.get("exclude_grace_until"),
        exclude_settle_pending=data.get("exclude_settle_pending", False),
    )


def _serialize(state: PeriodState) -> dict[str, Any]:
    return {
        "start_total_l_hour": state.start_total_l_hour,
        "start_total_l_day": state.start_total_l_day,
        "start_total_l_week": state.start_total_l_week,
        "start_total_l_month": state.start_total_l_month,
        "start_total_l_year": state.start_total_l_year,
        "last_hour_boundary": state.last_hour_boundary,
        "last_day_boundary": state.last_day_boundary,
        "last_week_boundary": state.last_week_boundary,
        "last_month_boundary": state.last_month_boundary,
        "last_year_boundary": state.last_year_boundary,
        "hourly_history": state.hourly_history,
        "daily_history": state.daily_history,
        "monthly_history": state.monthly_history,
        "consecutive_flow_hours": state.consecutive_flow_hours,
        "last_total_l": state.last_total_l,
        "leak_enabled": state.leak_enabled,
        "today_high_enabled": state.today_high_enabled,
        "alert_enabled": state.alert_enabled,
        "snooze_until": state.snooze_until,
        "excluded_today_l": state.excluded_today_l,
        "exclude_grace_until": state.exclude_grace_until,
        "exclude_settle_pending": state.exclude_settle_pending,
    }
