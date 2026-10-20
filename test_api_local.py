from fastapi.testclient import TestClient
from app.main import app

def test():
    client = TestClient(app)
    r = client.get('/health')
    print('Health response:', r.json())
    assert r.status_code == 200
    
    r_task = client.post('/tasks', json={'prompt': 'Auditoria de prueba local'})
    print('Task create response:', r_task.json())
    assert r_task.status_code == 202

if __name__ == '__main__':
    test()
