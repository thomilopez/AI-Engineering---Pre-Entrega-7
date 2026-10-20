from __future__ import annotations
import asyncio
import time
import math
from typing import Any
import httpx

API_BASE_URL = 'http://127.0.0.1:8000'

TASKS = [
    'Auditoria de saturacion de CPU y memoria en nodo cloud-cluster-prod-worker-1.',
    'Analisis cuantitativo de tasa de fallos y disponibilidad en pasarela de pagos gateway-prod-az1.',
    'Verificacion de integridad de replicas de base de datos en db-cluster-main.',
    'Inspeccion de anomalias de red y rendimiento en k8s-ingress-prod.',
    'Auditoria critica: escalado de infraestructura y reinicio preventivo en cloud-cluster-prod.',
]


async def run_single_task(client: httpx.AsyncClient, prompt: str, idx: int) -> dict[str, Any]:
    t1 = time.perf_counter()
    print(f'[Tarea {idx}] -> Enviando...')

    res = None
    for attempt in range(4):
        try:
            res = await client.post(f'{API_BASE_URL}/tasks', json={'prompt': prompt}, timeout=120.0)
            if res.status_code == 202:
                break
        except Exception as e:
            if attempt == 3:
                print(f'[Tarea {idx}] Fallo en envio: {e}')
                return {'idx': idx, 'success': False, 'time': time.perf_counter() - t1}
            await asyncio.sleep(2.0)

    if not res or res.status_code != 202:
        return {'idx': idx, 'success': False, 'time': time.perf_counter() - t1}

    job_id = res.json()['job_id']
    print(f'[Tarea {idx}] -> Encolada: {job_id}')

    polls = 0
    while polls < 120:
        await asyncio.sleep(2.0)
        polls += 1
        try:
            check = await client.get(f'{API_BASE_URL}/tasks/{job_id}', timeout=30.0)
        except Exception:
            continue

        if check.status_code != 200:
            continue
        data = check.json()
        st = data.get('status')

        if st == 'WAITING_APPROVAL':
            print(f'[Tarea {idx}] -> HITL detectado en {job_id}. Aprobando...')
            try:
                apr = await client.post(
                    f'{API_BASE_URL}/tasks/{job_id}/approve',
                    json={'approved': True, 'comments': 'Aprobado por SRE Lead', 'approver': 'sre_lead'},
                    timeout=45.0
                )
                if apr.status_code == 200:
                    st = apr.json().get('status')
            except Exception as e:
                print(f'[Tarea {idx}] Error en aprobacion HITL: {e}')

        if st in ('DONE', 'FAILED'):
            dur = time.perf_counter() - t1
            print(f'[Tarea {idx}] -> Finalizada: Status={st} en {dur:.2f}s')
            return {
                'idx': idx,
                'job_id': job_id,
                'status': st,
                'success': st == 'DONE',
                'time': dur,
            }

    return {'idx': idx, 'success': False, 'time': time.perf_counter() - t1}


def calc_pct(vals, p):
    if not vals:
        return 0.0
    s = sorted(vals)
    k = (len(s) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[int(f)] * (c - k) + s[int(c)] * (k - f)


async def main():
    print('=' * 80)
    print('INICIANDO PRUEBA DE 5 PETICIONES CONCURRENTES (PREENTREGA 7)')
    print('=' * 80)
    limits = httpx.Limits(max_keepalive_connections=30, max_connections=50)
    timeout = httpx.Timeout(connect=30.0, read=120.0, write=30.0, pool=120.0)
    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        t0 = time.perf_counter()
        res = await asyncio.gather(*[run_single_task(client, p, i + 1) for i, p in enumerate(TASKS)])
        total = time.perf_counter() - t0

    t = [r['time'] for r in res if 'time' in r]
    succ = sum(1 for r in res if r.get('success'))
    print('=' * 80)
    print('REPORTE DE RENDIMIENTO CONCURRENTE')
    print('=' * 80)
    print(f'Total Peticiones:  {len(res)}')
    print(f'Exitosas:          {succ} / {len(res)}')
    print(f'Tiempo Total:      {total:.2f}s')
    if t:
        print(f'Latencia p50:      {calc_pct(t, 50):.2f}s')
        print(f'Latencia p90:      {calc_pct(t, 90):.2f}s')
        print(f'Latencia p95:      {calc_pct(t, 95):.2f}s')
    print('=' * 80)


if __name__ == '__main__':
    asyncio.run(main())