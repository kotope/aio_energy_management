# Getting Started with AIO Energy Management

This guide walks you through setting up **AIO Energy Management** via the Home Assistant UI. For a complete list of every parameter, rule, and legacy YAML option, see the [Parameter & Configuration Reference](reference.md).

---

## Prerequisites

Before adding the integration, make sure you have:

1. **AIO Energy Management** installed and Home Assistant restarted.
2. **For Cheapest Hours:** one of the supported price integrations configured:
   * Nord Pool (custom integration)
   * Nord Pool (official integration)
   * Entso-E (average price sensor)
   * Strømligning (today and tomorrow sensors)
3. **For Excess Solar:** a grid power `sensor` entity where **negative values mean export** (surplus solar fed into the grid) and positive values mean import.

---

## Global Settings (Calendar & Default Price Modifications)

Every installation automatically gets one **`⚙️ Global Settings`** entry for overarching settings (recreated at startup if removed). Click **Configure** on `⚙️ Global Settings` to manage:

* **Enable calendar** — enable or disable the shared Energy Management calendar entity.
* **Calendar name** — friendly name for the calendar entity (defaults to `Energy Management`).
* **Price modifications** — optional Jinja2 template applied to the prices of every cheapest hours sensor whose Price modifications source is **Global**. Use it for tariffs and taxes that are the same for all your sensors. Same format as the per-sensor template (price and time variables). Changes don't touch plans that are already calculated: each sensor uses the new template from its next calculation, after its current plan expires.

> **Note:** Both the UI Global Settings and legacy YAML `calendar:` configuration manage the same underlying calendar entity.

---

## Setting Up a Cheapest Hours Sensor

### Step 1: Add the Integration

1. Go to **Settings → Devices & Services**.
2. Click **+ Add Integration** and search for **AIO Energy Management**.
3. Select **Cheapest hours sensor**.

### Step 2: Select a Data Provider

Choose the integration providing your electricity prices:

| Provider | What you need |
|---|---|
| **Nord Pool** | Sensor entity from the Nord Pool custom integration (e.g. `sensor.nordpool`) |
| **Nord Pool official** | Config entry from the official Nord Pool integration (plus optional market area) |
| **Entso-E** | Average price sensor entity from the Entso-E integration |
| **Strømligning** | Both today and tomorrow price sensor entities from Strømligning |

### Step 3: Configure Data Provider Settings

Fill in the price entity/config entry and select:

* **MTU** — Market Time Unit in minutes: `15` or `60` (default: `60`). If your provider supplies 15-minute prices and you choose `60`, the integration calculates hourly averages automatically.

### Step 4: Basic Settings

| Field | Description |
|---|---|
| **Name** | Friendly name for the sensor (creates `binary_sensor.<name>`) |
| **Number of slots** | Static number of time slots to select (leave empty when using a dynamic entity) |
| **Number of slots entity** | Dynamic `sensor` or `input_number` providing the slot count (mutually exclusive with static value) |
| **First hour** | Start hour of the search window (`0–23`) |
| **Last hour** | End hour of the search window (`0–23`) |
| **Sequential** | Select one continuous block of slots instead of scattered slots |
| **Add to calendar** | Display the scheduled window(s) on the Energy Management calendar |
| **Inversed** | Find the **most expensive** slots instead of the cheapest |

> **Overnight windows:** If **Last hour** is smaller than **First hour** (for example `First hour: 21`, `Last hour: 12`), the integration automatically treats the search window as overnight (ending the next day). Total search window length cannot exceed 24 hours.

> **Important:** Provide **either** a static **Number of slots** **or** a **Number of slots entity** — never both and never neither.

Click **Submit** to create `binary_sensor.<name>`.

### Step 5: Fine-Tuning via Configure (Optional)

Additional features are configured **after** the initial wizard:

1. Go to **Settings → Devices & Services → AIO Energy Management**.
2. Click **Configure** on your Cheapest Hours entry.
3. Choose from the configuration menu:
   * **Price data provider** — change price source or MTU.
   * **Basic settings** — adjust slots, search window, sequential mode, calendar, or inversed mode.
   * **Flexible hours** — configure extra flexible slots (`max_number_of_slots` and `flexible_price_limit` or `max_price_delta`).
   * **Advanced settings** — set `price_limit`, `min_seq_slots`, `number_of_blocks`, `trigger_hour`, `failsafe_starting_hour`, sensor-specific `price_modifications`, or `retention_days`.
   * **Time offset** *(only available when **Sequential** is enabled)* — shift start and/or end times.

See [reference.md](reference.md) for full details on each option.

---

## Setting Up Excess Solar

Excess Solar turns virtual `binary_sensor` entities `on` (one per configured device) whenever your grid power sensor shows sufficient solar export, respecting device priorities and minimum run/off times.

### Typical Use Cases

* **Diverting surplus PV to thermal storage:** automatically turn on a water heater, immersion heater, bathroom floor heating, or outdoor hot tub when exporting solar power instead of selling everything back to the grid.

