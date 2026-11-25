import time
from curl_cffi.requests import Session as CurlSession
from ..errors import TransportError
from ..fingerprint.profiles import headers_for
from .base import Response

class HttpTransport:
    name = "http"

    def __init__(self, profile, timeout=30.0):
        self.profile = profile
        self.timeout = timeout
        self._s = CurlSession(impersonate=profile.impersonate)

    def send(self, url, method="GET", *, headers=None, data=None, json=None,
             referer=None, proxy=None) -> Response:
        h = headers_for(self.profile, referer)
        if headers:
            h.update(headers)
        self._s.proxies = {"http": proxy, "https": proxy} if proxy else {}
        t0 = time.monotonic()
        try:
            r = self._s.request(method, url, headers=h, data=data, json=json,
                                timeout=self.timeout, allow_redirects=True)
        except Exception as e:
            raise TransportError(str(e)) from e
        return Response(r.status_code, dict(r.headers), r.text, str(r.url),
                        time.monotonic() - t0, self.name)

    # cookie bridging
    def inject_cookies(self, cookies: dict):
        for k, v in cookies.items():
            self._s.cookies.set(k, v)

    def cookies(self) -> dict:
        return {c.name: c.value for c in self._s.cookies.jar}

    def close(self):
        self._s.close()