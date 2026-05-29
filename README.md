# Simulacion TechClassUC M/M/c

Proyecto en Python basado en el documento `planteamiento_modelos_simulacion.docx`.
Modela un centro de atencion con llegadas Poisson, tiempos de servicio exponenciales,
tecnicos en paralelo, replicas Montecarlo, validacion analitica y graficas.

## Instalacion

```powershell
py -m pip install -r requirements.txt
```

## Ejecucion

```powershell
py main.py
```

Tambien puedes cambiar parametros:

```powershell
py main.py --lambda-llegadas 12 --servidores 4 --replicas 50
```

## Salidas

El programa crea la carpeta `resultados` con:

- `sensibilidad.csv`
- `evolucion_sistema.png`
- `histograma_esperas.png`
- `wq_vs_servidores.png`
- `rho_vs_lambda.png`
- `distribucion_medias_wq.png`
- `heatmap_wq.png`

La consola imprime las metricas Montecarlo, los valores analiticos M/M/c,
el error relativo porcentual y una recomendacion del minimo numero de tecnicos
para mantener `Wq <= 10` minutos.
