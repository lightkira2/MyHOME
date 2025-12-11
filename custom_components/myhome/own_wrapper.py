"""Local wrapper around vendored OWNd library."""

from .vendor_own.connection import (
    OWNGateway,
    OWNSession,
    OWNEventSession,
    OWNCommandSession,
)

# Se ti servono altre cose, puoi riesportarle qui:
# from .vendor_own.message import OWNMessage, OWNLightingEvent, ...

# Esportiamo anche __version__ se definita
try:
    from .vendor_own import __version__ as VERSION  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    VERSION = "vendored"
