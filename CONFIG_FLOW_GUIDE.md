# Configuration Flow Guide for AIO Energy Management

This guide explains how to use the UI-based configuration flow for AIO Energy Management.

## Overview

AIO Energy Management supports both:
- **UI Configuration** (recommended) — configure through Home Assistant’s UI (**Cheapest hours**, **Calendar**, **Excess solar**)
- **YAML Configuration** (legacy) — still supported for backward compatibility

## UI Configuration

### Adding a New Entity

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for **AIO Energy Management**
4. Select the type of entity:
   - **Cheapest hours sensor** - Binary sensor that tracks cheapest/expensive hours
   - **Calendar** - Calendar entity to display energy management events. Only one supported.
   - **Excess solar** - Manages loads when grid power shows solar export (surplus). You can add multiple excess solar entries if you want separate setups.

---

### Configuring Cheapest Hours Sensor

The configuration is split into multiple steps:

#### Step 1: Select Data Provider

Choose **one** data provider:
- **Nord Pool** - Uses a Nord Pool sensor entity from the Nord Pool custom integration
- **Nord Pool official** - Uses a config entry from the Nord Pool official integration
- **Entso-E** - Uses a sensor entity from the Entso-E integration

#### Step 2: Data Provider Settings

Depending on the provider selected in Step 1, you will see one of these screens:

**Nord Pool:**
| Field | Description |
|---|---|
| Nord Pool entity (required) | Entity ID of the Nord Pool sensor (e.g. `sensor.nordpool`) |
| MTU | Market time unit in minutes — `15` or `60` (default: `60`) |
| Allow dynamic entities | Enable support for dynamic entities on upcoming steps. (default: off)  |

**Nord Pool official:**
| Field | Description |
|---|---|
| Config entry (required) | Select from existing Nord Pool official config entries |
| Area | Market area override (optional) |
| MTU | Market time unit in minutes — `15` or `60` (default: `60`) |
| Allow dynamic entities | Enable support for dynamic entities on upcoming steps. (default: off)  |


**Entso-E:**
| Field | Description |
|---|---|
| Entso-E entity (required) | Entity ID of the Entso-E average price sensor |
| MTU | Market time unit in minutes — `15` or `60` (default: `60`) |
| Allow dynamic entities | Enable support for dynamic entities on upcoming steps. (default: off)  |


> **Note:** When **Allow dynamic entities** is enabled, additional optional entity fields appear on subsequent steps. These let you use `sensor` or `input_number` entities to supply values at runtime instead of static numbers.

#### Step 3: Basic Settings

| Field | Description | Validation |
|---|---|---|
| Name (required) | Friendly name (e.g. "Cheapest 3 Hours") | — |
| Number of slots | Static count of time slots to find (≥ 0; use `0` to rely on entity) | ≥ 0 |
| Number of slots entity *(dynamic only)* | `sensor`/`input_number` entity providing the slot count | Mutually exclusive with static value |
| First hour (required) | Start of the search window (0–23) | 0–23 |
| Last hour (required) | End of the search window (0–23) | 0–23, must be ≥ First hour |
| Sequential | Find consecutive hours only (vs. scattered) | — |

> **Important:** Exactly one of **Number of slots** or **Number of slots entity** must be provided.

#### Step 4: Advanced Settings

| Field | Description | Validation |
|---|---|---|
| Failsafe starting hour | Fallback hour when price data is unavailable (optional) | 0–23 |
| Inversed | Find most expensive hours instead of cheapest | — |
| Trigger hour | Static earliest hour to calculate next cheapest hours (optional) | 0–23 |
| Trigger hour entity *(dynamic only)* | Entity providing the trigger hour | Mutually exclusive with static value |
| Price limit | Only accept prices below this value (or above if Inversed) (optional) | — |
| Price limit entity *(dynamic only)* | Entity providing the price limit | Mutually exclusive with static value |
| Add to calendar | Show this sensor's schedule in the calendar | — |
| Retention days | Days of calendar history to keep (1–365, default: 1) | 1–365 |
| Price modifications | Jinja2 template for adjusting prices (tariffs, taxes, etc.) | — |
| Use offset | Enable start/end time offsets (shows Step 5 if enabled) | — |

#### Step 5: Time Offset *(only shown when "Use offset" is enabled)*

