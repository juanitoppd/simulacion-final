from __future__ import annotations

import html
import os
import sys
import time
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from socketserver import TCPServer
from urllib.parse import parse_qs
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent.parent
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


GRAFICAS = [
    ("evolucion_sistema.png", "Evolucion del sistema"),
    ("histograma_esperas.png", "Histograma de esperas"),
    ("wq_vs_servidores.png", "Wq vs tecnicos"),
    ("rho_vs_lambda.png", "Rho vs lambda"),
    ("distribucion_medias_wq.png", "Distribucion Wq"),
    ("heatmap_wq.png", "Heatmap Wq"),
]

VALORES_DEFECTO = {
    "lambda_llegadas": "10",
    "mu_servicio": "4",
    "servidores": "3",
    "tiempo": "480",
    "warmup": "60",
    "replicas": "30",
    "semilla": "42",
    "lambdas_sensibilidad": "8,10,12",
    "c_min": "2",
    "c_max": "7",
    "replicas_sensibilidad": "10",
    "umbral_wq": "10",
}


def _campo(datos: dict[str, list[str]], nombre: str) -> str:
    return datos.get(nombre, [VALORES_DEFECTO[nombre]])[0].strip()


def _float(datos: dict[str, list[str]], nombre: str) -> float:
    return float(_campo(datos, nombre))


def _int(datos: dict[str, list[str]], nombre: str) -> int:
    return int(float(_campo(datos, nombre)))


def _parametros_desde_formulario(datos: dict[str, list[str]]) -> dict:
    lambdas = _asegurar_lambda_base(
        _parsear_lista_floats(_campo(datos, "lambdas_sensibilidad")),
        _float(datos, "lambda_llegadas"),
    )
    c_min = _int(datos, "c_min")
    c_max = _int(datos, "c_max")
    if c_min > c_max:
        raise ValueError("El tecnico minimo no puede ser mayor que el tecnico maximo.")

    return {
        "lambda_llegadas": _float(datos, "lambda_llegadas"),
        "mu_servicio": _float(datos, "mu_servicio"),
        "servidores": _int(datos, "servidores"),
        "tiempo": _float(datos, "tiempo"),
        "warmup": _float(datos, "warmup"),
        "replicas": _int(datos, "replicas"),
        "semilla": _int(datos, "semilla"),
        "lambdas_sensibilidad": lambdas,
        "c_min": c_min,
        "c_max": c_max,
        "replicas_sensibilidad": _int(datos, "replicas_sensibilidad"),
        "umbral_wq": _float(datos, "umbral_wq"),
    }


def _form_values(parametros: dict | None) -> dict[str, str]:
    if parametros is None:
        return VALORES_DEFECTO.copy()
    valores = {
        "lambda_llegadas": f"{parametros['lambda_llegadas']:g}",
        "mu_servicio": f"{parametros['mu_servicio']:g}",
        "servidores": str(parametros["servidores"]),
        "tiempo": f"{parametros['tiempo']:g}",
        "warmup": f"{parametros['warmup']:g}",
        "replicas": str(parametros["replicas"]),
        "semilla": str(parametros["semilla"]),
        "lambdas_sensibilidad": ",".join(
            f"{x:g}" for x in parametros["lambdas_sensibilidad"]
        ),
        "c_min": str(parametros["c_min"]),
        "c_max": str(parametros["c_max"]),
        "replicas_sensibilidad": str(parametros["replicas_sensibilidad"]),
        "umbral_wq": f"{parametros['umbral_wq']:g}",
    }
    return valores


