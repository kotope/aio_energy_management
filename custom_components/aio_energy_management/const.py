"""Constants for Energy Management component."""

DOMAIN = "aio_energy_management"

# Parameters:
# Chepest hours sensor
CONF_ENTSOE_ENTITY = "entsoe_entity"
CONF_NORDPOOL_ENTITY = "nordpool_entity"
CONF_NORDPOOL_OFFICIAL_CONFIG_ENTRY = "nordpool_official_config_entry"
CONF_DATA_PROVIDER_TYPE = "data_provider_type"

# Data provider types
DATA_PROVIDER_NORDPOOL = "nordpool"
DATA_PROVIDER_NORDPOOL_OFFICIAL = "nordpool_official"
DATA_PROVIDER_ENTSOE = "entsoe"
CONF_FIRST_HOUR = "first_hour"
CONF_LAST_HOUR = "last_hour"
CONF_SEQUENTIAL = "sequential"
CONF_STARTING_TODAY = "starting_today"
CONF_NUMBER_OF_HOURS = "number_of_hours"
CONF_NUMBER_OF_SLOTS = "number_of_slots"
CONF_FAILSAFE_STARTING_HOUR = "failsafe_starting_hour"
CONF_INVERSED = "inversed"
CONF_TRIGGER_TIME = "trigger_time"  # DEPRECATED: use trigger_hour instead
CONF_TRIGGER_HOUR = "trigger_hour"
CONF_MAX_PRICE = "max_price"  # DEPRECATED: use price_limit instead
CONF_PRICE_LIMIT = "price_limit"
CONF_CALENDAR = "calendar"
CONF_OFFSET = "offset"
CONF_USE_OFFSET = "use_offset"
CONF_START = "start"
CONF_END = "end"
CONF_HOURS = "hours"
CONF_MINUTES = "minutes"
CONF_TRIGGER = "trigger"
CONF_MTU = "mtu"
CONF_PRICE_MODIFICATIONS = "price_modifications"
CONF_RETENTION_DAYS = "retention_days"
CONF_AREA = "area"

# Optional UI configurations for entity ids
CONF_ALLOW_DYNAMIC_ENTITIES = "allow_dynamic_entities"
CONF_NUMBER_OF_SLOTS_ENTITY = "number_of_slots_entity"
CONF_PRICE_LIMIT_ENTITY = "price_limit_entity"
CONF_TRIGGER_HOUR_ENTITY = "trigger_hour_entity"
CONF_START_HOURS_ENTITY = "start_hours_entity"
CONF_START_MINUTES_ENTITY = "start_minutes_entity"
CONF_END_HOURS_ENTITY = "end_hours_entity"
CONF_END_MINUTES_ENTITY = "end_minutes_entity"

# Entities
CONF_ENTITY_CHEAPEST_HOURS = "cheapest_hours"
CONF_ENTITY_CALENDAR = "calendar"

# Common
CONF_UNIQUE_ID = "unique_id"
CONF_NAME = "name"

# Data
COORDINATOR = "coordinator"

# Excess solar feature
CONF_EXCESS_SOLAR = "excess_solar"
CONF_GRID_POWER_SENSOR = "sensor"
CONF_POWER_DEVICES = "power_devices"
CONF_BUFFER = "buffer"
CONF_IS_FULL = "is_full"
CONF_CONSUMPTION = "consumption"
CONF_PRIORITY = "priority"
CONF_IS_ON_SCHEDULE = "is_on_schedule"
CONF_MINIMUM_PERIOD = "minimum_period"
CONF_TURN_ON_DELAY = "turn_on_delay"
EXCESS_SOLAR_MANAGER = "excess_solar_manager"
EXCESS_SOLAR_SWITCH = "excess_solar_switch"
