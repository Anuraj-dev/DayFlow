from app.schemas.common import HealthResponse


def test_health_shape():
    payload = HealthResponse(status="ok", service="dayflow-api")
    assert payload.status == "ok"
