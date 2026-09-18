"""Integration tests for secnorm lightweight HTTP daemon (`src/secnorm/server.py`)."""

import json
import threading
import urllib.error
import urllib.request
import pytest
from secnorm.pipeline import PIPELINE_VERSION
from secnorm.server import create_server


@pytest.fixture(scope="module")
def http_server():
    try:
        # Bind to port 0 to let OS select an available port
        server = create_server(host="127.0.0.1", port=0)
    except (PermissionError, OSError) as e:
        pytest.skip(f"Socket bind not permitted in current environment: {e}")

    actual_port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{actual_port}"

    # Verify if loopback socket connect is permitted in this environment
    try:
        with urllib.request.urlopen(f"{base_url}/health", timeout=1.0) as resp:
            pass
    except (urllib.error.URLError, PermissionError, OSError) as e:
        server.shutdown()
        server.server_close()
        pytest.skip(f"Socket connect not permitted in current environment: {e}")

    yield base_url

    server.shutdown()
    server.server_close()


def test_http_health_endpoint(http_server: str):
    url = f"{http_server}/health"
    with urllib.request.urlopen(url, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "ok"
        assert data["version"] == PIPELINE_VERSION


def test_http_normalize_endpoint(http_server: str):
    url = f"{http_server}/normalize"
    payload = json.dumps({
        "text": "Hello   world! Check аpple.com",
        "preset": "security_balanced",
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["normalized_text"] == "Hello world! Check apple.com"
        assert any(f["category"] == "homoglyph" for f in data["flags"])


def test_http_normalize_with_include_risk(http_server: str):
    url = f"{http_server}/normalize"
    payload = json.dumps({
        "text": "Check аpple.com",
        "include_risk": True,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "risk_report" in data
        assert data["risk_report"]["score"] > 0.0
        assert data["risk_report"]["recommended_action"] in ("allow", "flag", "block")


def test_http_normalize_batch_endpoint(http_server: str):
    url = f"{http_server}/normalize/batch"
    payload = json.dumps({
        "texts": ["Line   one", "аpple.com"],
        "preset": "security_strict",
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["normalized_text"] == "Line one"
        assert data[1]["normalized_text"] == "apple.com"


def test_http_bad_request_missing_text(http_server: str):
    url = f"{http_server}/normalize"
    payload = json.dumps({"preset": "minimal"}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req, timeout=5)
    assert exc_info.value.code == 400


def test_http_not_found(http_server: str):
    url = f"{http_server}/non_existent_route"
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(url, timeout=5)
    assert exc_info.value.code == 404


def test_http_batch_bad_request_types(http_server: str):
    url = f"{http_server}/normalize/batch"
    invalid_payloads = [
        {"texts": ["ok", 123]},
        {"texts": [None]},
        {"texts": "not-a-list"},
        {"texts": ["ok"], "n_jobs": "not-an-int"},
        {"texts": ["ok"], "n_jobs": 0},
    ]
    for p in invalid_payloads:
        req = urllib.request.Request(
            url,
            data=json.dumps(p).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req, timeout=5)
        assert exc_info.value.code == 400

    # Ensure server survived and handles next valid request
    valid_req = urllib.request.Request(
        url,
        data=json.dumps({"texts": ["alive"]}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(valid_req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert len(data) == 1
        assert data[0]["normalized_text"] == "alive"

