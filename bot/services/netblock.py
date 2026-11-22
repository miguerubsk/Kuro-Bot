"""
Esquivar bloqueos de la web (lo mismo que hace Anime-Automator en core/netblock.py).

Dos casos:

- Bloqueo de LaLiga: en los partidos, los operadores bloquean IPs enteras de
  Cloudflare y la conexión acaba en un servidor con un certificado falso. La
  web sigue funcionando en otras IPs de Cloudflare: se piden por DNS cifrado
  (DoH a 1.1.1.1 / 8.8.8.8, por IP) y se prueba cada una CON verificación de
  certificado (el SNI y el certificado siguen siendo los del nombre real; solo
  cambia a qué IP se conecta). La que funcione se fija para ese nombre un rato.
- La web nos niega el acceso (403 y parecidos) o no hay IP libre: si hay
  proxy (BLOCK_BYPASS_PROXY, p. ej. Tor «socks5://host:9050»), ese servidor
  se descarga por el proxy durante el mismo rato.
"""

import logging
import ssl
import time
import urllib.parse

import httpx

log = logging.getLogger(__name__)

DOH_SERVERS = (
    ("https://1.1.1.1/dns-query", {"accept": "application/dns-json"}),
    ("https://8.8.8.8/resolve", {}),
)


def is_cert_failure(exc: BaseException) -> bool:
    """¿Falló la verificación del certificado? (lo que se ve desde una IP bloqueada)"""
    while exc is not None:
        if isinstance(exc, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(exc):
            return True
        exc = exc.__cause__ or exc.__context__
    return False


def host_of(url: str) -> str:
    return (urllib.parse.urlparse(url).hostname or "").lower()


class NetBypass:
    TTL = 6 * 3600

    def __init__(self, proxy: str = "", headers: dict | None = None, timeout: float = 30):
        self.proxy = proxy
        self.headers = headers or {}
        self.timeout = timeout
        self._pins: dict[str, tuple[str, float]] = {}   # host -> (ip, caduca)
        self._proxied: dict[str, float] = {}           # host -> caduca
        self._proxy_client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------ estado
    def pinned(self, host: str) -> str | None:
        pin = self._pins.get(host)
        if pin and pin[1] < time.time():
            self._pins.pop(host, None)
            return None
        return pin[0] if pin else None

    def proxied(self, host: str) -> bool:
        until = self._proxied.get(host)
        if until and until < time.time():
            self._proxied.pop(host, None)
            return False
        return bool(until) and bool(self.proxy)

    def use_proxy(self, host: str):
        if self.proxy and not self.proxied(host):
            log.warning("%s nos bloquea: lo descargo por el proxy durante %s h", host, self.TTL // 3600)
        self._proxied[host] = time.time() + self.TTL

    # --------------------------------------------------------- peticiones
    async def get_pinned(self, client: httpx.AsyncClient, url: str, ip: str) -> httpx.Response:
        """GET a `url` conectando a `ip` (con el SNI, el Host y el certificado del nombre real)."""
        u = urllib.parse.urlparse(url)
        target = u._replace(netloc=ip + (f":{u.port}" if u.port else "")).geturl()
        return await client.get(target, headers={"Host": u.hostname},
                                extensions={"sni_hostname": u.hostname})

    async def get_proxied(self, url: str) -> httpx.Response:
        if self._proxy_client is None:
            self._proxy_client = httpx.AsyncClient(proxy=self.proxy, headers=self.headers,
                                                   follow_redirects=True, timeout=max(self.timeout, 60))
        return await self._proxy_client.get(url)

    async def close(self):
        if self._proxy_client is not None:
            await self._proxy_client.aclose()

    # --------------------------------------------------------- resolución
    @staticmethod
    async def resolve(host: str) -> list[str]:
        """IPv4 de `host` según los DoH (sin pasar por el DNS del sistema ni del operador)."""
        ips: list[str] = []
        async with httpx.AsyncClient(timeout=8) as c:
            for url, headers in DOH_SERVERS:
                try:
                    r = await c.get(url, params={"name": host, "type": "A"}, headers=headers)
                    for ans in r.json().get("Answer") or []:
                        if ans.get("type") == 1 and ans.get("data") not in ips:
                            ips.append(ans["data"])
                except Exception as ex:
                    log.debug("DoH %s falló para %s: %s", url, host, ex)
        return ips

    async def find_ip(self, client: httpx.AsyncClient, url: str) -> str | None:
        """Tras un certificado falso, una IP de ese nombre que funcione (y se queda fijada)."""
        host = host_of(url)
        bad = self.pinned(host)
        self._pins.pop(host, None)
        for ip in await self.resolve(host):
            if ip == bad:
                continue
            try:
                await self.get_pinned(client, f"https://{host}/", ip)
            except httpx.HTTPError:
                continue
            self._pins[host] = (ip, time.time() + self.TTL)
            log.warning("%s da un certificado falso (¿bloqueo de LaLiga?): uso %s durante %s h",
                        host, ip, self.TTL // 3600)
            return ip
        log.warning("%s da un certificado falso (¿bloqueo de LaLiga?) y no hay otra IP que funcione", host)
        return None
