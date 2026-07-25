"""Constants for the Ghost Mode integration."""

DOMAIN = "ghost_mode"

# Options: entity ids the user never wants learned or replayed.
CONF_EXCLUDE = "exclude"

# Transient options-flow field: a pasted blob merged into CONF_EXCLUDE and then
# dropped. Never stored.
CONF_PASTE = "paste"

# Options: the alarm that says the house is empty, and which domains replay is
# allowed to actually switch. Covers and media players stay opt-in — they have
# mechanical and power consequences a light does not.
CONF_ALARM = "alarm"
CONF_DRIVE = "drive_domains"
DEFAULT_DRIVE = ("light", "switch")

# Fired once the learner has folded new days in, so the sensor can redraw.
SIGNAL_PROFILE_UPDATED = f"{DOMAIN}_profile_updated"

# Fired when the master switch flips, so replay reacts at once rather than
# waiting for its next tick.
SIGNAL_ENABLED = f"{DOMAIN}_enabled"
