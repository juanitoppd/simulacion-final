"""Punto de entrada del proyecto de simulacion TechClassUC."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from textwrap import dedent

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
        print(
            "  replicas sugeridas para error relativo <= 5%: "
            f"{dato['n_minimo_error_5pct']}"
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


def _guardar_csv_llegadas(replica, carpeta: Path) -> Path:
    """Guarda el rastro de llegadas de la primera replica."""

    ruta = carpeta / "llegadas_clientes.csv"
    clientes_generados = {c.id_cliente: c for c in replica.clientes_generados}
    ids_en_metricas = {c.id_cliente for c in replica.clientes_atendidos}
    campos = [
        "id_cliente",
        "tiempo_llegada",
        "tiempo_entre_llegadas",
        "tipo_solicitud",
        "prioridad",
        "tiempo_inicio_atencion",
        "tiempo_fin_atencion",
        "tiempo_espera",
        "tiempo_servicio",
        "tiempo_sistema",
        "registrado_en_metricas",
    ]
    with ruta.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=campos)
        escritor.writeheader()
        for llegada in replica.llegadas_generadas:
            cliente = clientes_generados.get(llegada["id_cliente"])
            tiempo_servicio = (
                cliente.tiempo_fin_atencion - cliente.tiempo_inicio_atencion
                if cliente
                and cliente.tiempo_fin_atencion is not None
                and cliente.tiempo_inicio_atencion is not None
                else None
            )
            escritor.writerow(
                {
                    **llegada,
                    "tiempo_inicio_atencion": (
                        cliente.tiempo_inicio_atencion if cliente else None
                    ),
                    "tiempo_fin_atencion": (
                        cliente.tiempo_fin_atencion if cliente else None
                    ),
                    "tiempo_espera": cliente.tiempo_espera if cliente else None,
                    "tiempo_servicio": tiempo_servicio,
                    "tiempo_sistema": cliente.tiempo_sistema if cliente else None,
                    "registrado_en_metricas": llegada["id_cliente"] in ids_en_metricas,
                }
            )
    return ruta


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Simulacion M/M/c para TechClassUC con SimPy y Montecarlo.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=dedent(
            """
            Ejemplos:
              py main.py --lambda-llegadas 12 --servidores 4
              py main.py --mu-servicio 5 --tiempo 600 --replicas 50
              py main.py --lambdas-sensibilidad 8,10,12,14 --c-min 2 --c-max 8

            Interpretacion:
              --lambda-llegadas controla que tan frecuente llegan clientes.
              --mu-servicio controla que tan rapido atiende cada tecnico.
              --servidores controla la capacidad paralela del sistema.
            """
        ),
    )
    parser.add_argument(
        "--lambda-llegadas",
        type=float,
        default=10.0,
        help="Tasa promedio de llegada en clientes por hora.",
    )
    parser.add_argument(
        "--mu-servicio",
        type=float,
        default=4.0,
        help="Tasa promedio de servicio por tecnico en clientes por hora.",
    )
    parser.add_argument(
        "--servidores",
        type=int,
        default=3,
        help="Cantidad de tecnicos que atienden en paralelo.",
    )
    parser.add_argument(
        "--tiempo",
        type=float,
        default=480.0,
        help="Duracion de la jornada simulada en minutos.",
    )
    parser.add_argument(
        "--warmup",
        type=float,
        default=60.0,
        help="Minutos iniciales descartados para calcular metricas.",
    )
    parser.add_argument(
        "--replicas",
        type=int,
        default=30,
        help="Cantidad de replicas Montecarlo independientes.",
    )
    parser.add_argument(
        "--semilla",
        type=int,
        default=42,
        help="Semilla base para reproducibilidad.",
    )
    parser.add_argument(
        "--salida",
        default="resultados",
        help="Carpeta donde se guardan CSV y graficas.",
    )
    parser.add_argument(
        "--lambdas-sensibilidad",
        default="8,10,12",
        help="Lista de tasas de llegada para sensibilidad, separadas por coma.",
    )
    parser.add_argument(
        "--c-min",
        type=int,
        default=2,
        help="Minimo numero de tecnicos evaluado en sensibilidad.",
    )
    parser.add_argument(
        "--c-max",
        type=int,
        default=7,
        help="Maximo numero de tecnicos evaluado en sensibilidad.",
    )
    parser.add_argument(
        "--replicas-sensibilidad",
        type=int,
        default=10,
        help="Replicas por escenario del analisis de sensibilidad.",
    )
    parser.add_argument(
        "--umbral-wq",
        type=float,
        default=10.0,
        help="Meta maxima de espera promedio para recomendar tecnicos.",
    )
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
    csv_llegadas = _guardar_csv_llegadas(resumen["replicas"][0], carpeta)
    graficas = generar_graficas(
        resumen,
        resultados_sensibilidad,
        lambdas,
        servidores_lista,
        carpeta,
    )
    recomendacion = recomendar_minimo_servidores(
        resultados_sensibilidad, args.lambda_llegadas, umbral_wq=args.umbral_wq
    )

    _imprimir_resumen(resumen, teorico, comparacion)
    print("\n=== Recomendacion ===")
    if recomendacion:
        print(
            "Minimo recomendado: "
            f"{recomendacion['servidores']} tecnicos "
            f"con Wq={recomendacion['Wq_promedio']:.2f} min "
            f"para lambda={args.lambda_llegadas:g} clientes/h "
            f"y umbral Wq<={args.umbral_wq:g} min."
        )
    else:
        print(
            "No se encontro una configuracion con "
            f"Wq <= {args.umbral_wq:g} min en el barrido."
        )

    print("\n=== Archivos generados ===")
    print(csv_sensibilidad)
    print(csv_llegadas)
    for ruta in graficas:
        print(ruta)


if __name__ == "__main__":
    main()
