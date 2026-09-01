from __future__ import annotations

import json
import logging
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from statistics import mean
from typing import Any

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_EXCLUDE_ENTITIES,
    CONF_LEAK_HOURS,
    CONF_NAME,
    CONF_TODAY_HIGH_AFTER_HOUR,
    CONF_TODAY_HIGH_BUFFER_L,
    CONF_TODAY_HIGH_MIN_L,
    CONF_TODAY_HIGH_MULTIPLIER,
    CONF_EXCLUDE_GRACE_MIN,
    CONF_TOPIC,
    CONF_UNAVAILABLE_TIMEOUT,
    DEFAULT_EXCLUDE_ENTITIES,
    DEFAULT_EXCLUDE_GRACE_MIN,
    DEFAULT_LEAK_HOURS,
    DEFAULT_TODAY_HIGH_AFTER_HOUR,
    DEFAULT_TODAY_HIGH_BUFFER_L,
    DEFAULT_TODAY_HIGH_MIN_L,
    DEFAULT_TODAY_HIGH_MULTIPLIER,
    DEFAULT_UNAVAILABLE_TIMEOUT,
    DOMAIN,
)
from .storage import PeriodState, WaterSaverStore

LOGGER = logging.getLogger(__name__)

_HOURLY_HISTORY_MAX = 24
_DAILY_HISTORY_MAX = 14
_MONTHLY_HISTORY_MAX = 12

# States that count as "not drawing water" for exclusion entities. Anything
# else (switch "on", "open", "active", …) or a numeric value > 0 means active.
_EXCLUDE_INACTIVE_STATES = {
    "off", "idle", "unavailable", "unknown", "none", "closed", "standby", "paused", "",
}


def _state_is_active(state) -> bool:
    """True if an exclusion entity is currently drawing water."""
    if state is None:
        return False
    s = str(state.state).strip().lower()
    if s in _EXCLUDE_INACTIVE_STATES:
        return False
    try:
        return float(s) > 0
    except (ValueError, TypeError):
        # Non-numeric, non-inactive textual state (on / open / active / playing …)
        return True


@dataclass
class WaterSaverData:
    # Raw MQTT values
    total_m3: float | None = None
    battery_y: float | None = None
    rssi_dbm: float | None = None
    status: str | None = None
    power_mode: str | None = None
    meter_id: str | None = None
    telegram_timestamp: str | None = None
    last_rx_utc: datetime | None = None
    last_seen_min: int | None = None

    # Computed
    total_l: float | None = None
    hour_l: float = 0.0
    day_l: float = 0.0
    week_l: float = 0.0
    month_l: float = 0.0
    year_l: float = 0.0

    # Previous period values (for extra_state_attributes)
    last_hour_l: float | None = None
    last_day_l: float | None = None

    # Rolling averages
    avg_hour_24h: float | None = None
    avg_day_14d: float | None = None
    avg_month_12m: float | None = None

    # Binary states
    hour_active: bool = False
    leak_detected: bool = False
    today_high: bool = False

    # Exclusion (lawn/pool draws excluded from today-high)
    excluded_today_l: float = 0.0
    exclude_active: bool = False
    exclude_window_open: bool = False  # active OR within grace after close

    # Availability
    available: bool = False

    # Switch states
    leak_enabled: bool = True
    today_high_enabled: bool = True
    alert_enabled: bool = True

    # Snooze
    snoozed: bool = False
    snooze_until: str | None = None

    # Leak tracking
    consecutive_flow_hours: int = 0


