"""Local wrapper around OWNd (prefer pip package, fallback to vendored copy)."""

from .const import LOGGER

# ============================================================
# 1) PROVA A USARE OWNd INSTALLATO (site-packages)
# ============================================================

try:
    import OWNd  # type: ignore[import]
    from OWNd.connection import (  # type: ignore[import]
        OWNGateway as _BaseOWNGateway,
        OWNSession as _BaseOWNSession,
        OWNEventSession as _BaseOWNEventSession,
        OWNCommandSession as _BaseOWNCommandSession,
    )
    from OWNd.message import (  # type: ignore[import]
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
    from OWNd.discovery import find_gateways  # type: ignore[import]

    try:
        VERSION = getattr(OWNd, "__version__", "unknown (pip)")
    except Exception:  # pragma: no cover
        VERSION = "unknown (pip)"

    LOGGER.warning("OWNd (pip) via own_wrapper, version=%s", VERSION)

    # ---- Wrapper / sottoclassi per aggiungere il logger di HA ----

    class OWNGateway(_BaseOWNGateway):
        """Alias diretto della OWNGateway di OWNd."""
        pass

    class OWNSession(_BaseOWNSession):
        """Wrapper di OWNSession di OWNd che assicura un logger valido."""

        def __init__(
            self,
            gateway: _BaseOWNGateway = None,
            connection_type: str = "test",
            logger=None,
        ):
            # Se non viene passato un logger, usiamo quello dell'integrazione
            super().__init__(
                gateway=gateway,
                connection_type=connection_type,
                logger=logger or LOGGER,
            )

        @classmethod
        async def test_gateway(cls, gateway: _BaseOWNGateway) -> dict:
            """Replica la logica originale ma usando *questa* classe."""
            connection = cls(
                gateway=gateway,
                connection_type="test",
                logger=LOGGER,
            )
            return await connection.test_connection()

    class OWNEventSession(_BaseOWNEventSession):
        """Wrapper di OWNEventSession che forza l'uso di un logger valido."""

        def __init__(self, gateway: _BaseOWNGateway = None, logger=None):
            super().__init__(
                gateway=gateway,
                logger=logger or LOGGER,
            )

    class OWNCommandSession(_BaseOWNCommandSession):
        """Wrapper di OWNCommandSession che forza l'uso di un logger valido."""

        def __init__(self, gateway: _BaseOWNGateway = None, logger=None):
            super().__init__(
                gateway=gateway,
                logger=logger or LOGGER,
            )

except ImportError:
    # ============================================================
    # 2) SE OWNd NON È INSTALLATO: USA LA COPIA VENDOR_OWN
    # ============================================================

    LOGGER.debug(
        "OWNd wrapper: OWNd not found in site-packages, using vendored copy"
    )

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

    from .vendor_own.discovery import find_gateways

    try:
        from .vendor_own import __version__ as VERSION  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover
        VERSION = "vendored"

    LOGGER.warning("OWNd via own_wrapper (vendored), version=%s", VERSION)
