# CLAUDE.md

Home Assistant custom integration: **Ghost Mode** — presence simulation that
learns the home's real occupied rhythm from recorder history and replays it
with natural variation while away. Alpha. HACS-installable. Domain `ghost_mode`.

Repo: `github.com/MarcelHoell/ha-ghost-mode` (`origin`, branch `main`). Author's
other HA project is `home-assistant-navimow` (a fork); same conventions apply.

## Layout

The integration lives in `custom_components/ghost_mode/`; `tests/` holds
dependency-free self-checks (plain `python3 tests/test_*.py`, no pytest, no HA).

| File | Role |
| --- | --- |
| `const.py` | `DOMAIN`, `CONF_EXCLUDE` |
| `manifest.json` | domain, version, `iot_class: calculated`, `dependencies: [recorder]`, no requirements |
| `__init__.py` | entry setup/unload, `learn_now` + `forget` services, `async_remove_entry` deletes the store, forwards to platforms |
| `config_flow.py` | single-instance UI flow (unique_id = DOMAIN) + `OptionsFlowWithReload` for the exclude list |
| `switch.py` | `switch.ghost_mode` master on/off, `RestoreEntity` |
| `sensor.py` | `sensor.ghost_mode_learned_rhythm` — sparklines in an attribute so a plain markdown card can draw them. `_unrecorded_attributes` keeps it out of the recorder |
| `discovery.py` | entity-registry scan for switchable, user-facing entities |
| `rhythm.py` | the pure logic — history → per-weekday half-hour grid, EMA blend, sparklines, group collapsing. **No HA imports**, keep it that way so `tests/test_rhythm.py` runs bare. Logic lands here purely to stay testable |
| `learner.py` | recorder glue: nightly fold of unseen days into a `Store`d profile |
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

## Roadmap (not built yet)

1. An "away" trigger (default: an alarm `armed_away`) — currently nothing
   consumes the profile.
2. A replay coordinator that reproduces the profile with time jitter while the
   switch is on and the home is away, and yields immediately on real presence.
   It must not learn from its own output — tag or track the entities it drives.

Constraints replay will hit, worth designing for up front:

- **Motion automations keep running while away.** Replaying a motion-driven
  light means fighting the automation that turns it off after N minutes — or
  being silently overridden. Short slot values (`< ~0.2`) mark exactly those
  entities; treat them as brief flicks, and expect the light to go off on its
  own without treating that as real presence.
- **Duplicate entities for one device** (a TV as `media_player` + `switch` +
  `light`) would fire several service calls at the same hardware. Group
  collapsing only catches real HA groups; the rest is the exclude option.

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
