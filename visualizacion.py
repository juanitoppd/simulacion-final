"""Graficas Matplotlib para el proyecto TechClassUC."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def preparar_carpeta_salida(carpeta: str | Path) -> Path:
    ruta = Path(carpeta)
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def graficar_evolucion_temporal(replica, carpeta: str | Path) -> Path:
    ruta = preparar_carpeta_salida(carpeta) / "evolucion_sistema.png"
    tiempos = [p["tiempo"] for p in replica.serie_tiempo]
    sistema = [p["sistema"] for p in replica.serie_tiempo]
    cola = [p["cola"] for p in replica.serie_tiempo]

    plt.figure(figsize=(10, 5))
    plt.step(tiempos, sistema, where="post", label="Clientes en sistema")
    plt.step(tiempos, cola, where="post", label="Clientes en cola")
    plt.title("Evolucion temporal de clientes en el sistema")
    plt.xlabel("Tiempo (minutos)")
    plt.ylabel("Numero de clientes")
    plt.legend()
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(ruta, dpi=160)
    plt.close()
    return ruta


def graficar_histograma_esperas(esperas: list[float], carpeta: str | Path) -> Path:
    ruta = preparar_carpeta_salida(carpeta) / "histograma_esperas.png"
    plt.figure(figsize=(9, 5))
    plt.hist(esperas, bins=25, color="#2a9d8f", edgecolor="white")
    plt.title("Histograma de tiempos de espera Wq")
    plt.xlabel("Tiempo de espera (minutos)")
    plt.ylabel("Frecuencia")
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(ruta, dpi=160)
    plt.close()
    return ruta


def graficar_capacidad(resultados: list[dict], lambda_base: float, carpeta: str | Path) -> Path:
    ruta = preparar_carpeta_salida(carpeta) / "wq_vs_servidores.png"
    filas = [
        r
        for r in resultados
        if r["lambda_hora"] == lambda_base and r["estable"] and r["Wq_promedio"] is not None
    ]
    filas = sorted(filas, key=lambda r: r["servidores"])
    plt.figure(figsize=(9, 5))
    plt.plot(
        [r["servidores"] for r in filas],
        [r["Wq_promedio"] for r in filas],
        marker="o",
        label=f"lambda={lambda_base:g} clientes/h",
    )
    plt.axhline(10, color="#e76f51", linestyle="--", label="Umbral 10 min")
    plt.title("Tiempo promedio de espera vs. numero de tecnicos")
    plt.xlabel("Tecnicos")
    plt.ylabel("Wq promedio (minutos)")
    plt.xticks([r["servidores"] for r in filas])
    plt.legend()
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(ruta, dpi=160)
    plt.close()
    return ruta


def graficar_rho_vs_lambda(resultados: list[dict], carpeta: str | Path) -> Path:
    ruta = preparar_carpeta_salida(carpeta) / "rho_vs_lambda.png"
    servidores = sorted({r["servidores"] for r in resultados})
    plt.figure(figsize=(9, 5))
    for c in servidores:
        filas = sorted(
            [r for r in resultados if r["servidores"] == c], key=lambda r: r["lambda_hora"]
        )
        plt.plot(
            [r["lambda_hora"] for r in filas],
            [r["rho_teorico"] for r in filas],
            marker="o",
            label=f"c={c}",
        )
    plt.axhline(1, color="#e76f51", linestyle="--", label="Limite estabilidad")
    plt.title("Factor de utilizacion rho vs. tasa de llegada")
    plt.xlabel("Lambda (clientes/hora)")
    plt.ylabel("rho teorico")
    plt.legend()
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(ruta, dpi=160)
    plt.close()
    return ruta


def graficar_distribucion_medias_wq(medias_wq: list[float], carpeta: str | Path) -> Path:
    ruta = preparar_carpeta_salida(carpeta) / "distribucion_medias_wq.png"
    plt.figure(figsize=(9, 5))
    plt.hist(medias_wq, bins=12, color="#457b9d", edgecolor="white")
    plt.title("Distribucion de medias de Wq entre replicas")
    plt.xlabel("Wq promedio por replica (minutos)")
    plt.ylabel("Frecuencia")
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(ruta, dpi=160)
    plt.close()
    return ruta


def graficar_heatmap_wq(
    resultados: list[dict],
    lambdas_hora: list[float],
    servidores_lista: list[int],
    carpeta: str | Path,
) -> Path:
    ruta = preparar_carpeta_salida(carpeta) / "heatmap_wq.png"
    matriz = np.full((len(servidores_lista), len(lambdas_hora)), np.nan)
    for i, c in enumerate(servidores_lista):
        for j, lam in enumerate(lambdas_hora):
            fila = next(
                (
                    r
                    for r in resultados
                    if r["servidores"] == c and r["lambda_hora"] == lam and r["estable"]
                ),
                None,
            )
            if fila:
                matriz[i, j] = fila["Wq_promedio"]

    plt.figure(figsize=(9, 5))
    imagen = plt.imshow(matriz, aspect="auto", cmap="viridis")
    plt.colorbar(imagen, label="Wq promedio (minutos)")
    plt.xticks(range(len(lambdas_hora)), [f"{x:g}" for x in lambdas_hora])
    plt.yticks(range(len(servidores_lista)), [str(c) for c in servidores_lista])
    plt.title("Heatmap de Wq por lambda y tecnicos")
    plt.xlabel("Lambda (clientes/hora)")
    plt.ylabel("Tecnicos")

    for i in range(len(servidores_lista)):
        for j in range(len(lambdas_hora)):
            valor = matriz[i, j]
            texto = "inestable" if np.isnan(valor) else f"{valor:.1f}"
            plt.text(j, i, texto, ha="center", va="center", color="white", fontsize=8)

    plt.tight_layout()
    plt.savefig(ruta, dpi=160)
    plt.close()
    return ruta


def generar_graficas(
    resumen_mc: dict,
    resultados_sensibilidad: list[dict],
    lambdas_hora: list[float],
    servidores_lista: list[int],
    carpeta: str | Path = "resultados",
) -> list[Path]:
    """Genera todas las graficas requeridas por el proyecto."""

    replica_representativa = resumen_mc["replicas"][0]
    lambda_base = resumen_mc["parametros"]["lambda_hora"]
    rutas = [
        graficar_evolucion_temporal(replica_representativa, carpeta),
        graficar_histograma_esperas(resumen_mc["todos_los_tiempos_espera"], carpeta),
        graficar_capacidad(resultados_sensibilidad, lambda_base, carpeta),
        graficar_rho_vs_lambda(resultados_sensibilidad, carpeta),
        graficar_distribucion_medias_wq(resumen_mc["medias_wq"], carpeta),
        graficar_heatmap_wq(resultados_sensibilidad, lambdas_hora, servidores_lista, carpeta),
    ]
    return rutas
