import ipaddress
import socket
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter

TIMEOUT_SECONDS = 5
MAX_REDIRECTS = 3


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_result(url, checked_at, status_code=None, response_time_ms=None,
                error_type=None, error=None):
    is_success = error_type is None
    return {
        "url": url,
        "is_success": is_success,
        "status": "UP" if is_success else "DOWN",
        "status_code": status_code,
        "response_time_ms": response_time_ms,
        "checked_at": checked_at,
        "error_type": error_type,
        "error": error,
    }


def is_blocked_address(ip_text):
    ip = ipaddress.ip_address(ip_text)
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return (not ip.is_global) or ip.is_multicast


class Target:
    """A URL that has been checked and pinned to one validated IP address."""

    def __init__(self, scheme, hostname, ip, port, host_header, path):
        self.scheme = scheme
        self.hostname = hostname
        self.ip = ip
        self.port = port
        self.host_header = host_header
        self.path = path

    @property
    def pinned_url(self):
        ip_part = f"[{self.ip}]" if ":" in self.ip else self.ip
        return f"{self.scheme}://{ip_part}:{self.port}{self.path}"


def resolve_target(url):
    """Look the hostname up ONCE and validate every address it returned.

    Returns (Target, None) when safe, or (None, (error_type, message)).
    """
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        return None, ("invalid_url", "Only http and https URLs are allowed")
    if not parsed.hostname:
        return None, ("invalid_url", "URL has no hostname")
    if parsed.username or parsed.password:
        return None, ("invalid_url", "URLs with credentials are not allowed")

    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return None, ("invalid_url", "URL has an invalid port")

    try:
        addresses = socket.getaddrinfo(parsed.hostname, port,
                                       type=socket.SOCK_STREAM)
    except socket.gaierror:
        return None, ("dns", "Hostname could not be resolved")

    ips = []
    for address in addresses:
        ip_text = address[4][0]
        if is_blocked_address(ip_text):
            return None, ("blocked", "URL points to a private or internal address")
        ips.append(ip_text)

    if not ips:
        return None, ("dns", "Hostname could not be resolved")

    host_for_header = parsed.hostname
    if ":" in host_for_header:
        host_for_header = f"[{host_for_header}]"
    if parsed.port:
        host_for_header = f"{host_for_header}:{parsed.port}"

    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    target = Target(parsed.scheme, parsed.hostname, ips[0], port,
                    host_for_header, path)
    return target, None


class PinnedHTTPSAdapter(HTTPAdapter):
    """Connect to an IP address, but do the TLS checks against the hostname."""

    def __init__(self, hostname, **kwargs):
        self._hostname = hostname  # must be set before super().__init__
        super().__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        pool_kwargs["server_hostname"] = self._hostname   # name sent in the handshake (SNI)
        pool_kwargs["assert_hostname"] = self._hostname   # name the certificate must match
        super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)


def fetch_pinned(target):
    """Send one GET to the validated IP. No second DNS lookup happens."""
    session = requests.Session()
    session.trust_env = False  # ignore proxy variables, they would bypass the pinning
    try:
        if target.scheme == "https":
            session.mount("https://", PinnedHTTPSAdapter(target.hostname))
        return session.get(
            target.pinned_url,
            headers={"Host": target.host_header},
            timeout=TIMEOUT_SECONDS,
            allow_redirects=False,
        )
    finally:
        session.close()


def check_url(url):
    checked_at = utc_now()

    try:
        start = time.time()
        current_url = url
        redirects = 0

        while True:
            target, problem = resolve_target(current_url)
            if problem is not None:
                error_type, message = problem
                return make_result(url, checked_at,
                                   error_type=error_type, error=message)

            response = fetch_pinned(target)

            if not response.is_redirect:
                break

            redirects += 1
            if redirects > MAX_REDIRECTS:
                return make_result(url, checked_at,
                                   error_type="redirect_limit",
                                   error="Too many redirects")

            location = response.headers.get("Location")
            if not location:
                return make_result(url, checked_at,
                                   error_type="request_error",
                                   error="Redirect without a Location header")
            current_url = urljoin(current_url, location)

        end = time.time()
        elapsed_ms = round((end - start) * 1000)

        if response.status_code < 400:
            return make_result(url, checked_at, response.status_code, elapsed_ms)

        return make_result(url, checked_at, response.status_code, elapsed_ms,
                           "http_error", f"HTTP {response.status_code}")

    except requests.exceptions.Timeout:
        return make_result(url, checked_at,
                           error_type="timeout", error="Request timed out")

    except requests.exceptions.SSLError:
        return make_result(url, checked_at,
                           error_type="tls", error="TLS/SSL certificate or handshake error")

    except requests.exceptions.ConnectionError:
        return make_result(url, checked_at,
                           error_type="connection", error="Connection failed")

    except requests.exceptions.RequestException as error:
        return make_result(url, checked_at,
                           error_type="request_error", error=str(error))


if __name__ == "__main__":
    test_urls = [
        "https://www.google.com",
        "http://github.com",
        "https://github.com/this-page-is-fake-12345",
    ]

    for test_url in test_urls:
        print(check_url(test_url))