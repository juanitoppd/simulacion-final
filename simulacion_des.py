"""Simulacion de eventos discretos del sistema M/M/c con SimPy."""

from __future__ import annotations

from dataclasses import dataclass
import random
from statistics import mean

import simpy

from cliente import Cliente
from servidor import ConfiguracionServidores, crear_recurso_tecnicos


TIPOS_SOLICITUD = ("soporte", "mantenimiento", "reclamo")
PRIORIDADES = ("normal", "urgente")


@dataclass
class ResultadoReplica:
    """Resultado detallado de una replica independiente."""

    parametros: dict
    metricas: dict
    clientes_atendidos: list[Cliente]
    serie_tiempo: list[dict]
    tiempos_espera: list[float]
    tiempos_sistema: list[float]


class MonitorSistema:
    """Acumula estadisticas de tiempo despues del periodo warm-up."""

    def __init__(self, env: simpy.Environment, tiempo_simulacion: float, warmup: float):
        self.env = env
        self.tiempo_simulacion = tiempo_simulacion
        self.warmup = warmup
        self.ultimo_tiempo = 0.0
        self.clientes_en_sistema = 0
        self._estado_sistema = 0
        self._estado_cola = 0
        self._estado_ocupados = 0
        self.area_sistema = 0.0
        self.area_cola = 0.0
        self.area_ocupados = 0.0
        self.max_cola = 0
        self.serie_tiempo: list[dict] = [
            {"tiempo": 0.0, "sistema": 0, "cola": 0, "ocupados": 0}
        ]

    def _acumular_hasta(self, tiempo: float) -> None:
        inicio = max(self.ultimo_tiempo, self.warmup)
        fin = min(tiempo, self.tiempo_simulacion)
        if fin > inicio:
            dt = fin - inicio
            self.area_sistema += self._estado_sistema * dt
            self.area_cola += self._estado_cola * dt
            self.area_ocupados += self._estado_ocupados * dt
        self.ultimo_tiempo = tiempo

    def registrar_estado(self, recurso: simpy.Resource) -> None:
        """Registra el estado actual del sistema y actualiza areas."""

        tiempo = float(self.env.now)
        self._acumular_hasta(tiempo)
        self._estado_sistema = self.clientes_en_sistema
        self._estado_cola = len(recurso.queue)
        self._estado_ocupados = len(recurso.users)
        self.max_cola = max(self.max_cola, self._estado_cola)
        self.serie_tiempo.append(
            {
                "tiempo": tiempo,
                "sistema": self._estado_sistema,
                "cola": self._estado_cola,
                "ocupados": self._estado_ocupados,
            }
        )

    def finalizar(self, recurso: simpy.Resource) -> None:
        self.registrar_estado(recurso)
        self._acumular_hasta(self.tiempo_simulacion)


def _crear_cliente(id_cliente: int, tiempo: float, rng: random.Random) -> Cliente:
    return Cliente(
        id_cliente=id_cliente,
        tipo_solicitud=rng.choice(TIPOS_SOLICITUD),
        prioridad=rng.choices(PRIORIDADES, weights=(0.85, 0.15), k=1)[0],
        tiempo_llegada=tiempo,
    )


def _atender_cliente(
    env: simpy.Environment,
    cliente: Cliente,
    recurso: simpy.Resource,
    monitor: MonitorSistema,
    rng: random.Random,
    mu_hora: float,
    clientes_registrados: list[Cliente],
) -> simpy.events.Event:
    req = recurso.request()
    monitor.registrar_estado(recurso)
    yield req

    cliente.iniciar_atencion(float(env.now))
    monitor.registrar_estado(recurso)

    tiempo_servicio = rng.expovariate(mu_hora / 60.0)
    yield env.timeout(tiempo_servicio)

    cliente.finalizar_atencion(float(env.now))
    if cliente.tiempo_llegada >= monitor.warmup:
        clientes_registrados.append(cliente)

    monitor.clientes_en_sistema -= 1
    recurso.release(req)
    monitor.registrar_estado(recurso)


