"""Gesture and regression tests against the actual Home Assistant automation."""

import pytest


async def test_double_up_only_activates_scene(make_remote):
    remote = await make_remote()
    await remote.send("on")
    assert remote.calls == []
    await remote.send("on")
    assert remote.calls[0] == ("scene", "turn_on", {"entity_id": ["scene.reading"]})
    assert remote.state("light.desk") == "on"
    assert remote.state("light.ceiling") == "on"
    assert remote.state("switch.lamp") == "on"
    assert remote.attr("light.desk", "brightness") == 180
    count = len(remote.calls)
    await remote.wait()
    assert len(remote.calls) == count


@pytest.mark.parametrize("scenes", [False, True])
async def test_single_power_preserves_legacy_behavior(make_remote, scenes):
    remote = await make_remote(scenes=scenes, force_brightness=True, brightness_pct=40)
    await remote.send("on")
    if scenes:
        assert remote.calls == []
        await remote.wait()
    assert remote.state("light.desk") == "on"
    assert remote.state("light.ceiling") == "off"
    assert remote.calls[-1][2]["brightness_pct"] == 40
    await remote.send("off")
    if scenes:
        await remote.wait()
    assert remote.state("light.desk") == "off"
    count = len(remote.calls)
    await remote.send("off")
    if scenes:
        await remote.wait()
    assert len(remote.calls) == count


@pytest.mark.parametrize("arg", [0, 256])
@pytest.mark.parametrize("shape", ["list", "args_dict", "params"])
async def test_double_arrows_select_scenes_without_changing_lights(
    make_remote, arg, shape
):
    remote = await make_remote(scenes=["scene.reading", "scene.evening", "scene.third"])
    data = (
        {"args": [arg, 0, 0]}
        if shape == "list"
        else {
            "args" if shape == "args_dict" else "params": {"param1": arg, "param2": 0}
        }
    )
    for expected in ("1.0", "2.0", "0.0") if arg == 256 else ("2.0", "1.0", "0.0"):
        await remote.send("press", 5, **data)
        await remote.send("press", 5, **data)
        assert remote.state("input_number.scene") == expected
        assert remote.state("input_number.target") == "0.0"
    await remote.wait()
    assert remote.calls == []


async def test_activate_selected_scene_applies_saved_off_states(make_remote):
    remote = await make_remote()
    await remote.send("on")
    await remote.send("on")
    await remote.send("press", 5, [256, 0, 0])
    await remote.send("press", 5, [256, 0, 0])
    await remote.send("on")
    await remote.send("on")
    assert remote.state("light.desk") == "off"
    assert remote.state("switch.lamp") == "off"
    assert remote.attr("light.ceiling", "brightness") == 60


@pytest.mark.parametrize("scene_index", [0, 1])
async def test_double_down_turns_off_all_configured_lights_and_switches(
    make_remote, scene_index
):
    remote = await make_remote()
    remote.hass.states.async_set(
        "light.desk", "on", dict(remote.hass.states.get("light.desk").attributes)
    )
    remote.hass.states.async_set("switch.lamp", "on")
    remote.hass.states.async_set("light.scene_only", "on")
    remote.hass.states.async_set("light.other_scene_only", "on")
    # Only the target list supplies this switch, and only the other scene
    # supplies other_scene_only. Shared scene members must be sent once.
    remote.hass.states.async_set(
        "scene.evening",
        "unknown",
        {
            "entity_id": ["light.other_scene_only", "light.desk"],
        },
    )
    await remote.hass.services.async_call(
        "input_number",
        "set_value",
        {
            "entity_id": "input_number.scene",
            "value": scene_index,
        },
        blocking=True,
    )
    remote.hass.states.async_set("light.unreachable", "unavailable")
    remote.hass.states.async_set("media_player.tv", "on")
    remote.hass.states.async_set("light.unrelated", "on")
    remote.hass.states.async_set(
        "scene.reading",
        "unknown",
        {
            "entity_id": [
                "light.desk",
                "light.ceiling",
                "light.scene_only",
                "light.unreachable",
                "media_player.tv",
            ]
        },
    )
    await remote.send("off")
    assert remote.calls == []
    await remote.send("off")
    assert len(remote.calls) == 1
    assert remote.calls[0][:2] == ("homeassistant", "turn_off")
    assert set(remote.calls[0][2]["entity_id"]) == {
        "light.desk",
        "switch.lamp",
        "light.scene_only",
        "light.other_scene_only",
    }
    assert len(remote.calls[0][2]["entity_id"]) == 4
    for entity in remote.calls[0][2]["entity_id"]:
        assert remote.state(entity) == "off"
    assert "transition" not in remote.calls[0][2]
    assert remote.state("media_player.tv") == "on"
    assert remote.state("light.unrelated") == "on"
    assert remote.state("light.ceiling") == "off"
    await remote.send("off")
    await remote.send("off")
    assert len(remote.calls) == 1


