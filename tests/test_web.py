from __future__ import annotations

from fastapi.testclient import TestClient

from aircanvas.web.server import create_app


def test_health_and_index():
    client = TestClient(create_app())
    health = client.get("/api/health")
    assert health.status_code == 200
    payload = health.json()
    assert payload["ok"] is True
    assert payload["features"]["browser_camera"] is True
    assert payload["features"]["os_mouse_control"] is False
    index = client.get("/")
    assert index.status_code == 200
    assert "AirCanvas" in index.text
    assert "app.js" in index.text


def test_websocket_manual_drawing_is_shared_core():
    client = TestClient(create_app())
    with client.websocket_connect("/ws") as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "ready"
        state = websocket.receive_json()
        assert state["type"] == "state"
        websocket.send_json({"type": "hello", "config": {"mode": "screen", "tool": "draw"}})
        configured = websocket.receive_json()
        assert configured["type"] == "configured"
        websocket.receive_json()  # state after hello
        websocket.send_json({"type": "pointer", "phase": "start", "x": 0.2, "y": 0.2})
        websocket.receive_json()
        websocket.send_json({"type": "pointer", "phase": "move", "x": 0.4, "y": 0.4})
        websocket.receive_json()
        websocket.send_json({"type": "pointer", "phase": "end"})
        final = websocket.receive_json()
        assert final["type"] == "state"
        strokes = final["state"]["drawing"]["strokes"]
        assert len(strokes) == 1
        assert strokes[0]["points"][0] == [0.2, 0.2]
        assert final["state"]["mode"] == "screen"


def test_websocket_demo_seek_produces_tracking():
    client = TestClient(create_app())
    with client.websocket_connect("/ws") as websocket:
        websocket.receive_json()
        websocket.receive_json()
        websocket.send_json({"type": "hello", "config": {"mode": "mirror", "mirror_tool": "track"}})
        websocket.receive_json()
        websocket.receive_json()
        websocket.send_json({"type": "demo", "enabled": True, "seek": 5.8})
        found = False
        for _ in range(40):
            message = websocket.receive_json()
            if message["type"] == "state":
                tracks = message["state"].get("tracks", [])
                if any(track["status"] in ("tracking", "occluded", "reacquiring") for track in tracks):
                    found = True
                    break
        assert found