class WaterSaverCoordinator(DataUpdateCoordinator[WaterSaverData]):
    """Push-based coordinator fed by MQTT with period tracking."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        self.name = entry.options.get(CONF_NAME, entry.data.get(CONF_NAME))
        self.topic = entry.options.get(CONF_TOPIC, entry.data.get(CONF_TOPIC))

        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=f"{DOMAIN}:{self.name}",
            update_interval=None,
        )

        self._unsub_mqtt = None
        self._unsub_tick = None
        self._unsub_save_debounce = None
        self._unsub_exclude = None
        self._exclude_active = False

        self._store = WaterSaverStore(hass)
        self._period: PeriodState = PeriodState()

        self.async_set_updated_data(WaterSaverData())

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    def _opt(self, key: str, default):
        return self.entry.options.get(key, self.entry.data.get(key, default))

    @property
    def unavailable_timeout(self) -> int:
        return self._opt(CONF_UNAVAILABLE_TIMEOUT, DEFAULT_UNAVAILABLE_TIMEOUT)

    @property
    def leak_hours(self) -> int:
        return self._opt(CONF_LEAK_HOURS, DEFAULT_LEAK_HOURS)

    @property
    def today_high_multiplier(self) -> float:
        return self._opt(CONF_TODAY_HIGH_MULTIPLIER, DEFAULT_TODAY_HIGH_MULTIPLIER)

    @property
    def today_high_min_l(self) -> float:
        return self._opt(CONF_TODAY_HIGH_MIN_L, DEFAULT_TODAY_HIGH_MIN_L)

    @property
    def today_high_buffer_l(self) -> int:
        return self._opt(CONF_TODAY_HIGH_BUFFER_L, DEFAULT_TODAY_HIGH_BUFFER_L)

    @property
    def today_high_after_hour(self) -> int:
        return self._opt(CONF_TODAY_HIGH_AFTER_HOUR, DEFAULT_TODAY_HIGH_AFTER_HOUR)

    @property
    def exclude_entities(self) -> list[str]:
        val = self._opt(CONF_EXCLUDE_ENTITIES, DEFAULT_EXCLUDE_ENTITIES)
        return list(val) if val else []

    @property
    def exclude_grace_min(self) -> int:
        return self._opt(CONF_EXCLUDE_GRACE_MIN, DEFAULT_EXCLUDE_GRACE_MIN)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_initialize(self) -> None:
        self._period = await self._store.async_load()
        LOGGER.debug(
            "Water Saver loaded state: last_total_l=%s, hour_boundary=%s",
            self._period.last_total_l,
            self._period.last_hour_boundary,
        )

        # Seed current exclusion state from live entity states
        self._exclude_active = self._recompute_exclude_active()

        # Restore switch/snooze states into data
        d = self.data
        self.async_set_updated_data(
            replace(
                d,
                leak_enabled=self._period.leak_enabled,
                today_high_enabled=self._period.today_high_enabled,
                alert_enabled=self._period.alert_enabled,
                snooze_until=self._period.snooze_until,
                snoozed=self._is_snoozed(),
                consecutive_flow_hours=self._period.consecutive_flow_hours,
                excluded_today_l=self._period.excluded_today_l,
                exclude_active=self._exclude_active,
                exclude_window_open=self._exclude_window_open(dt_util.utcnow()),
            )
        )

        @callback
        def _msg_received(msg: mqtt.ReceiveMessage) -> None:
            self._handle_payload(msg.payload)

        self._unsub_mqtt = await mqtt.async_subscribe(
            self.hass, self.topic, _msg_received, qos=0, encoding="utf-8",
        )

        self._unsub_tick = async_track_time_interval(
            self.hass, self._tick, timedelta(minutes=1),
        )

        if self.exclude_entities:
            self._unsub_exclude = async_track_state_change_event(
                self.hass, self.exclude_entities, self._exclude_changed,
            )

    async def async_shutdown(self) -> None:
        if self._unsub_mqtt:
            self._unsub_mqtt()
            self._unsub_mqtt = None
        if self._unsub_tick:
            self._unsub_tick()
            self._unsub_tick = None
        if self._unsub_exclude:
            self._unsub_exclude()
            self._unsub_exclude = None
        if self._unsub_save_debounce:
            self._unsub_save_debounce()
            self._unsub_save_debounce = None
        await self._store.async_save(self._period)

    # ------------------------------------------------------------------
    # Tick (every minute)
    # ------------------------------------------------------------------

    @callback
    def _tick(self, _now: datetime) -> None:
        d = self.data
        changes: dict[str, Any] = {}

        # Update last_seen_min
        if d.last_rx_utc is not None:
            mins = int((dt_util.utcnow() - d.last_rx_utc).total_seconds() // 60)
            if mins != d.last_seen_min:
                changes["last_seen_min"] = mins

            # Availability
            avail = mins < self.unavailable_timeout
            if avail != d.available:
                changes["available"] = avail

        # Update snooze status
        snoozed = self._is_snoozed()
        if snoozed != d.snoozed:
            changes["snoozed"] = snoozed

        # Exclusion grace window may expire between telegrams → refresh the flag
        # and, once it closes, let today-high (re)evaluate against the fully
        # subtracted volume without having to wait for the next telegram.
        window_open = self._exclude_window_open(dt_util.utcnow())
        if window_open != d.exclude_window_open:
            changes["exclude_window_open"] = window_open
            th = self._eval_today_high(
                dt_util.now(), d.day_l, d.avg_day_14d, self._period.excluded_today_l
            )
            if th and window_open:
                th = False
            if th != d.today_high:
                changes["today_high"] = th

        if changes:
            self.async_set_updated_data(replace(d, **changes))

    # ------------------------------------------------------------------
    # Exclusion entities (lawn / pool) tracking
    # ------------------------------------------------------------------

    def _recompute_exclude_active(self) -> bool:
        """True if any configured exclusion entity is currently drawing water."""
        for eid in self.exclude_entities:
            if _state_is_active(self.hass.states.get(eid)):
                return True
        return False

    def _exclude_window_open(self, now_utc: datetime) -> bool:
        """True while a lawn/pool draw is active, still within the grace period
        after it closed, or still waiting for the telegram that books the tail
        of the draw. The meter reports consumption with a lag and in lumps, so
        the water drawn shortly before the valve closed lands in a LATER
        telegram — the window keeps the subtraction (and today-high
        suppression) alive long enough to catch it. While active, the grace
        deadline is pushed forward.

        Two independent conditions keep the window open after the draw ends:
        the grace period (a time floor, so meters that report faster than the
        grace can book the lump across several telegrams) and the settle flag
        (no floor, so meters that report SLOWER than the grace still get their
        one trailing telegram counted). Without the flag a meter reporting
        hourly would leave everything drawn after the last in-window telegram
        in today's effective volume."""
        if self._exclude_active:
            self._period.exclude_grace_until = (
                now_utc + timedelta(minutes=self.exclude_grace_min)
            ).isoformat()
            return True
        if self._period.exclude_settle_pending:
            return True
        until = (
            _parse_iso(self._period.exclude_grace_until)
            if self._period.exclude_grace_until
            else None
        )
        return until is not None and now_utc <= until

    @callback
    def _exclude_changed(self, _event) -> None:
        active = self._recompute_exclude_active()
        if active == self._exclude_active:
            return
        self._exclude_active = active
        # Start (or refresh) the grace deadline. When the valve just closed this
        # begins the countdown that still captures the delayed meter lump; while
        # active it keeps being pushed forward by _exclude_window_open().
        now_utc = dt_util.utcnow()
        self._period.exclude_grace_until = (
            now_utc + timedelta(minutes=self.exclude_grace_min)
        ).isoformat()
        # Closing the valve arms the settle flag: the window must survive until
        # one more telegram has been booked, however long the meter takes.
        self._period.exclude_settle_pending = not active
        self.async_set_updated_data(
            replace(
                self.data,
                exclude_active=active,
                exclude_window_open=self._exclude_window_open(now_utc),
            )
        )
        self._schedule_save()

    # ------------------------------------------------------------------
    # MQTT payload handling
    # ------------------------------------------------------------------

    def _handle_payload(self, payload: str) -> None:
        try:
            obj: dict[str, Any] = json.loads(payload)
        except Exception:
            return

        if obj.get("_") != "telegram":
            return

        total_m3 = obj.get("total_m3")
        if total_m3 is None:
            return

        now_utc = dt_util.utcnow()
        now_local = dt_util.now()
        total_l = round(float(total_m3) * 1000, 1)

        # Prior telegram total — baseline for the exclusion delta below
        prev_total_l = self._period.last_total_l

        # Check period boundaries BEFORE updating period starts
        # (resets excluded_today_l on a day rollover)
        need_save = self._check_boundaries(now_local, total_l)

        # Exclusion: while the exclusion window is open (lawn/pool active OR
        # within the grace period after it closed), attribute the meter delta
        # since the last telegram to today's excluded volume. The grace window
        # is what catches the meter's delayed lumps — the draw frequently lands
        # several minutes after the valve already went off.
        window_open = self._exclude_window_open(now_utc)
        if window_open and prev_total_l is not None:
            delta = round(total_l - prev_total_l, 1)
            if delta > 0:
                self._period.excluded_today_l = round(
                    self._period.excluded_today_l + delta, 1
                )
                # Persist promptly (debounced) so a restart mid-window doesn't
                # lose the accumulated exclusion or the grace deadline.
                need_save = True
            # The draw is over and this telegram carried its tail — the settle
            # flag has done its job. The grace deadline (if still running) can
            # keep the window open on its own; this telegram itself is still
            # treated as in-window.
            if not self._exclude_active and self._period.exclude_settle_pending:
                self._period.exclude_settle_pending = False
                need_save = True

        # Store last known total_l (survives unavailable periods)
        self._period.last_total_l = total_l

        # Compute current period consumption
        hour_l = self._period_consumption(total_l, self._period.start_total_l_hour)
        day_l = self._period_consumption(total_l, self._period.start_total_l_day)
        week_l = self._period_consumption(total_l, self._period.start_total_l_week)
        month_l = self._period_consumption(total_l, self._period.start_total_l_month)
        year_l = self._period_consumption(total_l, self._period.start_total_l_year)

        # Averages from history (trimmed to stay robust against outliers like
        # pool fills or short-term leaks: top-N values dropped before averaging)
        avg_hour = self._avg(self._period.hourly_history)
        avg_day = self._avg(self._period.daily_history, trim_top=2)
        avg_month = self._avg(self._period.monthly_history, trim_top=1)

        # Binary states
        hour_active = hour_l > 0
        leak_detected = self._period.consecutive_flow_hours >= self.leak_hours
        today_high = self._eval_today_high(
            now_local, day_l, avg_day, self._period.excluded_today_l
        )
        # Settle-Guard: while the exclusion window is open (draw active or the
        # grace period still running), suppress today-high — the meter may still
        # be booking the delayed pool/lawn lump, so effective_day_l is not yet
        # trustworthy. Once the window closes the next telegram (or tick) will
        # evaluate normally against the fully-subtracted volume.
        if today_high and window_open:
            today_high = False

        new_data = WaterSaverData(
            total_m3=float(total_m3),
            battery_y=_float_or_none(obj, "battery_y"),
            rssi_dbm=_float_or_none(obj, "rssi_dbm"),
            status=obj.get("status"),
            power_mode=obj.get("power_mode"),
            meter_id=str(obj["id"]) if obj.get("id") is not None else None,
            telegram_timestamp=obj.get("timestamp"),
            last_rx_utc=now_utc,
            last_seen_min=0,
            total_l=total_l,
            hour_l=hour_l,
            day_l=day_l,
            week_l=week_l,
            month_l=month_l,
            year_l=year_l,
            last_hour_l=self._last_history_value(self._period.hourly_history),
            last_day_l=self._last_history_value(self._period.daily_history),
            avg_hour_24h=avg_hour,
            avg_day_14d=avg_day,
            avg_month_12m=avg_month,
            hour_active=hour_active,
            leak_detected=leak_detected,
            today_high=today_high,
            excluded_today_l=self._period.excluded_today_l,
            exclude_active=self._exclude_active,
            exclude_window_open=window_open,
            available=True,
            leak_enabled=self._period.leak_enabled,
            today_high_enabled=self._period.today_high_enabled,
            alert_enabled=self._period.alert_enabled,
            snoozed=self._is_snoozed(),
            snooze_until=self._period.snooze_until,
            consecutive_flow_hours=self._period.consecutive_flow_hours,
        )

        self.async_set_updated_data(new_data)

        if need_save:
            self._schedule_save()

    # ------------------------------------------------------------------
    # Period boundary logic
    # ------------------------------------------------------------------

    def _check_boundaries(self, now_local: datetime, total_l: float) -> bool:
        """Check and process period boundaries. Returns True if any boundary crossed."""
        p = self._period
        changed = False

        # First message ever — initialise all starts
        if p.start_total_l_hour is None:
            p.start_total_l_hour = total_l
            p.start_total_l_day = total_l
            p.start_total_l_week = total_l
            p.start_total_l_month = total_l
            p.start_total_l_year = total_l
            p.last_hour_boundary = now_local.isoformat()
            p.last_day_boundary = now_local.isoformat()
            p.last_week_boundary = now_local.isoformat()
            p.last_month_boundary = now_local.isoformat()
            p.last_year_boundary = now_local.isoformat()
            return True

        last_hour = _parse_iso(p.last_hour_boundary) if p.last_hour_boundary else None

        # Hour boundary
        if last_hour is None or now_local.hour != last_hour.hour or now_local.date() != last_hour.date():
            consumption = self._period_consumption(total_l, p.start_total_l_hour)
            p.hourly_history.append(consumption)
            p.hourly_history = p.hourly_history[-_HOURLY_HISTORY_MAX:]

            # Leak detection: count consecutive hours with any flow
            if consumption > 0:
                p.consecutive_flow_hours += 1
            else:
                p.consecutive_flow_hours = 0

            p.start_total_l_hour = total_l
            p.last_hour_boundary = now_local.isoformat()
            changed = True

        # Day boundary
        last_day = _parse_iso(p.last_day_boundary) if p.last_day_boundary else None
        if last_day is None or now_local.date() != last_day.date():
            consumption = self._period_consumption(total_l, p.start_total_l_day)
            p.daily_history.append(consumption)
            p.daily_history = p.daily_history[-_DAILY_HISTORY_MAX:]
            p.start_total_l_day = total_l
            p.last_day_boundary = now_local.isoformat()
            p.excluded_today_l = 0.0  # new day → reset excluded volume
            # Bound the settle flag to the day it was armed in: this telegram
            # restarts day_l from zero, so yesterday's tail can no longer
            # distort today's total and must not hold the window open.
            p.exclude_settle_pending = False
            changed = True

        # Week boundary (Monday = 0)
        last_week = _parse_iso(p.last_week_boundary) if p.last_week_boundary else None
        if last_week is None or now_local.isocalendar()[1] != last_week.isocalendar()[1] or now_local.year != last_week.year:
            p.start_total_l_week = total_l
            p.last_week_boundary = now_local.isoformat()
            changed = True

        # Month boundary
        last_month = _parse_iso(p.last_month_boundary) if p.last_month_boundary else None
        if last_month is None or now_local.month != last_month.month or now_local.year != last_month.year:
            consumption = self._period_consumption(total_l, p.start_total_l_month)
            p.monthly_history.append(consumption)
            p.monthly_history = p.monthly_history[-_MONTHLY_HISTORY_MAX:]
            p.start_total_l_month = total_l
            p.last_month_boundary = now_local.isoformat()
            changed = True

        # Year boundary
        last_year = _parse_iso(p.last_year_boundary) if p.last_year_boundary else None
        if last_year is None or now_local.year != last_year.year:
            p.start_total_l_year = total_l
            p.last_year_boundary = now_local.isoformat()
            changed = True

        return changed

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _period_consumption(total_l: float, start: float | None) -> float:
        if start is None:
            return 0.0
        return max(0.0, round(total_l - start, 1))

    @staticmethod
    def _avg(history: list[float], trim_top: int = 0) -> float | None:
        if not history:
            return None
        if trim_top > 0 and len(history) > trim_top:
            # Sort descending, drop top-N, mean of the rest
            history = sorted(history, reverse=True)[trim_top:]
        return round(mean(history), 2)

    @staticmethod
    def _last_history_value(history: list[float]) -> float | None:
        return history[-1] if history else None

    def _eval_today_high(
        self,
        now_local: datetime,
        day_l: float,
        avg_day: float | None,
        excluded_l: float = 0.0,
    ) -> bool:
        if now_local.hour < self.today_high_after_hour:
            return False
        if avg_day is None or avg_day <= 0:
            return False
        # Subtract known lawn/pool draws before comparing against the baseline
        effective_l = max(0.0, day_l - excluded_l)
        return (
            effective_l > (avg_day * self.today_high_multiplier + self.today_high_buffer_l)
            and effective_l > self.today_high_min_l
        )

    def _is_snoozed(self) -> bool:
        if self._period.snooze_until is None:
            return False
        try:
            until = datetime.fromisoformat(self._period.snooze_until)
            if until > dt_util.now():
                return True
            # Snooze expired — clean up
            self._period.snooze_until = None
            return False
        except (ValueError, TypeError):
            self._period.snooze_until = None
            return False

    # ------------------------------------------------------------------
    # Snooze / Switch control (called by switch.py and services)
    # ------------------------------------------------------------------

    def set_snooze(self, hours: float) -> None:
        until = dt_util.now() + timedelta(hours=hours)
        self._period.snooze_until = until.isoformat()
        self._update_flags_and_save()

    def clear_snooze(self) -> None:
        self._period.snooze_until = None
        self._update_flags_and_save()

    def set_switch(self, switch: str, enabled: bool) -> None:
        if switch == "leak":
            self._period.leak_enabled = enabled
        elif switch == "today_high":
            self._period.today_high_enabled = enabled
        elif switch == "alert":
            self._period.alert_enabled = enabled
        self._update_flags_and_save()

    def _update_flags_and_save(self) -> None:
        d = self.data
        self.async_set_updated_data(
            replace(
                d,
                leak_enabled=self._period.leak_enabled,
                today_high_enabled=self._period.today_high_enabled,
                alert_enabled=self._period.alert_enabled,
                snoozed=self._is_snoozed(),
                snooze_until=self._period.snooze_until,
            )
        )
        self._schedule_save()

    # ------------------------------------------------------------------
    # Storage save (debounced)
    # ------------------------------------------------------------------

    @callback
    def _schedule_save(self) -> None:
        if self._unsub_save_debounce:
            self._unsub_save_debounce()
        self._unsub_save_debounce = async_call_later(
            self.hass, 5, self._do_save
        )

    async def _do_save(self, _now: datetime | None = None) -> None:
        self._unsub_save_debounce = None
        await self._store.async_save(self._period)


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _float_or_none(obj: dict, key: str) -> float | None:
    v = obj.get(key)
    return float(v) if v is not None else None


def _parse_iso(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None
