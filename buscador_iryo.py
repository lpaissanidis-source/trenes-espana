"""
Buscador Iryo usando Playwright + Chromium headless.

Estrategia:
1. Al primer uso se lanza Chromium en modo headless con fingerprint de Chrome real.
2. Navega a iryo.eu/es/home, lo que dispara el challenge JS de Cloudflare y
   deja la cookie cf_clearance setada en el contexto del browser.
3. Las llamadas a api.iryo.eu se hacen vía page.evaluate(fetch(...)), o sea
   desde adentro del browser, así el TLS fingerprint y las cookies que ve
   Cloudflare son las del Chromium real.
4. Tras un 401/403 se desactiva Iryo para el resto de la corrida.

cfgToken: firmado con HMAC-SHA256 por Iryo, expira ~24h. Si Iryo deja de
funcionar, capturalo de iryo.eu (DevTools > Network > 'search' > Payload)
y pegalo en CFG_TOKEN_DEFAULT o en el secret IRYO_CFG_TOKEN.
"""

import atexit
import os
import uuid
from datetime import datetime, time

try:
    from playwright.sync_api import sync_playwright
    _PW_AVAILABLE = True
except ImportError:
    _PW_AVAILABLE = False

API_URL          = "https://api.iryo.eu/b2c/availability/search"
HOME_URL         = "https://iryo.eu/es/home"
SUBSCRIPTION_KEY = "7c9b9b1ea0fe4f0c9d1739fcbf8b5438"

CFG_TOKEN_DEFAULT = (
    "H4sIAAAAAAAA/52QX0vDMBTFv0ueW0nSZs36NqWgOLHMgcgQSfNn1rUuJh0opd/dG8ukMkTw"
    "7Zybc3/nkh6JZotydHlH2QxFSNYKXEUlaCefQd8X56CNaUOqfCqvwfk3Ce5q9XALpqtb7TvR"
    "WhhRTGcxZjHN1iTNSZKz7AynLOEpS+eQ1e8/UvzXlHehoVyn+Cb0SYPyTQ9V4TrrYVR3Hchw"
    "sWlQbkTjdYSU9R+vKO/cAYy3ECZAO74P0ZHwckoYd04ByQgIk+m+0d8Ep6v9fvfvSyakg906"
    "ofSfKDpFPUJaevieIJQchXUw6dFiuRz9xapYrIugByhrvFDWhsDu6wjOKyESOY91Qqs4FUrF"
    "PNMi5ipjQhGMNSFoGD4BYuPt+SwCAAA="
    ".fRcDmoQXxwqrDt1G0VIgHWKJ5VEGFnVA+MJWYT7HhVE="
)
CFG_TOKEN = os.environ.get("IRYO_CFG_TOKEN") or CFG_TOKEN_DEFAULT

ESTACIONES = {
    "Madrid":      "X0000",
    "Barcelona":   "71801",   # Sants
    "Sevilla":     "51003",   # Santa Justa
    "Málaga":      "54413",   # María Zambrano
    "Córdoba":     "50500",
    "Alicante":    "60911",   # Terminal
    "Zaragoza":    "04040",   # Delicias
    "Valencia":    "60600",   # Joaquín Sorolla
}
DESTINOS_IRYO = set(ESTACIONES.keys()) - {"Madrid"}

# Globals del browser (lazy-init).
_pw            = None
_browser       = None
_context       = None
_page          = None
_session_dead  = False
_session_inited = False

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def sesion_activa():
    return _PW_AVAILABLE and not _session_dead


def ruta_disponible(destino):
    return destino in DESTINOS_IRYO


def _cleanup():
    global _pw, _browser, _context, _page
    for closer, obj in (("close", _page), ("close", _context),
                        ("close", _browser), ("stop", _pw)):
        try:
            if obj:
                getattr(obj, closer)()
        except Exception:
            pass
    _pw = _browser = _context = _page = None


def _init():
    """Lanza Chromium, abre iryo.eu y deja la sesión lista para llamar al API."""
    global _pw, _browser, _context, _page, _session_inited, _session_dead

    if _session_inited:
        return
    _session_inited = True

    if not _PW_AVAILABLE:
        print("  [Iryo] Playwright no instalado. Skipeando Iryo.")
        _session_dead = True
        return

    try:
        _pw = sync_playwright().start()
        _browser = _pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        _context = _browser.new_context(
            user_agent=USER_AGENT,
            locale="es-ES",
            viewport={"width": 1920, "height": 1080},
        )
        _page = _context.new_page()
        _page.goto(HOME_URL, wait_until="domcontentloaded", timeout=45000)
        # Esperar a que se ejecute el challenge JS de Cloudflare si hay.
        _page.wait_for_timeout(4000)
        print("  [Iryo] Browser inicializado (cookie cf_clearance lista).")
        atexit.register(_cleanup)
    except Exception as e:
        print(f"  [Iryo] Error al inicializar browser: {e}. Skipeando Iryo.")
        _session_dead = True
        _cleanup()


