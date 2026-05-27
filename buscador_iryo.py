"""
Buscador Iryo usando la API api.iryo.eu/b2c/availability/search.

Notas operativas:
- El cfgToken está firmado con HMAC-SHA256 por Iryo (no podemos generarlo).
  Caduca cada ~24h. Si Iryo deja de devolver resultados, hay que capturarlo
  de nuevo desde iryo.eu (DevTools > Network > request 'search' > Payload >
  copiar el valor de cfgToken) y actualizar la constante CFG_TOKEN o setear
  la variable de entorno IRYO_CFG_TOKEN como secret en GitHub Actions.
"""

import os
import uuid
import requests
from datetime import datetime, time
import time as time_module

API_URL = "https://api.iryo.eu/b2c/availability/search"

SUBSCRIPTION_KEY = "7c9b9b1ea0fe4f0c9d1739fcbf8b5438"

# Token capturado de iryo.eu el 2026-05-27 (válido ~24h). Si caduca, capturar
# uno nuevo. Se puede sobreescribir vía env var IRYO_CFG_TOKEN sin tocar código.
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


def ruta_disponible(destino):
    return destino in DESTINOS_IRYO


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
            "Chrome/148.0.0.0 Safari/537.36"
        ),
        "x-client-version": "1.104.2",
        "x-pwa-sessid": str(uuid.uuid4()),
        "x-request-id": str(uuid.uuid4()),
    }


def _llamar_api(orig_code, dest_code, fecha_ida, fecha_vuelta):
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
            resp = requests.post(API_URL, json=payload, headers=_headers(), timeout=20)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (401, 403):
                print(f"  [Iryo] {resp.status_code} — cfgToken probablemente expirado "
                      f"o Cloudflare bloqueó. Capturar nuevo cfgToken desde iryo.eu.")
                return None
            print(f"  [Iryo] API {resp.status_code} intento {intento+1}: {resp.text[:200]}")
            time_module.sleep(2)
        except Exception as e:
            print(f"  [Iryo] Error red intento {intento+1}: {e}")
            time_module.sleep(2)
    return None


def _to_time(s):
    """Parsea ISO 8601 → datetime con tz si existe."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _extraer_min_precio(svc):
    """Encuentra el menor precio entre todas las tarifas del servicio."""
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
    """Devuelve lista de {dt, hhmm, price} para la dirección dada, filtrada por hora."""
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
            dt = _to_time(dep) if isinstance(dep, str) else None
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
