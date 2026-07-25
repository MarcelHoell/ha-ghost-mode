<div align="center">

# 👻 Ghost Mode for Home Assistant

Make an empty house look lived-in — by replaying how *your* home actually
behaves, not dumb on/off timers.

[![release](https://img.shields.io/github/v/release/MarcelHoell/ha-ghost-mode)](https://github.com/MarcelHoell/ha-ghost-mode/releases)
[![Validate](https://github.com/MarcelHoell/ha-ghost-mode/actions/workflows/validate.yml/badge.svg)](https://github.com/MarcelHoell/ha-ghost-mode/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![hacs](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

</div>

> [!WARNING]
> **Alpha.** Ghost Mode learns your home's rhythm today, but does not replay it
> yet — nothing is switched on your behalf. Installing it is safe and
> read-only.

---

## The idea

Classic presence simulation flips a few lights on a fixed timer — obvious to
anyone watching for a few evenings. Ghost Mode instead **learns the real
rhythm of your home** from history (which lights, when the covers move, when
the TV runs) and **replays it with natural variation** while you are away, so
the pattern looks genuinely occupied.

## Planned behaviour

1. **Learn** — read the daily on/off rhythm of your lights, switches, covers
   and media players out of the recorder history. *(built)*
2. **Arm** — when `switch.ghost_mode` is on and the home is away (e.g. the
   alarm is `armed_away`), start replaying.
3. **Replay** — reproduce a realistic evening with jitter on times, not a
   fixed schedule.
4. **Yield** — hand control straight back the moment someone actually comes
   home.

## Current state (0.2.0)

- Installable via the UI (config flow), single instance.
- Creates `switch.ghost_mode` (restores across restarts) so automations and
  the alarm can already flip it.
- **Learns.** Every night it reads the days it has not seen out of the recorder
  and folds them into a per-weekday, half-hourly profile of what was on. It
  finds the entities itself from the entity registry — no picker to fill in,
  and config/diagnostic entities are skipped.
- Nothing listens to state changes: the recorder is already the recorder.
- Service `ghost_mode.learn_now` folds history in immediately instead of
  waiting for the nightly run.
- **No replay yet** — the profile is collected but nothing acts on it.

Because the recorder purges old rows (`purge_keep_days`, 10 by default), the
profile is *accumulated* with a moving average rather than re-derived. Give it
a few weeks before it knows your evenings.

## Installation

Until it is in HACS, add it as a custom repository:

1. HACS → ⋮ → **Custom repositories**
2. `https://github.com/MarcelHoell/ha-ghost-mode`, category **Integration**
3. Install, restart Home Assistant.
4. **Settings → Devices & Services → + Add Integration → Ghost Mode**.

## Configuration

**There is nothing to configure.** The setup dialog has no fields — confirm it
and Ghost Mode starts learning on the next nightly run. Only one instance can
be added.

That is deliberate: an entity picker is a form you fill in once, get wrong, and
never revisit. Ghost Mode reads the entity registry instead, so the thing you
already curate in Home Assistant is the thing that steers it.

### What gets learned

Entities in these domains: `light`, `switch`, `fan`, `media_player`, `cover`,
`input_boolean` — anything whose on/off state is visible from the street.

Skipped automatically:

- **Disabled** and **hidden** entities.
- Anything with an **entity category** of config or diagnostic — the "LED
  indicator", "child lock" and "restart" switches that ship with most Zigbee
  and Tasmota devices. These are what make a naive "all switches" list useless.

So to exclude something, hide or disable it in **Settings → Devices & Services
→ Entities**. To include a new device, do nothing — it is picked up on the next
run. Entities that leave the registry are dropped from the profile.

### Recorder

The learner reads recorder history and nothing else, so recorder settings
decide what it can see. Two matter:

- **`purge_keep_days`** (default 10) — the learner never looks further back
  than this. It does not need to: each night's reading is folded into a
  running average, so the profile outlives the rows it came from.
- **`exclude:`** filters — an excluded entity leaves no rows, and Ghost Mode
  learns nothing about it. It is *not* treated as "always off".

If you have trimmed recorder down, make sure the entities you want simulated
are still recorded:

```yaml
recorder:
  include:
    domains:
      - light
      - switch
      - cover
      - media_player
```

### Services

| Service | What it does |
| --- | --- |
| `ghost_mode.learn_now` | Folds available history in immediately, instead of waiting for the nightly run at 03:17. Useful right after install, or for checking it works. |

### Not exposed

These are constants in the source, not settings. Change them there if you must:

| Knob | File | Default |
| --- | --- | --- |
| `ALPHA` — how fast new days overwrite old habits | `rhythm.py` | `0.2` (~3 week half-life) |
| `SLOT_MINUTES` — profile resolution | `rhythm.py` | `30` |
| `GHOSTABLE_DOMAINS` | `discovery.py` | the six domains above |
| `LEARN_HOUR`, `LEARN_MINUTE` | `learner.py` | `03:17` |

`switch.ghost_mode` can be toggled today and survives restarts, but nothing
acts on it yet — replay is not built. Learning happens regardless of whether
the switch is on.

## Development

```text
custom_components/ghost_mode/
├── __init__.py      entry setup / unload, the learn_now service
├── config_flow.py   single-instance UI setup
├── switch.py        the master on/off switch
├── discovery.py     finds switchable entities in the entity registry
├── rhythm.py        history → per-weekday profile (no HA imports)
├── learner.py       nightly fold of recorder history into that profile
├── const.py         DOMAIN
├── services.yaml
└── manifest.json
tests/
└── test_rhythm.py   plain `python3 tests/test_rhythm.py`, no pytest
```

No dependencies, no build step. CI runs `hassfest` + HACS validation.
`rhythm.py` deliberately imports nothing from Home Assistant, so its self-check
runs on a bare interpreter.
Releases are automated by [release-please](https://github.com/googleapis/release-please)
from Conventional Commits — merge the release PR and the version in
`manifest.json` is bumped and tagged automatically.

## Disclaimer

Presence simulation is a deterrent, not a security guarantee. Use alongside
real measures.

## License

MIT — see [LICENSE](LICENSE).
