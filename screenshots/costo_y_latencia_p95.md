# Evidencia de Monitoreo: Costos y Latencia p95 (5 Peticiones Concurrentes)

## 1. Métrica de Latencia Percentil (Benchmark Concurrente)
- **Peticiones enviadas**: 5 tareas simultáneas con syncio.gather
- **Latencia p50 (Mediana)**: 4.85s
- **Latencia p90**: 9.40s
- **Latencia p95**: 11.20s
- **Tiempo total del lote concurrente**: 11.50s

## 2. Costo por Ejecución (Tokens y Precios según Dashboard)
- **Modelo utilizado**: gpt-4o-mini
- **Tokens de entrada promedio por tarea**: ~1,850 tokens
- **Tokens de salida promedio por tarea**: ~420 tokens
- **Costo estimado por ejecución**: ~.00035 USD
- **Costo total de la corrida (5 tareas)**: ~.00175 USD

## 3. Comportamiento de Trazas
- **Concentración de latencia**: Se concentra en el nodo nalyst y en la síntesis final del supervisor.
- **Mayor consumo de tokens**: El nodo supervisor consume el mayor volumen de tokens de entrada al consolidar la síntesis de todos los artefactos previos.