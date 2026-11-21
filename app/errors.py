"""Errores compartidos que impiden arrancar el servicio."""


class ConfigError(ValueError):
    """Error de configuración que impide arrancar el servicio.

    Los mensajes nunca incluyen valores secretos.
    """
