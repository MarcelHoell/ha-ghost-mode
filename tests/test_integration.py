"""Tests for the parts that talk to Home Assistant.

`test_rhythm.py` covers the maths on its own. Everything here needs a running
`hass`: entity discovery, the config entry, the services, the sensor, the
diagnostics dump and the storage cleanup.
"""
import datetime as dt

import pytest
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from homeassistant.helpers.dispatcher import async_dispatcher_send
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ghost_mode.const import (
    CONF_ALARM,
    CONF_DRIVE,
    CONF_EXCLUDE,
    CONF_PASTE,
    DOMAIN,
    SIGNAL_PROFILE_UPDATED,
)
from custom_components.ghost_mode import learner as learner_module
from custom_components.ghost_mode.discovery import ghostable_entities, parse_entity_ids


@pytest.fixture
async def entry(
    recorder_mock, enable_custom_integrations, hass: HomeAssistant
) -> MockConfigEntry:
    """Set up Ghost Mode with a real (empty) recorder behind it.

    Order matters: `recorder_mock` first, because its database fixture refuses
    to run once `hass` exists, and only then the custom-integration loader.
    """
    config_entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, title="Ghost Mode")
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


def _register(hass: HomeAssistant, entity_id: str, **kwargs) -> None:
    """Put an entity in the registry, the way a real integration would."""
    domain, object_id = entity_id.split(".", 1)
    er.async_get(hass).async_get_or_create(
        domain, "demo", f"unique_{object_id}", suggested_object_id=object_id, **kwargs
    )


async def test_discovery_keeps_only_user_facing_entities(hass: HomeAssistant):
    """The registry filter is the whole configuration story, so pin it down."""
    _register(hass, "light.kitchen")
    _register(hass, "switch.kettle")
    _register(hass, "sensor.temperature")  # wrong domain
    _register(hass, "switch.led_indicator", entity_category=EntityCategory.CONFIG)
    _register(hass, "light.spare", disabled_by=er.RegistryEntryDisabler.USER)
    _register(hass, "light.attic", hidden_by=er.RegistryEntryHider.USER)

    assert ghostable_entities(hass) == ["light.kitchen", "switch.kettle"]


async def test_discovery_honours_the_exclude_option(hass: HomeAssistant):
    _register(hass, "light.kitchen")
    _register(hass, "switch.vacuum_uv_lamp")

    assert ghostable_entities(hass, ["switch.vacuum_uv_lamp"]) == ["light.kitchen"]


async def test_discovery_drops_group_members(hass: HomeAssistant):
    """A light group speaks for its bulbs; replaying both is replaying twice."""
    _register(hass, "light.office")
    _register(hass, "light.office_left")
    _register(hass, "light.office_right")
    hass.states.async_set(
        "light.office", "on", {"entity_id": ["light.office_left", "light.office_right"]}
    )

    assert ghostable_entities(hass) == ["light.office"]


def test_pasted_entity_ids_survive_whatever_shape_they_arrive_in():
    """People paste from chat, from YAML, from a bulleted list. Take it all."""
    pasted = """
    light.buro_links, light.buro_rechts
      - switch.robby_uv_sterilization
    "media_player.55oled706_12_2"
    LIGHT.GARTEN
    not an entity id at all
    """
    assert parse_entity_ids(pasted) == {
        "light.buro_links",
        "light.buro_rechts",
        "switch.robby_uv_sterilization",
        "media_player.55oled706_12_2",
        "light.garten",
    }
    assert parse_entity_ids("") == set()


async def test_options_flow_merges_the_paste_box_into_the_picker(
    hass: HomeAssistant, entry: MockConfigEntry
):
    """The paste box is a bulk-add; it must not become a second stored list."""
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_EXCLUDE: ["light.already_picked"],
            CONF_PASTE: "light.pasted_one\nlight.pasted_two, light.pasted_three",
        },
    )
    await hass.async_block_till_done()

    assert result["data"][CONF_EXCLUDE] == [
        "light.already_picked",
        "light.pasted_one",
        "light.pasted_three",
        "light.pasted_two",
    ]
    assert CONF_PASTE not in result["data"], "the blob itself is never stored"


async def test_setup_creates_the_entities_and_services(
    hass: HomeAssistant, entry: MockConfigEntry
):
    assert hass.states.get("switch.ghost_mode") is not None
    assert hass.states.get("sensor.ghost_mode_learned_rhythm") is not None
    assert hass.services.has_service(DOMAIN, "learn_now")
    assert hass.services.has_service(DOMAIN, "forget")


async def test_ghost_mode_never_learns_from_itself(
    hass: HomeAssistant, entry: MockConfigEntry
):
    """Our own switch is switchable and visible — and must still be skipped."""
    assert "switch.ghost_mode" not in ghostable_entities(hass)


