# CLAUDE.md

Home Assistant custom integration: **Ghost Mode** — presence simulation that
learns the home's real occupied rhythm from recorder history and replays it
with natural variation while away. Alpha. HACS-installable. Domain `ghost_mode`.

Repo: `github.com/MarcelHoell/ha-ghost-mode` (`origin`, branch `main`). Author's
other HA project is `home-assistant-navimow` (a fork); same conventions apply.

## Layout

Everything lives in `custom_components/ghost_mode/`:

| File | Role |
| --- | --- |
| `const.py` | `DOMAIN` only |
| `manifest.json` | domain, version, `iot_class: calculated`, no requirements |
| `__init__.py` | entry setup/unload, forwards to the `switch` platform |
| `config_flow.py` | single-instance UI flow (unique_id = DOMAIN) |
| `switch.py` | `switch.ghost_mode` master on/off, `RestoreEntity` |

## Roadmap (not built yet)

The engine is deliberately absent in 0.1.0. Next steps, in order:
1. Options flow to pick learned entities (lights, covers, media_player) + the
   "away" trigger (default: an alarm `armed_away`).
2. A learner that reads recorder history into a per-weekday on/off profile.
3. A replay coordinator that reproduces the profile with time jitter while the
   switch is on and the home is away, and yields immediately on real presence.

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