@pytest.mark.parametrize("target_on", [False, True])
async def test_missing_scene_members_still_turns_off_targets_without_empty_calls(
    make_remote, target_on
):
    remote = await make_remote()
    remote.hass.states.async_set("scene.reading", "unknown")
    remote.hass.states.async_set("switch.lamp", "on" if target_on else "off")
    await remote.send("off")
    await remote.send("off")
    assert remote.state("switch.lamp") == "off"
    assert remote.calls == (
        [
            ("homeassistant", "turn_off", {"entity_id": ["switch.lamp"]}),
        ]
        if target_on
        else []
    )


async def test_different_power_buttons_preserve_both_single_clicks(make_remote):
    remote = await make_remote()
    await remote.send("on")
    await remote.send("off")
    assert remote.state("light.desk") == "on"
    await remote.wait()
    assert remote.state("light.desk") == "off"
    assert [call[1] for call in remote.calls] == ["turn_on", "turn_off"]


async def test_arrow_followed_by_power_uses_new_selected_light(make_remote):
    remote = await make_remote()
    await remote.send("press", 5, [256, 0, 0])
    await remote.send("on")
    assert remote.state("input_number.target") == "1.0"
    await remote.wait()
    assert remote.state("light.ceiling") == "on"
    assert remote.state("light.desk") == "off"


async def test_slow_repeated_clicks_are_two_singles(make_remote):
    remote = await make_remote()
    await remote.send("on")
    await remote.wait()
    await remote.send("on")
    await remote.wait()
    assert [call[:2] for call in remote.calls] == [("homeassistant", "turn_on")] * 2


@pytest.mark.parametrize("count, scenes, singles", [(3, 1, 1), (4, 2, 0)])
async def test_rapid_clicks_are_consumed_in_pairs(make_remote, count, scenes, singles):
    remote = await make_remote()
    for _ in range(count):
        await remote.send("on")
    await remote.wait()
    assert sum(call[:2] == ("scene", "turn_on") for call in remote.calls) == scenes
    assert (
        sum(call[:2] == ("homeassistant", "turn_on") for call in remote.calls)
        == singles
    )


@pytest.mark.parametrize("command, direction", [("move_with_on_off", 0), ("move", 1)])
@pytest.mark.parametrize("shape", ["list", "args_dict", "params", "no_args"])
async def test_dimming_and_release_preserve_direction(
    make_remote, command, direction, shape
):
    from enum import IntEnum

    class Mode(IntEnum):
        UP = 0
        DOWN = 1

    remote = await make_remote()
    args = (
        [Mode(direction), 83]
        if shape == "list"
        else {"move_mode": Mode(direction), "rate": 83}
    )
    data = (
        {"params" if shape == "params" else "args": args} if shape != "no_args" else {}
    )
    await remote.send(command, 8, **data)
    brightness = remote.attr("light.desk", "brightness")
    assert (brightness > 100) if direction == 0 else (brightness < 100)
    await remote.send("stop_with_on_off", 8)
    count = len(remote.calls)
    await remote.wait(0.12)
    assert len(remote.calls) == count


@pytest.mark.parametrize("arg, expected", [(3328, 3150), (3329, 2850)])
async def test_temperature_holds_and_release(make_remote, arg, expected):
    remote = await make_remote(arrow_hold_behavior="color_temp")
    await remote.send("hold", 5, [arg, 0])
    assert remote.attr("light.desk", "color_temp_kelvin") == expected
    await remote.send("release", 5, [arg, 0])
    count = len(remote.calls)
    await remote.wait(0.12)
    assert len(remote.calls) == count


async def test_hold_cancels_pending_click_for_same_button(make_remote):
    remote = await make_remote(force_brightness=True, brightness_pct=99)
    await remote.send("on")
    await remote.send("move_with_on_off", 8, [0, 83])
    assert remote.calls[0][:2] == ("light", "turn_on")
    assert remote.attr("light.desk", "brightness") == 126
    await remote.send("stop", 8)
    await remote.wait()
    assert len(remote.calls) == 1