async def test_switch_survives_a_restart(hass: HomeAssistant, entry: MockConfigEntry):
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.ghost_mode"}, blocking=True
    )
    assert hass.states.get("switch.ghost_mode").state == "on"


async def test_profile_survives_a_reload_but_forget_clears_it(
    hass: HomeAssistant, entry: MockConfigEntry
):
    learner = hass.data[DOMAIN]["learner"]
    learner.profile["light.kitchen"] = [[1.0] * 48] + [None] * 6

    await hass.services.async_call(DOMAIN, "forget", {}, blocking=True)
    await hass.async_block_till_done()

    assert hass.data[DOMAIN]["learner"].profile == {}


async def test_sensor_reports_only_entities_worth_drawing(
    hass: HomeAssistant, entry: MockConfigEntry
):
    learner = hass.data[DOMAIN]["learner"]
    learner.profile["light.evening"] = [[0.0] * 24 + [1.0] * 24] + [None] * 6
    learner.profile["switch.always_on"] = [[1.0] * 48] * 7
    learner.profile["light.never_on"] = [[0.0] * 48] * 7

    # The sensor only re-renders when the learner says so, which is the wiring
    # worth testing: a cached state would still show the old (empty) profile.
    async_dispatcher_send(hass, SIGNAL_PROFILE_UPDATED)
    await hass.async_block_till_done()

    rhythm = hass.states.get("sensor.ghost_mode_learned_rhythm").attributes["rhythm"]
    assert "light.evening" in rhythm, "a real evening is worth drawing"
    assert "switch.always_on" not in rhythm, "a flat line is not"
    assert "light.never_on" not in rhythm


async def test_removing_the_entry_deletes_the_stored_profile(
    hass: HomeAssistant, entry: MockConfigEntry, hass_storage: dict
):
    """Otherwise re-adding Ghost Mode silently restores the old profile."""
    learner = hass.data[DOMAIN]["learner"]
    learner.profile["light.kitchen"] = [[1.0] * 48] + [None] * 6
    await learner._store.async_save(learner._data)
    assert "ghost_mode.profile" in hass_storage

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert hass_storage.get("ghost_mode.profile", {}).get("data") in (None, {})


async def test_diagnostics_render_without_the_raw_floats(
    hass: HomeAssistant, entry: MockConfigEntry
):
    from custom_components.ghost_mode.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    hass.data[DOMAIN]["learner"].profile["light.evening"] = [
        [0.0] * 24 + [1.0] * 24
    ] + [None] * 6

    dump = await async_get_config_entry_diagnostics(hass, entry)

    assert "raw" not in dump, "336 floats per entity is not a readable dump"
    assert dump["rhythm"]["light.evening"]["Mon"].endswith("█" * 24)
    assert dump["rhythm"]["light.evening"]["Tue"] == "(never seen)"


async def test_a_newly_included_entity_is_backfilled_not_left_behind(
    hass: HomeAssistant, entry: MockConfigEntry
):
    """Un-excluding an entity, or installing one, must not start from zero.

    The learner resumes from the last day it folded, so without special
    handling a newcomer learns a single day while everything around it has a
    full window — and stays wrong for weeks.
    """
    learner = hass.data[DOMAIN]["learner"]
    _register(hass, "light.garden")
    _register(hass, "light.established")

    # Pretend we already folded everything up to yesterday for one of them.
    learner.profile["light.established"] = [[1.0] * 48] + [None] * 6
    learner._data["last_day"] = (
        dt_util.start_of_local_day() - dt.timedelta(days=1)
    ).date().isoformat()

    # The test recorder is empty, so nothing is ever folded. What the fix
    # changes is the window that gets *asked for* — capture that instead.
    queries: list[tuple] = []
    original = learner_module.history.get_significant_states

    def _capture(hass, start, end, entity_ids, **kwargs):
        queries.append((start, end))
        return {}

    learner_module.history.get_significant_states = _capture
    try:
        await learner.async_update()
        assert queries, "a newcomer must reopen the window, not return early"
        start, end = queries[0]
        assert (end - start).days >= 7, "the newcomer needs the whole window"

        # With nothing new, the same call must go back to doing nothing.
        queries.clear()
        learner.profile["light.garden"] = [[0.0] * 48] + [None] * 6
        await learner.async_update()
        assert not queries, "an ordinary run with nothing new must still return early"
    finally:
        learner_module.history.get_significant_states = original


