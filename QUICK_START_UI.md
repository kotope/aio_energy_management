# Quick Start - UI Configuration

## 🚀 Getting Started with UI Configuration

### Prerequisites
- Home Assistant installed and running
- AIO Energy Management integration installed (via HACS or manually)
- **Cheapest hours path:** one of the following price integrations configured:
  - Nord Pool (custom integration)
  - Nord Pool (official integration)
  - Entso-E
  - Strømligning
- **Excess solar path:** a `sensor` entity for **grid import/export power** (the integration expects **negative** values when you export solar to the grid)

---

### Configuring Global Settings

Every installation will have **one** `⚙️ Global Settings` identity for overarching configurations. This identity will be recreated at system startup if removed.
- **Enable calendar** - Enable or disable the calendar feature. Disabling this will remove the calendar identity and it's functionality.
- **Calendar name** - Provide a user-friendly name for the calendar. Defaults to `Energy Management`.

---

### Option 1: Cheapest Hours Sensor

The cheapest hours sensor is added through a **multi-step wizard**:

#### Step 1 — Add Integration
- Go to **Settings → Devices & Services**
- Click **"+ Add Integration"**
- Search for **"AIO Energy Management"**
- Select **"Cheapest hours sensor"**

#### Step 2 — Select Data Provider
Choose the integration that provides electricity price data:

| Option | Description |
|---|---|
| **Nord Pool** | Uses a sensor entity from the Nord Pool custom integration |
| **Nord Pool official** | Uses a config entry from the Nord Pool official integration |
| **Entso-E** | Uses an average price sensor from the Entso-E integration |
| **Strømligning** | Uses a sensor from the Strømligning integration |

#### Step 3 — Configure Price Source
Depending on the provider selected above, fill in:

**Nord Pool (custom)**
- **Nord Pool entity** — sensor entity from Nord Pool custom integration
- **MTU** — market time unit: `15` or `60` minutes (default: 60)
- **Allow dynamic entities** — enable entity-based inputs in later steps

**Nord Pool (official)**
- **Nord Pool official config entry** — select from dropdown
- **Area** — (optional) market area
- **MTU** — `15` or `60` minutes (default: 60)
- **Allow dynamic entities** — enable entity-based inputs in later steps

**Entso-E**
- **Entso-E entity** — average price sensor entity
- **MTU** — `15` or `60` minutes (default: 60)
- **Allow dynamic entities** — enable entity-based inputs in later steps

**Strømligning**
- **Strømligning today entity** — select from dropdown
- **Strømligning tomorrow entity** — select from dropdown
- **MTU** — `15` or `60` minutes (default: 60)

#### Step 4 — Basic Settings

| Field | Default | Description |
|---|---|---|
| **Name** | `Cheapest Hours` | Friendly name (becomes the entity ID) |
| **Number of slots (static)** | `0` | How many time slots to find; leave `0` to use an entity instead |
| **First hour** | `0` | Start of the allowed time window (0–23) |
| **Last hour** | `23` | End of the allowed time window (0–23) |
| **Sequential** | `false` | Require selected slots to be consecutive |
| **Add to calendar** | `true` | Show scheduled hours on the energy management calendar |
| **Inversed** | `false` | Find the most expensive hours instead of cheapest |
| **Number of slots (entity)** | — | Entity (sensor/input_number) to set slots dynamically |

✅ **Done!** Your sensor is now available as `binary_sensor.<name>`.

> [!NOTE]
> You must provide **either** a static number of slots greater than 0 **or** a dynamic entity — not both, not neither.

> [!NOTE]
> Advanced settings and Time Offset will **NOT** be shown during the first time wizard. They can be adapted by configuring the sensor afterwards!

#### Advanced Settings *(all optional)*

| Field | Default | Description |
|---|---|---|
| **Failsafe starting hour** | — | Fallback hour if price data is unavailable |
| **Trigger hour (static)** | — | Earliest hour to recalculate cheapest hours for the next day |
| **Price limit (static)** | — | Only accept hours below this price (or above if Inversed) |
| **Flexbile: price limit** | — | Only add extra slots whose price is below this value (or above if inversed). Requires the max number of slots |
| **Flexbile: max number of slots**| — | Add up to this many extra slots on top of the base number of slots while each extra slot stays within the flexible price limit (non-sequential only). Requires the flexible price limit |
| **Minimum continuous slots** |—| Enforce a number of continuous slots |
| **Number of time blocks** |—| Divides the number of slots over the given number of blocks in order to get multiple blocks a day |
| **Retention days** | `1` | Days of calendar history to keep (1–365) |
| **Price modifications** | — | Jinja2 template to adjust prices before calculation (e.g. tariffs, taxes) |
| **Trigger hour (entity)** | — | Entity to set `trigger hour` dynamically *(mutually exclusive with static)* |
| **Price limit (entity)** | — | Entity to set `price limit` dynamically *(mutually exclusive with static)* |
| **Flexbile: price limit (entity)** | — | Entity to set `Flexbile: price limit` dynamically *(mutually exclusive with static)* |
| **Flexbile: max number of slots (entity)**| — | Entity to set `Flexbile: max number of slots` dynamically *(mutually exclusive with static)* |

#### Time Offset *(all optional)*

Configure how much the on/off times are shifted relative to the calculated slot boundaries.
Each field accepts a **static integer value** or a **dynamic entity** (mutually exclusive):

| Field | Description |
|---|---|
| **Start offset hours** | Hours to add to the slot start time |
| **Start offset minutes** | Minutes to add to the slot start time (0–59) |
| **End offset hours** | Hours to add to the slot end time |
| **End offset minutes** | Minutes to add to the slot end time (0–59) |

