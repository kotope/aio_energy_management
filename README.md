# All in One Energy Management for Home Assistant

All in One Energy Management (`aio_energy_management`) provides configurable energy automation helpers for Home Assistant:

* **Cheapest (or Most Expensive) Hours** — finds optimal 15-minute or hourly slots using Nord Pool (custom & official), Entso-E, or Strømligning price data.
* **Excess Solar** — routes surplus solar export to controllable devices based on priority and power consumption.
* **Energy Management Calendar** — automatically displays scheduled windows on a Home Assistant calendar entity.
* **Service Utilities** — clear cached calculations or reload configuration without restarting Home Assistant.

Read more background articles on [creatingsmarthome.com](https://www.creatingsmarthome.com/index.php/tag/aio-energy-management/).

---

## Documentation

* **[Getting Started (UI Setup Guide)](docs/getting-started.md)** — step-by-step walkthrough for setting up Cheapest Hours, Excess Solar, and Global Settings through the Home Assistant UI.
* **[Parameter & Configuration Reference](docs/reference.md)** — complete reference of all parameters, pricing rules, block options, services, and legacy YAML configuration.

---

## Installation

### Option 1: HACS (Recommended)

1. Open HACS in Home Assistant using the button below, or add `https://github.com/kotope/aio_energy_management` as a custom repository (Type: **Integration**):

   [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=kotope&repository=aio_energy_management&category=integration)

2. Search for **AIO Energy Management** and click **Download**.
3. Restart Home Assistant.

### Option 2: Manual

SSH into your Home Assistant instance and run:

```bash
cd /config/custom_components
wget -O - https://raw.githubusercontent.com/kotope/aio_energy_management/master/install_to_home_assistant.sh | bash
```

Restart Home Assistant after installation.

---

## Prerequisites

Depending on the features you want to use, configure one of the following integrations first:

* **Nord Pool (custom):** [custom-components/nordpool](https://github.com/custom-components/nordpool)
* **Nord Pool (official):** [Home Assistant Nord Pool integration](https://www.home-assistant.io/integrations/nordpool/)
* **Entso-E:** [JaccoR/hass-entso-e](https://github.com/JaccoR/hass-entso-e)
* **Strømligning:** [MTrab/stromligning](https://github.com/MTrab/stromligning)
* **Excess Solar:** a grid import/export power `sensor` where **negative values represent solar export**.

---

## Quick Start

1. Go to **Settings → Devices & Services → + Add Integration**.
2. Search for **AIO Energy Management**.
3. Choose **Cheapest hours sensor** or **Excess solar** and follow the setup wizard.
4. To fine-tune advanced options (such as price limits, flexible slots, block sizes, or time offsets), open the created entry and click **Configure**.

For full step-by-step instructions, see [docs/getting-started.md](docs/getting-started.md).

---

## Support & Contributing

* **Issues & Bug Reports:** [GitHub Issues](https://github.com/kotope/aio_energy_management/issues)
* **Discussions:** [GitHub Discussions](https://github.com/kotope/aio_energy_management/discussions)
* **Support the Developer:**

  [!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/tokorhon)