### Step 1: Add Excess Solar

1. Go to **Settings → Devices & Services → + Add Integration → AIO Energy Management**.
2. Select **Excess solar**.

### Step 2: Global Entry Settings

| Field | Description |
|---|---|
| **Name** | Name for this Excess Solar entry (used for the master switch and device entity names) |
| **Grid power sensor** | `sensor` reporting grid power (**negative = export**, positive = import) |
| **Buffer** | Extra watts of surplus required before activating a device (default: `0` W) |

### Step 3: Add Power Devices

Configure at least one controllable load:

| Field | Description |
|---|---|
| **Device name** | Label for this device |
| **Consumption (W)** | Expected load in watts used for activation budgeting (**must be > 0**) |
| **Consumption entity** | Optional live power `sensor` (W) while the device is running |
| **Priority** | Lower number = higher priority, turned on first (default: `100`) |
| **Is on schedule entity** | Optional `binary_sensor` or `input_boolean`; when `on`, Excess Solar will not interfere with this device |
| **Minimum on-period (min)** | Minimum minutes the device stays `on` once activated (default: `0`) |
| **Minimum off time (min)** | Minimum minutes the device stays `off` before turning on again |

### Step 4: Add More Devices or Finish

Toggle **Add another device** to repeat Step 3 for additional loads, or leave it disabled to finish.

### Created Entities

For each Excess Solar entry, Home Assistant creates:

* **`binary_sensor.<entry_name>_<device_name>`** — `on` when Excess Solar wants that device active.
* **`number.<entry_name>_<device_name>_priority`** — adjust device priority directly from the UI.
* **`switch.<entry_name>`** — master switch to enable/disable the entire Excess Solar entry.
* **`switch.<entry_name>_<device_name>`** — per-device switch to temporarily exclude a load.

---

## Using the Sensors in Automations

### Cheapest Hours Example

```yaml
automation:
  - alias: "Run dishwasher during cheapest hours"
    trigger:
      - platform: state
        entity_id: binary_sensor.cheapest_hours
        to: "on"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.dishwasher
```

### Excess Solar Example

```yaml
automation:
  - alias: "Control water heater on excess solar"
    trigger:
      - platform: state
        entity_id: binary_sensor.excess_solar_water_heater
    action:
      - service: "switch.turn_{{ trigger.to_state.state }}"
        target:
          entity_id: switch.water_heater
```

---

## Common Configuration Examples

### Cheapest hours Charging (Sequential)
* **Number of slots:** `6` (with 60-min MTU) or `24` (with 15-min MTU)
* **First hour:** `22`, **Last hour:** `21` *(overnight)*
* **Sequential:** `Yes`

### Best Scattered Slots (Non-Sequential)
* **Number of slots:** `4`
* **First hour:** `0`, **Last hour:** `23`
* **Sequential:** `No`

### Avoid Expensive Peak Hours
* **Number of slots:** `3`
* **First hour:** `0`, **Last hour:** `23`
* **Sequential:** `No`, **Inversed:** `Yes`

### With Tariffs & Taxes (`Price modifications`)
```jinja2
{%- set as_snt = price / 10.0 %}
{%- set with_taxes = (as_snt * 1.255) | float %}
{%- if time.hour >= 22 or time.hour <= 7 %}
  {{ with_taxes + 3.1 }}
{%- else %}
  {{ with_taxes + 5.0 }}
{%- endif %}
```

---

## Troubleshooting

* **"No slots configured" / "Both X configured" error:** For fields that support both a static value and a dynamic entity (`Number of slots`, `Trigger hour`, `Price limit`, `Flexible` limits, `Time offset`), provide **either** the static value **or** the entity — never both. Leave the static field empty when using an entity.
* **Cheapest Hours sensor stays `off`:** Check that your price source entity has valid data, verify `trigger_hour` has passed, and confirm `price_limit` is not filtering out all slots.
* **Calendar shows no events:** Ensure **Add to calendar** is enabled on the sensor and **Enable calendar** is turned on in `⚙️ Global Settings`.
* **Excess Solar never turns a device `on`:**
  * Verify **Consumption (W)** is greater than `0`.
  * Check that your grid power sensor reports **negative** values during export.
  * Ensure both the master switch and the device's enabled switch are `on`.
  * Check that **Is on schedule entity** is not currently `on`.

  ### Next Steps

- Read the detailed [Parameter & Configuration Reference Guide](docs/reference.md)
- Join the discussion on [GitHub Discussion](https://github.com/kotope/aio_energy_management/discussions)
- Star the project on [GitHub](https://github.com/kotope/aio_energy_management)
- Check blog articles about AIO Energy Management at [creatingsmarthome.com](https://www.creatingsmarthome.com/index.php/tag/aio-energy-management/)

### Support

- Report issues: [GitHub Issues](https://github.com/kotope/aio_energy_management/issues)
- ☕ Support the developer: [Buy Me A Coffee](https://www.buymeacoffee.com/tokorhon)