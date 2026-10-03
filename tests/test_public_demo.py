"""Verify the actual deployment entrypoint and its public boundary."""
from index import app


def test_wsgi_entrypoint_serves_assets_and_does_not_expose_evaluation_files():
    client = app.test_client()
    assert client.get('/').status_code == 200
    for asset in ('app.js', 'style.css'):
        response = client.get('/static/' + asset)
        assert response.status_code == 200 and response.data
    for path in ('/data/demo/truth/stable-0.csv', '/.env', '/api/sample/unknown'):
        assert client.get(path).status_code == 404


def test_public_demo_recalculates_and_responses_are_not_cached():
    client = app.test_client()
    overdue = client.post('/api/forecast', data={'sample': 'stable', 'capacity': '1000'})
    spacious = client.post('/api/forecast', data={'sample': 'stable', 'capacity': '9999'})
    assert overdue.status_code == spacious.status_code == 200
    assert overdue.json['plan']['status'] == 'overdue'
    assert spacious.json['plan']['hit_date'] is None
    assert overdue.headers['Cache-Control'] == spacious.headers['Cache-Control'] == 'no-store'
    assert client.get('/api/sample/stable').headers['Cache-Control'] == 'no-store'
