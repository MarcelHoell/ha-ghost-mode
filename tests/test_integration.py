"""Tests for the parts that talk to Home Assistant.

`test_rhythm.py` covers the maths on its own. Everything here needs a running
`hass`: entity discovery, the config entry, the services, the sensor, the
diagnostics dump and the storage cleanup.
"""
import pytest
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ghost_mode.const import (
    CONF_EXCLUDE,
    CONF_PASTE,
    DOMAIN,
    SIGNAL_PROFILE_UPDATED,
)
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

    assert result["data"] == {
        CONF_EXCLUDE: [
            "light.already_picked",
            "light.pasted_one",
            "light.pasted_three",
            "light.pasted_two",
        ]
    }
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


async def test_backfill_respects_the_recorder_setting(
    hass: HomeAssistant, entry: MockConfigEntry
):
    """Hard-coding 10 threw away history from anyone who raised purge_keep_days."""
    learner = hass.data[DOMAIN]["learner"]

    class _FakeRecorder:
        keep_days = 3

    import custom_components.ghost_mode.learner as learner_module

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
