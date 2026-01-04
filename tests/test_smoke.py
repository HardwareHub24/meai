from fastapi.testclient import TestClient

import meai_web.server as server


def test_health():
    client = TestClient(server.app)
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "uptime_seconds" in data


def test_ask_normal(monkeypatch):
    def fake_rag_answer(mode, message, session_id):
        return "ok", [], {}

    monkeypatch.setattr(server, "rag_answer", fake_rag_answer)
    client = TestClient(server.app)
    res = client.post(
        "/api/ask",
        json={"mode": "mode_1", "message": "hello", "session_id": "s1"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["answer"] == "ok"


def test_ask_system_docs_only(monkeypatch):
    def fake_rag_answer(mode, message, session_id):
        return "system docs ok", [], {}

    monkeypatch.setattr(server, "rag_answer", fake_rag_answer)
    client = TestClient(server.app)
    res = client.post(
        "/api/ask",
        json={
            "mode": "mode_1",
            "message": "system-docs-only: show me the architecture",
            "session_id": "s2",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["answer"] == "system docs ok"


def test_math_simplify():
    client = TestClient(server.app)
    res = client.post(
        "/api/math",
        json={"task": "simplify", "expr": "2+2", "var": "x"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "result" in data


def test_hardwarehub_schedule(monkeypatch):
    import meai_core.engine as engine

    monkeypatch.setattr(engine, "ensure_session", lambda *args, **kwargs: None)
    monkeypatch.setattr(engine, "insert_message", lambda *args, **kwargs: "mid")

    def fail_plan(*args, **kwargs):
        raise AssertionError("plan should not be called for scheduling intent")

    monkeypatch.setattr(engine, "plan", fail_plan)

    client = TestClient(server.app)
    res = client.post(
        "/api/ask",
        json={
            "mode": "mode_1",
            "message": "I want to schedule a meeting with hardwarehub",
            "session_id": "s3",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "calendar.app.google/b9H7oKXC58tDX4ge9" in data["answer"]