def _generar_llegadas(
    env: simpy.Environment,
    recurso: simpy.Resource,
    monitor: MonitorSistema,
    rng: random.Random,
    lambda_hora: float,
    mu_hora: float,
    tiempo_simulacion: float,
    clientes_registrados: list[Cliente],
) -> simpy.events.Event:
    id_cliente = 0
    tasa_llegada_minuto = lambda_hora / 60.0

    while True:
        yield env.timeout(rng.expovariate(tasa_llegada_minuto))
        if env.now > tiempo_simulacion:
            break

        id_cliente += 1
        cliente = _crear_cliente(id_cliente, float(env.now), rng)
        monitor.clientes_en_sistema += 1
        monitor.registrar_estado(recurso)
        env.process(
            _atender_cliente(
                env, cliente, recurso, monitor, rng, mu_hora, clientes_registrados
            )
        )


def validar_estabilidad(lambda_hora: float, mu_hora: float, servidores: int) -> float:
    """Valida rho < 1 y devuelve el factor de utilizacion teorico."""

    if lambda_hora <= 0 or mu_hora <= 0:
        raise ValueError("Las tasas lambda y mu deben ser mayores que cero.")
    if servidores <= 0:
        raise ValueError("El numero de servidores debe ser mayor que cero.")

    rho = lambda_hora / (servidores * mu_hora)
    if rho >= 1:
        raise ValueError(
            f"Configuracion inestable: rho={rho:.3f}. "
            "Debe cumplirse lambda/(c*mu) < 1."
        )
    return rho


def correr_una_replica(
    lambda_hora: float = 10.0,
    mu_hora: float = 4.0,
    servidores: int = 3,
    tiempo_simulacion: float = 480.0,
    warmup: float = 60.0,
    semilla: int | None = None,
) -> ResultadoReplica:
    """Ejecuta una replica DES del sistema de atencion."""

    rho_teorico = validar_estabilidad(lambda_hora, mu_hora, servidores)
    if warmup < 0 or warmup >= tiempo_simulacion:
        raise ValueError("El warm-up debe estar entre 0 y T_sim.")

    rng = random.Random(semilla)
    env = simpy.Environment()
    configuracion = ConfiguracionServidores(servidores, mu_hora)
    recurso = crear_recurso_tecnicos(env, configuracion)
    monitor = MonitorSistema(env, tiempo_simulacion, warmup)
    clientes_registrados: list[Cliente] = []

    env.process(
        _generar_llegadas(
            env,
            recurso,
            monitor,
            rng,
            lambda_hora,
            mu_hora,
            tiempo_simulacion,
            clientes_registrados,
        )
    )
    env.run()
    monitor.finalizar(recurso)

    tiempos_espera = [
        c.tiempo_espera for c in clientes_registrados if c.tiempo_espera is not None
    ]
    tiempos_sistema = [
        c.tiempo_sistema for c in clientes_registrados if c.tiempo_sistema is not None
    ]
    duracion_observada = tiempo_simulacion - warmup

    metricas = {
        "clientes_atendidos": len(clientes_registrados),
        "tiempo_espera_promedio": mean(tiempos_espera) if tiempos_espera else 0.0,
        "tiempo_sistema_promedio": mean(tiempos_sistema) if tiempos_sistema else 0.0,
        "tiempo_espera_maximo": max(tiempos_espera) if tiempos_espera else 0.0,
        "Lq": monitor.area_cola / duracion_observada,
        "L": monitor.area_sistema / duracion_observada,
        "rho": monitor.area_ocupados / (servidores * duracion_observada),
        "rho_teorico": rho_teorico,
        "cola_maxima": monitor.max_cola,
        "throughput_hora": len(clientes_registrados) / duracion_observada * 60.0,
    }

    parametros = {
        "lambda_hora": lambda_hora,
        "mu_hora": mu_hora,
        "servidores": servidores,
        "tiempo_simulacion": tiempo_simulacion,
        "warmup": warmup,
        "semilla": semilla,
    }

    return ResultadoReplica(
        parametros=parametros,
        metricas=metricas,
        clientes_atendidos=clientes_registrados,
        serie_tiempo=monitor.serie_tiempo,
        tiempos_espera=tiempos_espera,
        tiempos_sistema=tiempos_sistema,
    )
