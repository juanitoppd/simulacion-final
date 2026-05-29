"""Formulas cerradas del modelo M/M/c."""

from __future__ import annotations

from math import factorial

from simulacion_des import validar_estabilidad


def metricas_mm_c(lambda_hora: float, mu_hora: float, servidores: int) -> dict:
    """Calcula P0, Lq, Wq, L y W para un sistema M/M/c estable."""

    rho = validar_estabilidad(lambda_hora, mu_hora, servidores)
    a = lambda_hora / mu_hora
    suma = sum((a**n) / factorial(n) for n in range(servidores))
    ultimo = (a**servidores) / (factorial(servidores) * (1.0 - rho))
    p0 = 1.0 / (suma + ultimo)
    lq = (
        p0
        * (a**servidores)
        * rho
        / (factorial(servidores) * (1.0 - rho) ** 2)
    )
    wq_horas = lq / lambda_hora
    w_horas = wq_horas + (1.0 / mu_hora)
    l = lambda_hora * w_horas

    return {
        "rho": rho,
        "P0": p0,
        "Lq": lq,
        "Wq": wq_horas * 60.0,
        "L": l,
        "W": w_horas * 60.0,
    }


def comparar_con_simulacion(resumen_mc: dict, teorico: dict) -> list[dict]:
    """Compara las medias simuladas contra las metricas analiticas."""

    equivalencias = {
        "Wq": "tiempo_espera_promedio",
        "W": "tiempo_sistema_promedio",
        "Lq": "Lq",
        "L": "L",
        "rho": "rho",
    }
    filas = []
    for metrica_teorica, metrica_simulada in equivalencias.items():
        sim = resumen_mc["metricas"][metrica_simulada]["media"]
        teo = teorico[metrica_teorica]
        error = abs(sim - teo) / abs(teo) * 100.0 if teo != 0 else 0.0
        filas.append(
            {
                "metrica": metrica_teorica,
                "simulacion": sim,
                "analitico": teo,
                "error_relativo_pct": error,
            }
        )
    return filas