async def test_custom_arrow_actions_are_preserved(make_remote):
    remote = await make_remote(
        arrow_left_hold=[{"event": "custom_hold"}],
        arrow_left_release=[{"event": "custom_release"}],
    )
    events = []
    remote.hass.bus.async_listen(
        "custom_hold", lambda event: events.append(event.event_type)
    )
    remote.hass.bus.async_listen(
        "custom_release", lambda event: events.append(event.event_type)
    )
    await remote.send("hold", 5, [3329, 0])
    await remote.send("release", 5, [3329, 0])
    assert events == ["custom_hold", "custom_release"]


async def test_switches_receive_no_light_only_options_or_hold_actions(make_remote):
    remote = await make_remote(
        scenes=False, force_brightness=True, arrow_hold_behavior="color_temp"
    )
    await remote.hass.services.async_call(
        "input_number",
        "set_value",
        {"entity_id": "input_number.target", "value": 2},
        blocking=True,
    )
    await remote.send("on")
    assert remote.calls == [
        ("homeassistant", "turn_on", {"entity_id": ["switch.lamp"]})
    ]
    await remote.send("move", 8, [1, 83])
    await remote.send("hold", 5, [3328, 0])
    assert len(remote.calls) == 1


@pytest.mark.parametrize("interrupt", [False, True])
async def test_manual_flash_restores_off_state_and_remembered_brightness(
    make_remote, interrupt
):
    remote = await make_remote(scenes=False, enable_flash=True, flash_duration=100)
    await remote.send("press", 5, [256, 0, 0])
    assert remote.state("light.ceiling") == "on"
    assert remote.attr("light.ceiling", "brightness") == 100
    if interrupt:
        # A stop used to leave this flash on until another arrow was pressed.
        await remote.send("stop", 8)
    else:
        await remote.wait(0.15)
    assert remote.state("light.ceiling") == "off"
    assert remote.attr("light.ceiling", "brightness") == 100
    assert remote.hass.states.get("scene.styrbar_flash_target") is None
    assert all(
        "brightness" not in data
        for domain, service, data in remote.calls
        if domain == "homeassistant"
    )


async def test_native_flash_does_not_override_brightness(make_remote):
    remote = await make_remote(scenes=False, enable_flash=True)
    attrs = dict(remote.hass.states.get("light.ceiling").attributes)
    remote.hass.states.async_set(
        "light.ceiling", "on", {**attrs, "supported_features": 8}
    )
    await remote.send("press", 5, [256, 0, 0])
    assert remote.calls == [
        ("light", "turn_on", {"flash": "short", "entity_id": ["light.ceiling"]})
    ]


async def test_double_click_during_previous_selection_flash(make_remote):
    remote = await make_remote(enable_flash=True, flash_duration=300)
    await remote.send("press", 5, [256, 0, 0])
    await remote.send("on")
    assert remote.state("light.ceiling") == "on"
    await remote.send("on")
    await remote.wait(0.4)
    assert (
        sum(
            call[0] == "scene"
            and call[1] == "turn_on"
            and call[2]["entity_id"] == ["scene.reading"]
            for call in remote.calls
        )
        == 1
    )
    assert not any(
        call[0] == "homeassistant" and "transition" in call[2] for call in remote.calls
    )
    assert remote.state("input_number.target") == "1.0"


async def test_disabled_automation_does_not_replay_pending_click(make_remote):
    remote = await make_remote()
    await remote.send("on")
    for service in ("turn_off", "turn_on"):
        await remote.hass.services.async_call(
            "automation", service, {"entity_id": "automation.remote"}, blocking=True
        )
    await remote.send("off")
    await remote.wait()
    assert remote.calls == []
    assert remote.state("input_text.click") == ""


@pytest.mark.parametrize("memory", ["not json", "[]", '{"button":"on","at":"bad"}'])
async def test_malformed_click_memory_recovers_as_single(make_remote, memory):
    remote = await make_remote()
    await remote.hass.services.async_call(
        "input_text",
        "set_value",
        {"entity_id": "input_text.click", "value": memory},
        blocking=True,
    )
    await remote.send("on")
    await remote.wait()
    assert remote.calls == [
        ("homeassistant", "turn_on", {"transition": 0.3, "entity_id": ["light.desk"]})
    ]


