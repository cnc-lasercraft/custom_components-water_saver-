# Changelog

All notable changes to this project are documented here.
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-08-30

First release intended for general use. The 0.0.x line was an early prototype
built around YAML template sensors and `utility_meter`; everything is now
computed inside the integration and persisted across restarts.

### Added
- **Leak detection (continuous flow)** — alarm when every hour across a
  configurable window (default 12 h) shows consumption above 0 L.
- **Today-high detection** — alarm when today's consumption exceeds
  `14-day average × multiplier + buffer`, gated by a minimum volume and an
  earliest hour of day so a quiet morning never triggers it.
- **Rolling baseline** with 24 h / 14 d / 12 m history, averaged with the top
  values trimmed so a pool fill or a past leak does not raise the bar for the
  next alarm.
- **Pool / irrigation exclusion** — while a nominated entity is active, the
  meter delta is attributed to it and subtracted from today's total before the
  today-high threshold is checked, including a grace window that catches the
  meter's delayed lumps. Exposed as `excluded_today_l`, `effective_day_l` and
  `exclude_active` attributes on `binary_sensor.water_saver_today_high`.
- **Snooze** — `water_saver.snooze` / `water_saver.unsnooze` services plus a
  master switch and one switch per alarm type; turning the master switch off
  stops a running alarm within a second.
- **Binary sensors** `hour_active`, `leak_12h`, `today_high`, `alert`.
- **Comparison sensors** — today vs. 14-day average (delta and percent), month
  vs. 12-month average including an over/under split — and a leak-status text
  sensor.
- **Options flow** for every threshold, the exclusion entities and the grace
  window; no YAML required.
- **State persistence** — period starts, history and counters survive restarts.
- Availability handling: entities go unavailable after a configurable number of
  minutes without a telegram, instead of silently reporting zero consumption.
- Optional integration with the `herold` message broker: the topic
  `wasser/leck_alarm` is registered on startup when Herold is installed.
- Brand assets shipped in `custom_components/water_saver/brand/`.

### Changed
- Consumption per period is computed from meter deltas inside the integration;
  the `utility_meter` / template-sensor package (`water_saver.yaml`) is gone.
- `hacs.json` reduced to the keys HACS actually supports, and the country
  restriction removed — the integration works with any MQTT source.
- `manifest.json` gained `issue_tracker`; keys sorted as hassfest expects.

### Removed
- `custom_components/water_saver/water_saver.yaml` (superseded).
- A duplicate `hacs.json` inside the component directory.

## [0.0.10] - 2026-02-08
- Early prototype: MQTT JSON ingest, total / hour / day / week / month / year
  sensors, last seen, RSSI, battery, and a config flow for name and topic.

[0.1.0]: https://github.com/cnc-lasercraft/water_saver/releases/tag/v0.1.0
[0.0.10]: https://github.com/cnc-lasercraft/water_saver/releases/tag/v0.0.10
