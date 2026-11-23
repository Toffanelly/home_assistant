# IKEA STYRBAR: lights and scenes

[![Tests](https://github.com/Toffanelly/ikea-styrbar-zha/actions/workflows/test.yml/badge.svg)](https://github.com/Toffanelly/ikea-styrbar-zha/actions/workflows/test.yml)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

A Home Assistant blueprint for the four-button IKEA STYRBAR remote paired through **ZHA**.

[![Import blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FToffanelly%2Fikea-styrbar-zha%2Fblob%2Fmain%2Fikea_styrbar.yaml)

## Controls

| Button | Single click | Double-click | Hold |
| --- | --- | --- | --- |
| Up | Turn on selected light/switch | Activate selected scene | Brighten selected light |
| Down | Turn off selected light/switch | Turn off chosen group or default set | Dim selected light |
| Left | Select previous light/switch | Select previous scene | Warmer white or custom action |
| Right | Select next light/switch | Select next scene | Colder white or custom action |

Light and scene selections are independent and wrap around their lists. Selecting a scene does not activate it. Double-up applies its saved states, including brightness, colour and off states.

Double-clicks require scene controls to be configured. Single clicks then wait for a second tap, **350 ms** by default. Without scene controls, singles remain immediate. Holds stop on release.

## Setup

1. Pair the remote through **ZHA**, then import the blueprint above.
2. Create a **Number** helper for the selected light index: minimum `0`, maximum `99`, step `1`.
3. Create an automation from the blueprint. Select the remote, an ordered light/switch list and the index helper.
4. For scene controls, select an ordered scene list and provide two additional helpers: a separate **Number** helper with the same range, and a **Text** helper with minimum length `0` and maximum `255`.
5. For arrow holds, choose **Adjust colour temperature**, or leave the default custom actions.

Use one automation and a separate set of helpers per remote. Indices start at `0`; increase a Number helper's maximum if its list has more than 100 entries.

## Double-down

**Double-down Targets** is optional:

- **Empty:** turn off every light/switch in the target list and all configured scenes.
- **Selected:** turn off only those entities or group members. For example, choose `light.living_room` to turn off the living room, leaving other rooms on.

You can select individual lights, switches or groups. To create a light group, go to **Settings → Devices & services → Helpers → Create helper → Group → Light group**. Already off or unavailable members are skipped; an empty or unavailable chosen group never falls back to turning everything off.

The default set includes scene members exposed in the scene's `entity_id` attribute. For scenes without that attribute, add their lights to the target list or choose an explicit double-down group.

## Updating

Re-import the blueprint and reconfigure the automation as needed, then reload automations. If you installed the older, long-named blueprint, import this version and create an automation from it, reusing your helpers. Disable the old automation before enabling its replacement.

## Examples and tuning

YAML examples: [helpers](examples/helpers.yaml), [scenes](examples/scenes.yaml), [automation](examples/automation.yaml). Replace their device and entity IDs with your own.

- Increase **Double-click Window** for slower taps. Its 150–600 ms range also sets single-click latency.
- For slow Wi-Fi/cloud bulbs, try **Dimming Speed** at 250–400 ms.
- Include explicit off states in a scene to turn off lights from the previous scene when switching.
- Selection flash preserves the selected entity's state and remembered brightness. **Force Brightness** applies to single-up, while scenes retain their saved values.

For failures, inspect the automation trace and listen for `zha_event` in **Developer tools → Events**.

## Tests

Tested with **Home Assistant 2026.11.2** and **Python 3.14**. The suite runs the blueprint in Home Assistant with simulated device services:

```bash
uv run --no-project --python 3.14 --with-requirements requirements-test.txt python -m pytest -q
```

Physical remote timing still needs checking on a paired device. Licensed under [Apache 2.0](LICENSE).
