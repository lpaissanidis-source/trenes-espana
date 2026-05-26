import requests


def leer_credenciales():
    credenciales = {}
    with open("credenciales.txt", "r") as archivo:
        for linea in archivo:
            linea = linea.strip()
            if not linea or linea.startswith("#"):
                continue
            if "=" in linea:
                clave, valor = linea.split("=", 1)
                credenciales[clave.strip()] = valor.strip()
    return credenciales


_credenciales = leer_credenciales()

TOKEN   = _credenciales.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = _credenciales.get("TELEGRAM_CHAT_ID", "")

URL_API = f"https://api.telegram.org/bot{TOKEN}"


def enviar_mensaje(texto):
    url   = f"{URL_API}/sendMessage"
    datos = {
        "chat_id":    CHAT_ID,
        "text":       texto,
        "parse_mode": "HTML",
    }
    try:
        respuesta = requests.post(url, data=datos, timeout=10)
        resultado = respuesta.json()
        if resultado.get("ok"):
            return True
        print(f"  Error de Telegram: {resultado.get('description', 'Error desconocido')}")
        return False
    except requests.exceptions.Timeout:
        print("  Error: Timeout al conectar con Telegram")
        return False
    except requests.exceptions.ConnectionError:
        print("  Error: Sin conexión a internet")
        return False
    except Exception as e:
        print(f"  Error inesperado: {e}")
        return False


def enviar_alerta_tren(ruta, fecha_ida, fecha_vuelta, precio_total,
                       operador, hora_ida="", hora_vuelta="",
                       buscador="Trenes España", es_minimo_historico=False):

    encabezado = "NUEVO MÍNIMO HISTÓRICO" if es_minimo_historico else "PRECIO BAJO UMBRAL"

    linea_hora_ida    = f"<b>🕐 Horario ida:</b> {hora_ida}\n"    if hora_ida    else ""
    linea_hora_vuelta = f"<b>🕐 Horario vuelta:</b> {hora_vuelta}\n" if hora_vuelta else ""

    mensaje = (
        f"<b>📁 {buscador}</b>\n"
        f"<b>🚂 {encabezado}</b>\n"
        f"\n"
        f"<b>Ruta:</b> {ruta}\n"
        f"<b>Ida:</b> {fecha_ida}\n"
        f"<b>Vuelta:</b> {fecha_vuelta}\n"
        f"\n"
        f"<b>💰 Precio por persona:</b> {precio_total:.2f} EUR\n"
        f"<b>Precio x2 personas:</b> {precio_total * 2:.2f} EUR\n"
        f"\n"
        f"<b>Operador:</b> {operador}\n"
        f"{linea_hora_ida}"
        f"{linea_hora_vuelta}"
    )

    return enviar_mensaje(mensaje)


if __name__ == "__main__":
    print("Leyendo credenciales...")
    print(f"  TOKEN: {'OK' if TOKEN else 'NO encontrado'}")
    print(f"  CHAT_ID: {'OK' if CHAT_ID else 'NO encontrado'}")
    print("\nEnviando mensaje de prueba...")
    exito = enviar_mensaje(
        "<b>✅ Test Trenes España</b>\n\nEl buscador de trenes está configurado."
    )
    if exito:
        print("✓ Enviado correctamente.")
    else:
        print("✗ Error. Revisa credenciales.txt")
