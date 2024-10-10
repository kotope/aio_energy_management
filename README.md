# All in One Energy Management for Home Assistant
Purpose of this component is to provide easily configurable energy management for Home Assistant automations.

During the first phase it supports only to find nord pool cheapest hours (or most expensive) per day and automatic calendar creation.
Later AIO Energy Management is planned to integrate into solar forecast to get support for solar energy usage.

Read more detailed information at the [creatingsmarthome.com](https://www.creatingsmarthome.com/?p=3256) blog

## Installation
### Option 1: HACS
- Follow [![Open your Home Assistant instance and open a repositoryinside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=kotope&repository=aio_energy_management&category=integration) and install it
- Restart Home Assistant

  *or*
- Go to `HACS` -> `Integrations`,
- Select `...` from upper right corner,
- Select `Custom repositories`
- Add `https://github.com/kotope/aio_energy_management` and select Category as `Integration`
- Search for `AIO Energy Management` and select it
- Press `Download`
- Restart Home Assistant

### Option 2: Manual
SSH into Home assistant and write the following:
```
cd /config/custom_components
wget -O - https://raw.githubusercontent.com/kotope/aio_energy_management/master/install_to_home_assistant.sh | bash
```

## Features
* Cheapest Hours (or most expensive) - Nord Pool and Entso-E integration support
* Event Calendar

## Cheapest hours sensor (supports nord pool and entso-e integrations)
The cheapest hours configuration will create a binary_sensor type entity that will provide timeframe(s) containing percentually the chepeast hours per day.<br>
Binary sensor will have the state 'on' when cheapest hours is active.<br>
Automations can them be set to follow this sensor 'on' state.
The feature supports failsafe to ensure critical devices to run if for some reason Nord Pool price fetch has failed!

### Nord Pool Prerequisites (if using nord pool)
Installed and configured [Nord Pool integration](https://github.com/custom-components/nordpool)

### Entso-E Prerequisites (if using entso-e)
Installed and configured [Entso-E integration](https://github.com/JaccoR/hass-entso-e)

### Configuration
Configuration is done through configuration.yaml.<br>

Either nordpool_entity or entsoe_entity must be set depending of which integration you want to use.

Configuration parameters are shown below:

| Configuration    | Mandatory | Description |
|------------------|-----------|-------------|
| nordpool_entity  | no       | Entity id of the nord pool integration |
| entsoe_entity    | no       | Entity id of the entso-e integration. This is entso-e **average_price** sensor that provides all extra attributes |
| unique_id        | yes       | Unique id to identify newly created entity |
| name             | yes       | Friendly name of the created entity |
| number_of_hours  | yes       |  Number of hours required to get. Can contain entity_id of dynamic entity to get value from e.g. input_number |
| first_hour       | yes       | starting hour used by cheapest hours calculation. If used 'starting_today' as true, must be AFTER nord pool price publishing. |
| last_hour        | yes       | last hour used by cheapest hours calculation |
| starting_today   | yes       | first_hour should be already on the same day. False if next day calculations only |
| sequential       | yes       | true if trying to calculate sequential cheapet hours timeframe. False if multiple values are acceptable. |
| failsafe_starting_hour | no        | If for some reason nord pool prices can't be fetched before first_hour, use failsafe time to turn the sensor on. If failsafe_starting_hour is not given, the failsafe is disabled for the sensor. |
| inversed         | no        | Want to find expensive hours to avoid? Set to True! default: false |
| trigger_time     | no        | Earliest time to create next cheapest hours. Format: "HH:mm". Useful when waiting for other data to arrive before triggering event creation. Example: 'trigger_time: "19:00"' |
| max_price        | no        | Only accept prices less than given float value (use decimal number as parameter, not int). *Note: given hours might be less than requested if not enough values can be found with given parameters.* Only supported by non-seuqential cheapest_hours. Example: max_price: 5.0 |

### Example configuration
The example configuration presents creation of three sensors: one for **nord pool cheapest three hours**, one for **nord pool most expensive prices** and final one for **entso-e cheapest hours**.
The expensive sensor uses external input_number to get number of hours requested.

```
aio_energy_management:
    cheapest_hours:
      - nordpool_entity: sensor.nordpool
        unique_id: my_cheapest_hours
        name: My Cheapest Hours
        first_hour: 21
        last_hour: 12
        starting_today: true
        number_of_hours: 3
        sequential: false
        failsafe_starting_hour: 1
      - nordpool_entity: sensor.nordpool
        unique_id: my_expensive_hours
        name: Expensive Hours
        first_hour: 0
        last_hour: 22
        starting_today: false
        number_of_hours: input_number.my_input_number
        sequential: false
        failsafe_starting_hour: 1
        inversed: true
      - entsoe_entity: sensor.entsoe_average_price
        unique_id: my_entsoe_cheapest_hours
        name: My Entso-E Cheapest Hours
        first_hour: 21
        last_hour: 10
        starting_today: true
        number_of_hours: 5
        sequential: false
```
## Calendar
Calendar feature will create a new calendar entity to display all upcoming scheduled energy management events.
Also please note that the events can't be modified through the calendar, it's for displaying and automation purposes (for now at least).

### Configuration
Configuration required for energy management calendar:
| Configuration    | Mandatory | Description |
|------------------|-----------|-------------|
| unique_id        | yes       | Unique id to identify newly created entity |
| name             | yes       | Friendly name of the created entity |

### Example configuration
```
aio_energy_management:
  calendar:
    name: Energy Management
    unique_id: energy_management_calendar
```


## Support the developer?
[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/tokorhon)