All offset fields are optional. Each can use a static integer **or** an entity (when dynamic entities are enabled), but not both.

| Field | Description | Validation |
|---|---|---|
| Start hours | Hours to offset the start time | Any integer |
| Start hours entity *(dynamic only)* | Entity providing start hours offset | — |
| Start minutes | Minutes to offset the start time | 0–59 |
| Start minutes entity *(dynamic only)* | Entity providing start minutes offset | — |
| End hours | Hours to offset the end time | Any integer |
| End hours entity *(dynamic only)* | Entity providing end hours offset | — |
| End minutes | Minutes to offset the end time | 0–59 |
| End minutes entity *(dynamic only)* | Entity providing end minutes offset | — |

---

### Configuring Calendar

Simple single-step configuration:
- **Name** (required) — Friendly name for the calendar (e.g. "Energy Management")

---

### Configuring Excess solar

Excess solar turns devices on when your **grid power** sensor shows enough export (surplus), using priority and per-device rules. Typical use: divert spare PV to a water heater, floor heating, or similar when you are not selling or storing all production in a battery.

The flow is: **global settings** → **one or more power devices** → optional **add another device** loop.

#### Step 1: Global settings

| Field | Description | Validation |
|---|---|---|
| Name (required) | Friendly name for this excess solar entry (also used for the master switch and device grouping) | — |
| Grid power sensor (required) | `sensor` entity for grid import/export power. **Negative values mean export** (solar feeding the grid) | `sensor` domain |
| Buffer (optional) | Extra watts of surplus required before any device is activated (reduces flapping). Default: `0` | 0–10000 W |

#### Step 2: Power device (repeat for each device)

You configure at least one device. After each device you can add more in the next step.

| Field | Description | Validation |
|---|---|---|
| Device name (required) | Label for this load (used in entity names) | Non-empty |
| Consumption (W) (required) | Static power in watts used for **turn-on** budgeting. Must be **greater than `0`** or the manager will never activate this device. Set it to the load you expect when the device runs (for example rated heater power) | 0–100000 |
| Consumption entity (optional) | `sensor` reporting live consumption in watts; used with **current** surplus while devices run (static watts still define eligibility and expected load for activation) | `sensor` domain |
| Priority (optional) | Lower number = higher priority (turned on first). Default: `100` | 1–999 |
| Is on schedule entity (optional) | `binary_sensor` or `input_boolean` that is `on` when this device is already running on its own schedule; excess solar avoids interfering while it is `on` | `binary_sensor` or `input_boolean` |
| Minimum on-period (min) (optional) | Minimum time the device stays on before the manager may turn it off. Default: `0` | 0–1440 |
| Minimum off time (min) (optional) | Minimum minutes the device must stay off before it can turn on again; omit to use the integration default (1 minute) | 0–1440 |

#### Step 3: Add another device?

- Enable **Add another device** to return to Step 2 for the next load.
- Leave it disabled to finish and create the config entry.

#### Created entities

For each entry you get:

- One **binary sensor** per device — `on` when excess solar logic wants that load active (name: `"{entry name} {device name}"`).
- One **number** per device — adjustable **priority**.
- **Master switch** — enables or disables the whole excess solar manager for this entry (name matches the entry **Name**).
- One **enabled switch** per device — include or exclude that device without deleting it.

---

### Modifying existing entities (Excess solar)

1. Go to **Settings** → **Devices & Services** → **AIO Energy Management** → choose the excess solar entry → **Configure**.
2. Choose an action:
   - **Edit global settings** — grid power sensor and buffer.
   - **Add a device** — same device form as initial setup; then optionally add more devices.
   - **Remove device(s)** — multi-select device names to remove.

Submit completes the chosen action and returns to Home Assistant.

---

### Modifying Existing Entities

1. Go to **Settings** → **Devices & Services**
2. Find **AIO Energy Management**
3. Open the config entry you want to change → **Configure**

**Cheapest hours:** Walk through the same steps as the initial setup — existing values are pre-filled — then **Submit**.

**Calendar:** Options may only confirm there are no extra settings.

