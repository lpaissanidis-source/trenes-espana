# ============================================================
# MAIN.PY - Trenes España
# Busca los trenes más baratos de Ouigo para fines de semana.
# Salida viernes >= 15:00, vuelta domingo >= 17:00.
# Alerta por Telegram si el precio baja del umbral o es nuevo mínimo.
# ============================================================

import yaml
import datetime
import time

from database     import crear_tabla, guardar_precio, obtener_minimo_historico
from buscador_ouigo import buscar as buscar_ouigo, ruta_disponible
from telegram_bot import enviar_alerta_tren

NOMBRE_BUSCADOR = "Trenes España"


def leer_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config


def generar_fechas(semanas_adelante):
    """
    Genera pares (viernes, domingo) desde el próximo viernes
    hasta semanas_adelante semanas adelante.
    """
    hoy   = datetime.date.today()
    dias_hasta_viernes = (4 - hoy.weekday()) % 7
    if dias_hasta_viernes == 0:
        dias_hasta_viernes = 7

    primer_viernes = hoy + datetime.timedelta(days=dias_hasta_viernes)

    pares = []
    for i in range(semanas_adelante):
        viernes = primer_viernes + datetime.timedelta(weeks=i)
        domingo = viernes + datetime.timedelta(days=2)
        pares.append((str(viernes), str(domingo)))

    return pares


def procesar_ruta(config_ruta, fechas, config_global):
    nombre   = config_ruta["nombre"]
    origen   = config_ruta["origen"]
    destino  = config_ruta["destino"]
    umbral   = config_ruta["umbral_precio"]

    hora_minima_ida    = config_global.get("hora_minima_ida",    "15:00")
    hora_minima_vuelta = config_global.get("hora_minima_vuelta", "17:00")

    codigo_ruta = f"{origen}-{destino}"

    print(f"\n{'='*55}")
    print(f"  Ruta: {nombre}")
    print(f"  Umbral: {umbral} EUR/persona")
    print(f"{'='*55}")

    if not ruta_disponible(destino):
        print(f"  (Ouigo no cubre esta ruta — pendiente Renfe)")
        return

    resultados = []

    for fecha_ida, fecha_vuelta in fechas:
        resultado = buscar_ouigo(
            origen=origen,
            destino=destino,
            fecha_ida=fecha_ida,
            fecha_vuelta=fecha_vuelta,
            hora_minima_ida=hora_minima_ida,
            hora_minima_vuelta=hora_minima_vuelta,
        )

        time.sleep(1.5)

        if resultado is None:
            continue

        precio = resultado["precio_total"]
        bajo   = "✓ BAJO UMBRAL" if precio < umbral else ""
        print(f"  {fecha_ida} → {fecha_vuelta} | {precio:.0f} EUR | "
              f"{resultado['operador']} {bajo}")

        resultados.append({
            "fecha_ida":    fecha_ida,
            "fecha_vuelta": fecha_vuelta,
            **resultado,
        })

    if not resultados:
        print(f"  Sin resultados disponibles.")
        return

    print(f"\n  Total combinaciones encontradas: {len(resultados)}")

    # Guardar todos y detectar el mejor
    mejor         = None
    mejor_precio  = float("inf")
    mejor_es_min  = False

    for r in resultados:
        guardar_precio(
            operador     = r["operador"],
            ruta         = codigo_ruta,
            fecha_ida    = r["fecha_ida"],
            fecha_vuelta = r["fecha_vuelta"],
            precio_total = r["precio_total"],
            hora_ida     = r.get("hora_ida", ""),
            hora_vuelta  = r.get("hora_vuelta", ""),
        )

        if r["precio_total"] < mejor_precio:
            mejor_precio = r["precio_total"]
            mejor        = r

            minimo_hist = obtener_minimo_historico(
                operador     = r["operador"],
                ruta         = codigo_ruta,
                fecha_ida    = r["fecha_ida"],
                fecha_vuelta = r["fecha_vuelta"],
            )

            if minimo_hist is None or r["precio_total"] < minimo_hist:
                mejor_es_min = True
            else:
                mejor_es_min = False

    if mejor is None:
        return

    debe_alertar = (mejor_precio < umbral) or mejor_es_min

    if debe_alertar:
        print(f"\n  *** ALERTA: {mejor_precio:.0f} EUR/persona — {mejor['operador']}")
        if mejor_es_min:
            print(f"  *** Nuevo mínimo histórico")
        print(f"  Enviando Telegram...")

        exito = enviar_alerta_tren(
            ruta               = nombre,
            fecha_ida          = mejor["fecha_ida"],
            fecha_vuelta       = mejor["fecha_vuelta"],
            precio_total       = mejor_precio,
            operador           = mejor["operador"],
            hora_ida           = mejor.get("hora_ida", ""),
            hora_vuelta        = mejor.get("hora_vuelta", ""),
            buscador           = NOMBRE_BUSCADOR,
            es_minimo_historico = mejor_es_min,
        )

        if exito:
            print(f"  ✓ Telegram enviado")
        else:
            print(f"  ✗ Error al enviar Telegram")
    else:
        print(f"\n  Mejor precio: {mejor_precio:.0f} EUR — sobre el umbral ({umbral} EUR)")


if __name__ == "__main__":

    hora_inicio = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\nTrenes España iniciado: {hora_inicio}")

    crear_tabla()

    try:
        config = leer_config()
    except FileNotFoundError:
        print("ERROR: No se encontró config.yaml")
        exit(1)

    rutas             = config.get("rutas", [])
    semanas_adelante  = config.get("semanas_adelante", 12)

    if not rutas:
        print("ERROR: No hay rutas en config.yaml")
        exit(1)

    fechas = generar_fechas(semanas_adelante)
    print(f"Rutas: {len(rutas)} | Fines de semana: {len(fechas)} "
          f"(del {fechas[0][0]} al {fechas[-1][0]})")

    for ruta in rutas:
        try:
            procesar_ruta(ruta, fechas, config)
        except Exception as e:
            print(f"\n  ERROR en {ruta.get('nombre', '?')}: {e}")
            print(f"  Continuando con la siguiente ruta...")

    hora_fin = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*55}")
    print(f"Búsqueda completada: {hora_fin}")
    print(f"{'='*55}\n")