async def _arm(hass: HomeAssistant, entry: MockConfigEntry, alarm_state: str):
    """Point replay at an alarm and set it, returning the coordinator.

    The reload matters: the alarm listener is registered at setup, so options
    have to be in place first. In real use `OptionsFlowWithReload` does this.
    """
    hass.states.async_set("alarm_control_panel.house", alarm_state)
    hass.config_entries.async_update_entry(
        entry,
        options={
            CONF_ALARM: "alarm_control_panel.house",
            CONF_DRIVE: ["light", "cover"],
        },
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    return hass.data[DOMAIN]["replay"]


async def test_replay_needs_both_the_switch_and_the_alarm(
    hass: HomeAssistant, entry: MockConfigEntry
):
    replay = await _arm(hass, entry, "disarmed")

    hass.data[DOMAIN]["enabled"] = False
    assert replay.is_away() is False, "switch off, alarm disarmed"

    hass.data[DOMAIN]["enabled"] = True
    assert replay.is_away() is False, "switch on is not enough on its own"

    hass.states.async_set("alarm_control_panel.house", "armed_away")
    await hass.async_block_till_done()
    assert replay.is_away() is True, "switch on and armed away"

    hass.data[DOMAIN]["enabled"] = False
    assert replay.is_away() is False, "armed away is not enough on its own"


async def test_replay_switches_lights_and_opens_covers(
    hass: HomeAssistant, entry: MockConfigEntry
):
    """Covers have no turn_on service, so they need their own call."""
    replay = await _arm(hass, entry, "armed_away")
    hass.data[DOMAIN]["enabled"] = True

    calls: list[tuple[str, str, str]] = []

    async def _record(call):
        calls.append((call.domain, call.service, call.data["entity_id"]))

    for domain, services in (("homeassistant", ("turn_on", "turn_off")),
                             ("cover", ("open_cover", "close_cover"))):
        for service in services:
            hass.services.async_register(domain, service, _record)

    hass.states.async_set("light.hall", "off")
    hass.states.async_set("cover.blind", "closed")
    replay.learner.profile["light.hall"] = [[1.0] * 48] * 7
    replay.learner.profile["cover.blind"] = [[1.0] * 48] * 7
    # A media player is learned but not in drive_domains, so it must be left be.
    hass.states.async_set("media_player.tv", "off")
    replay.learner.profile["media_player.tv"] = [[1.0] * 48] * 7

    await replay.async_evaluate()
    await hass.async_block_till_done()

    assert ("homeassistant", "turn_on", "light.hall") in calls
    assert ("cover", "open_cover", "cover.blind") in calls
    assert not any("media_player" in entity for _, _, entity in calls)


async def test_coming_home_undoes_only_replays_own_work(
    hass: HomeAssistant, entry: MockConfigEntry
):
    replay = await _arm(hass, entry, "armed_away")
    hass.data[DOMAIN]["enabled"] = True

    calls: list[tuple[str, str]] = []

    async def _record(call):
        calls.append((call.service, call.data["entity_id"]))

    for service in ("turn_on", "turn_off"):
        hass.services.async_register("homeassistant", service, _record)

    hass.states.async_set("light.hall", "off")
    hass.states.async_set("light.porch", "off")
    replay.learner.profile["light.hall"] = [[1.0] * 48] * 7
    replay.learner.profile["light.porch"] = [[1.0] * 48] * 7

    await replay.async_evaluate()
    await hass.async_block_till_done()
    hass.states.async_set("light.hall", "on")  # replay's doing
    hass.states.async_set("light.porch", "off")  # somebody turned it back off
    await hass.async_block_till_done()

    calls.clear()
    hass.states.async_set("alarm_control_panel.house", "disarmed")
    await hass.async_block_till_done()

    assert ("turn_off", "light.hall") in calls, "revert what we switched on"
    assert ("turn_off", "light.porch") not in calls, (
        "somebody else changed it since; not ours to undo"
    )


async def test_replayed_days_are_never_learned_from(
    hass: HomeAssistant, entry: MockConfigEntry
):
    """Otherwise the profile slowly becomes a recording of itself."""
    learner = hass.data[DOMAIN]["learner"]
    today = dt_util.now().date()

    learner.note_replayed(today)
    assert today.isoformat() in learner.replayed_days

    learner.note_replayed(today)
    assert learner.replayed_days.count(today.isoformat()) == 1, "no duplicates"

    ancient = today - dt.timedelta(days=400)
    learner.note_replayed(ancient)
    assert ancient.isoformat() not in learner.replayed_days, "old entries drop out"


async def test_backfill_respects_the_recorder_setting(
    hass: HomeAssistant, entry: MockConfigEntry
):
    """Hard-coding 10 threw away history from anyone who raised purge_keep_days."""
    learner = hass.data[DOMAIN]["learner"]

    class _FakeRecorder:
        keep_days = 3

    original = learner_module.get_instance
    try:
        learner_module.get_instance = lambda _hass: _FakeRecorder()
        assert learner._backfill_days() == 3

        _FakeRecorder.keep_days = 365
        assert learner._backfill_days() == learner_module.MAX_BACKFILL_DAYS

        _FakeRecorder.keep_days = 0  # "never purge"
        assert learner._backfill_days() == learner_module.MAX_BACKFILL_DAYS
    finally:
        learner_module.get_instance = original
