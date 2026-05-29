"""Ejecucion de replicas Montecarlo e intervalos de confianza."""

from __future__ import annotations

from math import ceil, sqrt
from statistics import mean, stdev

from simulacion_des import ResultadoReplica, correr_una_replica


METRICAS_RESUMEN = (
    "clientes_atendidos",
    "tiempo_espera_promedio",
    "tiempo_sistema_promedio",
    "tiempo_espera_maximo",
    "Lq",
    "L",
    "rho",
    "cola_maxima",
    "throughput_hora",
)


def _resumir_valores(valores: list[float], confianza: float = 0.95) -> dict:
    z = 1.96 if confianza == 0.95 else 1.96
    n = len(valores)
    media = mean(valores) if valores else 0.0
    desviacion = stdev(valores) if n > 1 else 0.0
    error = z * desviacion / sqrt(n) if n > 1 else 0.0
    n_minimo = (
        ceil((z * desviacion / (0.05 * abs(media))) ** 2)
        if n > 1 and media != 0
        else n
    )
    return {
        "media": media,
        "desviacion": desviacion,
        "ic95_inf": media - error,
        "ic95_sup": media + error,
        "error_absoluto": error,
        "n_minimo_error_5pct": n_minimo,
    }


def correr_replicas(
    n: int = 30,
    lambda_hora: float = 10.0,
    mu_hora: float = 4.0,
    servidores: int = 3,
    tiempo_simulacion: float = 480.0,
    warmup: float = 60.0,
    semilla_base: int = 42,
) -> dict:
    """Ejecuta N replicas independientes y resume las metricas."""

    if n <= 0:
        raise ValueError("El numero de replicas debe ser mayor que cero.")

    replicas: list[ResultadoReplica] = []
    for i in range(n):
        replicas.append(
            correr_una_replica(
                lambda_hora=lambda_hora,
                mu_hora=mu_hora,
                servidores=servidores,
                tiempo_simulacion=tiempo_simulacion,
                warmup=warmup,
                semilla=semilla_base + i,
            )
        )

    resumen_metricas = {}
    for metrica in METRICAS_RESUMEN:
        valores = [float(rep.metricas[metrica]) for rep in replicas]
        resumen_metricas[metrica] = _resumir_valores(valores)

    return {
        "parametros": {
            "n": n,
            "lambda_hora": lambda_hora,
            "mu_hora": mu_hora,
            "servidores": servidores,
            "tiempo_simulacion": tiempo_simulacion,
            "warmup": warmup,
            "semilla_base": semilla_base,
        },
        "metricas": resumen_metricas,
        "replicas": replicas,
        "medias_wq": [
            rep.metricas["tiempo_espera_promedio"] for rep in replicas
        ],
        "todos_los_tiempos_espera": [
            espera for rep in replicas for espera in rep.tiempos_espera
        ],
    }
