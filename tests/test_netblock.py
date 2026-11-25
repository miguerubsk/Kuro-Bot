"""Esquivar bloqueos: certificados falsos (otra IP de Cloudflare) y el proxy."""

import ssl
import unittest
from unittest import mock

import httpx

from bot.services.netblock import NetBypass, host_of, is_cert_failure
from tests.test_services import fake_http

REAL_CLIENT = httpx.AsyncClient   # el de verdad (fake_http parchea httpx.AsyncClient)


def doh(answers: dict[str, list[dict]]):
    """Respuestas de los DNS cifrados: {servidor: Answer} (sin entrada, el servidor falla)."""
    def handler(request):
        if request.url.host not in answers:
            return httpx.Response(500, text="caído")
        return httpx.Response(200, json={"Answer": answers[request.url.host]})
    return handler


def a(ip: str, kind: int = 1) -> dict:
    return {"type": kind, "data": ip}


class CertFailureTest(unittest.TestCase):
    def test_fake_certificate(self):
        self.assertTrue(is_cert_failure(ssl.SSLCertVerificationError("mal")))
        self.assertTrue(is_cert_failure(httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate")))

    def test_looks_inside_the_chain(self):
        for link in ("__cause__", "__context__"):
            outer = httpx.ConnectError("fallo de conexión")
            setattr(outer, link, ssl.SSLCertVerificationError("mal"))
            self.assertTrue(is_cert_failure(outer), link)

    def test_other_errors(self):
        outer = httpx.ConnectError("fallo de conexión")
        outer.__cause__ = OSError("sin red")
        self.assertFalse(is_cert_failure(outer))

    def test_host_of(self):
        self.assertEqual(host_of("https://Paste.Japan-Paw.net:8443/?v=1"), "paste.japan-paw.net")
        self.assertEqual(host_of("no es una url"), "")


class ProxyStateTest(unittest.TestCase):
    def test_a_blocking_host_goes_through_the_proxy(self):
        bypass = NetBypass("socks5://tor:9050")
        self.assertFalse(bypass.proxied("web.com"))
        with self.assertLogs("bot.services.netblock", "WARNING") as logs:
            bypass.use_proxy("web.com")
            bypass.use_proxy("web.com")
        self.assertEqual(len(logs.output), 1)   # se avisa una vez
        self.assertTrue(bypass.proxied("web.com"))
        self.assertFalse(bypass.proxied("otra.com"))

    def test_without_proxy_nothing_goes_through_it(self):
        bypass = NetBypass()
        with self.assertNoLogs("bot.services.netblock"):
            bypass.use_proxy("web.com")
        self.assertFalse(bypass.proxied("web.com"))

    def test_only_for_a_while(self):
        bypass = NetBypass("socks5://tor:9050")
        bypass.TTL = -1
        with self.assertLogs("bot.services.netblock", "WARNING"):
            bypass.use_proxy("web.com")
        self.assertFalse(bypass.proxied("web.com"))
        self.assertFalse(bypass.proxied("web.com"))


class ResolveTest(unittest.IsolatedAsyncioTestCase):
    async def test_ipv4_from_both_servers_without_repeats(self):
        seen = []
        handler = doh({"1.1.1.1": [a("10.0.0.1"), a("::1", kind=28), a("10.0.0.2")],
                       "8.8.8.8": [a("10.0.0.2"), a("10.0.0.3")]})

        def record(request):
            seen.append(request)
            return handler(request)

        with fake_http(record):
            self.assertEqual(await NetBypass.resolve("web.com"), ["10.0.0.1", "10.0.0.2", "10.0.0.3"])
        self.assertEqual([(r.url.host, dict(r.url.params)) for r in seen],
                         [("1.1.1.1", {"name": "web.com", "type": "A"}), ("8.8.8.8", {"name": "web.com", "type": "A"})])
        self.assertEqual(seen[0].headers["accept"], "application/dns-json")

    async def test_a_failing_server_is_skipped(self):
        with fake_http(doh({"8.8.8.8": [a("10.0.0.3")]})):
            self.assertEqual(await NetBypass.resolve("web.com"), ["10.0.0.3"])
        with fake_http(doh({"1.1.1.1": None, "8.8.8.8": [a("10.0.0.4")]})):
            self.assertEqual(await NetBypass.resolve("web.com"), ["10.0.0.4"])


class FindIpTest(unittest.IsolatedAsyncioTestCase):
    def site(self, working: set[str]):
        """La web: solo responde por las IPs de `working`; registra a qué IP se conecta."""
        self.tried: list[httpx.Request] = []

        def handler(request):
            self.tried.append(request)
            if request.url.host in working:
                return httpx.Response(200)
            raise httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED]", request=request)

        return REAL_CLIENT(transport=httpx.MockTransport(handler))

    async def test_pins_the_first_ip_that_works(self):
        client = self.site({"10.0.0.3"})
        bypass = NetBypass()
        with fake_http(doh({"1.1.1.1": [a("10.0.0.1"), a("10.0.0.2"), a("10.0.0.3")]})), \
                self.assertLogs("bot.services.netblock", "WARNING"):
            self.assertEqual(await bypass.find_ip(client, "https://web.com/x"), "10.0.0.3")
        self.assertEqual([(r.url.host, r.url.path, r.headers["host"]) for r in self.tried],
                         [("10.0.0.1", "/", "web.com"), ("10.0.0.2", "/", "web.com"), ("10.0.0.3", "/", "web.com")])
        self.assertEqual(self.tried[0].extensions["sni_hostname"], "web.com")
        self.assertEqual(bypass.pinned("web.com"), "10.0.0.3")

    async def test_the_pinned_ip_that_failed_is_not_retried(self):
        client = self.site({"10.0.0.1", "10.0.0.2"})
        bypass = NetBypass()
        with fake_http(doh({"1.1.1.1": [a("10.0.0.1"), a("10.0.0.2")]})), \
                self.assertLogs("bot.services.netblock", "WARNING"):
            await bypass.find_ip(client, "https://web.com/x")
            self.assertEqual(await bypass.find_ip(client, "https://web.com/x"), "10.0.0.2")

    async def test_no_ip_works(self):
        client = self.site(set())
        bypass = NetBypass()
        with fake_http(doh({"1.1.1.1": [a("10.0.0.1")]})), \
                self.assertLogs("bot.services.netblock", "WARNING") as logs:
            self.assertIsNone(await bypass.find_ip(client, "https://web.com/x"))
        self.assertIn("no hay otra IP", logs.output[0])
        self.assertIsNone(bypass.pinned("web.com"))

    async def test_the_pin_expires(self):
        client = self.site({"10.0.0.1"})
        bypass = NetBypass()
        bypass.TTL = -1
        with fake_http(doh({"1.1.1.1": [a("10.0.0.1")]})), self.assertLogs("bot.services.netblock", "WARNING"):
            self.assertEqual(await bypass.find_ip(client, "https://web.com/x"), "10.0.0.1")
        self.assertIsNone(bypass.pinned("web.com"))

    async def test_get_pinned_keeps_the_port(self):
        client = self.site({"10.0.0.1"})
        await NetBypass().get_pinned(client, "https://web.com:8443/a?b=1", "10.0.0.1")
        self.assertEqual(str(self.tried[0].url), "https://10.0.0.1:8443/a?b=1")


class ProxiedClientTest(unittest.IsolatedAsyncioTestCase):
    async def test_one_proxy_client_with_the_headers(self):
        created, clients, seen = [], [], []

        def factory(*args, **kwargs):
            created.append(dict(kwargs))
            kwargs.pop("proxy")
            clients.append(REAL_CLIENT(*args, **kwargs, transport=httpx.MockTransport(
                lambda r: seen.append(r) or httpx.Response(200))))
            return clients[-1]

        bypass = NetBypass("socks5://tor:9050", {"User-Agent": "Kuro"}, timeout=30)
        with mock.patch("httpx.AsyncClient", side_effect=factory):
            await bypass.get_proxied("https://web.com/1")
            await bypass.get_proxied("https://web.com/2")
        self.assertEqual(len(created), 1)
        self.assertEqual((created[0]["proxy"], created[0]["timeout"]), ("socks5://tor:9050", 60))
        self.assertEqual([(str(r.url), r.headers["user-agent"]) for r in seen],
                         [("https://web.com/1", "Kuro"), ("https://web.com/2", "Kuro")])
        await bypass.close()
        self.assertTrue(clients[0].is_closed)

    async def test_close_without_proxy_client(self):
        await NetBypass().close()


if __name__ == "__main__":
    unittest.main()