async def test_previous_arrow_does_not_delay_dimming_with_flash_enabled(make_remote):
    remote = await make_remote(enable_flash=True, flash_duration=300)
    await remote.send("press", 5, [256, 0, 0])
    await remote.send("move_with_on_off", 8, [0, 83])
    assert remote.state("input_number.target") == "1.0"
    assert remote.calls == [
        ("light", "turn_on", {"brightness": 126, "entity_id": ["light.ceiling"]})
    ]
    await remote.send("stop", 8)


@pytest.mark.parametrize("direction, start, expected", [(0, 250, 255), (1, 20, 15)])
async def test_brightness_stops_at_bounds(make_remote, direction, start, expected):
    remote = await make_remote()
    attrs = dict(remote.hass.states.get("light.desk").attributes)
    remote.hass.states.async_set("light.desk", "on", {**attrs, "brightness": start})
    await remote.send("move", 8, [direction, 83])
    await remote.wait(0.12)
    assert remote.attr("light.desk", "brightness") == expected
    assert len(remote.calls) == 1


@pytest.mark.parametrize(
    "arg, start, expected", [(3328, 6450, 6500), (3329, 2050, 2000)]
)
async def test_temperature_stops_at_light_limits(make_remote, arg, start, expected):
    remote = await make_remote(arrow_hold_behavior="color_temp")
    attrs = dict(remote.hass.states.get("light.desk").attributes)
    remote.hass.states.async_set(
        "light.desk", "on", {**attrs, "color_temp_kelvin": start}
    )
    await remote.send("hold", 5, [arg, 0])
    await remote.wait(0.12)
    assert remote.attr("light.desk", "color_temp_kelvin") == expected
    assert len(remote.calls) == 1


async def test_other_remote_events_do_not_complete_double_or_interrupt_single(
    make_remote,
):
    remote = await make_remote()
    await remote.send("on")
    remote.hass.bus.async_fire(
        "zha_event", {"device_id": "another_remote", "command": "on", "cluster_id": 6}
    )
    await remote.wait()
    assert [call[:2] for call in remote.calls] == [("homeassistant", "turn_on")]


async def test_out_of_range_indices_are_normalized(make_remote):
    remote = await make_remote()
    for entity, value in [("input_number.target", 19), ("input_number.scene", 19)]:
        await remote.hass.services.async_call(
            "input_number",
            "set_value",
            {"entity_id": entity, "value": value},
            blocking=True,
        )
    await remote.send("on")
    await remote.wait()
    assert remote.state("light.ceiling") == "on"
    await remote.send("on")
    await remote.send("on")
    assert remote.calls[-1][0] != "homeassistant"
    assert remote.attr("light.ceiling", "brightness") == 60


@pytest.mark.parametrize(
    "field,value",
    [
        ("selected_scene", ""),
        ("click_memory", ""),
        ("selected_scene", "input_number.target"),
    ],
)
async def test_incomplete_scene_configuration_has_clear_error(
    make_remote, caplog, field, value
):
    caplog.set_level("INFO", logger="homeassistant.components.automation.remote")
    remote = await make_remote(**{field: value})
    await remote.send("on")
    assert remote.calls == []
    assert (
        "Scenes require a separate Scene Index helper and a Click Memory helper"
        in caplog.text
    )


async def test_empty_targets_has_clear_error(make_remote, caplog):
    caplog.set_level("INFO", logger="homeassistant.components.automation.remote")
    remote = await make_remote(targets=[])
    await remote.send("on")
    assert remote.calls == []
    assert "Configure at least one light or switch" in caplog.text


async def test_expired_pending_click_is_preserved_when_event_processing_is_late(
    make_remote,
):
    import json

    remote = await make_remote()
    await remote.send("on")
    memory = json.loads(remote.state("input_text.click"))
    memory["at"] -= 0.2
    await remote.hass.services.async_call(
        "input_text",
        "set_value",
        {
            "entity_id": "input_text.click",
            "value": json.dumps(memory),
        },
        blocking=True,
    )
    await remote.send("on")
    await remote.wait()
    assert [call[:2] for call in remote.calls] == [("homeassistant", "turn_on")] * 2


async def test_remote_telemetry_does_not_interrupt_double_click(make_remote):
    remote = await make_remote()
    await remote.send("on")
    await remote.send("attribute_updated", 1)
    await remote.send("on")
    assert remote.calls[0] == ("scene", "turn_on", {"entity_id": ["scene.reading"]})


async def test_remote_telemetry_does_not_stop_a_hold(make_remote):
    remote = await make_remote()
    await remote.send("move_with_on_off", 8, [0, 83])
    await remote.send("attribute_updated", 1)
    await remote.wait(0.12)
    assert len(remote.calls) >= 2
    await remote.send("stop", 8)


