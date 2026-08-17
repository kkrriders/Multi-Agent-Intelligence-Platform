import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.tools.rest_adapter import ToolConfigError, invoke


class _EchoHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format, *args):
        pass


@pytest.fixture
def echo_server():
    server = HTTPServer(("127.0.0.1", 0), _EchoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join()


def test_invoke_get_returns_status_and_body(echo_server):
    result = invoke({"url": echo_server, "method": "GET"}, {})
    assert result["status"] == 200
    assert result["body"] == "ok"


def test_invoke_rejects_non_http_scheme():
    with pytest.raises(ToolConfigError):
        invoke({"url": "file:///etc/passwd", "method": "GET"}, {})


def test_invoke_rejects_private_network_address():
    with pytest.raises(ToolConfigError):
        invoke({"url": "http://10.1.2.3/", "method": "GET"}, {})


def test_invoke_rejects_cloud_metadata_address():
    with pytest.raises(ToolConfigError):
        invoke({"url": "http://169.254.169.254/", "method": "GET"}, {})


def test_invoke_rejects_private_ipv6_address():
    with pytest.raises(ToolConfigError):
        invoke({"url": "http://[fd00::1]/", "method": "GET"}, {})


def test_invoke_rejects_link_local_ipv6_address():
    with pytest.raises(ToolConfigError):
        invoke({"url": "http://[fe80::1]/", "method": "GET"}, {})
