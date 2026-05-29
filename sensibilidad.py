"""Analisis de sensibilidad variando lambda y numero de tecnicos."""

from __future__ import annotations

from simulacion_des import validar_estabilidad
from montecarlo import correr_replicas


def barrido_sensibilidad(
    lambdas_hora: list[float],
    servidores_lista: list[int],
    mu_hora: float = 4.0,
    replicas: int = 10,
    tiempo_simulacion: float = 480.0,
    warmup: float = 60.0,
    semilla_base: int = 1000,
) -> list[dict]:
    """Ejecuta Montecarlo para cada combinacion (lambda, c)."""

    resultados: list[dict] = []
    indice = 0
    for c in servidores_lista:
        for lambda_hora in lambdas_hora:
            indice += 1
            try:
                rho_teorico = validar_estabilidad(lambda_hora, mu_hora, c)
                resumen = correr_replicas(
                    n=replicas,
                    lambda_hora=lambda_hora,
                    mu_hora=mu_hora,
                    servidores=c,
                    tiempo_simulacion=tiempo_simulacion,
                    warmup=warmup,
                    semilla_base=semilla_base + indice * 100,
                )
                resultados.append(
                    {
                        "lambda_hora": lambda_hora,
                        "servidores": c,
                        "estable": True,
                        "rho_teorico": rho_teorico,
                        "rho_simulado": resumen["metricas"]["rho"]["media"],
                        "Wq_promedio": resumen["metricas"][
                            "tiempo_espera_promedio"
                        ]["media"],
                        "Lq_promedio": resumen["metricas"]["Lq"]["media"],
                        "cola_maxima": resumen["metricas"]["cola_maxima"]["media"],
                    }
                )
            except ValueError:
                resultados.append(
                    {
                        "lambda_hora": lambda_hora,
                        "servidores": c,
                        "estable": False,
                        "rho_teorico": lambda_hora / (c * mu_hora),
                        "rho_simulado": None,
                        "Wq_promedio": None,
                        "Lq_promedio": None,
                        "cola_maxima": None,
                    }
                )
    return resultados


def recomendar_minimo_servidores(
    resultados: list[dict], lambda_objetivo: float, umbral_wq: float = 10.0
) -> dict | None:
    """Busca el menor c con Wq promedio menor o igual al umbral."""

    candidatos = [
        fila
        for fila in resultados
        if fila["estable"]
        and fila["lambda_hora"] == lambda_objetivo
        and fila["Wq_promedio"] is not None
        and fila["Wq_promedio"] <= umbral_wq
    ]
    if not candidatos:
        return None
    return min(candidatos, key=lambda fila: fila["servidores"])
