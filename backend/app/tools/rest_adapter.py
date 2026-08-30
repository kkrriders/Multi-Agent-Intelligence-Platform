import ipaddress
import socket
from urllib.parse import urlparse

import httpx


class ToolConfigError(Exception):
    pass


def _guard_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ToolConfigError(f"Unsupported scheme: {parsed.scheme}")
    host = parsed.hostname
    if not host:
        raise ToolConfigError("Missing host in URL")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ToolConfigError(f"Could not resolve host: {host}") from exc
    
    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if addr.is_loopback:
            continue
        if addr.is_private or addr.is_link_local or addr.is_reserved:
            raise ToolConfigError(f"Refusing to call private/internal address: {host}")


def invoke(config: dict, input: dict) -> dict:
    url = config["url"]
    method = config.get("method", "GET").upper()
    headers = config.get("headers", {})

    _guard_url(url)

    response = httpx.request(
        method,
        url,
        headers=headers,
        json=input if method in ("POST", "PUT", "PATCH") else None,
        params=input if method == "GET" else None,
        timeout=10.0,
       
        follow_redirects=False,
    )
    return {"status": response.status_code, "body": response.text}