@pytest.mark.parametrize("arg,expected", [(0, "2.0"), (256, "1.0")])
async def test_legacy_single_arrows_select_correct_direction(
    make_remote, arg, expected
):
    remote = await make_remote(scenes=False)
    await remote.send("press", 5, [arg, 0, 0])
    assert remote.state("input_number.target") == expected
    assert remote.calls == []


@pytest.mark.parametrize("group_entity", ["light.living_room", "group.living_room"])
async def test_double_down_custom_group_replaces_default_and_skips_dark_members(
    make_remote, group_entity
):
    remote = await make_remote(
        light_group=True,
        double_down_targets=[group_entity, "light.desk"],
    )
    remote.hass.states.async_set(
        "light.desk", "on", dict(remote.hass.states.get("light.desk").attributes)
    )
    remote.hass.states.async_set("switch.lamp", "on")
    remote.hass.states.async_set("light.unavailable", "unavailable")
    remote.hass.states.async_set("media_player.tv", "on")
    if group_entity.startswith("group."):
        remote.hass.states.async_set(
            group_entity,
            "on",
            {
                "entity_id": [
                    "light.living_room",
                    "light.unavailable",
                    "media_player.tv",
                ],
            },
        )
    await remote.send("off")
    assert remote.calls == []
    await remote.send("off")
    assert remote.calls == [
        ("homeassistant", "turn_off", {"entity_id": ["light.desk"]})
    ]
    assert remote.state("light.desk") == "off"
    assert remote.state("light.ceiling") == "off"
    assert remote.state("switch.lamp") == "on"
    assert remote.state("media_player.tv") == "on"


@pytest.mark.parametrize("state", ["off", "unavailable", None])
async def test_custom_double_down_never_falls_back_to_default(make_remote, state):
    remote = await make_remote(double_down_targets=["light.custom"])
    if state is not None:
        remote.hass.states.async_set("light.custom", state)
    remote.hass.states.async_set(
        "light.desk", "on", dict(remote.hass.states.get("light.desk").attributes)
    )
    await remote.send("off")
    await remote.send("off")
    assert remote.calls == []
    assert remote.state("light.desk") == "on"


async def test_custom_double_down_accepts_individual_lights_and_switches(make_remote):
    remote = await make_remote(double_down_targets=["light.desk", "switch.lamp"])
    for entity in ("light.desk", "light.ceiling", "switch.lamp"):
        remote.hass.states.async_set(
            entity, "on", dict(remote.hass.states.get(entity).attributes)
        )
    await remote.send("off")
    await remote.send("off")
    assert len(remote.calls) == 1
    assert set(remote.calls[0][2]["entity_id"]) == {"light.desk", "switch.lamp"}
    assert remote.state("light.ceiling") == "on"


async def test_custom_double_down_leaves_single_power_and_scene_up_unchanged(
    make_remote,
):
    remote = await make_remote(double_down_targets=["light.ceiling"])
    await remote.send("on")
    await remote.wait()
    assert remote.state("light.desk") == "on"
    assert remote.state("light.ceiling") == "off"
    await remote.send("off")
    await remote.wait()
    assert remote.state("light.desk") == "off"
    await remote.send("on")
    await remote.send("on")
    assert remote.state("light.desk") == "on"
    assert remote.state("light.ceiling") == "on"
    assert remote.state("switch.lamp") == "on"


@pytest.mark.parametrize("features", [0, 32])
@pytest.mark.parametrize(
    "command,cluster,args",
    [
        ("on", 6, []),
        ("move_with_on_off", 8, [0, 83]),
        ("hold", 5, [3328, 0]),
    ],
)
async def test_transition_smoothness_input_is_used_when_supported(
    make_remote, features, command, cluster, args
):
    remote = await make_remote(
        scenes=False,
        transition_time=0.7,
        arrow_hold_behavior="color_temp",
    )
    attrs = dict(remote.hass.states.get("light.desk").attributes)
    remote.hass.states.async_set(
        "light.desk", "off", {**attrs, "supported_features": features}
    )
    await remote.send(command, cluster, args)
    assert remote.calls
    data = remote.calls[0][2]
    if features:
        assert data["transition"] == 0.7
    else:
        assert "transition" not in data
    if command == "move_with_on_off":
        await remote.send("stop", 8)
    elif command == "hold":
        await remote.send("release", 5, [3328, 0])
