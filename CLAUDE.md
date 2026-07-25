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
| `const.py` | `DOMAIN` only |
| `manifest.json` | domain, version, `iot_class: calculated`, `dependencies: [recorder]`, no requirements |
| `__init__.py` | entry setup/unload, `ghost_mode.learn_now` service, forwards to `switch` |
| `config_flow.py` | single-instance UI flow (unique_id = DOMAIN) |
| `switch.py` | `switch.ghost_mode` master on/off, `RestoreEntity` |
| `discovery.py` | entity-registry scan for switchable, user-facing entities |
| `rhythm.py` | the maths — history → per-weekday half-hour grid, EMA blend. **No HA imports**, keep it that way so `tests/test_rhythm.py` runs bare |
| `learner.py` | recorder glue: nightly fold of unseen days into a `Store`d profile |

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

`ALPHA` and `SLOT_MINUTES` are the tuning knobs; real homes are noisier than
the model.

## Roadmap (not built yet)

1. An "away" trigger (default: an alarm `armed_away`) — currently nothing
   consumes the profile.
2. A replay coordinator that reproduces the profile with time jitter while the
   switch is on and the home is away, and yields immediately on real presence.
   It must not learn from its own output — tag or track the entities it drives.

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
