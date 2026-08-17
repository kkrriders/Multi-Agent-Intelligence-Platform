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
    # ponytail: blocks the real SSRF targets (internal networks, cloud metadata
    # endpoint) but allows loopback so a tool can target a locally-run service.
    # Every resolved address is checked, not just the first: a host can carry
    # both an IPv4 A record and an IPv6 AAAA record, and the HTTP client may
    # connect via either — validating only gethostbyname's IPv4 result would
    # let a public A record mask a private AAAA record on the same domain.
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
        # ponytail: explicit, not relying on httpx's default — a redirect target
        # is never re-validated by _guard_url, so silently following one would
        # let a public URL bounce the request to a private/internal address.
        follow_redirects=False,
    )
    return {"status": response.status_code, "body": response.text}
