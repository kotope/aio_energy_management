"""Constants for Energy Management component."""

DOMAIN = "aio_energy_management"

# Parameters:
# Chepest hours sensor
CONF_ENTSOE_ENTITY = "entsoe_entity"
CONF_NORDPOOL_ENTITY = "nordpool_entity"
CONF_FIRST_HOUR = "first_hour"
CONF_LAST_HOUR = "last_hour"
CONF_SEQUENTIAL = "sequential"
CONF_STARTING_TODAY = "starting_today"
CONF_NUMBER_OF_HOURS = "number_of_hours"
CONF_FAILSAFE_STARTING_HOUR = "failsafe_starting_hour"
CONF_INVERSED = "inversed"
CONF_TRIGGER_TIME = "trigger_time"  # DEPRECATED: use trigger_hour instead
CONF_TRIGGER_HOUR = "trigger_hour"
CONF_MAX_PRICE = "max_price"  # DEPRECATED: use price_limit instead
CONF_PRICE_LIMIT = "price_limit"
CONF_CALENDAR = "calendar"

# Entities
CONF_ENTITY_CHEAPEST_HOURS = "cheapest_hours"
CONF_ENTITY_CALENDAR = "calendar"

# Common
CONF_UNIQUE_ID = "unique_id"
CONF_NAME = "name"

# Data
COORDINATOR = "coordinator"
