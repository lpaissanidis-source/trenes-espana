from ouigo import Ouigo
from datetime import time
import time as time_module

_ouigo = None

DESTINOS_OUIGO = {
    "Sevilla", "Málaga", "Alicante", "Córdoba",
    "Barcelona", "Tarragona", "Valencia", "Zaragoza", "Murcia",
}


def _get_ouigo():
    global _ouigo
    if _ouigo is None:
        _ouigo = Ouigo("ES")
    return _ouigo


def ruta_disponible(destino):
    return destino in DESTINOS_OUIGO


def buscar(origen, destino, fecha_ida, fecha_vuelta,
           hora_minima_ida="15:00", hora_minima_vuelta="17:00"):
    """
    Busca el tren más barato en Ouigo para ida y vuelta.
    fecha_ida / fecha_vuelta: string "YYYY-MM-DD"
    Retorna dict con info del mejor precio, o None si no encuentra.
    """
    if destino not in DESTINOS_OUIGO:
        return None

    o = _get_ouigo()

    h_ida    = time(*map(int, hora_minima_ida.split(":")))
    h_vuelta = time(*map(int, hora_minima_vuelta.split(":")))

    try:
        viajes_ida = o.find_travels(
            origin=origen,
            destination=destino,
            outbound=fecha_ida,
            minimum_departure_time=h_ida,
        )

        time_module.sleep(1.5)

        viajes_vuelta = o.find_travels(
            origin=destino,
            destination=origen,
            outbound=fecha_vuelta,
            minimum_departure_time=h_vuelta,
        )

        if not viajes_ida or not viajes_vuelta:
            return None

        mejor_ida    = min(viajes_ida,    key=lambda x: x.price)
        mejor_vuelta = min(viajes_vuelta, key=lambda x: x.price)

        return {
            "operador":    "Ouigo",
            "precio_total": mejor_ida.price + mejor_vuelta.price,
            "precio_ida":   mejor_ida.price,
            "precio_vuelta": mejor_vuelta.price,
            "hora_ida":     str(mejor_ida.departure_timestamp),
            "hora_vuelta":  str(mejor_vuelta.departure_timestamp),
        }

    except Exception as e:
        print(f"  [Ouigo] Error {origen}→{destino}: {e}")
        return None
