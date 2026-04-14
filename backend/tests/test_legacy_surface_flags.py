from flask import Flask

from app.api import report_bp, simulation_bp
from app.config import Config


def _make_simulation_client():
    app = Flask(__name__)
    app.register_blueprint(simulation_bp, url_prefix="/api/simulation")
    return app.test_client()


def _make_report_client():
    app = Flask(__name__)
    app.register_blueprint(report_bp, url_prefix="/api/report")
    return app.test_client()


def test_simulation_surface_returns_410_when_disabled(monkeypatch):
    client = _make_simulation_client()
    monkeypatch.setattr(Config, "ENABLE_LEGACY_ZEP_SIMULATION", False)

    response = client.get("/api/simulation/entities/graph-1")

    assert response.status_code == 410
    payload = response.get_json()
    assert payload["success"] is False
    assert payload["surface"] == "simulation"
    assert payload["runtime_surface"] == "legacy_zep"


def test_simulation_surface_still_routes_when_enabled(monkeypatch):
    client = _make_simulation_client()
    monkeypatch.setattr(Config, "ENABLE_LEGACY_ZEP_SIMULATION", True)
    monkeypatch.setattr(Config, "ZEP_API_KEY", None)

    response = client.get("/api/simulation/entities/graph-1")

    assert response.status_code == 500
    payload = response.get_json()
    assert payload["error"] == "ZEP_API_KEY未配置"


def test_report_surface_returns_410_when_disabled(monkeypatch):
    client = _make_report_client()
    monkeypatch.setattr(Config, "ENABLE_LEGACY_ZEP_REPORTING", False)

    response = client.post("/api/report/generate", json={})

    assert response.status_code == 410
    payload = response.get_json()
    assert payload["success"] is False
    assert payload["surface"] == "reporting"
    assert payload["runtime_surface"] == "legacy_zep"


def test_report_surface_still_routes_when_enabled(monkeypatch):
    client = _make_report_client()
    monkeypatch.setattr(Config, "ENABLE_LEGACY_ZEP_REPORTING", True)

    response = client.post("/api/report/generate", json={})

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["error"] == "请提供 simulation_id"
