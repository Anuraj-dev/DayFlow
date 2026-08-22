from httpx import AsyncClient

from app.schemas.common import HealthResponse


def test_health_shape():
    payload = HealthResponse(status="ok", service="dayflow-api")
    assert payload.status == "ok"


async def test_health_endpoint(client: AsyncClient):
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "dayflow-api"}
