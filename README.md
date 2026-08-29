# Water Saver

[![hacs][hacs-badge]][hacs-url]
[![validate][validate-badge]][validate-url]
[![release][release-badge]][release-url]
[![license][license-badge]](LICENSE)

Home Assistant integration that turns a plain MQTT water-meter feed into consumption
statistics and **leak alarms** — continuous-flow detection and an unusually high daily
total measured against your own rolling baseline.

Built for [wmbusmeters][wmbusmeters] pushing wM-Bus telegrams to MQTT, but any source
producing the same small JSON payload works.

## Features

- **Consumption per period** — current hour, day, week, month and year, plus the meter total.
- **Rolling baseline** — 24 h / 14 d / 12 m history, averaged with the top values trimmed so
  a pool fill or a past leak does not quietly raise the bar for the next alarm.
- **Leak detection (continuous flow)** — fires when *every* hour over a configurable window
  (default 12 h) shows consumption > 0 L. Nobody uses water around the clock; a dripping
  toilet or a burst pipe does.
- **Today-high detection** — fires when today's consumption exceeds
  `14-day average × multiplier + buffer`, evaluated only after a configurable hour of the day
  and above a minimum volume, so a quiet morning never triggers it.
- **Pool / irrigation exclusion** — while a nominated entity is active (a valve switch, a
  pool refill flow sensor …), the meter delta is attributed to that entity and subtracted
  from today's total before the today-high threshold is checked. A grace period catches the
  meter's delayed lumps. A real leak on the same day still triggers.
- **Snooze** — suppress all alerts for N hours from a service call, a dashboard button or an
  automation. Plus a master switch and one switch per alarm type.
- **Meter health** — last-seen minutes, RSSI, battery-years and an availability timeout, so a
  meter that goes silent is visible instead of looking like zero consumption.

## Installation

### HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.][hacs-repo-badge]][hacs-repo-url]

1. HACS → Integrations → ⋮ → **Custom repositories**
2. Add `https://github.com/cnc-lasercraft/water_saver`, category **Integration**
3. Install **Water Saver**, then restart Home Assistant

### Manual

Copy `custom_components/water_saver/` into your Home Assistant `config/custom_components/`
directory and restart.

## Configuration

Settings → Devices & Services → **Add Integration** → *Water Saver*.

You are asked for a name and the MQTT topic (default `wmbusmeters/Wasser`). Everything else
lives in the integration's **Configure** dialog:

| Option | Default | Meaning |
| --- | --- | --- |
| Unavailable timeout | 30 min | Minutes without a telegram before entities go unavailable |
| Leak: consecutive hours | 12 | Hours that must *all* show flow > 0 L |
| Today high: multiplier | 1.8 | Factor applied to the 14-day average |
| Today high: minimum liters | 200 L | Floor below which the alarm never fires |
| Today high: buffer liters | 100 L | Added to the average before comparing |
| Today high: after hour | 8 | Local hour from which the check runs |
| Exclusion entities | — | Entities whose active time is excluded from today-high |
| Exclusion grace | — | Minutes after an exclusion entity closes that still count |
| Default snooze duration | 8 h | Used when `water_saver.snooze` is called without `hours` |

### Expected MQTT payload

A JSON object with `"_": "telegram"` and a cumulative `total_m3`, i.e. what wmbusmeters emits:

```json
{
  "_": "telegram",
  "media": "water",
  "meter": "iperl",
  "id": "12345678",
  "total_m3": 1234.567,
  "timestamp": "2026-08-30T10:00:00Z",
  "rssi_dbm": -71
}
```

Optional extras (`status`, `power_mode`, `battery_y`, `rssi_dbm`) are surfaced as attributes
on the total sensor. Anything without `total_m3` is ignored.

## Entities

**Sensors** — meter total and current hour / day / week / month / year (L), rounded display
variants of each, comparison sensors against the baseline (today vs. 14-day average as delta
and percent, month vs. 12-month average incl. over/under split), a leak-status text sensor,
and meter health: last seen (min), battery (y), RSSI (dBm).

**Binary sensors**

| Entity | Device class | Fires when |
| --- | --- | --- |
| `binary_sensor.water_saver_hour_active` | — | Water is flowing this hour |
| `binary_sensor.water_saver_leak_12h` | moisture | Every hour in the window showed flow |
| `binary_sensor.water_saver_today_high` | problem | Today exceeds the baseline threshold |
| `binary_sensor.water_saver_alert` | problem | Either alarm is active and not snoozed |

`today_high` carries `excluded_today_l`, `effective_day_l` and `exclude_active` as attributes,
so you can see exactly what was subtracted and why.

**Switches** — a master `alert` switch plus one per alarm type (`leak`, `today_high`).
Turning the master switch off stops a running alarm within a second.

## Services

| Service | Fields | Description |
| --- | --- | --- |
| `water_saver.snooze` | `hours` (optional, 1–72) | Suppress all alerts; falls back to the configured default |
| `water_saver.unsnooze` | — | Cancel an active snooze immediately |

## Automation example

```yaml
automation:
  - alias: Water leak alarm
    triggers:
      - trigger: state
        entity_id: binary_sensor.water_saver_alert
        to: "on"
    actions:
      - action: notify.mobile_app_phone
        data:
          title: 💧 Water alarm
          message: >-
            {% set a = state_attr('binary_sensor.water_saver_alert', 'leak_12h') %}
            {{ 'Continuous flow detected' if a else 'Unusually high consumption' }} —
            {{ states('sensor.water_saver_display_today') }} L today
          data:
            push:
              sound:
                name: default
                critical: 1
                volume: 1.0
```

## Optional: Herold

Water Saver looks for a custom component with the domain `herold` — a local pub/sub message
broker used by the author to route notifications — and, if present, registers the topic
`wasser/leck_alarm` on startup so alarms can be dispatched through it. This is entirely
optional: without Herold the integration behaves identically and you route alerts with your
own automations, as in the example above.

## Contributing

Issues and pull requests are welcome. Please open an issue before starting larger changes.

## License

[MIT](LICENSE) © Urs Landis

[wmbusmeters]: https://github.com/wmbusmeters/wmbusmeters
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[hacs-url]: https://github.com/hacs/integration
[validate-badge]: https://github.com/cnc-lasercraft/water_saver/actions/workflows/validate.yml/badge.svg
[validate-url]: https://github.com/cnc-lasercraft/water_saver/actions/workflows/validate.yml
[release-badge]: https://img.shields.io/github/v/release/cnc-lasercraft/water_saver
[release-url]: https://github.com/cnc-lasercraft/water_saver/releases
[license-badge]: https://img.shields.io/github/license/cnc-lasercraft/water_saver
[hacs-repo-badge]: https://my.home-assistant.io/badges/hacs_repository.svg
[hacs-repo-url]: https://my.home-assistant.io/redirect/hacs_repository/?owner=cnc-lasercraft&repository=water_saver&category=integration
