# API de Produccion y Monitoreo Activo - Pre-entrega 7

> **Sistema Multi-Agente asincrono, desacoplado con Redis, Human-in-the-Loop (HITL) y Observabilidad (Arize Phoenix / LangSmith).**

---

## Tabla de Contenidos
1. [Arquitectura del Sistema](#arquitectura-del-sistema)
2. [Estructura del Repositorio](#estructura-del-repositorio)
3. [Requisitos de Instalacion](#requisitos-de-instalacion)
4. [Guia de Ejecucion](#guia-de-ejecucion)
5. [Prueba de Carga Concurrente (5 Peticiones)](#prueba-de-carga-concurrente-5-peticiones)
6. [Flujo Human-in-the-Loop (HITL)](#flujo-human-in-the-loop-hitl)
7. [Capas de Observabilidad y Costos](#capas-de-observabilidad-y-costos)
8. [Capturas del Dashboard (/screenshots)](#capturas-del-dashboard-screenshots)

---

## Arquitectura del Sistema
En este Modulo 7 se evoluciona el orquestador multi-agente del Modulo 6 para convertirlo en una arquitectura de produccion desacoplada:

- **FastAPI (El Recepcionista)**: Endpoints asincronos no bloqueantes. POST /tasks encola la tarea, persiste el estado inicial como PENDING en Redis y retorna inmediatamente un job_id. GET /tasks/{id} permite consultar el estado mediante polling.
- **Redis (El Buzon y Persistencia)**: Gestiona atomicamente las transiciones de estado (PENDING -> RUNNING -> WAITING_APPROVAL -> DONE / FAILED) y persiste los checkpoints de LangGraph.
- **Worker Asincrono (El Especialista)**: Proceso desacoplado que ejecuta el grafo. Ante excepciones, garantiza la transicion a FAILED para evitar loops infinitos en clientes.
- **Human-in-the-Loop (HITL)**: Nodo de aprobacion humana mediante interrupt() que detiene tareas criticas (riesgo ALTO o acciones operativas sensibles) con estado WAITING_APPROVAL, hasta recibir autorizacion via POST /tasks/{id}/approve.
- **Observabilidad (Arize Phoenix / LangSmith)**: Trazado nativo con OpenInference/OpenTelemetry para monitorear cada span, los tokens y costos por ejecucion, y la latencia p95.

---

## Estructura del Repositorio

`	ext
mi-api-agente/
├── app/
│   ├── main.py            # FastAPI: POST /tasks (async), GET /tasks/{id}, POST /tasks/{id}/approve
│   ├── graph.py           # Orquestador M6 + Redis Checkpointer + Nodo HITL
│   ├── worker.py          # Worker asincrono y transiciones de estado (PENDING/RUNNING/DONE/FAILED)
│   ├── observability.py   # Setup de Arize Phoenix / LangSmith y decoradores de trazas
│   ├── hitl.py            # Nodo Human-in-the-Loop (interrupt)
│   ├── redis_state.py     # Gestor de estado persistente y checkpointer
│   ├── state.py           # MultiAgentState y esquemas estructurados Pydantic
│   ├── tools.py           # Herramientas del sistema
│   └── agents/            # Supervisor, ResearchAgent, AnalystAgent, Validator
├── scripts/
│   └── benchmark_load.py  # Script de carga concurrente (5 peticiones), polling y latencia p95
├── screenshots/           # Capturas y reportes de trazas, costos y latencia p95
├── docker-compose.yml     # Orquestacion multi-contenedor (API + Redis + Arize Phoenix)
├── Dockerfile             # Imagen Docker para FastAPI
├── .env.example           # Variables de entorno
├── requirements.txt       # Dependencias
└── README.md              # Documentacion tecnica
`

---

## Requisitos e Instalacion

1. Clonar el repositorio y configurar entorno:
`ash
python -m venv venv
pip install -r requirements.txt
`

2. Configurar variables de entorno:
`ash
cp .env.example .env
`
Configurar en .env:
- OPENAI_API_KEY: Tu clave de OpenAI.
- REDIS_URL: edis://localhost:6379/0 (o el servicio de Redis).
- ENABLE_PHOENIX: 	rue
- PHOENIX_PORT: 6006

---

## Guia de Ejecucion

### Opcion A: Con Docker Compose (Recomendado)
`ash
docker compose up --build
`
Servicios disponibles:
- **FastAPI API**: http://localhost:8000 (Swagger UI interactivo en http://localhost:8000/docs)
- **Arize Phoenix UI**: http://localhost:6006
- **Redis Server**: redis://localhost:6379

### Opcion B: Ejecucion Local (Sin Docker)
`ash
uvicorn app.main:app --reload --port 8000
`
(Si Redis no esta corriendo en local, el sistema activa de forma transparente un backend de estado compatible en memoria sin interrumpir el funcionamiento de la API).

---

## Prueba de Carga Concurrente (5 Peticiones)
Para verificar la asincronia no bloqueante, ejecuta en una terminal secundaria:
`ash
python scripts/benchmark_load.py
`
El script realiza:
1. Encolado simultaneo de 5 peticiones mediante syncio.gather.
2. Polling no bloqueante a GET /tasks/{job_id}.
3. Aprobacion automatica de tareas que requieran HITL (POST /tasks/{id}/approve).
4. Medicion de duracion total y calculo de percentiles de latencia (p50, p90, p95).

---

## Flujo Human-in-the-Loop (HITL)
Cuando una tarea es calificada como critica, el nodo human_approval activa una interrupcion nativa de LangGraph y actualiza el estado en Redis a WAITING_APPROVAL.
Para reanudarla manualmente desde consola:
`ash
curl -X POST  http://localhost:8000/tasks/<job_id>/approve \
     -H Content-Type: application/json \
     -d '{approved: true, comments: Aprobado por SRE Lead, approver: admin@system.local}'
`

---

## Capturas y Evidencias (/screenshots)
En el directorio screenshots/ se encuentran las evidencias y reportes del monitoreo:
- **spans_multi_agent_trace**: Trazas completas del orquestador y nodo HITL.
- **costo_y_latencia_p95**: Reporte de costos por ejecucion y latencia p95 de las 5 corridas concurrentes.