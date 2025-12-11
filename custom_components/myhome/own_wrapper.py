"""Local wrapper around vendored OWNd library."""

from .vendor_own.connection import (
    OWNGateway,
    OWNSession,
    OWNEventSession,
    OWNCommandSession,
)
from .vendor_own.message import (
    OWNLightingEvent,
    OWNLightingCommand,
    OWNAutomationEvent,
    OWNAutomationCommand,
    OWNHeatingEvent,
    OWNHeatingCommand,
    CLIMATE_MODE_OFF,
    CLIMATE_MODE_HEAT,
    CLIMATE_MODE_COOL,
    CLIMATE_MODE_AUTO,
    MESSAGE_TYPE_MAIN_TEMPERATURE,
    MESSAGE_TYPE_MAIN_HUMIDITY,
    MESSAGE_TYPE_TARGET_TEMPERATURE,
    MESSAGE_TYPE_LOCAL_OFFSET,
    MESSAGE_TYPE_LOCAL_TARGET_TEMPERATURE,
    MESSAGE_TYPE_MODE,
    MESSAGE_TYPE_MODE_TARGET,
    MESSAGE_TYPE_ACTION,
    OWNDryContactEvent,
    OWNDryContactCommand,
    MESSAGE_TYPE_MOTION,
    MESSAGE_TYPE_PIR_SENSITIVITY,
    MESSAGE_TYPE_MOTION_TIMEOUT,
    MESSAGE_TYPE_ACTIVE_POWER,
    MESSAGE_TYPE_CURRENT_DAY_CONSUMPTION,
    MESSAGE_TYPE_CURRENT_MONTH_CONSUMPTION,
    MESSAGE_TYPE_ENERGY_TOTALIZER,
    MESSAGE_TYPE_ILLUMINANCE,
    MESSAGE_TYPE_SECONDARY_TEMPERATURE,
    OWNEnergyCommand,
    OWNEnergyEvent,
    OWNMessage,
    OWNAuxEvent,
    OWNCENPlusEvent,
    OWNCENEvent,
    OWNGatewayEvent,
    OWNGatewayCommand,
    OWNCommand,
)

from OWNd.discovery import (
    find_gateways
)

# Se ti servono altre cose, puoi riesportarle qui:
# from .vendor_own.message import OWNMessage, OWNLightingEvent, ...

# Esportiamo anche __version__ se definita
try:
    from .vendor_own import __version__ as VERSION  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    VERSION = "vendored"
