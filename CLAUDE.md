# CLAUDE.md

Home Assistant custom integration: **Ghost Mode** — presence simulation that
learns the home's real occupied rhythm from recorder history and replays it
with natural variation while away. Alpha. HACS-installable. Domain `ghost_mode`.

Repo: `github.com/MarcelHoell/ha-ghost-mode` (`origin`, branch `main`). Author's
other HA project is `home-assistant-navimow` (a fork); same conventions apply.

## Layout

The integration lives in `custom_components/ghost_mode/`. Tests come in two
layers:

- `tests/test_rhythm.py` — the maths, **no pytest and no Home Assistant**.
  Run it with `python3 tests/test_rhythm.py`. Keep it that way.
- `tests/test_integration.py` — everything that needs a real `hass`, via
  `pytest-homeassistant-custom-component`. **Requires Python 3.13**; HA 2025.8
  dropped 3.12, so this layer cannot run on a 3.12 interpreter at all. CI
  (`.github/workflows/validate.yml`) is where it actually gets verified.

Fixture ordering in `tests/conftest.py` is load-bearing: `recorder_db_url`
asserts no `hass` exists yet, so an autouse fixture requests it first.

| File | Role |
| --- | --- |
| `const.py` | `DOMAIN`, option keys, dispatcher signal names |
| `manifest.json` | domain, version, `iot_class: calculated`, `dependencies: [recorder]`, no requirements |
| `__init__.py` | entry setup/unload, `learn_now` + `forget` services, `async_remove_entry` deletes the store, forwards to platforms |
| `config_flow.py` | single-instance UI flow (unique_id = DOMAIN) + `OptionsFlowWithReload` for alarm, drive-domains and exclusions |
| `switch.py` | `switch.ghost_mode` (allow) and `switch.ghost_mode_force` (override the alarm), both `RestoreEntity`. Publish `SIGNAL_ENABLED` so replay reacts at once |
| `binary_sensor.py` | `binary_sensor.ghost_mode_replaying` — the honest answer to "is it performing", plus `waiting_for` and `restores_on_return` |
| `sensor.py` | `sensor.ghost_mode_learned_rhythm` — sparklines in an attribute so a plain markdown card can draw them. `_unrecorded_attributes` keeps it out of the recorder |
| `discovery.py` | entity-registry scan for switchable, user-facing entities |
| `rhythm.py` | the pure logic — sampling, EMA blend, sparklines, group collapsing, and the replay decision (`desired_on`, `stable_random`). **No HA imports**, keep it that way so `tests/test_rhythm.py` runs bare. Logic lands here purely to stay testable |
| `learner.py` | recorder glue: nightly fold of unseen days into a `Store`d profile; records replayed days so they are never folded |
| `replay.py` | drives the house while empty, reverts its own work on return |
| `diagnostics.py` | downloadable dump; sparklines only, never the raw floats |

Not named `profile.py` — that shadows a stdlib module.

## How learning works

No state listeners: recorder already records everything. Nightly (03:17) the
learner queries `get_significant_states` for the days it has not seen, samples
each entity into 48 half-hour slots per day, and blends that into the running
profile with an EMA (`ALPHA`, `rhythm.py`). Recorder purges after
`purge_keep_days` (10 by default), so the profile is *accumulated*, never
re-derived — that is why the EMA exists rather than a raw history window.

Profile shape: `{entity_id: [week], ...}` where `week` is 7 entries (Mon=0) of
either `None` (never observed) or 48 floats in 0.0–1.0. Persisted via `Store`
under `ghost_mode.profile`.

Each float is **the fraction of that half hour the entity was on**, integrated
from the state changes — not a sample of the instant at the slot boundary.
Motion-triggered lights are the reason: a two-minute hall light would be
invisible at 29 boundaries out of 30 and a solid half hour at the thirtieth.

The oldest day the query can reach is deliberately **not folded** — it sits on
the recorder purge horizon, where the row that last turned something off may be
gone, making the day read as on-from-midnight for every entity at once. It is
queried only to carry state into the first day that *is* folded.

`ALPHA` and `SLOT_MINUTES` are the tuning knobs; real homes are noisier than
the model.

Discovery excludes, in order: disabled/hidden entities, anything with an
`entity_category`, Ghost Mode's own entities (never learn from your own
replay), members of a group that is itself learned, and the user's
`CONF_EXCLUDE` list. That last one exists because `entity_category` is only as
good as the integration setting it — a Dreame vacuum's always-on "UV
sterilisation" switch is the motivating real-world case.

