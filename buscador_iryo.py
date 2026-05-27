"""
Buscador Iryo usando la API api.iryo.eu/b2c/availability/search.

Notas operativas:
- Usa curl_cffi con impersonate=chrome120 para imitar el fingerprint TLS de
  un navegador real y esquivar el WAF de Cloudflare que protege api.iryo.eu.
- El cfgToken está firmado con HMAC-SHA256 por Iryo (no podemos generarlo).
  Caduca cada ~24h. Si Iryo deja de devolver resultados:
    1) Abrí iryo.eu en Chrome, DevTools > Network, hacé una búsqueda.
    2) En el request 'search' copiá el valor de cfgToken del Payload.
    3) Pegalo en CFG_TOKEN_DEFAULT abajo o en el GitHub Secret IRYO_CFG_TOKEN.
- Si Cloudflare sigue bloqueando con 403 pese a curl_cffi, capturar la cookie
  cf_clearance del browser y setearla como secret IRYO_COOKIES con formato
  "cf_clearance=xxx; __cf_bm=yyy".
- Tras el primer 403/401 se asume sesión inválida y se skipean las llamadas
  restantes (evita ruido en los logs y latencia inútil).
"""

import os
import uuid
from datetime import datetime, time
import time as time_module

try:
    from curl_cffi import requests as http
    _IMPERSONATE = "chrome120"
except ImportError:
    import requests as http
    _IMPERSONATE = None

API_URL = "https://api.iryo.eu/b2c/availability/search"
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
CFG_TOKEN   = os.environ.get("IRYO_CFG_TOKEN")  or CFG_TOKEN_DEFAULT
COOKIES_RAW = os.environ.get("IRYO_COOKIES", "")

# Códigos UIC que usa Iryo. Madrid X0000 es virtual ("todas las estaciones",
# agrupa Atocha 60000 + Chamartín 17000).
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

# Flag de sesión: tras un 401/403 dejamos de llamar a Iryo el resto de la corrida.
_session_dead = False


def sesion_activa():
    return not _session_dead


def ruta_disponible(destino):
    return destino in DESTINOS_IRYO


def _parse_cookies(raw):
    if not raw:
        return None
    out = {}
    for piece in raw.split(";"):
        piece = piece.strip()
        if "=" in piece:
            k, v = piece.split("=", 1)
            out[k.strip()] = v.strip()
    return out or None


def _headers():
    return {
        "accept": "application/json, text/plain, */*",
        "accept-language": "es-ES",
        "content-type": "application/json;charset=UTF-8",
        "no-authorization": "",
        "ocp-apim-subscription-key": SUBSCRIPTION_KEY,
        "origin": "https://iryo.eu",
        "referer": "https://iryo.eu/",
        "request-channel": "WEB",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "x-client-version": "1.104.2",
        "x-pwa-sessid": str(uuid.uuid4()),
        "x-request-id": str(uuid.uuid4()),
    }


def _post(payload):
    kwargs = {
        "json":    payload,
        "headers": _headers(),
        "timeout": 20,
        "cookies": _parse_cookies(COOKIES_RAW),
    }
    if _IMPERSONATE:
        kwargs["impersonate"] = _IMPERSONATE
    return http.post(API_URL, **kwargs)


def _llamar_api(orig_code, dest_code, fecha_ida, fecha_vuelta):
    global _session_dead
    if _session_dead:
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
    for intento in range(3):
        try:
            resp = _post(payload)
            sc = resp.status_code
            if sc == 200:
                return resp.json()
            if sc in (401, 403):
                _session_dead = True
                print(f"  [Iryo] Bloqueado ({sc}) — Cloudflare WAF o cfgToken "
                      f"expirado. Skipeando Iryo el resto de la corrida. Si "
                      f"persiste: capturar cookie cf_clearance del browser y "
                      f"setear secret IRYO_COOKIES.")
                return None
            print(f"  [Iryo] API {sc} intento {intento+1}: {resp.text[:200]}")
            time_module.sleep(2)
        except Exception as e:
            print(f"  [Iryo] Error red intento {intento+1}: {e}")
            time_module.sleep(2)
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
    if _session_dead:
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