---

### Option 2: Excess solar

Excess solar drives **binary sensors** (one per configured device) when your grid meter shows enough **export**; you wire real devices with automations. You can add **several** excess solar entries if you need separate setups.

#### Step 1 — Add integration
- **Settings → Devices & Services** → **+ Add Integration** → **AIO Energy Management**
- Choose **Excess solar**

#### Step 2 — Global settings

| Field | Description |
|---|---|
| **Name** | Title for this entry (master switch and device names use it) |
| **Grid power sensor** | `sensor` for grid power; **negative = solar export** |
| **Buffer** | Extra watts of surplus required before turning anything on (default `0`) |

#### Step 3 — Each power device

Configure at least one device. Fields you will use most:

| Field | Tips |
|---|---|
| **Device name** | Shown in entity names |
| **Consumption (W)** | **Must be greater than 0** or this device is never activated (expected load for budgeting) |
| **Priority** | Lower number = turned on first (default `100`) |
| **Consumption entity** | Optional live watts while running |
| **Is on schedule entity** | Optional; when `on`, excess solar leaves that device alone (for example cheapest-hours windows) |
| **Minimum on-period / off time** | Optional short-cycle protection (minutes) |

#### Step 4 — Add another device?
- Toggle **Add another device** to repeat Step 3, or finish the wizard.

#### What you get
- **`binary_sensor`** per device — automate your real `switch` / `climate` / etc. from these
- **`number`** per device — change **priority** from the UI
- **Master switch** — disables the whole excess solar manager for this entry
- **Per-device enabled switches** — temporarily exclude one load

✅ **Done!** Open **Developer tools → States** and filter by your entry name to find the new entities.

---

### Common Sensor Configurations

#### 🌙 Night Charging (Sequential)
```
Number of slots: 6   First hour: 22   Last hour: 8
Sequential: Yes      Use case: EV charging, water heater
```

#### 💰 Best Prices (Non-Sequential)
```
Number of slots: 4   First hour: 0   Last hour: 23
Sequential: No       Use case: Dishwasher, washing machine
```

#### 🔥 Avoid Expensive Hours
```
Number of slots: 3   First hour: 0   Last hour: 23
Sequential: No       Inversed: Yes   Use case: Avoid peak prices
```

#### ☀️ Excess solar (example)
```
Grid sensor: negative when exporting
Buffer: 100–300 W     Device consumption (W): match real load (e.g. 3000)
Priority: lower = first   Optional: is_on_schedule → cheapest hours binary
```

#### 🏠 With Tariffs (Price Modifications template)
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

### Using Your Sensors

#### In Automations
```yaml
automation:
  - alias: "Start dishwasher during cheap hours"
    trigger:
      - platform: state
        entity_id: binary_sensor.cheapest_hours
        to: "on"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.dishwasher
```

**Excess solar:** each device gets a **binary sensor** whose friendly name is `"{entry name} {device name}"` — copy the exact **entity ID** from **Developer tools → States**. Turn the real load **on** when that sensor is `on` and **off** when it is `off`; you can add conditions using the master switch and per-device enabled switches.

#### In Scripts
```yaml
script:
  charge_ev:
    sequence:
      - condition: state
        entity_id: binary_sensor.cheapest_hours
        state: "on"
      - service: switch.turn_on
        target:
          entity_id: switch.ev_charger
```

#### In Templates
```yaml
sensor:
  - platform: template
    sensors:
      charging_status:
        value_template: >
          {% if is_state('binary_sensor.cheapest_hours', 'on') %}
            Charging
          {% else %}
            Waiting
          {% endif %}
```

---

### Modifying Configuration

1. Go to **Settings → Devices & Services**
2. Find **"AIO Energy Management"**
3. Click **"Configure"** on the entry you want to change
4. **Cheapest hours:** choose whatever setting you would like to change:
 - Price data provider
 - Basic settings
 - Advanced settings
 - Time offset
5. **Excess solar:** pick **Edit global settings**, **Add a device**, or **Remove device(s)** from the menu, then submit

Changes take effect immediately!

---

### Troubleshooting

**Sensor not updating?**
- Check that your price source entity has data
- Verify the trigger hour has passed
- Check Home Assistant logs

**Calendar empty?**
- Ensure **Add to calendar** is enabled on your sensor(s)
- Verify a calendar entity has been created
- Check that sensors have calculated hours

**Can't find integration?**
- Restart Home Assistant after installation
- Clear browser cache
- Check that the integration is in the `custom_components` folder

**"Already configured" error when adding a calendar?**
- Only one calendar entity is allowed; it already exists. Find it under your existing AIO Energy Management entries.

**Excess solar never activates?**
- Set **Consumption (W)** above zero for each device
- Confirm the grid sensor goes **negative** when you export solar
- Check the **master** and **enabled** switches for that entry

---

### Next Steps

- 📖 Read the full [Configuration Flow Guide](CONFIG_FLOW_GUIDE.md)
- 📝 Check the [README](README.md) for detailed documentation
- 💬 Join the discussion on [GitHub Discussion](https://github.com/kotope/aio_energy_management/discussions)
- ⭐ Star the project on [GitHub](https://github.com/kotope/aio_energy_management)
- 📖 Check blog articles about AIO Energy Management at [creatingsmarthome.com](https://www.creatingsmarthome.com/index.php/tag/aio-energy-management/)

### Support

- 🐛 Report issues: [GitHub Issues](https://github.com/kotope/aio_energy_management/issues)
- ☕ Support the developer: [Buy Me A Coffee](https://www.buymeacoffee.com/tokorhon)
