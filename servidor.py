"""Configuracion de tecnicos para el modelo SimPy."""

from dataclasses import dataclass

import simpy


@dataclass(frozen=True)
class ConfiguracionServidores:
    """Parametros de los tecnicos homogeneos."""

    cantidad: int
    tasa_servicio_hora: float

    @property
    def tasa_servicio_minuto(self) -> float:
        return self.tasa_servicio_hora / 60.0


def crear_recurso_tecnicos(
    env: simpy.Environment, configuracion: ConfiguracionServidores
) -> simpy.Resource:
    """Crea el recurso compartido que representa a los tecnicos."""

    if configuracion.cantidad <= 0:
        raise ValueError("La cantidad de tecnicos debe ser mayor que cero.")
    return simpy.Resource(env, capacity=configuracion.cantidad)