Options changes reload the entry via `OptionsFlowWithReload`. Do **not** add a
config-entry update listener; HA forbids combining the two.

**Minimum HA is 2025.8.0**, set in `hacs.json`. `OptionsFlowWithReload` landed
in exactly that release (verified against the tagged sources, not guessed);
`_unrecorded_attributes` is older. Bump the floor whenever a newer API is used
— a custom integration has no other way to refuse an old core, and the failure
is an ImportError at load rather than a message.

Any change to what a stored float *means* invalidates every profile in the
wild. The EMA would blend the old and new meanings for weeks, so ship such a
change together with a note to call `ghost_mode.forget`.

## How replay works

Active when `hass.data[DOMAIN]["enabled"]` (written by the master switch)
**and** the configured alarm is in `AWAY_STATES`. No alarm configured → the
switch alone decides; that is a deliberate fallback, not an oversight.

`hass.data[DOMAIN]["forced"]` short-circuits all of it, master switch included.
The force switch is the manual override, so it wins on purpose — the alarm is
the right signal almost always and exactly wrong when you want to *see* what
replay does.

`blocked_by()` is the single source of truth: `is_away()` is just
`blocked_by() is None`, and the binary sensor surfaces the string verbatim.

Woken by three things: a five-minute `TICK`, the `SIGNAL_ENABLED` dispatcher
from the switch, and a state listener on the alarm. The last two exist because
coming home has to stop replay *now*, not within five minutes.

`desired_on()` in `rhythm.py` turns a stored float into a decision. It is a
**probability, not a threshold** — 0.6 means on in roughly 60% of that slot's
occurrences, which is what stops the same week repeating forever. Both the
per-day time drift and the per-slot draw come from `stable_random()`, a hash of
entity/date/slot, so the answer is identical on every tick within a slot. Using
`random` here would make a 60% light flicker every five minutes.

Three rules that are easy to break by accident:

- **One command per entity per `SLOT_MINUTES`.** This is what keeps replay from
  fighting a motion automation that switches its light straight back off.
- **`cover` has no `turn_on`/`turn_off` service** — it registers
  `open_cover`/`close_cover` only, so `homeassistant.turn_on` skips covers in
  silence. Hence `_SERVICES` in `replay.py`.
- **A failing service call must not end the pass.** One unavailable bulb used
  to abort the whole evaluation part-way through. Entities are only recorded as
  driven once the call actually went out, or stand-down would "restore"
  something never changed.
- **State listeners must not be plain lambdas.** An undecorated callable is run
  in an executor thread, and scheduling loop work from there now raises. Pass
  the coroutine (or a `@callback`) directly.

Stand-down reverts only entities still in the state replay left them in;
anything changed since belongs to somebody else. `async_unload_entry` stands
down too, so a reload never abandons a lit house.

`learner.note_replayed()` records each day replay ran, and the fold loop skips
those days — otherwise the profile becomes a recording of its own output.

## Roadmap

Replay is built. What is still open:

- **Sub-slot pulses.** A two-minute motion event replays as a full 30-minute
  block, because the slot is the smallest unit replay can express. This is the
  case most likely to argue with a motion automation.
- **Duplicate entities for one device** (a TV as `media_player` + `switch` +
  `light`) still fire several commands at one piece of hardware. Group
  collapsing only catches real HA groups; the rest is the exclude option.
- **A cold profile is confidently wrong** about any day the household happened
  to be away, and replay has no notion of confidence — one observation is
  treated exactly like twenty.

## Conventions

- Commit messages: Conventional Commits, English only. **No AI/assistant
  attribution anywhere** — no `Co-Authored-By` trailer, no "generated with"
  line, no such mention in the subject or body.
- Versioning is automated: **release-please** reads the Conventional Commits,
  opens a release PR that bumps `manifest.json` (`$.version`) and updates the
  changelog, and tags `vX.Y.Z` when that PR is merged. Never bump the version by
  hand. `feat:` → minor, `fix:` → patch, `feat!:`/`BREAKING CHANGE` → major.
- No new runtime dependency unless unavoidable — keep `requirements` empty.
- Entities use `_attr_has_entity_name` + translation keys; user strings live in
  `strings.json` / `translations/`.
