# IKEA STYRBAR: lights and scenes

[![Tests](https://github.com/Toffanelly/ikea-styrbar-zha/actions/workflows/test.yml/badge.svg)](https://github.com/Toffanelly/ikea-styrbar-zha/actions/workflows/test.yml)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

A Home Assistant automation blueprint for the four-button IKEA STYRBAR remote using **ZHA**. Select and control individual lights or switches, hold to adjust brightness or colour temperature, and double-click to control scenes with several lights.

[![Import blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FToffanelly%2Fikea-styrbar-zha%2Fblob%2Fmain%2Fikea_styrbar.yaml)

## Controls

| Button | Single click | Fast double-click | Hold |
| --- | --- | --- | --- |
| Up / on | Turn on the selected light or switch | Activate the selected scene | Brighten the selected light |
| Down / off | Turn off the selected light or switch | Turn off all configured lights and switches | Dim the selected light |
| Left | Select the previous light or switch | Select the previous scene | Warmer white, or a custom action |
| Right | Select the next light or switch | Select the next scene | Colder white, or a custom action |

Light and scene selection are independent and wrap around their respective lists. Double-clicking an arrow selects a scene without activating it or changing the selected light. Double-up applies that scene's saved states. Double-down is the leaving-home shortcut: it turns off every light and switch in the target list and in **all configured scenes**, regardless of which light or scene is selected. Other domains and entities outside those lists are left alone.

Scenes have [no on/off state](https://www.home-assistant.io/integrations/scene/). This blueprint uses their `entity_id` attribute to include scene members in the all-off action. Scenes created in Home Assistant's scene editor or YAML expose this list. Some scenes supplied by other integrations do not: they can be activated, but their lights and switches must also be included in the target list or another scene with a member list for double-down to reach them.

With scenes configured, single clicks wait for the double-click window, **350 ms** by default. A double-click consumes both taps and never runs the corresponding single-click action. Different buttons remain separate single clicks. Holds replace a pending tap of the same button and release stops the adjustment. Without scenes configured, single clicks remain immediate.

## Setup

1. Pair your STYRBAR through **ZHA**. Zigbee2MQTT is not supported by this blueprint.
2. Under **Settings → Devices & services → Helpers**, create a **Number** helper for the selected light index. Use minimum `0`, maximum `99`, and step `1`. The maximum must be at least the number of targets minus one, and greater than the minimum.
3. Import the blueprint using the button above, then create an automation from it. Choose the remote, an ordered list of light/switch entities, and the Number helper.
4. To enable scene controls, choose an ordered list of scenes and provide two more helpers:
   - A separate **Number** helper for the scene index, also minimum `0`, maximum `99`, step `1`.
   - A **Text** helper for click memory, minimum length `0`, maximum length `255`. Leave its value alone.
5. Choose **Adjust colour temperature** for arrow holds if desired. The existing default runs the custom hold actions instead.

Give every remote its own helpers and create one automation per remote. Keep the two index helpers distinct. The first entry in each list is index `0`. The selected scene index is visible in its Number helper, which can also be shown on a dashboard.

For manual installation, copy [the blueprint](ikea_styrbar.yaml) to:

```text
config/blueprints/automation/Toffanelly/ikea_styrbar.yaml
```

Reload automations and create an automation from the blueprint. Complete YAML examples are in [examples/helpers.yaml](examples/helpers.yaml), [examples/scenes.yaml](examples/scenes.yaml), and [examples/automation.yaml](examples/automation.yaml). Replace the example device and entity IDs with your own. Match the `use_blueprint.path` to the location shown by your installation.

## Scene example

A Reading scene might turn on a desk lamp and ceiling light. An Evening scene might dim the ceiling light, turn off the desk lamp, and turn on a floor lamp. Double-right selects Evening. Double-up applies it. Double-down switches off the desk lamp, ceiling light and floor lamp, regardless of the selected scene. A single up still controls only the independently selected light.

To make scene switching turn off lights from the previous scene, include their off states in the destination scene. Activating a scene changes only the entities saved in it. The [example scenes](examples/scenes.yaml) show this explicitly.

## Existing features and tuning

- **Selection flash:** uses a light's native flash when available. Otherwise, snapshots its state, blinks it, and restores the snapshot. Selecting an off light does not overwrite its remembered brightness. A subsequent button event restores an interrupted blink before taking action.
- **Brightness:** absolute steps stop at full brightness or a minimum of `15/255`, preserving remote control at the dark end. Releases stop immediately. Ramps are bounded to 200 steps if a release packet is lost.
- **Colour temperature:** left warms and right cools within the light's reported Kelvin range. Lights without tunable white fall back to the configured custom actions. Custom release actions remain available.
- **Mixed devices:** transitions, brightness and colour temperature are sent only to lights that report support. Plain switches still support selection and on/off.
- **Force brightness:** optionally applies a fixed brightness on a single up click. Scenes retain their saved brightness and colours.

For cloud-connected bulbs, raise **Dimming Speed** to 250–400 ms if commands arrive too quickly. Adjust **Double-click Window** between 150 and 600 ms to suit your tapping speed. Increasing it also increases single-click latency. The default **Arrow long-press behaviour** remains custom actions for compatibility with existing automations.

## Updating and troubleshooting

Re-import the blueprint to update it, then reload automations. Existing input names are preserved. Existing automations need no new helpers unless you enable scenes.

If you installed the earlier version from `Toffanelly/home_assistant`, the published file has moved and the old import link no longer points to the blueprint. Migrate once as follows:

1. Download [ikea_styrbar.yaml](ikea_styrbar.yaml).
2. Replace the contents of your existing installed file at `config/blueprints/automation/Toffanelly/ikea_styrbar_remote-control_multiple_entities.yaml`, keeping that local filename.
3. Reload automations.

This preserves your automations’ `use_blueprint.path` values and inputs, and updates the blueprint’s `source_url` to the new address. New installations use `Toffanelly/ikea_styrbar.yaml` as shown above.

- **Scene double-clicks do nothing:** configure the scene list and both additional helpers. Verify the scene index helper differs from the light index helper. Check the automation trace for configuration errors.
- **Double-down misses a light:** include it in the target list or a configured scene. In **Developer tools → States**, check that the scene exposes an `entity_id` attribute listing its members. Already off or unavailable entities are skipped.
- **Two singles instead of a double:** increase the double-click window. Two presses must be of the same button, with no intervening button action.
- **Unexpected scene contents:** activate it directly in Home Assistant and check its saved states. Double-up uses `scene.turn_on` without overriding them.
- **No response from the remote:** listen for `zha_event` in **Developer tools → Events** and check the automation targets the right ZHA device. Disable other automations controlling the same remote while diagnosing conflicts.

When reporting an issue, include your Home Assistant version, remote model/firmware, the relevant automation trace and `zha_event` payloads, and whether scenes and selection flash are enabled. Remove personal entity names and device identifiers before posting.

## Development

The tests load this exact YAML through Home Assistant's blueprint loader and run its event triggers, templates, helpers, scenes and restart mode. Only physical device power services are simulated. They cover single/double timing, rapid mixed-button sequences, scene activation and all-off, holds/releases, custom actions, capability detection and selection-flash restoration.

The test environment is pinned to **Home Assistant 2026.11.2** on **Python 3.14**. With [uv](https://docs.astral.sh/uv/), run without installing packages into your system Python:

```bash
uv run --no-project --python 3.14 --with-requirements requirements-test.txt python -m pytest -q
```

Alternatively, install `requirements-test.txt` in a Python 3.14 virtual environment and run `python -m pytest -q`. GitHub Actions runs the same suite for pushes and pull requests. Physical radio timing and device-specific behaviour still need checking on a paired remote.

## License

[Apache License 2.0](LICENSE).
