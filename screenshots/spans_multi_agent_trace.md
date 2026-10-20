# Evidencia de Trazas y Spans (Arize Phoenix / OpenInference)

## Árbol de Spans por Tarea
`
[Trace] MultiAgentGraph Execution (job_id: cb48f4e7-4f46-426f)
  ├── [Span] START
  ├── [Span] supervisor (Enrutamiento dinámico -> researcher)
  ├── [Span] researcher (Extracción de telemetría y llamadas a tools)
  ├── [Span] supervisor (Enrutamiento dinámico -> analyst)
  ├── [Span] analyst (Cómputo determinístico: disponibilidad y estrés)
  ├── [Span] supervisor (Enrutamiento dinámico -> validator)
  ├── [Span] validator (Control determinístico de calidad de datos)
  ├── [Span] supervisor (Síntesis final ejecutiva -> FINISH)
  └── [Span] human_approval (Pausa HITL obligatoria e interrupt)
`

## Plataformas de Monitoreo
- **Arize Phoenix**: Trazado visual en tiempo real en http://localhost:6006 con árbol de spans e inspección de payloads.
- **LangSmith**: Trazas integradas en la nube mediante LANGCHAIN_TRACING_V2=true.