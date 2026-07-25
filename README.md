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

Each half-hour slot stores **how much of that half hour the entity was on**,
not whether it happened to be on at the boundary. That is what makes
motion-triggered lights work: a hall light on for two minutes stores as `0.067`
and stays a brief flick, instead of being missed entirely or inflated into a
solid half hour.

## Installation

Needs **Home Assistant 2025.8 or newer** (`OptionsFlowWithReload`).

Until it is in HACS, add it as a custom repository:

1. HACS → ⋮ → **Custom repositories**
2. `https://github.com/MarcelHoell/ha-ghost-mode`, category **Integration**
3. Install, restart Home Assistant.
4. **Settings → Devices & Services → + Add Integration → Ghost Mode**.

## Configuration

**There is almost nothing to configure.** The setup dialog has no fields —
confirm it and Ghost Mode starts learning on the next nightly run. Only one
instance can be added.

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
- **Group members**, when the group itself is learned. A light group and its
  three bulbs are one light to a passer-by, so only the group is kept.
- **Ghost Mode's own entities**, so it can never learn from its own replay.

So to exclude something, hide or disable it in **Settings → Devices & Services
→ Entities**. To include a new device, do nothing — it is picked up on the next
run. Entities that leave the registry are dropped from the profile.

### The one option

**Settings → Devices & Services → Ghost Mode → Configure** takes a list of
entities to ignore outright.

Two ways in. The picker is fine for one or two. For a real list — one
television is easily eight entities — use the **paste box** underneath and drop
in entity IDs, one per line or comma separated:

```text
light.buro_links, light.buro_rechts
media_player.55oled706_12
switch.robby_uv_sterilization
```

Anything shaped like an entity ID is picked up, so pasting a bulleted or
quoted list works too. The box is a bulk-add: its contents merge into the list
above and are not kept, so reopening the form shows one list rather than two.

It exists because the entity-category filter only works when an integration
bothers to set it. Some do not: a robot vacuum's "UV sterilisation" and
"auto drying" switches are permanently on, invisible from outside, and get
learned as constantly-lit — exactly the sort of thing to drop here. Changing
the list reloads the integration, and the excluded entities disappear from the
profile on the next run.

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
| `ghost_mode.forget` | Throws the profile away and rebuilds it from whatever recorder history still exists. Use it when an update changes how the profile is measured — the moving average would otherwise blend the old and new meanings together for weeks. |

Removing the integration deletes the stored profile too, so removing and
re-adding it really does start over.

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

## Seeing what it learned

### On a dashboard

`sensor.ghost_mode_learned_rhythm` carries the whole profile. Its state is how
many entities have a rhythm worth showing; the `rhythm` attribute holds the
drawing. Paste this into a **Markdown card** — no custom card, no
JavaScript, nothing to install:

````yaml
type: markdown
content: |
  {% set sensor = 'sensor.ghost_mode_learned_rhythm' %}
  {% set rhythm = state_attr(sensor, 'rhythm') %}
  {% if rhythm %}
  ### Learned rhythm
  Last full day learned: **{{ state_attr(sensor, 'last_learned_day') }}**
  {% for entity, week in rhythm.items() %}
  **{{ entity }}**
  ```text
       0h    3h    6h    9h    12h   15h   18h   21h
  {% for day, bars in week.items() %}{{ day }}  {{ bars }}
  {% endfor %}```
  {% endfor %}
  {% else %}
  ### Learned rhythm
  _Nothing to draw yet._ Check the sensor exists and that the learner has run —
  call `ghost_mode.learn_now`, then look at **Settings → System → Logs**.
  {% endif %}
````

The `{% if %}` matters: without it, a missing sensor makes the card throw
`UndefinedError: 'None' has no attribute 'items'` rather than saying so.

Which draws:

```text
**light.wohnzimmer**
     0h    3h    6h    9h    12h   15h   18h   21h
Mon  ·········································██████·
Tue  ··········································████··
Wed  (never seen)
Thu  ········································██████··
```

Entities that draw as a flat line — off all week, or a device setting that is
on all week — are left out of the attribute. They stay in the profile; they
just make no picture. That keeps the card readable and the attribute small.

### As a file, for bug reports

**Settings → Devices & Services → Ghost Mode → ⋮ → Download diagnostics.**

The dump renders each entity's week as one line per weekday, one character per
half hour, starting at local midnight. The character says how much of that half
hour the entity was on — `·` none, `▁` briefly, `▃`/`▅` partly, `█` all of it.

```text
light.living_room
  Mon ·············████·················████████████··
  Tue ··············▪▪▪▪▪·····························
  Sat (never seen)
```

That is a light used in the morning and again all evening, on a home that has
not been observed on a Saturday yet.

It also reports `discovered_but_unlearned` — entities Ghost Mode can see but
has no history for. A long list there usually means recorder is excluding them.

The dump deliberately omits the raw numbers: 336 floats per entity is the same
information at fifty times the size. Read `.storage/ghost_mode.profile` if you
need exact values.

### If it looks like nothing happened

The learner only folds in **complete** days, so calling `ghost_mode.learn_now`
twice on the same day does nothing the second time — it logs why. To see that,
turn on debug logging: **Settings → Devices & Services → Ghost Mode → Enable
debug logging**, or

```yaml
logger:
  logs:
    custom_components.ghost_mode: debug
```

To start over completely, call **`ghost_mode.forget`**. It deletes the profile
and immediately relearns from recorder history — no shell, no hunting for
hidden files.

The profile itself lives at `.storage/ghost_mode.profile` in your config
directory, but note that `.storage` is hidden from the File Editor and Samba
addons by default. Prefer the diagnostics download.

## Development

```text
custom_components/ghost_mode/
├── __init__.py      entry setup / unload, the learn_now service
├── config_flow.py   single-instance UI setup + the exclude option
├── switch.py        the master on/off switch
├── sensor.py        the learned rhythm, for a markdown card to draw
├── discovery.py     finds switchable entities in the entity registry
├── rhythm.py        the pure logic — sampling, blending, group collapsing
├── learner.py       nightly fold of recorder history into that profile
├── diagnostics.py   the downloadable "what did it learn" dump
├── const.py         DOMAIN, option keys
├── services.yaml
└── manifest.json
tests/
└── test_rhythm.py   plain `python3 tests/test_rhythm.py`, no pytest
```

No dependencies, no build step. CI runs the tests, `hassfest` and HACS
validation.

Two test layers:

```bash
python tests/test_rhythm.py                  # the maths, no Home Assistant
pip install pytest-homeassistant-custom-component && pytest -q   # the rest
```

`rhythm.py` deliberately imports nothing from Home Assistant, so its self-check
runs on a bare interpreter. `tests/test_integration.py` needs a real `hass`,
and therefore **Python 3.13** — Home Assistant 2025.8 does not support 3.12.
Releases are automated by [release-please](https://github.com/googleapis/release-please)
from Conventional Commits — merge the release PR and the version in
`manifest.json` is bumped and tagged automatically.

## Disclaimer

Presence simulation is a deterrent, not a security guarantee. Use alongside
real measures.

## License

MIT — see [LICENSE](LICENSE).