def _ejecutar_simulacion(parametros: dict) -> dict:
    validar_estabilidad(
        parametros["lambda_llegadas"],
        parametros["mu_servicio"],
        parametros["servidores"],
    )
    carpeta = preparar_carpeta_salida(ASSETS)
    resumen = correr_replicas(
        n=parametros["replicas"],
        lambda_hora=parametros["lambda_llegadas"],
        mu_hora=parametros["mu_servicio"],
        servidores=parametros["servidores"],
        tiempo_simulacion=parametros["tiempo"],
        warmup=parametros["warmup"],
        semilla_base=parametros["semilla"],
    )
    teorico = metricas_mm_c(
        parametros["lambda_llegadas"],
        parametros["mu_servicio"],
        parametros["servidores"],
    )
    comparacion = comparar_con_simulacion(resumen, teorico)
    servidores_lista = list(range(parametros["c_min"], parametros["c_max"] + 1))
    sensibilidad = barrido_sensibilidad(
        lambdas_hora=parametros["lambdas_sensibilidad"],
        servidores_lista=servidores_lista,
        mu_hora=parametros["mu_servicio"],
        replicas=parametros["replicas_sensibilidad"],
        tiempo_simulacion=parametros["tiempo"],
        warmup=parametros["warmup"],
        semilla_base=parametros["semilla"] + 5000,
    )
    _guardar_csv_sensibilidad(sensibilidad, carpeta)
    _guardar_csv_llegadas(resumen["replicas"][0], carpeta)
    generar_graficas(
        resumen,
        sensibilidad,
        parametros["lambdas_sensibilidad"],
        servidores_lista,
        carpeta,
    )
    recomendacion = recomendar_minimo_servidores(
        sensibilidad,
        parametros["lambda_llegadas"],
        umbral_wq=parametros["umbral_wq"],
    )
    return {
        "parametros": parametros,
        "resumen": resumen,
        "teorico": teorico,
        "comparacion": comparacion,
        "sensibilidad": sensibilidad,
        "recomendacion": recomendacion,
        "timestamp": int(time.time()),
    }


def _input(nombre: str, etiqueta: str, valores: dict[str, str], tipo: str = "number") -> str:
    valor = html.escape(valores[nombre])
    step = ' step="any"' if tipo == "number" else ""
    return (
        f'<label><span>{etiqueta}</span>'
        f'<input name="{nombre}" type="{tipo}" value="{valor}" required{step}></label>'
    )


def _numero_tabla(valor: float | None) -> str:
    return "-" if valor is None else f"{valor:.4f}"


