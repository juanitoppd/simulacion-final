"""Entidad cliente para el sistema de atencion TechClassUC."""

from dataclasses import dataclass


@dataclass
class Cliente:
    """Solicitud que llega al centro de soporte."""

    id_cliente: int
    tipo_solicitud: str
    prioridad: str
    tiempo_llegada: float
    tiempo_inicio_atencion: float | None = None
    tiempo_fin_atencion: float | None = None

    def iniciar_atencion(self, tiempo: float) -> None:
        self.tiempo_inicio_atencion = tiempo

    def finalizar_atencion(self, tiempo: float) -> None:
        self.tiempo_fin_atencion = tiempo

    @property
    def tiempo_espera(self) -> float | None:
        if self.tiempo_inicio_atencion is None:
            return None
        return self.tiempo_inicio_atencion - self.tiempo_llegada

    @property
    def tiempo_sistema(self) -> float | None:
        if self.tiempo_fin_atencion is None:
            return None
        return self.tiempo_fin_atencion - self.tiempo_llegada
