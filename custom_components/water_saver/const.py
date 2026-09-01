DOMAIN = "water_saver"

CONF_TOPIC = "topic"
CONF_NAME = "name"

DEFAULT_NAME = "Water"
DEFAULT_TOPIC = "wmbusmeters/Wasser"

STORE_KEY = "water_saver_state"
STORE_VERSION = 2

# Availability
CONF_UNAVAILABLE_TIMEOUT = "unavailable_timeout_min"
DEFAULT_UNAVAILABLE_TIMEOUT = 30  # minutes without MQTT → unavailable

# Leak detection
CONF_LEAK_HOURS = "leak_hours"
DEFAULT_LEAK_HOURS = 12  # consecutive hours with flow > 0 L

# Today high detection
CONF_TODAY_HIGH_MULTIPLIER = "today_high_multiplier"
DEFAULT_TODAY_HIGH_MULTIPLIER = 1.8
CONF_TODAY_HIGH_MIN_L = "today_high_min_l"
DEFAULT_TODAY_HIGH_MIN_L = 200  # minimum liters before alarm triggers
CONF_TODAY_HIGH_BUFFER_L = "today_high_buffer_l"
DEFAULT_TODAY_HIGH_BUFFER_L = 100  # liters added to avg before comparison
CONF_TODAY_HIGH_AFTER_HOUR = "today_high_after_hour"
DEFAULT_TODAY_HIGH_AFTER_HOUR = 8  # only evaluate after this hour (local time)

# Exclusion entities — while any of these is "active" (switch on / flow > 0),
# the main-meter consumption during that window is measured and subtracted from
# today's total before the today-high threshold is evaluated. This prevents
# known large draws (lawn irrigation, pool refill) from triggering false alarms.
# Counter resets at the day boundary.
#
# Empty by default: these are entirely installation-specific. Pick your own in
# the options flow — typically an irrigation valve switch and/or a pool refill
# flow sensor.
CONF_EXCLUDE_ENTITIES = "exclude_entities"
DEFAULT_EXCLUDE_ENTITIES: list[str] = []

# Exclusion grace window (minutes). The water meter reports consumption with a
# lag and in lumps: a pool/lawn draw often lands in the meter total several
# minutes AFTER the valve already closed. Keep the exclusion window "open" for
# this many minutes after the last active moment so those delayed lumps are
# still subtracted (and today-high stays suppressed until they settle).
#
# This is a floor, not a deadline: the window also stays open until one
# telegram has been booked since the draw ended, so a meter that reports less
# often than the grace period (hourly, say) still gets the tail of the draw
# subtracted. Raising this only matters for meters that report FASTER than the
# grace and need several telegrams to book the whole lump.
CONF_EXCLUDE_GRACE_MIN = "exclude_grace_min"
DEFAULT_EXCLUDE_GRACE_MIN = 20

# Snooze
CONF_SNOOZE_DEFAULT_HOURS = "snooze_default_hours"
DEFAULT_SNOOZE_DEFAULT_HOURS = 4

# Herold (optional dependency)
HEROLD_DOMAIN = "herold"
HEROLD_TOPICS = {
    "wasser/leck_alarm": {
        "name": "Wasserleck Alarm",
        "beschreibung": "Wassersensor oder Water Saver Dauerfluss erkannt",
        "default_severity": "kritisch",
        "default_rollen": ["erwachsener"],
        "interruption_level": "critical",
    },
}
