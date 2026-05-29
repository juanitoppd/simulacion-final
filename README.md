# Simulacion TechClassUC M/M/c

Proyecto en Python basado en `planteamiento_modelos_simulacion.docx`.
Modela un centro de atencion con llegadas Poisson, tiempos de servicio
exponenciales, tecnicos en paralelo, replicas Montecarlo, validacion analitica y
graficas.

## Como se simula la llegada de clientes

El sistema usa un modelo M/M/c. La primera `M` significa que las llegadas siguen
un proceso de Poisson con tasa `lambda` clientes por hora. En la simulacion esto
se implementa generando el tiempo entre dos llegadas consecutivas con una
distribucion exponencial:

```python
tasa_llegada_minuto = lambda_hora / 60.0
tiempo_entre_llegadas = rng.expovariate(tasa_llegada_minuto)
yield env.timeout(tiempo_entre_llegadas)
```

Flujo de cada cliente:

1. SimPy avanza el reloj hasta la siguiente llegada.
2. Se crea un `Cliente` con ID, tipo de solicitud, prioridad y tiempo de llegada.
3. El cliente solicita un tecnico (`simpy.Resource`).
4. Si todos los tecnicos estan ocupados, espera en cola.
5. Cuando inicia la atencion se registra `Wq = inicio - llegada`.
6. El tiempo de servicio se genera con otra exponencial usando `mu`.
7. Al finalizar se registra el tiempo total en el sistema.

Cada ejecucion guarda `llegadas_clientes.csv` en la carpeta de salida. Ese
archivo permite ver cliente por cliente el tiempo de llegada, el tiempo entre
llegadas, el inicio de atencion, el fin de atencion y la espera.

## Como modificar el comportamiento

Instala dependencias:

```powershell
py -m pip install -r requirements.txt
```

Ejecuta con valores base:

```powershell
py main.py
```

Cambia la frecuencia de llegada, capacidad y numero de replicas:

```powershell
py main.py --lambda-llegadas 12 --servidores 4 --replicas 50
```

Ejemplos utiles:

```powershell
py main.py --lambda-llegadas 8
py main.py --lambda-llegadas 14 --servidores 5
py main.py --mu-servicio 5 --tiempo 600 --warmup 60
py main.py --lambdas-sensibilidad 8,10,12,14 --c-min 2 --c-max 8
py main.py --umbral-wq 8
```

Parametros principales:

- `--lambda-llegadas`: clientes que llegan por hora. Si sube, llegan mas
  clientes y la cola tiende a crecer.
- `--mu-servicio`: clientes atendidos por hora por tecnico. Si sube, cada
  atencion dura menos.
- `--servidores`: tecnicos disponibles en paralelo.
- `--tiempo`: duracion de la jornada simulada en minutos.
- `--warmup`: minutos iniciales descartados para reducir sesgo por iniciar con
  sistema vacio.
- `--replicas`: corridas independientes usadas por Montecarlo.
- `--semilla`: hace reproducible la simulacion.
- `--lambdas-sensibilidad`, `--c-min`, `--c-max`: escenarios del analisis de
  sensibilidad.
- `--umbral-wq`: meta de espera usada para recomendar el minimo numero de
  tecnicos.

## Revision de requerimientos

| Requerimiento del enunciado | Donde esta implementado |
| --- | --- |
| Llegadas con `random.expovariate(lambda)` | `simulacion_des.py`, funcion `_generar_llegadas` |
| Cliente con atributos de llegada, tipo y prioridad | `cliente.py` y `_crear_cliente` |
| Modelo DES con `simpy.Environment` y `simpy.Resource` | `simulacion_des.py`, funcion `correr_una_replica` |
| Calculo de `Wq` y tiempo en sistema | `cliente.py`, propiedades `tiempo_espera` y `tiempo_sistema` |
| N replicas Montecarlo con semillas distintas | `montecarlo.py`, funcion `correr_replicas` |
| Intervalos de confianza al 95% y replicas minimas | `montecarlo.py`, funcion `_resumir_valores`; se imprime en consola |
| Validacion analitica M/M/c | `analitico.py` |
| Comparacion simulacion vs analitico con error relativo | `analitico.py` y salida de `main.py` |
| Sensibilidad variando `lambda` y tecnicos `c` | `sensibilidad.py` |
| Heatmap y graficas de linea | `visualizacion.py` |
| Recomendacion de minimo numero de tecnicos | `sensibilidad.py`, funcion `recomendar_minimo_servidores` |
| Evidencia de llegadas simuladas | `llegadas_clientes.csv` generado por `main.py` |

## Salidas

El programa crea la carpeta indicada en `--salida` con:

- `sensibilidad.csv`
- `llegadas_clientes.csv`
- `evolucion_sistema.png`
- `histograma_esperas.png`
- `wq_vs_servidores.png`
- `rho_vs_lambda.png`
- `distribucion_medias_wq.png`
- `heatmap_wq.png`

La consola imprime las metricas Montecarlo, los valores analiticos M/M/c, el
error relativo porcentual, replicas sugeridas para error relativo menor o igual
a 5%, y una recomendacion del minimo numero de tecnicos para cumplir el umbral
de espera definido.
