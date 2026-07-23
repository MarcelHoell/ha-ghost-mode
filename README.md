<div align="center">

# 👻 Ghost Mode for Home Assistant

Make an empty house look lived-in — by replaying how *your* home actually
behaves, not dumb on/off timers.

[![Validate](https://github.com/MarcelHoell/ha-ghost-mode/actions/workflows/validate.yml/badge.svg)](https://github.com/MarcelHoell/ha-ghost-mode/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![hacs](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

</div>

> [!WARNING]
> **Alpha / scaffold.** Right now this installs a single `switch.ghost_mode`
> that holds state. The learning and replay engine is not built yet.

---

## The idea

Classic presence simulation flips a few lights on a fixed timer — obvious to
anyone watching for a few evenings. Ghost Mode instead **learns the real
rhythm of your home** from history (which lights, when the covers move, when
the TV runs) and **replays it with natural variation** while you are away, so
the pattern looks genuinely occupied.

## Planned behaviour

1. **Learn** — record the daily on/off rhythm of selected lights, covers and
   media players from the recorder history.
2. **Arm** — when `switch.ghost_mode` is on and the home is away (e.g. the
   alarm is `armed_away`), start replaying.
3. **Replay** — reproduce a realistic evening with jitter on times, not a
   fixed schedule.
4. **Yield** — hand control straight back the moment someone actually comes
   home.

## Current state (0.1.0)

- Installable via the UI (config flow), single instance.
- Creates `switch.ghost_mode` (restores across restarts) so automations and
  the alarm can already flip it.
- No learning or replay yet — this release is the skeleton.

## Installation

Until it is in HACS, add it as a custom repository:

1. HACS → ⋮ → **Custom repositories**
2. `https://github.com/MarcelHoell/ha-ghost-mode`, category **Integration**
3. Install, restart Home Assistant.
4. **Settings → Devices & Services → + Add Integration → Ghost Mode**.

## Development

```
custom_components/ghost_mode/
├── __init__.py      entry setup / unload
├── config_flow.py   single-instance UI setup
├── switch.py        the master on/off switch
├── const.py         DOMAIN
└── manifest.json
```

No dependencies, no build step. CI runs `hassfest` + HACS validation.

## Disclaimer

Presence simulation is a deterrent, not a security guarantee. Use alongside
real measures.

## License

MIT — see [LICENSE](LICENSE).