def _render_pagina(
    valores: dict[str, str],
    resultado: dict | None = None,
    error: str | None = None,
) -> bytes:
    metricas_html = ""
    intervalos_html = ""
    comparacion_html = ""
    sensibilidad_html = ""
    recomendacion_html = ""
    parametros_html = ""
    graficas_html = ""
    cache = int(time.time()) if resultado is None else resultado["timestamp"]

    if resultado:
        parametros = resultado["parametros"]
        resumen = resultado["resumen"]
        teorico = resultado["teorico"]
        metricas = resumen["metricas"]
        principales = [
            ("Clientes atendidos", metricas["clientes_atendidos"]["media"], ""),
            ("Wq promedio", metricas["tiempo_espera_promedio"]["media"], "min"),
            ("Tiempo en sistema", metricas["tiempo_sistema_promedio"]["media"], "min"),
            ("Lq", metricas["Lq"]["media"], "clientes"),
            ("L", metricas["L"]["media"], "clientes"),
            ("Rho simulado", metricas["rho"]["media"], ""),
            ("Rho teorico", teorico["rho"], ""),
            ("P0 analitico", teorico["P0"], ""),
        ]
        metricas_html = "".join(
            f"<article><strong>{nombre}</strong><span>{valor:.3f} {unidad}</span></article>"
            for nombre, valor, unidad in principales
        )
        parametros_html = (
            f"Clientes/hora={parametros['lambda_llegadas']:g}, "
            f"servicio/hora={parametros['mu_servicio']:g}, "
            f"tecnicos={parametros['servidores']}, "
            f"tiempo={parametros['tiempo']:g} min, "
            f"warm-up={parametros['warmup']:g} min, "
            f"replicas={parametros['replicas']}."
        )
        metricas_intervalo = [
            ("Clientes atendidos", "clientes_atendidos"),
            ("Wq promedio", "tiempo_espera_promedio"),
            ("Tiempo en sistema", "tiempo_sistema_promedio"),
            ("Lq", "Lq"),
            ("L", "L"),
            ("Rho", "rho"),
            ("Throughput/hora", "throughput_hora"),
        ]
        intervalos_html = "".join(
            "<tr>"
            f"<td>{nombre}</td>"
            f"<td>{metricas[clave]['media']:.4f}</td>"
            f"<td>{metricas[clave]['ic95_inf']:.4f} - {metricas[clave]['ic95_sup']:.4f}</td>"
            f"<td>{metricas[clave]['n_minimo_error_5pct']}</td>"
            "</tr>"
            for nombre, clave in metricas_intervalo
        )
        comparacion_html = "".join(
            "<tr>"
            f"<td>{fila['metrica']}</td>"
            f"<td>{fila['simulacion']:.4f}</td>"
            f"<td>{fila['analitico']:.4f}</td>"
            f"<td>{fila['error_relativo_pct']:.2f}%</td>"
            "</tr>"
            for fila in resultado["comparacion"]
        )
        sensibilidad_html = "".join(
            "<tr>"
            f"<td>{fila['lambda_hora']:g}</td>"
            f"<td>{fila['servidores']}</td>"
            f"<td>{'Si' if fila['estable'] else 'No'}</td>"
            f"<td>{fila['rho_teorico']:.4f}</td>"
            f"<td>{_numero_tabla(fila['Wq_promedio'])}</td>"
            f"<td>{_numero_tabla(fila['Lq_promedio'])}</td>"
            "</tr>"
            for fila in resultado["sensibilidad"]
        )
        recomendacion = resultado["recomendacion"]
        if recomendacion:
            recomendacion_html = (
                f"Minimo recomendado: {recomendacion['servidores']} tecnicos "
                f"con Wq={recomendacion['Wq_promedio']:.2f} min."
            )
        else:
            recomendacion_html = "No se encontro una configuracion que cumpla el umbral."

    for archivo, titulo in GRAFICAS:
        ruta = ASSETS / archivo
        if ruta.exists():
            graficas_html += (
                "<figure>"
                f'<a href="/assets/{archivo}?v={cache}" target="_blank">'
                f'<img src="/assets/{archivo}?v={cache}" alt="{titulo}"></a>'
                f"<figcaption>{titulo}</figcaption>"
                "</figure>"
            )

    aviso_error = f'<div class="alert">{html.escape(error)}</div>' if error else ""
    bloque_resultado = ""
    if resultado:
        bloque_resultado = f"""
        <section class="metrics" aria-label="Metricas principales">
          {metricas_html}
        </section>
        <section class="panel">
          <h2>Parametros usados</h2>
          <p>{parametros_html}</p>
        </section>
        <section class="panel">
          <h2>Recomendacion</h2>
          <p>{recomendacion_html}</p>
        </section>
        <section class="panel table-panel">
          <h2>Montecarlo e intervalos de confianza</h2>
          <table>
            <thead>
              <tr><th>Metrica</th><th>Media</th><th>IC 95%</th><th>Replicas para error 5%</th></tr>
            </thead>
            <tbody>{intervalos_html}</tbody>
          </table>
        </section>
        <section class="panel table-panel">
          <h2>Comparacion simulacion vs analitico</h2>
          <table>
            <thead>
              <tr><th>Metrica</th><th>Simulacion</th><th>Analitico</th><th>Error</th></tr>
            </thead>
            <tbody>{comparacion_html}</tbody>
          </table>
        </section>
        <section class="panel table-panel">
          <h2>Tabla de sensibilidad</h2>
          <table>
            <thead>
              <tr><th>Clientes/hora</th><th>Tecnicos</th><th>Estable</th><th>Rho teorico</th><th>Wq promedio</th><th>Lq promedio</th></tr>
            </thead>
            <tbody>{sensibilidad_html}</tbody>
          </table>
        </section>
        """

    pagina = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Simulacion TechClassUC</title>
  <style>
    :root {{
      --bg: #f4f6f8;
      --panel: rgba(255, 255, 255, 0.9);
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
      background: linear-gradient(rgba(6, 15, 24, 0.35), rgba(6, 15, 24, 0.42)), url("/Luffy.jpeg");
      background-size: cover;
      background-position: center top;
      background-attachment: fixed;
      color: var(--text);
    }}
    header {{
      padding: 22px clamp(16px, 4vw, 44px);
      background: rgba(255,255,255,0.72);
      border-bottom: 1px solid var(--line);
      backdrop-filter: blur(8px);
    }}
    h1 {{ margin: 0 0 6px; font-size: clamp(26px, 4vw, 38px); }}
    h2 {{ margin: 0 0 14px; font-size: 20px; }}
    p {{ margin: 0; color: var(--muted); line-height: 1.5; }}
    main {{ width: min(1180px, calc(100% - 32px)); margin: 22px auto 44px; }}
    .layout {{ display: grid; grid-template-columns: minmax(280px, 360px) 1fr; gap: 18px; align-items: start; }}
    .panel, form, .metrics article, figure {{
      background: var(--panel);
      border: 1px solid rgba(255,255,255,0.72);
      border-radius: 8px;
      backdrop-filter: blur(10px);
      box-shadow: 0 8px 24px rgba(18, 28, 38, 0.08);
    }}
    form {{ padding: 16px; display: grid; gap: 12px; position: sticky; top: 16px; }}
    label {{ display: grid; gap: 6px; color: var(--muted); font-weight: 700; font-size: 13px; }}
    input {{
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px 10px;
      color: var(--text);
      font: inherit;
      background: #fff;
    }}
    button {{
      min-height: 42px;
      border: 1px solid var(--accent);
      border-radius: 6px;
      background: var(--accent);
      color: #fff;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }}
    button:hover {{ background: var(--accent-dark); }}
    .alert {{ margin-bottom: 16px; padding: 12px 14px; border-radius: 8px; background: #fff1f0; border: 1px solid #ffccc7; color: #8c1d18; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin-bottom: 18px; }}
    .metrics article {{ padding: 14px; }}
    .metrics strong {{ display: block; color: var(--muted); font-size: 13px; margin-bottom: 7px; }}
    .metrics span {{ color: var(--accent); font-size: 22px; font-weight: 800; }}
    .panel {{ padding: 16px; margin-bottom: 18px; }}
    .graphs {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }}
    figure {{ margin: 0; overflow: hidden; }}
    img {{ display: block; width: 100%; height: auto; background: #fff; }}
    figcaption {{ padding: 11px 13px; border-top: 1px solid var(--line); font-weight: 700; }}
    .table-panel {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; min-width: 620px; }}
    th, td {{ padding: 9px 8px; border-bottom: 1px solid var(--line); text-align: left; }}
    th {{ color: var(--muted); }}
    .links {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    a {{ color: var(--accent); font-weight: 700; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    @media (max-width: 850px) {{
      .layout {{ grid-template-columns: 1fr; }}
      form {{ position: static; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Simulacion TechClassUC</h1>
    <p>Ingresa los clientes por hora, capacidad y escenarios; al ejecutar, las metricas y graficas cambian con esos valores.</p>
  </header>
  <main>
    {aviso_error}
    <div class="layout">
      <form method="post" action="/simular">
        <h2>Datos de entrada</h2>
        {_input("lambda_llegadas", "Ingreso de clientes (clientes/hora)", valores)}
        {_input("mu_servicio", "Atencion por tecnico (clientes/hora)", valores)}
        {_input("servidores", "Tecnicos actuales", valores)}
        {_input("tiempo", "Tiempo simulado (minutos)", valores)}
        {_input("warmup", "Warm-up (minutos)", valores)}
        {_input("replicas", "Replicas Montecarlo", valores)}
        {_input("semilla", "Semilla", valores)}
        {_input("lambdas_sensibilidad", "Lambdas sensibilidad", valores, "text")}
        {_input("c_min", "Tecnicos minimo sensibilidad", valores)}
        {_input("c_max", "Tecnicos maximo sensibilidad", valores)}
        {_input("replicas_sensibilidad", "Replicas sensibilidad", valores)}
        {_input("umbral_wq", "Umbral Wq recomendado (min)", valores)}
        <button type="submit">Ejecutar simulacion</button>
        <div class="links">
          <a href="/assets/sensibilidad.csv" target="_blank">sensibilidad.csv</a>
          <a href="/assets/llegadas_clientes.csv" target="_blank">llegadas_clientes.csv</a>
          <a href="/manual_usuario.html" target="_blank">Manual</a>
        </div>
      </form>
      <div>
        {bloque_resultado}
        <section class="graphs" aria-label="Graficas generadas">
          {graficas_html}
        </section>
      </div>
    </div>
  </main>
</body>
</html>
"""
    return pagina.encode("utf-8")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:
        ruta = urlparse(self.path).path
        if ruta in ("/", "/index.html", "/vista_resultados.html", "/visor_grafica.html"):
            self._enviar_html(_render_pagina(_form_values(None)))
            return
        super().do_GET()

    def do_POST(self) -> None:
        if self.path != "/simular":
            self.send_error(404)
            return

        longitud = int(self.headers.get("Content-Length", "0"))
        cuerpo = self.rfile.read(longitud).decode("utf-8")
        datos = parse_qs(cuerpo)
        try:
            parametros = _parametros_desde_formulario(datos)
            resultado = _ejecutar_simulacion(parametros)
            pagina = _render_pagina(_form_values(parametros), resultado=resultado)
        except Exception as exc:  # noqa: BLE001
            pagina = _render_pagina(
                {**VALORES_DEFECTO, **{k: v[0] for k, v in datos.items()}},
                error=str(exc),
            )
        self._enviar_html(pagina)

    def _enviar_html(self, contenido: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(contenido)))
        self.end_headers()
        self.wfile.write(contenido)


if __name__ == "__main__":
    with TCPServer(("0.0.0.0", PORT), Handler) as httpd:
        print(f"Serving {ROOT} on port {PORT}")
        httpd.serve_forever()
