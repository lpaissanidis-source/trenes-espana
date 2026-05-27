# ============================================================
# MAIN.PY - Trenes España
# Busca en Ouigo Y Renfe, compara, y manda el más barato.
# Salida viernes >= 15:00, vuelta domingo >= 17:00.
# ============================================================

import yaml
import datetime
import time

from database       import crear_tabla, guardar_precio, obtener_minimo_historico
from buscador_ouigo import buscar as buscar_ouigo, ruta_disponible as ouigo_disponible
from buscador_renfe import buscar_todos as buscar_renfe, ruta_disponible as renfe_disponible
from telegram_bot   import enviar_alerta_tren

NOMBRE_BUSCADOR = "Trenes España"


def leer_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def filtrar_ausencias(fechas, ausencias):
    """
    Elimina los pares (fecha_ida, fecha_vuelta) cuya fecha_ida
    cae dentro de alguno de los períodos de ausencia definidos en config.yaml.
    """
    if not ausencias:
        return fechas

    periodos = [
        (datetime.date.fromisoformat(a["inicio"]), datetime.date.fromisoformat(a["fin"]))
        for a in ausencias
    ]

    return [
        (fi, fv) for fi, fv in fechas
        if not any(ini <= datetime.date.fromisoformat(fi) <= fin for ini, fin in periodos)
    ]


def generar_fechas(semanas_adelante):
    """Pares (viernes, domingo) desde el próximo viernes hasta N semanas."""
    hoy = datetime.date.today()
    dias_hasta_viernes = (4 - hoy.weekday()) % 7
    if dias_hasta_viernes == 0:
        dias_hasta_viernes = 7

    primer_viernes = hoy + datetime.timedelta(days=dias_hasta_viernes)
    return [
        (
            str(primer_viernes + datetime.timedelta(weeks=i)),
            str(primer_viernes + datetime.timedelta(weeks=i, days=2)),
        )
        for i in range(semanas_adelante)
    ]


def procesar_ruta(config_ruta, fechas, config_global):
    nombre   = config_ruta["nombre"]
    origen   = config_ruta["origen"]
    destino  = config_ruta["destino"]
    umbral   = config_ruta["umbral_precio"]

    hora_min_ida    = config_global.get("hora_minima_ida",    "15:00")
    hora_min_vuelta = config_global.get("hora_minima_vuelta", "17:00")

    codigo_ruta = f"{origen}-{destino}"

    print(f"\n{'='*55}")
    print(f"  Ruta: {nombre}")
    print(f"  Umbral: {umbral} EUR/persona")
    print(f"{'='*55}")

    todos_resultados = []

    # ── Ouigo ───────────────────────────────────────────────
    if ouigo_disponible(destino):
        print(f"  [Ouigo] Buscando {len(fechas)} fines de semana...")
        for fecha_ida, fecha_vuelta in fechas:
            r = buscar_ouigo(
                origen=origen,
                destino=destino,
                fecha_ida=fecha_ida,
                fecha_vuelta=fecha_vuelta,
                hora_minima_ida=hora_min_ida,
                hora_minima_vuelta=hora_min_vuelta,
            )
            if r:
                r["fecha_ida"]    = fecha_ida
                r["fecha_vuelta"] = fecha_vuelta
                todos_resultados.append(r)
    else:
        print(f"  [Ouigo] No cubre esta ruta.")

    # ── Renfe ───────────────────────────────────────────────
    if renfe_disponible(destino):
        renfe_resultados = buscar_renfe(origen, destino, fechas)
        todos_resultados.extend(renfe_resultados)
    else:
        print(f"  [Renfe] No cubre esta ruta.")

    if not todos_resultados:
        print(f"  Sin resultados disponibles.")
        return

    # ── Mostrar todos los resultados ─────────────────────────
    print(f"\n  Resultados ({len(todos_resultados)} combinaciones):")
    for r in todos_resultados:
        bajo = "✓ BAJO UMBRAL" if r["precio_total"] < umbral else ""
        print(f"    {r['fecha_ida']} → {r['fecha_vuelta']} | "
              f"{r['precio_total']:.0f} EUR | {r['operador']} {bajo}")

    # ── Guardar en DB y detectar el mejor ───────────────────
    mejor        = None
    mejor_precio = float("inf")
    mejor_es_min = False

    for r in todos_resultados:
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
        print(f"\n  *** ALERTA: {mejor_precio:.0f} EUR | {mejor['operador']}")
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
        print(f"\n  Mejor precio: {mejor_precio:.0f} EUR ({mejor['operador']}) "
              f"— sobre el umbral ({umbral} EUR)")


if __name__ == "__main__":

    hora_inicio = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\nTrenes España iniciado: {hora_inicio}")

    crear_tabla()

    try:
        config = leer_config()
    except FileNotFoundError:
        print("ERROR: No se encontró config.yaml")
        exit(1)

    rutas            = config.get("rutas", [])
    semanas_adelante = config.get("semanas_adelante", 12)
    ausencias        = config.get("ausencias", [])

    if not rutas:
        print("ERROR: No hay rutas en config.yaml")
        exit(1)

    fechas = generar_fechas(semanas_adelante)
    fechas = filtrar_ausencias(fechas, ausencias)

    if not fechas:
        print("ERROR: No quedan fechas disponibles (todas excluidas por ausencias)")
        exit(1)

    if ausencias:
        rangos = [a["inicio"] + " -> " + a["fin"] for a in ausencias]
        print(f"Períodos excluidos: {rangos}")

    print(f"Rutas: {len(rutas)} | Fines de semana disponibles: {len(fechas)} "
          f"(del {fechas[0][0]} al {fechas[-1][0]})")

    for ruta in rutas:
        try:
            procesar_ruta(ruta, fechas, config)
        except Exception as e:
            print(f"\n  ERROR en {ruta.get('nombre', '?')}: {e}")
            print(f"  Continuando...")
        time.sleep(5)  # pausa entre rutas para no saturar Ouigo

    hora_fin = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*55}")
    print(f"Búsqueda completada: {hora_fin}")
    print(f"{'='*55}\n")
