# Quick Start - UI Configuration

## 🚀 Getting Started with UI Configuration

### Prerequisites
- Home Assistant installed and running
- AIO Energy Management integration installed (via HACS or manually)
- One of the following price integrations configured:
  - Nord Pool (custom integration)
  - Nord Pool (official integration)
  - Entso-E

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

#### Step 4 — Basic Settings

| Field | Default | Description |
|---|---|---|
| **Name** | `Cheapest Hours` | Friendly name (becomes the entity ID) |
| **Number of slots (static)** | `0` | How many time slots to find; leave `0` to use an entity instead |
| **Number of slots (entity)** | — | Entity (sensor/input_number) to set slots dynamically *(if Allow dynamic entities is on)* |
| **First hour** | `0` | Start of the allowed time window (0–23) |
| **Last hour** | `23` | End of the allowed time window (0–23) |
| **Sequential** | `false` | Require selected slots to be consecutive |

> [!NOTE]
> You must provide **either** a static number of slots greater than 0 **or** a dynamic entity — not both, not neither.

#### Step 5 — Advanced Settings *(all optional)*

| Field | Default | Description |
|---|---|---|
| **Failsafe starting hour** | — | Fallback hour if price data is unavailable |
| **Inversed** | `false` | Find the most expensive hours instead of cheapest |
| **Trigger hour (static)** | — | Earliest hour to recalculate cheapest hours for the next day |
| **Trigger hour (entity)** | — | Entity to set trigger hour dynamically *(mutually exclusive with static)* |
| **Price limit (static)** | — | Only accept hours below this price (or above if Inversed) |
| **Price limit (entity)** | — | Entity to set price limit dynamically *(mutually exclusive with static)* |
| **Add to calendar** | `true` | Show scheduled hours on the energy management calendar |
| **Retention days** | `1` | Days of calendar history to keep (1–365) |
| **Price modifications** | — | Jinja2 template to adjust prices before calculation (e.g. tariffs, taxes) |
| **Configure time offset** | `false` | Enable an extra step to set start/end time offsets |

#### Step 6 — Time Offset *(only shown if "Configure time offset" is enabled)*

Configure how much the on/off times are shifted relative to the calculated slot boundaries.  
Each field accepts a **static integer value** or a **dynamic entity** (mutually exclusive):

| Field | Description |
|---|---|
| **Start offset hours** | Hours to add to the slot start time |
| **Start offset minutes** | Minutes to add to the slot start time (0–59) |
| **End offset hours** | Hours to add to the slot end time |
| **End offset minutes** | Minutes to add to the slot end time (0–59) |

✅ **Done!** Your sensor is now available as `binary_sensor.<name>`.

---

### Option 2: Calendar

> [!IMPORTANT]
> Only **one** calendar entity can be created per Home Assistant instance.

1. Go to **Settings → Devices & Services**
2. Click **"+ Add Integration"** → search for **"AIO Energy Management"**
3. Select **"Calendar"**
4. Enter a **Name** (default: `Energy Management`)

✅ **Done!** Your calendar is now available as `calendar.<name>`.

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
4. Step through the wizard (same steps as initial setup — current values are pre-filled)
5. Submit at the final step

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

---

### Next Steps

- 📖 Read the full [Configuration Flow Guide](CONFIG_FLOW_GUIDE.md)
- 📝 Check the [README](README.md) for detailed documentation
- 💬 Join the discussion on [Home Assistant Community](https://community.home-assistant.io/)
- ⭐ Star the project on [GitHub](https://github.com/kotope/aio_energy_management)

### Support

- 🐛 Report issues: [GitHub Issues](https://github.com/kotope/aio_energy_management/issues)
- ☕ Support the developer: [Buy Me A Coffee](https://www.buymeacoffee.com/tokorhon)
