# Parameter & Configuration Reference

This document is the complete reference for all parameters, calculation rules, services, and YAML configuration options in **AIO Energy Management**.

For a step-by-step UI walkthrough, see [Getting Started](getting-started.md).

---

## 1. Cheapest Hours Sensor

A Cheapest Hours entry creates a `binary_sensor` that turns `on` during the selected time window(s) and exposes attributes such as `list` (scheduled `{start, end}` blocks), `mean_price`, `min_price`, `max_price`, and `next`.

### Data Provider Parameters

| UI Field | YAML Key | Required | Description |
|---|---|---|---|
| **Nord Pool entity** | `nordpool_entity` | One provider required | Entity ID from the Nord Pool custom integration (e.g. `sensor.nordpool`). |
| **Nord Pool official config entry** | `nordpool_official_config_entry` | One provider required | Config entry ID of the official Home Assistant Nord Pool integration. |
| **Area** | `area` | No | Market area override for the official Nord Pool integration (defaults to the integration's configured area). |
| **Entso-E entity** | `entsoe_entity` | One provider required | Entity ID of the Entso-E **average price** sensor. |
| **Strømligning today entity** | `stromligning_entity` | One provider required | Entity ID of Strømligning today's prices sensor. |
| **Strømligning tomorrow entity** | `stromligning_tomorrow_entity` | With Strømligning | Entity ID of Strømligning tomorrow's prices sensor. |
| **MTU** | `mtu` | No | Market Time Unit in minutes: `15` or `60` (default: `60`). If the provider uses 15-minute slots and `60` is requested, hourly mean prices are calculated. |

### Core Selection Parameters

| UI Field | YAML Key | Required | Description |
|---|---|---|---|
| **Name** | `name` | Yes | Friendly name of the created `binary_sensor`. |
| — *(UI generates automatically)* | `unique_id` | Yes (YAML) | Unique identifier for the entity. |
| **Number of slots** *(static or entity)* | `number_of_slots` | Yes | Number of base slots to select (matching `mtu`). Accepts a static integer or a dynamic entity ID (`sensor` / `input_number`). Leave static field empty in the UI when using an entity. |
| — *(deprecated)* | `number_of_hours` | No | *Deprecated:* use `number_of_slots` instead. |
| **First hour** | `first_hour` | Yes | Start hour of the search window (`0–23`). |
| **Last hour** | `last_hour` | Yes | End hour of the search window (`0–23`). |
| — *(automatic)* | `starting_today` | No | *Deprecated since 0.9.0:* determined automatically from `first_hour` and `last_hour`. |
| **Sequential** | `sequential` | Yes | When `true`, selects a single contiguous block of slots. When `false`, selects individual or grouped blocks across the window. |
| **Inversed** | `inversed` | No | When `true`, selects the **most expensive** slots instead of the cheapest (default: `false`). |
| **Add to calendar** | `calendar` | No | Add scheduled blocks to the Energy Management calendar (default: `true`). |

#### Search Window Rules (`first_hour` & `last_hour`)
* When `last_hour < first_hour`, the window automatically wraps overnight (`last_hour` is on the next day).
* When `last_hour >= first_hour`, the window stays within the same day.
* The total search window cannot exceed **24 hours**.

---

### Price Limits & Flexible Slots

All price comparisons are evaluated **after** `price_modifications` have been applied.

| UI Field | YAML Key | Required | Description |
|---|---|---|---|
| **Price limit** *(static or entity)* | `price_limit` | No | Hard price ceiling for the base `number_of_slots` selection (slots above `price_limit`, or below when `inversed: true`, are excluded). Accepts a static float or a dynamic entity ID. |
| **Flexible: max number of slots** *(static or entity)* | `add_flexible.max_number_of_slots` | With flex | Maximum total number of slots including the base `number_of_slots` (capped at 24 for 60-min MTU and 96 for 15-min MTU). |
| **Flexible: price limit** *(static or entity)* | `add_flexible.price_limit` | With flex¹ | Hard price ceiling (or floor when `inversed: true`) for extra flexible slots beyond `number_of_slots`. |
| **Flexible: max price delta** | `add_flexible.max_price_delta` | With flex¹ | Relative threshold: extra slots are allowed while their price is within `max_price_delta` of the cheapest slot (or most expensive when `inversed: true`) in the search window. |

> ¹ Configure **either** `flexible_price_limit` **or** `max_price_delta` (not both). If both are provided in YAML, `flexible_price_limit` takes precedence.

#### How `price_limit` and Flexible Slots Interact
* **`price_limit`** applies as a hard per-slot filter on the base `number_of_slots` selection. If fewer slots meet `price_limit` than requested, fewer slots (or none) are returned.
* **`flexible_price_limit` / `max_price_delta`** governs extra slots added on top of `number_of_slots` (up to `max_number_of_slots`). The flexible limit is enforced as a hard bound and is never exceeded.
* **When `sequential: true`:** The cheapest contiguous block of `number_of_slots` is selected first (subject to `price_limit`), and then grown one slot at a time at its start or end edge while neighboring slots remain within the flexible limit and search window.
* **When `sequential: false`:** All active rules (`price_limit`, flexible limit, and block size rules) are solved together so the largest feasible set of cheapest slots is chosen without violating any constraint.

---

### Block Grouping Parameters (`sequential: false` only)

| UI Field | YAML Key | Default | Description |
|---|---|---|---|
| **Minimum continuous slots** | `min_seq_slots` | `1` | Minimum length of every selected contiguous block of slots. Ignored when `number_of_blocks` is set. |
| **Number of time blocks** | `number_of_blocks` | — | Divides the selected slots into at most this many separate contiguous blocks. Takes precedence over `min_seq_slots`. |

---

### Time Offset (`sequential: true` only)

> **Breaking change since 1.2.0:** Time offsets are supported **only** on sequential sensors (`sequential: true`). In the UI, the offset step is hidden for non-sequential sensors and reconfiguring clears any legacy offset. In YAML, offsets on non-sequential sensors are ignored with an error log.

Each field accepts either a static integer or a dynamic entity (`sensor` / `input_number`), mutually exclusive:

| UI Field | YAML Key | Range | Description |
|---|---|---|---|
| **Start offset hours** | `offset.start.hours` | Any integer | Hours added to the block start time (negative values start earlier). |
| **Start offset minutes** | `offset.start.minutes` | `0–59` | Minutes added to the block start time. |
| **End offset hours** | `offset.end.hours` | Any integer | Hours added to the block end time. |
| **End offset minutes** | `offset.end.minutes` | `0–59` | Minutes added to the block end time. |

* Note: `mean_price`, `min_price`, and `max_price` attributes reflect the unshifted calculated slots and do not include offset adjustments.

---

### Scheduling, Failsafe & Price Modifications

| UI Field | YAML Key | Description |
|---|---|---|---|
| **Trigger hour** *(static or entity)* | `trigger_hour` | Earliest hour (`0–23`) to calculate the next day's window. Useful when waiting for external sensors or dynamic inputs to update. *(Replaces deprecated `trigger_time`.)* |
| **Failsafe starting hour** | `failsafe_starting_hour` | Fallback hour (`0–23`) to turn the sensor `on` if price data could not be fetched before `first_hour`. Disabled if omitted. |
| **Price modifications** | `price_modifications` | Jinja2 template evaluated per slot before any limits or selection rules run. Exposes `price` (raw slot price) and `time` (slot start `datetime`). |
| **Retention days** | `retention_days` | Number of days of historical events to keep on the calendar (`1–365`, default: `1`). |

---

## 2. Excess Solar

Excess Solar monitors a grid power sensor and controls per-device virtual `binary_sensor` entities based on available export surplus, priority, and minimum on/off durations.

### Global Parameters

| UI Field | YAML Key | Required | Description |
|---|---|---|---|
| **Name** | — | Yes (UI) | Entry name used as prefix for the master switch and device entities. |
| **Grid power sensor** | `sensor` | Yes | `sensor` entity reporting grid power in watts. **Negative values indicate export** (solar surplus). |
| **Buffer** | `buffer` | No (UI: `0`) / Yes (YAML) | Surplus power buffer (W) required before turning devices on, preventing rapid cycling (`0–10000` W). |

### Power Device Parameters

| UI Field | YAML Key | Required | Description |
|---|---|---|---|
| **Device name** | `name` | Yes | Name of the controllable load. |
| **Consumption (W)** | `consumption` | Yes | Expected power draw in watts (`> 0`). Used to determine whether enough surplus exists to activate the device. |
| **Consumption entity** | `consumption_entity` | No | Optional `sensor` reporting live power draw (W) while the device is active. |
| **Priority** | `priority` | No (UI: `100`) / Yes (YAML) | Activation order (`1–999`). **Lower numbers have higher priority** and are turned on first. |
| **Minimum on-period (min)** | `minimum_on_time` | No (UI: `0`) / Yes (YAML) | Minimum time in minutes the device must stay `on` before Excess Solar can turn it `off` (`0–1440`). |
| **Minimum off time (min)** | `minimum_off_time` | No | Minimum time in minutes the device must stay `off` before turning on again (`0–1440`, default: `1` min in UI). |
| **Is on schedule entity** | `is_on_schedule` | No | Optional `binary_sensor` or `input_boolean`. When `on`, Excess Solar leaves the device alone (for example during a Cheapest Hours window). |

---

## 3. Calendar

Both `⚙️ Global Settings` in the UI and `calendar:` in legacy YAML configure the same shared calendar entity.

| UI Field (`⚙️ Global Settings`) | YAML Key (`calendar:`) | Description |
|---|---|---|
| **Enable calendar** | *(presence of `calendar:`)* | Enables or disables the calendar entity. |
| **Calendar name** | `name` | Friendly name of the calendar entity (default: `Energy Management`). |
| *(automatic)* | `unique_id` | Unique ID for the calendar entity in YAML. |

---

## 4. Services

The integration registers two services automatically:

### `aio_energy_management.clear_data`
Clears stored calculation data for a specific Cheapest Hours entry so changes take effect within ~30 seconds instead of waiting for the next trigger cycle.

| Parameter | Required | Description |
|---|---|---|
| `unique_id` | Yes | The `unique_id` of the Cheapest Hours sensor to clear. |

```yaml
service: aio_energy_management.clear_data
data:
  unique_id: my_cheapest_hours
```

### `aio_energy_management.reload_data`
Reloads the integration configuration without restarting Home Assistant. Call `aio_energy_management.clear_data` afterward if cached windows need to be recalculated immediately.

---

## 5. Legacy YAML Configuration & Migration

YAML configuration remains supported for backward compatibility. You can migrate individual entries from YAML to the UI one at a time, as long as the same `unique_id` / entity is not defined in both places simultaneously.

### Full YAML Example

```yaml
aio_energy_management:
  cheapest_hours:
    - nordpool_entity: sensor.nordpool
      unique_id: my_cheapest_hours
      name: My Cheapest Hours
      first_hour: 21
      last_hour: 12
      number_of_slots: 3
      sequential: false
      failsafe_starting_hour: 1

    - nordpool_official_config_entry: 01K07FX4QRHEZW8GHSK3KT1ESY
      unique_id: my_cheapest_hours_tariffs
      name: My Cheapest Hours With Tariffs
      first_hour: 21
      last_hour: 12
      number_of_slots: 5
      sequential: true
      offset:
        start:
          hours: 0
          minutes: 30
        end:
          hours: 1
          minutes: 15
      price_modifications: >
        {%- set as_snt = price / 10.0 %}
        {%- set with_taxes = (as_snt * 1.255) | float %}
        {%- if time.hour >= 22 or time.hour <= 7 %}
          {{ with_taxes + 3.1 }}
        {%- else %}
          {{ with_taxes + 5.0 }}
        {%- endif %}

    - nordpool_entity: sensor.nordpool
      unique_id: my_flexible_cheapest_hours
      name: My Flexible Cheapest Hours
      first_hour: 21
      last_hour: 12
      number_of_slots: 5
      sequential: false
      add_flexible:
        max_number_of_slots: 21
        price_limit: 0.05

  excess_solar:
    sensor: sensor.grid_power
    buffer: 100
    power_devices:
      - name: Water Heater
        consumption: 3000
        consumption_entity: sensor.water_heater_power_consumption
        priority: 1
        minimum_on_time: 5
        is_on_schedule: binary_sensor.my_cheapest_hours
      - name: EV Charger
        consumption: 1000
        priority: 2
        minimum_on_time: 10
        minimum_off_time: 1

  calendar:
    name: Energy Management
    unique_id: energy_management_calendar
```