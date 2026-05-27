"""
Buscador Renfe usando la API vhi_priceCalendar.
Una llamada cubre todo el rango de fechas (sin Playwright).
Devuelve el precio mínimo del día — verificar hora exacta en renfe.com.
"""

import requests
from datetime import date, timedelta
import calendar as cal
import time as time_module

API_URL = "https://wsrestcorp.renfe.es/api/wsrviajeros/vhi_priceCalendar"

HEADERS = {
    "sec-ch-ua-platform": '"Windows"',
    "referer": "https://www.renfe.com/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "sec-ch-ua": '"Chromium";v="120", "Google Chrome";v="120", "Not/A)Brand";v="99"',
    "content-type": "application/json",
    "sec-ch-ua-mobile": "?0",
    "accept": "application/json, text/plain, */*",
    "accept-language": "es-ES,es;q=0.9",
    "origin": "https://www.renfe.com",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
}

# Códigos de estación Renfe (desde estacionesEstaticas.js)
ESTACIONES = {
    "Madrid":      "MADRI",
    "Sevilla":     "51003",
    "Málaga":      "54413",
    "Alicante":    "60911",
    "Córdoba":     "50500",
    "Barcelona":   "BARCE",
    "Tarragona":   "TARRA",
    "Valencia":    "VALEN",
    "Zaragoza":    "ZARAG",
    "Murcia":      "61200",
    "Toledo":      "92102",
    "Granada":     "05000",
    "Cádiz":       "51405",
    "Almería":     "56312",
    "Cartagena":   "61307",
}


def ruta_disponible(destino):
    return destino in ESTACIONES


def _meses_en_rango(init_date_str, end_date_str):
    """Genera pares (primer_dia_mes, ultimo_dia_mes) para cubrir el rango."""
    inicio = date.fromisoformat(init_date_str)
    fin    = date.fromisoformat(end_date_str)
    meses  = []
    año, mes = inicio.year, inicio.month
    while date(año, mes, 1) <= fin:
        ultimo = cal.monthrange(año, mes)[1]
        d_ini  = max(date(año, mes, 1),  inicio)
        d_fin  = min(date(año, mes, ultimo), fin)
        meses.append((str(d_ini), str(d_fin)))
        mes += 1
        if mes > 12:
            mes, año = 1, año + 1
    return meses


def _fetch_precios_rango(origen, destino, init_date, end_date):
    """
    Llama a la API mes a mes y devuelve dict {fecha: precio_minimo}.
    La API soporta máximo ~1 mes por llamada.
    """
    orig_code = ESTACIONES.get(origen)
    dest_code = ESTACIONES.get(destino)
    if not orig_code or not dest_code:
        return {}

    precios = {}
    for mes_ini, mes_fin in _meses_en_rango(init_date, end_date):
        body = {
            "originId": orig_code,
            "destinyId": dest_code,
            "initDate": mes_ini,
            "endDate":  mes_fin,
            "salesChannel": {"codApp": "VLP"},
        }
        for intento in range(3):
            try:
                resp = requests.post(API_URL, json=body, headers=HEADERS, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    for j in data.get("journeysPriceCalendar", []):
                        if j.get("minPriceAvailable"):
                            precios[j["date"]] = j["minPrice"]
                    break
                elif resp.status_code == 404:
                    break  # ruta no disponible en AVE, no reintentar
                else:
                    print(f"  [Renfe] API {resp.status_code} ({mes_ini}) intento {intento+1}")
                    time_module.sleep(2)
            except Exception as e:
                print(f"  [Renfe] Error {origen}→{destino} intento {intento+1}: {e}")
                time_module.sleep(2)
        time_module.sleep(0.5)

    return precios


def buscar_todos(origen, destino, fechas):
    """
    Busca en Renfe para todas las (fecha_ida, fecha_vuelta) del listado.
    Hace UNA llamada de API por dirección que cubre todas las fechas.

    fechas: lista de (str_viernes, str_domingo)
    Returns: lista de dicts con resultado, una por par de fechas.
    """
    if not ruta_disponible(destino):
        return []

    if not fechas:
        return []

    # Rango completo: desde la primera fecha_ida hasta la última fecha_vuelta
    init_date = fechas[0][0]
    end_date   = fechas[-1][1]

    print(f"  [Renfe] Buscando {origen}→{destino} ({init_date} a {end_date})...")
    precios_ida    = _fetch_precios_rango(origen, destino, init_date, end_date)
    time_module.sleep(0.8)
    print(f"  [Renfe] Buscando {destino}→{origen} (vuelta)...")
    precios_vuelta = _fetch_precios_rango(destino, origen, init_date, end_date)

    resultados = []
    for fecha_ida, fecha_vuelta in fechas:
        precio_ida    = precios_ida.get(fecha_ida)
        precio_vuelta = precios_vuelta.get(fecha_vuelta)

        if precio_ida is None or precio_vuelta is None:
            continue

        resultados.append({
            "operador":     "Renfe",
            "fecha_ida":    fecha_ida,
            "fecha_vuelta": fecha_vuelta,
            "precio_total": float(precio_ida + precio_vuelta),
            "hora_ida":     "",   # precio mínimo del día; ver renfe.com para hora exacta
            "hora_vuelta":  "",
        })

    return resultados