def _post(payload):
    """POST al API desde adentro del browser; usa el TLS y cookies de Chromium."""
    if not sesion_activa():
        return None
    _init()
    if _session_dead:
        return None

    headers = {
        "accept":                       "application/json, text/plain, */*",
        "accept-language":              "es-ES",
        "content-type":                 "application/json;charset=UTF-8",
        "no-authorization":             "",
        "ocp-apim-subscription-key":    SUBSCRIPTION_KEY,
        "request-channel":              "WEB",
        "x-client-version":             "1.104.2",
        "x-pwa-sessid":                 str(uuid.uuid4()),
        "x-request-id":                 str(uuid.uuid4()),
    }
    # Origin y Referer los pone el browser solo.

    try:
        result = _page.evaluate(
            """async (args) => {
                try {
                    const resp = await fetch(args.url, {
                        method:      'POST',
                        headers:     args.headers,
                        body:        JSON.stringify(args.payload),
                        credentials: 'include',
                    });
                    let body;
                    try { body = await resp.json(); }
                    catch (_) { body = await resp.text(); }
                    return { status: resp.status, body };
                } catch (e) {
                    return { status: -1, body: String(e) };
                }
            }""",
            {"url": API_URL, "headers": headers, "payload": payload},
        )
        return result
    except Exception as e:
        return {"status": -1, "body": f"playwright error: {e}"}


def _llamar_api(orig_code, dest_code, fecha_ida, fecha_vuelta):
    global _session_dead
    if not sesion_activa():
        return None

    payload = {
        "cfgToken": CFG_TOKEN,
        "currency": "EUR",
        "passengers": [{"id": "passenger_1", "type": "AD"}],
        "travels": [
            {"origin": orig_code, "destination": dest_code,
             "direction": "outbound", "departure": fecha_ida},
            {"origin": dest_code, "destination": orig_code,
             "direction": "inbound",  "departure": fecha_vuelta},
        ],
    }

    for intento in range(2):
        result = _post(payload)
        if result is None:
            return None
        sc = result.get("status")
        body = result.get("body")
        if sc == 200:
            if isinstance(body, dict):
                return body
            return None
        if sc in (401, 403):
            _session_dead = True
            print(f"  [Iryo] Bloqueado ({sc}) — Cloudflare WAF tras el browser, "
                  f"o cfgToken expirado. Skipeando Iryo el resto de la corrida.")
            return None
        snippet = str(body)[:200] if body else ""
        print(f"  [Iryo] Status {sc} intento {intento+1}: {snippet}")
    return None


def _to_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _extraer_min_precio(svc):
    candidatos = []
    for k in ("fares", "tariffs", "offers", "prices", "products", "rates"):
        items = svc.get(k)
        if not isinstance(items, list):
            continue
        for t in items:
            if not isinstance(t, dict):
                continue
            for pk in ("price", "amount", "totalPrice", "totalAmount"):
                v = t.get(pk)
                if isinstance(v, dict):
                    v = v.get("amount") or v.get("value")
                try:
                    candidatos.append(float(v))
                except (TypeError, ValueError):
                    pass
    return min(candidatos) if candidatos else None


def _extraer_trenes(data, direccion, hora_minima):
    if not data:
        return []
    h_min = time(*map(int, hora_minima.split(":")))
    trenes = []

    container = data.get("data") if isinstance(data.get("data"), dict) else data
    travels = (
        container.get("travels") or
        container.get("journeys") or
        container.get("legs") or
        []
    )

    for travel in travels:
        d = travel.get("direction")
        if d and d != direccion:
            continue
        servicios = (
            travel.get("services") or
            travel.get("trains") or
            travel.get("trips") or
            travel.get("itineraries") or
            []
        )
        for svc in servicios:
            dep = (
                svc.get("departureDateTime") or
                svc.get("departureTime") or
                svc.get("departure") or
                ""
            )
            dt = _to_dt(dep) if isinstance(dep, str) else None
            precio = _extraer_min_precio(svc)
            if not dt or precio is None:
                continue
            if dt.time() < h_min:
                continue
            trenes.append({
                "dt":    dt,
                "hhmm":  dt.strftime("%H:%M"),
                "price": precio,
            })
    return trenes


def buscar(origen, destino, fecha_ida, fecha_vuelta,
           hora_minima_ida="14:30", hora_minima_vuelta="16:00"):
    """
    Busca ida+vuelta en Iryo respetando filtros de hora.
    Devuelve dict con la misma estructura que buscador_ouigo.buscar, o None.
    """
    if not sesion_activa():
        return None
    if not ruta_disponible(destino):
        return None
    orig_code = ESTACIONES.get(origen)
    dest_code = ESTACIONES.get(destino)
    if not orig_code or not dest_code:
        return None

    try:
        data = _llamar_api(orig_code, dest_code, fecha_ida, fecha_vuelta)
        if data is None:
            return None

        ida    = _extraer_trenes(data, "outbound", hora_minima_ida)
        vuelta = _extraer_trenes(data, "inbound",  hora_minima_vuelta)

        if not ida or not vuelta:
            return None

        mejor_ida    = min(ida,    key=lambda t: t["price"])
        mejor_vuelta = min(vuelta, key=lambda t: t["price"])

        return {
            "operador":      "Iryo",
            "precio_total":  mejor_ida["price"] + mejor_vuelta["price"],
            "precio_ida":    mejor_ida["price"],
            "precio_vuelta": mejor_vuelta["price"],
            "hora_ida":      mejor_ida["hhmm"],
            "hora_vuelta":   mejor_vuelta["hhmm"],
        }
    except Exception as e:
        print(f"  [Iryo] Error {origen}→{destino}: {e}")
        return None
