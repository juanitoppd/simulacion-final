from __future__ import annotations

import html
import os
import sys
import time
from pathlib import Path

from flask import Flask
from flask import Response
from flask import request
from flask import send_from_directory


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
PORT = int(os.environ.get("PORT", "8000"))

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analitico import comparar_con_simulacion, metricas_mm_c  # noqa: E402
from main import (  # noqa: E402
    _asegurar_lambda_base,
    _guardar_csv_llegadas,
    _guardar_csv_sensibilidad,
    _parsear_lista_floats,
)
from montecarlo import correr_replicas  # noqa: E402
from sensibilidad import barrido_sensibilidad, recomendar_minimo_servidores  # noqa: E402
from simulacion_des import validar_estabilidad  # noqa: E402
from visualizacion import generar_graficas, preparar_carpeta_salida  # noqa: E402


app = Flask(__name__)

GRAFICAS = [
    ("evolucion_sistema.png", "Evolucion del sistema"),
    ("histograma_esperas.png", "Histograma de esperas"),
    ("wq_vs_servidores.png", "Espera promedio vs tecnicos"),
    ("rho_vs_lambda.png", "Utilizacion vs clientes/hora"),
]

DEFAULTS = {
    "lambda_llegadas": "10",
    "mu_servicio": "4",
    "servidores": "3",
    "tiempo": "480",
    "warmup": "60",
    "replicas": "20",
    "semilla": "42",
    "lambdas_sensibilidad": "8,10,12",
    "c_min": "2",
    "c_max": "6",
    "replicas_sensibilidad": "6",
    "umbral_wq": "10",
}


def _field(data: dict[str, str], name: str) -> str:
    return str(data.get(name, DEFAULTS[name])).strip()


def _to_float(data: dict[str, str], name: str) -> float:
    return float(_field(data, name).replace(",", "."))


def _to_int(data: dict[str, str], name: str) -> int:
    return int(float(_field(data, name).replace(",", ".")))


def _params(data: dict[str, str]) -> dict:
    lambdas = _asegurar_lambda_base(
        _parsear_lista_floats(_field(data, "lambdas_sensibilidad")),
        _to_float(data, "lambda_llegadas"),
    )
    c_min = _to_int(data, "c_min")
    c_max = _to_int(data, "c_max")
    if c_min > c_max:
        raise ValueError("El minimo de tecnicos no puede ser mayor que el maximo.")

    return {
        "lambda_llegadas": _to_float(data, "lambda_llegadas"),
        "mu_servicio": _to_float(data, "mu_servicio"),
        "servidores": _to_int(data, "servidores"),
        "tiempo": _to_float(data, "tiempo"),
        "warmup": _to_float(data, "warmup"),
        "replicas": _to_int(data, "replicas"),
        "semilla": _to_int(data, "semilla"),
        "lambdas_sensibilidad": lambdas,
        "c_min": c_min,
        "c_max": c_max,
        "replicas_sensibilidad": _to_int(data, "replicas_sensibilidad"),
        "umbral_wq": _to_float(data, "umbral_wq"),
    }


def _values(params: dict | None = None) -> dict[str, str]:
    if params is None:
        return DEFAULTS.copy()
    return {
        "lambda_llegadas": f"{params['lambda_llegadas']:g}",
        "mu_servicio": f"{params['mu_servicio']:g}",
        "servidores": str(params["servidores"]),
        "tiempo": f"{params['tiempo']:g}",
        "warmup": f"{params['warmup']:g}",
        "replicas": str(params["replicas"]),
        "semilla": str(params["semilla"]),
        "lambdas_sensibilidad": ",".join(
            f"{x:g}" for x in params["lambdas_sensibilidad"]
        ),
        "c_min": str(params["c_min"]),
        "c_max": str(params["c_max"]),
        "replicas_sensibilidad": str(params["replicas_sensibilidad"]),
        "umbral_wq": f"{params['umbral_wq']:g}",
    }


def _run(params: dict) -> dict:
    validar_estabilidad(
        params["lambda_llegadas"],
        params["mu_servicio"],
        params["servidores"],
    )
    out_dir = preparar_carpeta_salida(ASSETS)
    resumen = correr_replicas(
        n=params["replicas"],
        lambda_hora=params["lambda_llegadas"],
        mu_hora=params["mu_servicio"],
        servidores=params["servidores"],
        tiempo_simulacion=params["tiempo"],
        warmup=params["warmup"],
        semilla_base=params["semilla"],
    )
    teorico = metricas_mm_c(
        params["lambda_llegadas"],
        params["mu_servicio"],
        params["servidores"],
    )
    servidores = list(range(params["c_min"], params["c_max"] + 1))
    sensibilidad = barrido_sensibilidad(
        lambdas_hora=params["lambdas_sensibilidad"],
        servidores_lista=servidores,
        mu_hora=params["mu_servicio"],
        replicas=params["replicas_sensibilidad"],
        tiempo_simulacion=params["tiempo"],
        warmup=params["warmup"],
        semilla_base=params["semilla"] + 1000,
    )
    _guardar_csv_sensibilidad(sensibilidad, out_dir)
    _guardar_csv_llegadas(resumen["replicas"][0], out_dir)
    generar_graficas(
        resumen,
        sensibilidad,
        params["lambdas_sensibilidad"],
        servidores,
        out_dir,
    )
    return {
        "params": params,
        "resumen": resumen,
        "teorico": teorico,
        "comparacion": comparar_con_simulacion(resumen, teorico),
        "recomendacion": recomendar_minimo_servidores(
            sensibilidad,
            params["lambda_llegadas"],
            umbral_wq=params["umbral_wq"],
        ),
        "timestamp": int(time.time()),
    }


