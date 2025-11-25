from artemis.api.http_gateway.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_health():
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json()['status'] == 'ok'

def test_list_tasks():
    r = client.get('/tasks')
    assert r.status_code == 200
    assert 'pull_stock_quotes' in r.json()['tasks']

def test_run_stock_quotes():
    r = client.post('/tasks/pull_stock_quotes/run', json={'params': {'symbols': ['AAPL','MSFT']}})
    assert r.status_code == 200
    data = r.json()
    assert data['task_code'] == 'pull_stock_quotes'
    assert data['stats']['records_emitted'] == 2

