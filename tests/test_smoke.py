from fastapi.testclient import TestClient
from app.main import app

def test_health_reports_unconfigured_ai_honestly():
    with TestClient(app) as client:
        response = client.get('/api/health')
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'ok'
        assert data['clinical_validation'] is False

def test_register_and_me():
    import uuid
    email = f"test-{uuid.uuid4().hex}@example.com"
    with TestClient(app) as client:
        response = client.post('/api/auth/register', json={"email": email, "password": "a-strong-test-password", "language": "fa", "role": "general"})
        assert response.status_code == 200, response.text
        token = response.json()['access_token']
        me = client.get('/api/auth/me', headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()['email'] == email

def test_chat_requires_auth():
    with TestClient(app) as client:
        response = client.post('/api/chat', json={"message": "What is hypertension?", "language": "en"})
        assert response.status_code == 401
