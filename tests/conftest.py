"""Run the shipped blueprint in Home Assistant, with simulated light services."""

import asyncio
import shutil
from copy import deepcopy
from pathlib import Path

import pytest_asyncio
from homeassistant import bootstrap, config_entries, loader
from homeassistant.const import EVENT_CALL_SERVICE
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import async_setup_component

BLUEPRINT = Path(__file__).parents[1] / "ikea_styrbar.yaml"


async def settle():
    # Drain ready tasks without waiting for click windows or held-button loops.
    await asyncio.sleep(0.01)


class Remote:
    def __init__(self, hass, device_id, calls):
        self.hass = hass
        self.device_id = device_id
        self.calls = calls

    async def send(self, command, cluster=6, args=None, params=None):
        data = {"device_id": self.device_id, "command": command, "cluster_id": cluster}
        if args is not None:
            data["args"] = args
        if params is not None:
            data["params"] = params
        self.hass.bus.async_fire("zha_event", data)
        await settle()

    async def wait(self, seconds=0.2):
        await asyncio.sleep(seconds)
        await settle()

    def state(self, entity):
        return self.hass.states.get(entity).state

    def attr(self, entity, attr):
        return self.hass.states.get(entity).attributes.get(attr)


@pytest_asyncio.fixture
async def make_remote(tmp_path, caplog):
    hass = HomeAssistant(str(tmp_path))
    hass.config.skip_pip = True
    loader.async_setup(hass)
    hass.config_entries = config_entries.ConfigEntries(hass, {})
    assert await bootstrap.async_load_base_functionality(hass)
    calls = []

    # Service doubles model devices, never the gesture logic or template engine.
    @callback
    def power(call):
        ids = call.data["entity_id"]
        for entity in [ids] if isinstance(ids, str) else ids:
            old = hass.states.get(entity)
            attrs = dict(old.attributes) if old else {}
            attrs.update({k: v for k, v in call.data.items() if k != "entity_id"})
            if "brightness_pct" in attrs:
                attrs["brightness"] = round(attrs["brightness_pct"] * 2.55)
            hass.states.async_set(
                entity, "on" if call.service == "turn_on" else "off", attrs
            )

    @callback
    def record_service(event):
        data = event.data
        if data["domain"] in ("homeassistant", "light", "switch", "scene"):
            calls.append((data["domain"], data["service"], dict(data["service_data"])))

    hass.bus.async_listen(EVENT_CALL_SERVICE, record_service)

    async def factory(*, scenes=True, light_group=False, **overrides):
        inputs = {
            "switch_remote": "test_remote",
            "targets": ["light.desk", "light.ceiling", "switch.lamp"],
            "selected_target": "input_number.target",
            "enable_flash": False,
            "double_click_window": 150,
            "repeat_delay": 50,
        }
        if scenes:
            inputs.update(
                scenes=["scene.reading", "scene.evening"] if scenes is True else scenes,
                selected_scene="input_number.scene",
                click_memory="input_text.click",
            )
        inputs.update(overrides)
        config = {
            "input_number": {
                "target": {"min": 0, "max": 20, "step": 1, "initial": 0},
                "scene": {"min": 0, "max": 20, "step": 1, "initial": 0},
            },
            "input_text": {"click": {"max": 255, "initial": ""}},
            "scene": [
                {
                    "name": "Reading",
                    "entities": {
                        "light.desk": {
                            "state": "on",
                            "brightness": 180,
                            "color_temp_kelvin": 3300,
                        },
                        "light.ceiling": "on",
                        "switch.lamp": "on",
                    },
                },
                {
                    "name": "Evening",
                    "entities": {
                        "light.desk": "off",
                        "light.ceiling": {"state": "on", "brightness": 60},
                        "switch.lamp": "off",
                    },
                },
            ],
            "automation": [
                {
                    "alias": "Remote",
                    "id": "remote_test",
                    "use_blueprint": {
                        "path": "Toffanelly/ikea_styrbar.yaml",
                        "input": inputs,
                    },
                }
            ],
        }
        if light_group:
            config["light"] = [
                {
                    "platform": "group",
                    "name": "Living room",
                    "entities": ["light.desk", "light.ceiling"],
                }
            ]
        for entity, modes, features in [
            ("light.desk", ["color_temp"], 32),
            ("light.ceiling", ["brightness"], 0),
            ("switch.lamp", [], 0),
        ]:
            hass.states.async_set(
                entity,
                "off",
                {
                    "supported_color_modes": modes,
                    "color_mode": modes[0] if modes else "onoff",
                    "supported_features": features,
                    "brightness": 100,
                    "color_temp_kelvin": 3000,
                    "min_color_temp_kelvin": 2000,
                    "max_color_temp_kelvin": 6500,
                },
            )
        destination = tmp_path / "blueprints/automation/Toffanelly/ikea_styrbar.yaml"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(BLUEPRINT, destination)
        domains = ["input_number", "input_text", "scene"]
        if light_group:
            domains.append("light")
        for domain in [*domains, "automation"]:
            assert await async_setup_component(hass, domain, deepcopy(config))
        await hass.async_start()
        await hass.async_block_till_done()
        assert hass.states.get("automation.remote") is not None, caplog.text
        assert hass.states.get("automation.remote").state == "on", caplog.text
        for domain in ("homeassistant", "light", "switch"):
            for service in ("turn_on", "turn_off"):
                hass.services.async_register(domain, service, power)
        calls.clear()
        return Remote(hass, "test_remote", calls)

    yield factory
    await hass.async_stop()
    errors = [
        record.getMessage()
        for phase in ("setup", "call", "teardown")
        for record in caplog.get_records(phase)
        if record.levelname == "ERROR"
    ]
    assert not errors, "\n".join(errors)