def _input(name: str, label: str, values: dict[str, str], type_: str = "number") -> str:
    step = ' step="any"' if type_ == "number" else ""
    return (
        f"<label><span>{label}</span>"
        f'<input name="{name}" type="{type_}" value="{html.escape(values[name])}" required{step}>'
        "</label>"
    )


def _metrics(result: dict | None) -> str:
    if result is None:
        cards = [
            ("Clientes/hora", DEFAULTS["lambda_llegadas"]),
            ("Tecnicos", DEFAULTS["servidores"]),
            ("Replicas", DEFAULTS["replicas"]),
            ("Salida", "graficas + CSV"),
        ]
    else:
        m = result["resumen"]["metricas"]
        rec = result["recomendacion"]
        cards = [
            ("Clientes atendidos", f"{m['clientes_atendidos']['media']:.1f}"),
            ("Wq promedio", f"{m['tiempo_espera_promedio']['media']:.2f} min"),
            ("Tiempo en sistema", f"{m['tiempo_sistema_promedio']['media']:.2f} min"),
            ("Rho", f"{m['rho']['media']:.3f}"),
            ("Lq", f"{m['Lq']['media']:.2f}"),
            ("Recomendacion", f"{rec['servidores']} tecnicos" if rec else "Sin umbral"),
        ]
    return "".join(
        f"<article><strong>{name}</strong><span>{value}</span></article>"
        for name, value in cards
    )


def _result_tables(result: dict | None) -> str:
    if result is None:
        return (
            "<section class='panel'>"
            "<h2>Resultados</h2>"
            "<p>Ejecuta la simulacion para ver metricas Montecarlo, validacion analitica y recomendacion de tecnicos.</p>"
            "</section>"
        )

    comparison = "".join(
        "<tr>"
        f"<td>{row['metrica']}</td>"
        f"<td>{row['simulacion']:.4f}</td>"
        f"<td>{row['analitico']:.4f}</td>"
        f"<td>{row['error_relativo_pct']:.2f}%</td>"
        "</tr>"
        for row in result["comparacion"]
    )
    rec = result["recomendacion"]
    rec_text = (
        f"Minimo recomendado: {rec['servidores']} tecnicos con Wq={rec['Wq_promedio']:.2f} min."
        if rec
        else "No se encontro una configuracion dentro del umbral definido."
    )
    return f"""
    <section class="panel">
      <h2>Recomendacion</h2>
      <p>{html.escape(rec_text)}</p>
    </section>
    <section class="panel table-panel">
      <h2>Simulacion vs analitico</h2>
      <table>
        <thead><tr><th>Metrica</th><th>Simulacion</th><th>Analitico</th><th>Error</th></tr></thead>
        <tbody>{comparison}</tbody>
      </table>
    </section>
    """


def _graphs(cache: int) -> str:
    figures = []
    for filename, title in GRAFICAS:
        if (ASSETS / filename).exists():
            src = f"/assets/{filename}?v={cache}"
            figures.append(
                f"<figure><a href='{src}' target='_blank'>"
                f"<img src='{src}' alt='{html.escape(title)}'></a>"
                f"<figcaption>{html.escape(title)}</figcaption></figure>"
            )
    return "".join(figures)


