# Water Saver (Home Assistant)

**Water Saver** is a Home Assistant custom integration that reads water meter data from an MQTT topic (JSON),
typically published by **wmbusmeters**, and creates ready-to-use sensors in **liters**.

This is designed as a sister project to **Tariff Saver**.

---

## Features

- Reads water meter telegrams from an MQTT topic (default: `wmbusmeters/Wasser`)
- Creates sensors:
  - Total water consumption (L)
  - Hour / Day / Week / Month / Year consumption (L)
  - Last seen (minutes)
  - RSSI (dBm)
  - Battery (years)
  - Status / Power mode (as attributes)
- Works great with:
  - Bubble Cards
  - ApexCharts

---

## Requirements

- Home Assistant OS / Supervised / Container
- MQTT integration enabled
- A publisher like **wmbusmeters** publishing JSON to MQTT

Example payload:

```json
{
  "_": "telegram",
  "meter": "gwfwater",
  "name": "Wasser",
  "id": "25536106",
  "battery_y": 14.5,
  "total_m3": 1.9,
  "status": "OK",
  "timestamp": "2026-02-05T10:47:56Z",
  "rssi_dbm": -67
}
