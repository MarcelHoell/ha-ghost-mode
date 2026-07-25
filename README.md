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
> **Alpha.** Ghost Mode learns *and* replays — it will switch real lights in
> your house. It only does that while `switch.ghost_mode` is on and your alarm
> says away. Leave the switch off and it stays read-only.

---

## The idea

Classic presence simulation flips a few lights on a fixed timer — obvious to
anyone watching for a few evenings. Ghost Mode learns the **real rhythm of your
home** from history: which lights, when the covers move, when the TV runs. Then
it replays that with natural variation while you are away.

1. **Learn** — from recorder history. Nothing to configure, nothing to record.
2. **Arm** — when the switch is on *and* the alarm says away.
3. **Replay** — a realistic evening, at slightly different times each day.
4. **Yield** — stop the moment someone comes home, and tidy up after itself.

## Requirements

- Home Assistant **2025.8** or newer
- The **recorder** (on by default). Ghost Mode reads it and nothing else.

## Installation

Until it is in HACS, add it as a custom repository:

1. HACS → ⋮ → **Custom repositories**
2. `https://github.com/MarcelHoell/ha-ghost-mode`, category **Integration**
3. Install, restart Home Assistant.
4. **Settings → Devices & Services → + Add Integration → Ghost Mode**.

There is nothing to fill in. It finds your lights, switches, covers and media
players by itself and starts learning tonight.

## Configuration

**Settings → Devices & Services → Ghost Mode → Configure.**

| Option | What it does |
| --- | --- |
| **Alarm that means the house is empty** | Replay runs only while this is `armed_away` or `armed_vacation`, and stops the moment it is disarmed. Leave empty to let the switch decide on its own. |
| **Replay may switch these** | Which kinds of thing replay may command. Defaults to lights and switches. Tick **covers** or **media players** deliberately — a cover physically moves and a television really powers up. |
| **Never learn or replay these** | Entities to ignore completely. |
| **Paste entity IDs to exclude** | Bulk version of the above — paste a list instead of clicking each one. |

### What gets found automatically

Lights, switches, fans, covers, media players and input booleans — anything
whose on/off state is visible from the street.

Skipped without asking: disabled and hidden entities, anything Home Assistant
marks as a config or diagnostic entity (all those "LED indicator" and "child
lock" switches), members of a group when the group itself is learned, and Ghost
Mode's own entities.

### The exclusion list matters

Most homes have several entities for one physical thing — a television is
easily eight, a room of Hue bulbs five. Learning the same lamp five times
doesn't improve anything, and replaying it means five commands to one bulb.

Use the **paste box** and drop in a list, one per line or comma separated:

```text
light.office_left, light.office_right
media_player.tv_screen
switch.vacuum_uv_lamp
```

Anything shaped like an entity ID is picked up, so pasting a bulleted or quoted
list works too. It merges into the list above and is not kept, so reopening the
form shows one list rather than two.

Permanently-on device settings — a robot vacuum's UV lamp, say — are the other
thing worth excluding. Home Assistant doesn't always mark them as settings, so
Ghost Mode can't tell them from a real lamp.

## Replay

Replay runs only while **both** are true: the switch is on, and the alarm says
away. Learning happens either way, regardless of the switch.

It is **not a schedule.** A light that was on for 60% of your observed Tuesday
evenings comes on about 60% of Tuesdays — not every Tuesday at the same minute.
Times drift by up to 20 minutes, so the house doesn't light up all at once.

**Coming home:** the moment the alarm disarms or the switch goes off, replay
stops and undoes **its own changes only**. Anything you or another automation
changed meanwhile is left alone.

It won't fight your automations — one command per entity per half hour, so if a
motion automation switches a replayed light back off, it stays off. And it
never learns from itself: days it ran are skipped by the learner.

## Seeing what it learned

### On a dashboard

Add a **Markdown card** — no custom card, nothing to install:

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
  _Nothing to draw yet._ Call `ghost_mode.learn_now`, then check
  **Settings → System → Logs**.
  {% endif %}
````

Which draws:

```text
**light.wohnzimmer**
     0h    3h    6h    9h    12h   15h   18h   21h
Mon  ········································▃█████▁·
Tue  ············································▁█▃·
Wed  (never seen)
```

### How to read it

One row per weekday, one character per half hour, midnight on the left. The
character says **how much of that half hour the thing was on**:

| | |
| --- | --- |
| `·` | never on |
| `▁` | briefly — a couple of minutes |
| `▃` `▅` | a third, to three-quarters |
| `█` | the whole half hour |
| `(never seen)` | that weekday hasn't been observed yet |

So the Monday row above reads: living room light on around 20:00, solid until
23:00, off by 23:30.

Each row is an **average over every time that weekday has been seen**, not one
particular day. Entities that never vary — off all week, or a setting that's on
all week — are left out of the card entirely.

### As a file

**Settings → Devices & Services → Ghost Mode → ⋮ → Download diagnostics** gives
you the same picture as a file, plus a list of entities Ghost Mode can see but
has no history for. That's the one to attach to a bug report.

## Services

| Service | What it does |
| --- | --- |
| `ghost_mode.learn_now` | Read history in now, instead of waiting for the nightly run at 03:17. |
| `ghost_mode.forget` | Throw the profile away and rebuild it from scratch. Use after an update changes how the profile is measured. |

Removing the integration deletes the stored profile too, so removing and
re-adding really does start over.

## If something looks wrong

**Nothing appears on the card.** The profile only fills in after the learner has
run once. Call `ghost_mode.learn_now`, then check **Settings → System → Logs**
and filter for `ghost_mode` — it says plainly whether it learned, found no
history, or failed.

**"Nothing to learn" in the log.** Expected. Only *complete* days are learned,
so a second run on the same day has nothing to do.

**A row is blank on one weekday.** That weekday hasn't been observed yet, or you
were out. A fresh profile can be confidently wrong about a day you happened to
be away — it corrects itself over a few weeks.

**Give it time.** Recorder only keeps about ten days, so the profile is built up
gradually rather than read in one go. Expect a couple of weeks before it really
knows your evenings.

## Development

```bash
python tests/test_rhythm.py    # the maths, no Home Assistant needed
pip install pytest-homeassistant-custom-component && pytest -q
```

No dependencies, no build step. See [CLAUDE.md](CLAUDE.md) for how the
internals fit together.

## Disclaimer

Presence simulation is a deterrent, not a security guarantee. Use alongside
real measures.

## License

MIT — see [LICENSE](LICENSE).
