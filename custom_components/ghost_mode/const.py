"""Constants for the Ghost Mode integration."""

DOMAIN = "ghost_mode"

# Options: entity ids the user never wants learned or replayed.
CONF_EXCLUDE = "exclude"

# Fired once the learner has folded new days in, so the sensor can redraw.
SIGNAL_PROFILE_UPDATED = f"{DOMAIN}_profile_updated"
