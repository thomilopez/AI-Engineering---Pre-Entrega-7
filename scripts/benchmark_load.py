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
    print(f'*Tarea {idx}] -> Enviando...('.replace('*', '[').replace('(', ']'))
    res = await client.post(f'{API_BASE_URL}/tasks', json={'prompt': prompt}, timeout=30.0)
    if res.status_code != 202:
        return {'idx': idx, 'success': False, 'time': time.perf_counter() - t1}

    job_id = res.json()['job_id']
    print(f'*Tarea {idx}] -> Encolada: {job_id}'.replace('*', '['))

    polls = 0
    while polls < 60:
        await asyncio.sleep(2.0)
        polls += 1
        check = await client.get(f'{API_BASE_URL}/tasks/{job_id}', timeout=10.0)
        if check.status_code != 200:
            continue
        data = check.json()
        st = data.get('status')

        if st == 'WAITING_APPROVAL':
            print(f'*Tarea {idx}] -> HITL detectado. Aprobando...'.replace('*', '[').replace('(', ']'))
            apr = await client.post(
                f'{API_BASE_URL}/tasks/{job_id}/approve',
                json={'approved': True, 'comments': 'Aprobado', 'approver': 'sre_lead'},
                timeout=30.0
            )
            if apr.status_code == 200:
                st = apr.json().get('status')

        if st in ('DONE', 'FAILED'):
            dur = time.perf_counter() - t1
            print(f'*Tarea {idx}] -> Status: st en dur'.replace('*', '['))
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
    print('-' * 80)
    print('INICIANDO PRUEBA 5 PETICIONES CONCURRENTES')
    print('-' * 80)
    async with httpx.AsyncClient() as client:
        t0 = time.perf_counter()
        res = await asyncio.gather(*[run_single_task(client, p, i + 1) for i, p in enumerate(TASKS)])
        total = time.perf_counter() - t0

    t = [r['time'] for r in res if 'time' in r]
    succ = sum(1 for r in res if r.get('success'))
    print('-' * 80)
    print('REPORTE DE RENDIMIENTO CONCURRENTE')
    print('-' * 80)
    print('Peticiones: ', len(res))
    print('Exitosas:  ', succ, '/', len(res))
    print('Duracion:   ', round(total, 2))
    if t:
        print('Latencia p50:', round(calc_pct(t, 50), 2))
        print('Latencia p95:', round(calc_pct(t, 95), 2))
    print('-' * 80)


if __name__ == '__main__':
    asyncio.run(main())
