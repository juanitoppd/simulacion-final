"""Punto de entrada del proyecto de simulacion TechClassUC."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from analitico import comparar_con_simulacion, metricas_mm_c
from montecarlo import correr_replicas
from sensibilidad import barrido_sensibilidad, recomendar_minimo_servidores
from simulacion_des import validar_estabilidad
from visualizacion import generar_graficas, preparar_carpeta_salida


def _parsear_lista_floats(texto: str) -> list[float]:
    return [float(x.strip()) for x in texto.split(",") if x.strip()]


def _imprimir_resumen(resumen: dict, teorico: dict, comparacion: list[dict]) -> None:
    print("\n=== Resumen Montecarlo ===")
    print(f"Replicas: {resumen['parametros']['n']}")
    print(f"lambda: {resumen['parametros']['lambda_hora']} clientes/h")
    print(f"mu: {resumen['parametros']['mu_hora']} clientes/h por tecnico")
    print(f"tecnicos: {resumen['parametros']['servidores']}")

    for clave in ("tiempo_espera_promedio", "tiempo_sistema_promedio", "Lq", "L", "rho"):
        dato = resumen["metricas"][clave]
        print(
            f"{clave}: {dato['media']:.4f} "
            f"(IC95%: {dato['ic95_inf']:.4f}, {dato['ic95_sup']:.4f})"
        )

    print("\n=== Valores analiticos M/M/c ===")
    for clave, valor in teorico.items():
        print(f"{clave}: {valor:.4f}")

    print("\n=== Comparacion simulacion vs analitico ===")
    for fila in comparacion:
        print(
            f"{fila['metrica']}: sim={fila['simulacion']:.4f}, "
            f"analitico={fila['analitico']:.4f}, "
            f"error={fila['error_relativo_pct']:.2f}%"
        )


def _guardar_csv_sensibilidad(resultados: list[dict], carpeta: Path) -> Path:
    ruta = carpeta / "sensibilidad.csv"
    with ruta.open("w", newline="", encoding="utf-8") as archivo:
        campos = [
            "lambda_hora",
            "servidores",
            "estable",
            "rho_teorico",
            "rho_simulado",
            "Wq_promedio",
            "Lq_promedio",
            "cola_maxima",
        ]
        escritor = csv.DictWriter(archivo, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(resultados)
    return ruta


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Simulacion M/M/c para TechClassUC con SimPy y Montecarlo."
    )
    parser.add_argument("--lambda-llegadas", type=float, default=10.0)
    parser.add_argument("--mu-servicio", type=float, default=4.0)
    parser.add_argument("--servidores", type=int, default=3)
    parser.add_argument("--tiempo", type=float, default=480.0)
    parser.add_argument("--warmup", type=float, default=60.0)
    parser.add_argument("--replicas", type=int, default=30)
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--salida", default="resultados")
    parser.add_argument("--lambdas-sensibilidad", default="8,10,12")
    parser.add_argument("--c-min", type=int, default=2)
    parser.add_argument("--c-max", type=int, default=7)
    parser.add_argument("--replicas-sensibilidad", type=int, default=10)
    return parser


def main() -> None:
    args = construir_parser().parse_args()

    validar_estabilidad(args.lambda_llegadas, args.mu_servicio, args.servidores)

    carpeta = preparar_carpeta_salida(args.salida)
    resumen = correr_replicas(
        n=args.replicas,
        lambda_hora=args.lambda_llegadas,
        mu_hora=args.mu_servicio,
        servidores=args.servidores,
        tiempo_simulacion=args.tiempo,
        warmup=args.warmup,
        semilla_base=args.semilla,
    )
    teorico = metricas_mm_c(args.lambda_llegadas, args.mu_servicio, args.servidores)
    comparacion = comparar_con_simulacion(resumen, teorico)

    lambdas = _parsear_lista_floats(args.lambdas_sensibilidad)
    servidores_lista = list(range(args.c_min, args.c_max + 1))
    resultados_sensibilidad = barrido_sensibilidad(
        lambdas_hora=lambdas,
        servidores_lista=servidores_lista,
        mu_hora=args.mu_servicio,
        replicas=args.replicas_sensibilidad,
        tiempo_simulacion=args.tiempo,
        warmup=args.warmup,
        semilla_base=args.semilla + 5000,
    )

    csv_sensibilidad = _guardar_csv_sensibilidad(resultados_sensibilidad, carpeta)
    graficas = generar_graficas(
        resumen,
        resultados_sensibilidad,
        lambdas,
        servidores_lista,
        carpeta,
    )
    recomendacion = recomendar_minimo_servidores(
        resultados_sensibilidad, args.lambda_llegadas, umbral_wq=10.0
    )

    _imprimir_resumen(resumen, teorico, comparacion)
    print("\n=== Recomendacion ===")
    if recomendacion:
        print(
            "Minimo recomendado: "
            f"{recomendacion['servidores']} tecnicos "
            f"con Wq={recomendacion['Wq_promedio']:.2f} min "
            f"para lambda={args.lambda_llegadas:g} clientes/h."
        )
    else:
        print("No se encontro una configuracion con Wq <= 10 min en el barrido.")

    print("\n=== Archivos generados ===")
    print(csv_sensibilidad)
    for ruta in graficas:
        print(ruta)


if __name__ == "__main__":
    main()
