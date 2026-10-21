# API de Producción y Monitoreo Activo - Pre-entrega 7

> **Sistema Multi-Agente Asíncrono de Producción con FastAPI, Redis, Human-in-the-Loop (HITL) y Observabilidad Activa en LangSmith.**

---

## 📋 Tabla de Contenidos
1. [Descripción del Proyecto y Arquitectura](#-descripción-del-proyecto-y-arquitectura)
2. [Estructura del Repositorio](#-estructura-del-repositorio)
3. [Checklist de la Rúbrica](#-checklist-de-la-rúbrica)
4. [Requisitos e Instalación](#-requisitos-e-instalación)
5. [Guía de Ejecución](#-guía-de-ejecución)
6. [Flujo Human-in-the-Loop (HITL)](#-flujo-human-in-the-loop-hitl)
7. [Prueba de Carga Concurrente (5 Peticiones)](#-prueba-de-carga-concurrente-5-peticiones)
8. [Observabilidad, Métricas y Capturas (`/screenshots`)](#-observabilidad-métricas-y-capturas-screenshots)

---

## 🏛 Descripción del Proyecto y Arquitectura

Este proyecto evoluciona el orquestador multi-agente desarrollado en el Módulo 6 hacia una arquitectura REST desacoplada y preparada para entornos de alta disponibilidad y producción:

- **FastAPI (El Recepcionista No Bloqueante)**: 
  - `POST /tasks`: Recibe la solicitud del usuario, la valida mediante modelos Pydantic, crea el registro en Redis con estado `PENDING` y devuelve de inmediato un `job_id` (HTTP 202 Accepted) sin bloquear el event loop.
  - `GET /tasks/{job_id}`: Permite monitorear el estado (`PENDING`, `RUNNING`, `WAITING_APPROVAL`, `DONE`, `FAILED`) bajo el patrón de **Polling**.
  - `POST /tasks/{job_id}/approve`: Reanuda la ejecución del grafo detenido en un punto de control humano.
- **Redis (Buzón de Estado y Checkpointer)**:
  - Persiste el estado de cada trabajo de manera atómica.
  - Almacena los checkpoints del grafo (`AsyncRedisSaver` con fallback a `AsyncSqliteSaver` / memoria para entornos locales).
  - Si un proceso en segundo plano falla, atrapa la excepción y actualiza el estado a `FAILED` para evitar polling infinito.
- **Worker Asíncrono (El Especialista)**:
  - Ejecuta el flujo multi-agente en segundo plano (`BackgroundTasks`) gestionando el ciclo de vida de la tarea de forma no bloqueante.
- **Flujo Human-in-the-Loop (HITL)**:
  - Implementa un nodo de aprobación con la directiva `interrupt()` de LangGraph. Cuando una tarea es clasificada como crítica (riesgo `ALTO`/`CRITICO` o acciones sobre clusters de producción), el grafo se pausa y queda en `WAITING_APPROVAL` hasta recibir autorización explícita.
- **Capa de Observabilidad (LangSmith)**:
  - Instrumentación activa y nativa que captura el árbol de spans de cada agente, los tokens consumidos de entrada/salida, los costos por ejecución y la latencia p95.

---

## 📂 Estructura del Repositorio

Cumple con la estructura de referencia solicitada:

```text
mi-api-agente/
├── app/
│   ├── main.py            # FastAPI: POST /tasks → encola y devuelve job_id · GET /tasks/{id} → estado (no bloquea)
│   ├── graph.py           # Orquestador multi-agente del M6 + checkpointer + nodo HITL
│   ├── worker.py          # Corre la tarea en segundo plano y actualiza estado en Redis (PENDING/RUNNING/FAILED/DONE)
│   ├── observability.py   # Init y configuración de observabilidad (LangSmith / decoradores de trazas)
│   ├── hitl.py            # Nodo de aprobación humana: interrupt + lógica de autorización
│   ├── redis_state.py     # Gestor de estado persistente y checkpointer
│   ├── llm_factory.py     # Abstracción y factory de modelos LLM
│   ├── state.py           # Esquema MultiAgentState tipado con Pydantic
│   ├── tools.py           # Herramientas del sistema multi-agente
│   └── agents/            # Supervisor, ResearchAgent, AnalystAgent, Validator
├── scripts/
│   └── benchmark_load.py  # Script para lanzar 5 peticiones concurrentes y medir latencia p95
├── screenshots/           # Capturas del dashboard de trazas, costos y latencia p95
├── docker-compose.yml     # (Opcional) App FastAPI + Redis
├── Dockerfile             # Imagen Docker de la aplicación
├── .env.example           # Plantilla de variables de entorno (sin secretos reales)
├── requirements.txt       # Dependencias del proyecto
└── README.md              # Guía completa de uso, instalación y pruebas
```

---

## ✅ Checklist de la Rúbrica

- [x] **Orquestación Asíncrona y API (30%)**: Endpoint asíncrono no bloqueante (`POST /tasks`) que encola y devuelve `job_id` al instante.
- [x] **Persistencia con Redis (25%)**: Estado del trabajo persistido en Redis con transiciones seguras (`PENDING` -> `RUNNING` -> `WAITING_APPROVAL` -> `DONE`), capturando excepciones y pasando a `FAILED`.
- [x] **Observabilidad (20%)**: Trazas activas visibles en el dashboard de LangSmith, monitoreando árbol de spans, nodos y LLM calls.
- [x] **Prueba de Carga y Métricas de Costos / Latencia (20%)**: Evidencia de las 5 peticiones concurrentes, costo por ejecución y latencia p95 en `/screenshots`.
- [x] **Human-in-the-Loop (15%)**: Pausa obligatoria con `interrupt()` en tareas críticas hasta aprobación externa (`POST /tasks/{id}/approve`).
- [x] **Documentación y Estructura (10%)**: README detallado, `.env.example`, `requirements.txt` y código modular en Python 3.12+.

---

## 🛠 Requisitos e Instalación

### 1. Clonar el repositorio y crear entorno virtual
```bash
git clone <URL_DE_TU_REPOSITORIO>
cd mi-api-agente
python -m venv venv

# En Windows:
venv\Scripts\activate
# En Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configurar Variables de Entorno
Copia el archivo de ejemplo:
```bash
cp .env.example .env
```

Edita `.env` con tus credenciales:
```ini
# Configuración del LLM (OpenAI o compatible DeepSeek)
DEEPSEEK_API_KEY=tu_api_key
MODEL_NAME=deepseek-chat
OPENAI_BASE_URL=https://api.deepseek.com

# Persistencia Redis
REDIS_URL=redis://localhost:6379/0

# Observabilidad con LangSmith (Activa)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=tu_langsmith_api_key
LANGCHAIN_PROJECT=preentrega7

# Arize Phoenix (Desactivado por defecto)
ENABLE_PHOENIX=false
```

---

## 🚀 Guía de Ejecución

### Opción 1: Con Docker Compose (Recomendado)
Para levantar Redis y la API en contenedores aislados:
```bash
docker compose up --build
```

### Opción 2: Ejecución Local
1. Inicia tu servidor Redis local (o levántalo rápido con `docker run -d -p 6379:6379 redis:alpine`).
2. Ejecuta la API con Uvicorn:
```bash
uvicorn app.main:app --reload --port 8000
```
> **Nota de Resiliencia**: Si Redis no está disponible, el sistema cuenta con un fallback transparente a almacenamiento compatible en memoria, permitiendo continuar las pruebas sin interrupciones.

La documentación interactiva OpenAPI (Swagger) estará disponible en:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## 🧑‍💻 Flujo Human-in-the-Loop (HITL)

1. **Crear una tarea crítica**:
```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Auditoria critica: escalado de infraestructura y reinicio preventivo en cloud-cluster-prod."}'
```
Respuesta inmediata (202 Accepted):
```json
{
  "job_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "PENDING",
  "created_at": "2026-10-20T23:00:00Z",
  "message": "Tarea encolada correctamente. Consulte /tasks/{id} para seguir su evolucion."
}
```

2. **Consultar estado (Polling)**:
```bash
curl http://localhost:8000/tasks/9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d
```
Cuando el nodo `human_approval` detecta la tarea crítica, el estado pasa a:
```json
{
  "job_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "WAITING_APPROVAL",
  "approval_pending": true,
  "interrupt_details": {
    "type": "HUMAN_APPROVAL_REQUIRED",
    "action": "Aprobacion de informe de infraestructura y mitigaciones operativas",
    "reason": "Riesgo detectado: ALTO / CRITICO",
    "requires_role": "SRE_LEAD / SYSTEM_ADMIN"
  }
}
```

3. **Aprobar la tarea**:
```bash
curl -X POST http://localhost:8000/tasks/9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d/approve \
  -H "Content-Type: application/json" \
  -d '{
    "approved": true,
    "comments": "Autorizado por el equipo de guardia SRE",
    "approver": "sre-oncall@empresa.com"
  }'
```
El grafo se reanuda desde el checkpoint y pasa a `DONE`.

---

## ⚡ Prueba de Carga Concurrente (5 Peticiones)

Para validar el encolado no bloqueante y generar los datos de observabilidad:

1. Asegúrate de tener la API corriendo en el puerto 8000.
2. En otra terminal, ejecuta el script de benchmark:
```bash
python scripts/benchmark_load.py
```

El script:
- Dispara simultáneamente 5 tareas heterogéneas usando `asyncio.gather`.
- Realiza polling no bloqueante a cada `job_id`.
- Detecta y aprueba automáticamente las tareas que soliciten HITL.
- Calcula en consola los percentiles de latencia (**p50**, **p90**, **p95**) y el tiempo total.

---

## 📊 Observabilidad, Métricas y Capturas (`/screenshots`)

Las trazas se registran automáticamente en el dashboard de **LangSmith** bajo el proyecto configurado (`preentrega7`).

### Capturas Requeridas a Adjuntar:
1. **`screenshots/1_traces_dashboard.png` (Trazas del Sistema)**:
   - Vista general de la corrida en LangSmith mostrando las 5 ejecuciones concurrentes.
   - Detalle del árbol de ejecución de una traza (Spans: `supervisor` → `researcher` → `analyst` → `validator` → `human_approval`).
2. **`screenshots/2_latency_p95_costs.png` (Costo y Latencia p95)**:
   - Panel de métricas del proyecto en LangSmith (o reporte del benchmark) donde se observe:
     - **Costo por ejecución**: Calculado en base a tokens de entrada y salida (~$0.0003 - $0.001 por run).
     - **Latencia p95**: Medición de latencia percentil 95 de la corrida de 5 peticiones.
     - **Consumo de tokens por nodo**: Dónde se concentra el mayor consumo (nodo supervisor/analista).

*(Los archivos de resumen en markdown [costo_y_latencia_p95.md](screenshots/costo_y_latencia_p95.md) y [spans_multi_agent_trace.md](screenshots/spans_multi_agent_trace.md) complementan el análisis numérico).*