def _page(values: dict[str, str], result: dict | None = None, error: str | None = None) -> str:
    cache = result["timestamp"] if result else int(time.time())
    error_html = f"<div class='alert'>{html.escape(error)}</div>" if error else ""
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Simulacion TechClassUC</title>
  <style>
    :root {{
      --bg: #eef2f6;
      --panel: rgba(255, 255, 255, .94);
      --text: #17202a;
      --muted: #5f6b7a;
      --line: #d7dde5;
      --accent: #0f766e;
      --accent-dark: #0b5f59;
      font-family: Arial, Helvetica, sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: #eef2f6;
      color: var(--text);
    }}
    header {{
      padding: 24px clamp(16px, 4vw, 46px);
      background: #ffffff;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{ margin: 0 0 8px; font-size: clamp(28px, 4vw, 42px); }}
    h2 {{ margin: 0 0 14px; font-size: 20px; }}
    p {{ margin: 0; color: var(--muted); line-height: 1.5; }}
    main {{ width: min(1180px, calc(100% - 32px)); margin: 22px auto 44px; }}
    .layout {{ display: grid; grid-template-columns: minmax(280px, 360px) 1fr; gap: 18px; align-items: start; }}
    .panel, form, .metrics article, figure {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 8px 22px rgba(18, 28, 38, .07);
    }}
    form {{ padding: 16px; display: grid; gap: 12px; position: sticky; top: 16px; }}
    label {{ display: grid; gap: 6px; color: var(--muted); font-weight: 700; font-size: 13px; }}
    input {{ min-height: 38px; border: 1px solid var(--line); border-radius: 6px; padding: 8px 10px; font: inherit; }}
    button {{ min-height: 42px; border: 0; border-radius: 6px; background: var(--accent); color: white; font: inherit; font-weight: 700; cursor: pointer; }}
    button:hover {{ background: var(--accent-dark); }}
    .links {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    a {{ color: var(--accent); font-weight: 700; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .alert {{ margin-bottom: 16px; padding: 12px 14px; border-radius: 8px; background: #fff1f0; border: 1px solid #ffccc7; color: #8c1d18; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin-bottom: 18px; }}
    .metrics article {{ padding: 14px; }}
    .metrics strong {{ display: block; color: var(--muted); font-size: 13px; margin-bottom: 7px; }}
    .metrics span {{ color: var(--accent); font-size: 22px; font-weight: 800; }}
    .panel {{ padding: 16px; margin-bottom: 18px; }}
    .graphs {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }}
    figure {{ margin: 0; overflow: hidden; }}
    img {{ display: block; width: 100%; height: auto; background: white; }}
    figcaption {{ padding: 11px 13px; border-top: 1px solid var(--line); font-weight: 700; }}
    .table-panel {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 560px; font-size: 14px; }}
    th, td {{ padding: 9px 8px; border-bottom: 1px solid var(--line); text-align: left; }}
    th {{ color: var(--muted); }}
    @media (max-width: 850px) {{
      .layout {{ grid-template-columns: 1fr; }}
      form {{ position: static; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Simulacion TechClassUC</h1>
    <p>Modelo de colas M/M/c para analizar llegada de clientes, capacidad de tecnicos y tiempos de espera.</p>
  </header>
  <main>
    {error_html}
    <section class="metrics" aria-label="Metricas principales">{_metrics(result)}</section>
    <div class="layout">
      <form method="post" action="/simular">
        <h2>Datos de entrada</h2>
        {_input("lambda_llegadas", "Clientes por hora", values)}
        {_input("mu_servicio", "Atencion por tecnico/hora", values)}
        {_input("servidores", "Tecnicos actuales", values)}
        {_input("tiempo", "Tiempo simulado (min)", values)}
        {_input("warmup", "Warm-up (min)", values)}
        {_input("replicas", "Replicas Montecarlo", values)}
        {_input("lambdas_sensibilidad", "Lambdas sensibilidad", values, "text")}
        {_input("c_min", "Tecnicos minimo", values)}
        {_input("c_max", "Tecnicos maximo", values)}
        {_input("replicas_sensibilidad", "Replicas sensibilidad", values)}
        {_input("umbral_wq", "Umbral Wq (min)", values)}
        <input name="semilla" type="hidden" value="{html.escape(values['semilla'])}">
        <button type="submit">Ejecutar simulacion</button>
        <div class="links">
          <a href="/assets/sensibilidad.csv" target="_blank">Sensibilidad CSV</a>
          <a href="/assets/llegadas_clientes.csv" target="_blank">Llegadas CSV</a>
          <a href="/manual_usuario.html" target="_blank">Manual</a>
        </div>
      </form>
      <div>
        {_result_tables(result)}
        <section class="graphs" aria-label="Graficas generadas">{_graphs(cache)}</section>
      </div>
    </div>
  </main>
</body>
</html>"""


def _html(content: str) -> Response:
    return Response(content, mimetype="text/html; charset=utf-8")


@app.get("/")
@app.get("/index.html")
@app.get("/vista_resultados.html")
@app.get("/visor_grafica.html")
def home() -> Response:
    return _html(_page(_values()))


@app.post("/simular")
def simulate() -> Response:
    form = request.form.to_dict(flat=True)
    try:
        params = _params(form)
        result = _run(params)
        return _html(_page(_values(params), result=result))
    except Exception as exc:  # noqa: BLE001
        values = {**DEFAULTS, **form}
        return _html(_page(values, error=str(exc)))


@app.get("/assets/<path:filename>")
def asset(filename: str):
    return send_from_directory(ASSETS, filename)


@app.get("/manual_usuario.html")
def manual():
    return send_from_directory(ROOT, "manual_usuario.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
