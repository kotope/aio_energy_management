# All in One Energy Management for Home Assistant
Purpose of this component is to provide easily configurable energy management for Home Assistant automations.

During the first phase it supports only to find Nord Pool cheapest hours (or most expensive) per day and automatic calendar creation.
Later AIO Energy Management is planned to integrate into solar forecast to get support for solar energy usage.

Read more detailed information at the [creatingsmarthome.com](https://www.creatingsmarthome.com/index.php/tag/aio-energy-management/) blog

## Installation
### Option 1: HACS
- Follow [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=kotope&repository=aio_energy_management&category=integration) and install it
- Restart Home Assistant

  *or*
- Go to `HACS` -> `Integrations`,
- Select `...` from upper right corner,
- Select `Custom repositories`
- Add `https://github.com/kotope/aio_energy_management` and select Type as `Integration`
- Search for `AIO Energy Management` and select it
- Press `Download`
- Restart Home Assistant

### Option 2: Manual
SSH into Home Assistant and write the following:
```
cd /config/custom_components
wget -O - https://raw.githubusercontent.com/kotope/aio_energy_management/master/install_to_home_assistant.sh | bash
```

## Features
* Cheapest Hours (or most expensive) - Nord Pool and Entso-E integration support
* Event Calendar
* Service utility

## Cheapest hours sensor (supports Nord Pool and Entso-E integrations)
The cheapest hours configuration will create a binary_sensor type entity that will provide timeframe(s) containing percentually the cheapest hours per day.<br>
Binary sensor will have the state 'on' when cheapest hours is active.<br>
Automations can then be set to follow this sensor 'on' state.
The feature supports failsafe to ensure critical devices to run if for some reason Nord Pool price fetch has failed!

### Nord Pool Prerequisites (if using Nord Pool custom integration)
Installed and configured [Nord Pool integration](https://github.com/custom-components/nordpool)

### Entso-E Prerequisites (if using Entso-E)
Installed and configured [Entso-E integration](https://github.com/JaccoR/hass-entso-e)

### Nord Pool Official integration Prerequisites (if using Nord Pool official integration)
Installed and configured [Nord Pool official integration](https://www.home-assistant.io/integrations/nordpool/)
#### Getting configuration entry id
- Navigate to Home Assistant settings -> Devices & Services -> Nord Pool integration
- Press '24 entities' link
-> config entry is presented at the end of browser URL field (e.g. http://192.168.1.XXX:8123/config/entities?historyBack=1&config_entry=01JPHC0B39ST11081WFZQCKMVC)

### Configuration
Configuration is done through configuration.yaml.<br>

Either nordpool_entity or entsoe_entity must be set, depending on which integration you want to use.

Configuration parameters are shown below:

| Configuration    | Mandatory | Description |
|------------------|-----------|-------------|
| nordpool_entity  | no       | Entity id of the Nord Pool integration |
| entsoe_entity    | no       | Entity id of the Entso-E integration. This is Entso-E **average_price** sensor that provides all extra attributes |
| nordpool_official_config_entry  | no       | Configuration entry id of Nord Pool official integration |
| unique_id        | yes       | Unique id to identify newly created entity |
| name             | yes       | Friendly name of the created entity |
| number_of_hours  | yes       |  Number of hours required to get. Can contain entity_id of dynamic entity to get value from e.g. input_number |
| first_hour       | yes       | Starting hour used by cheapest hours calculation. If used 'starting_today' as true, must be AFTER Nord Pool price publishing. |
| last_hour        | yes       | Last hour used by cheapest hours calculation |
| starting_today   | yes       | First_hour should be already on the same day. False if next day calculations only |
| sequential       | yes       | True if trying to calculate sequential cheapest hours timeframe. False if multiple values are acceptable. |
| failsafe_starting_hour | no        | If for some reason Nord Pool prices can't be fetched before first_hour, use failsafe time to turn the sensor on. If failsafe_starting_hour is not given, the failsafe is disabled for the sensor. |
| inversed         | no        | Want to find expensive hours to avoid? Set to True! default: false |
| trigger_time     | no        | Earliest time to create next cheapest hours. Format: "HH:mm". Useful when waiting for other data to arrive before triggering event creation. Example: 'trigger_time: "19:00"' **! Deprecated: use trigger_hour instead !** |
| price_limit      | no        | Only accept prices less than given float value or more than given float value if inversed is used. *Note: given hours might be less than requested if not enough values can be found with given parameters.* Only supported by non-sequential cheapest_hours. Can contain entity_id of dynamic entity to get value from e.g. input_number |
| trigger_hour     | no        | Earliest hour to create next cheapest hours.  "HH:mm". Useful when waiting for other data to arrive before triggering event creation. Example: 'trigger_hour: 19'. Can contain entity_id of dynamic entity to get value from e.g. input_number |
| calendar    | no        | Should the entity be added to the calendar. Defaults to true. |
| offset    | no      | Possible start and end offset. On non-sequential the start offset is only added to first item and end offset to last item. Avg/min/max prices does not take the offset into account. See example below. |

### Example configuration
The example configuration presents creation of three sensors: one for **Nord Pool cheapest three hours**, one for **Nord Pool most expensive prices**, one for **Entso-E cheapest hours** and final one for **Nord Pool cheapest hours with offset**

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
        number_of_hours: 4
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
      - nordpool_entity: sensor.nordpool
        unique_id: my_cheapest_hours_offset
        name: My Cheapest Hours With Offset
        first_hour: 21
        last_hour: 10
        starting_today: true
        number_of_hours: 5
        sequential: True
        offset:
          start:
            hours: 0
            minutes: 30
          end:
            hours: 1
            minutes: 15

```
## Calendar
Calendar feature will create a new calendar entity to display all upcoming scheduled energy management events.
Also please note that the events can't be modified through the calendar, it's for displaying and automation purposes (for now at least).

### Configuration
Configuration required for energy management calendar:
| Configuration    | Mandatory | Description |
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

## Service utility
AIO Energy Management integration provides a service utility to be used alongside with other components. For now it only supports to clear cached cheapest hours data.

Service utility is provided automatically with the integration and does not need separate configuration.

### Action: Clear cached data (aio_energy_management.clear_data)
Will clear stored data for specified cheapest hours configuration. Changes will take effect in next 30s when Home Assistant event loop is run. This is especially useful when trying different parameters for cheapest hours: No longer need to wait until next day for changes to effect.

| Parameter        | Description    |
|------------------|----------------|
| unique_id        | unique_id of the item to be cleared. Unique_id should be the same as defined in cheapest_hours configuration entry. |

### Example service call
```
service: aio_energy_management.clear_data
data:
  unique_id: my_cheapest_hours
```

## Full example with Nord Pool cheapest hours, expensive hours and a calendar
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
        number_of_hours: 4
        sequential: false
        failsafe_starting_hour: 1
        inversed: true
  calendar:
    name: Energy Management
    unique_id: energy_management_calendar
```

## Support the developer?
[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/tokorhon)