**Excess solar:** Use the **manage** menu (edit global settings, add device, remove devices) as described in [Modifying existing entities (Excess solar)](#modifying-existing-entities-excess-solar).

---

## YAML Configuration (Legacy)

The YAML configuration method is still supported. See [README.md](README.md) for YAML configuration examples.

## Migration from YAML to UI

1. **Keep your YAML configuration** — It will continue to work
2. **Add new entities via UI** — Use the UI for new entities
3. **Optional: Migrate existing entities**:
   - Add the entity via UI with the same settings
   - Remove the YAML configuration
   - Restart Home Assistant

> **Note:** You cannot have the same entity configured in both YAML and UI. Choose one method per entity.

---

## Examples

### Example 1: Basic Cheapest Hours (Nord Pool)
- **Data provider**: Nord Pool → entity `sensor.nordpool`
- **MTU**: 60
- **Name**: "Cheapest 3 Hours"
- **Number of slots**: 3
- **First hour**: 21, **Last hour**: 12 *(wraps overnight)*
- **Sequential**: No

> ⚠️ Note: first_hour > last_hour is currently not blocked by validation, but it will result in an error after entity is created.

### Example 2: Expensive Hours (Inversed)
- **Data provider**: Nord Pool → entity `sensor.nordpool`
- **Name**: "Expensive Hours"
- **Number of slots**: 4
- **First hour**: 0, **Last hour**: 22
- **Sequential**: No
- **Inversed**: Yes

### Example 3: With Price Modifications (Nord Pool official)
- **Data provider**: Nord Pool official → select config entry from dropdown
- **Name**: "Cheapest Hours with Tariffs"
- **Number of slots**: 3
- **Price modifications**:
  ```jinja2
  {%- set as_snt = price / 10.0 %}
  {%- set with_taxes = (as_snt * 1.255) | float %}
  {%- if time.hour >= 22 or time.hour <= 7 %}
    {{ with_taxes + 3.1 }}
  {%- else %}
    {{ with_taxes + 5.0 }}
  {%- endif %}
  ```

### Example 4: With Time Offset and Dynamic Entities
- **Data provider**: Nord Pool → entity `sensor.nordpool`, **Allow dynamic entities**: on
- **Name**: "Cheapest Hours with Offset"
- **Number of slots**: 5
- **Sequential**: Yes
- **Use offset**: Yes
- **Start hours**: 0, **Start minutes**: 30
- **End hours**: 1, **End minutes**: 15

### Example 5: Excess solar (water heater + buffer)
- **Entry type**: Excess solar
- **Name**: "Excess Solar"
- **Grid power sensor**: `sensor.grid_power` *(negative when exporting to the grid)*
- **Buffer**: `200` W
- **Device 1**: Name "Water heater", **Consumption (W)**: `3000`, **Priority**: `10`, **Minimum on-period**: `15` min
- **Add another device**: No

Automate your real switch or climate entity from the binary sensor that Home Assistant creates for `"Excess Solar Water heater"` (see **Created entities** above).

---

## Troubleshooting

### "No slots configured" error
Provide either a static **Number of slots** value (≥ 1) or a **Number of slots entity**. If you set both, the flow will also return an error.

### "Both X configured" error
You have filled in both the static value and the entity for the same field (e.g. both **Trigger hour** and **Trigger hour entity**). Clear one of them.

### "Last hour before first hour" error
**Last hour** must be greater than or equal to **First hour**. Adjust your search window.

### "First/last hour out of range" error
**First hour** and **Last hour** must be between 0 and 23.

### "Minutes out of range" error
Start/end **minutes** offset fields only accept values between 0 and 59.

### Entity not appearing
- Check that the integration is loaded in **Settings** → **Devices & Services**
- Verify the price source entity exists and has a valid state
- Check Home Assistant logs for errors

### Calendar not showing events
- Ensure **Add to calendar** is enabled for your cheapest hours sensors
- Verify a calendar entity has been created
- Check that the calendar entity is not disabled

### Excess solar device never turns `on`
- Confirm **Consumption (W)** is greater than `0` for that device
- Check the **grid power** sensor: export should appear as **negative** power (import positive); adjust your sensor or template if your sign convention differs
- Ensure the **master switch** and that device’s **enabled switch** are on
- If **Buffer** is large, surplus must exceed it before activation
- If **Is on schedule entity** is `on`, excess solar will not start that device

### Excess solar "already configured"
- Each excess solar entry uses a unique id derived from its **Name**. Pick a different name or remove the existing entry first

---

## Support

- GitHub: https://github.com/kotope/aio_energy_management
