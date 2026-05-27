# Pendiente — handoff para próxima sesión de Claude

## Estado actual

Rama de trabajo: **`claude/telegram-bot-timing-SN06g`** (pusheada al remoto).

### Lo que YA está hecho y pusheado en esta rama

Commit `bd04c41` — "Separa alertas Ouigo/Renfe y ajusta horarios a 14:30/16:00":

- `config.yaml`: `hora_minima_ida` 15:00 → **14:30**, `hora_minima_vuelta` 17:00 → **16:00**.
- `main.py`: Ouigo y Renfe ahora alertan **por separado** (antes solo se mandaba el más barato y Renfe sin filtro de hora le ganaba siempre a Ouigo).
  - **Ouigo**: alerta por umbral o mínimo histórico (igual que antes).
  - **Renfe**: alerta **solo por mínimo histórico** porque la API actual (`vhi_priceCalendar`) devuelve el mínimo del día sin hora. El mensaje sigue marcando "ver renfe.com para horario exacto".

### Validación local

Se corrió `python main.py` en este entorno: el código compila y la lógica corre sin excepciones. No se pudo verificar precios reales porque el entorno bloquea hosts externos (`Host not in allowlist` para `wsrestcorp.renfe.es` y la API de Ouigo). **En GitHub Actions sí tiene acceso** — confirmar haciendo "Run workflow" sobre esta rama en la pestaña Actions.

---

## Pendiente — agregar Iryo como tercer operador

El usuario quiere que el bot mande **Renfe, Ouigo e Iryo por separado**, cada uno con su propia alerta de Telegram. La estructura del módulo de Iryo debe ser **igual a `buscador_ouigo.py`**.

### Por qué quedó pendiente

1. No existe librería pública de Python para Iryo (sí existe `ouigo`).
2. La API de Iryo no está documentada.
3. iryo.eu tiene protección Cloudflare → un `requests.get` simple devuelve 403.
4. Este entorno de Claude bloquea hosts externos, no permite reverse-engineering en vivo.

### Lo que el usuario va a traer en la próxima sesión

Una de estas dos cosas, capturada desde su PC en Chrome/Firefox abriendo iryo.eu y buscando un viaje real:

- **Mejor**: el comando **cURL** del request que devuelve la lista de trenes (DevTools → Network → Fetch/XHR → click derecho → Copy as cURL bash).
- **Alternativa**: archivo **HAR** con todo el tráfico de la búsqueda.

Con eso se saca: URL del endpoint, headers/token/cookies necesarios, formato del payload, formato de respuesta JSON.

### Plan de implementación cuando llegue el cURL

1. Crear `buscador_iryo.py` con la misma estructura que `buscador_ouigo.py`:
   - `DESTINOS_IRYO = {...}` con las rutas que cubre Iryo (Madrid - Barcelona, Valencia, Sevilla, Málaga, Albacete, Córdoba, Zaragoza, etc.).
   - `ruta_disponible(destino)`.
   - `buscar(origen, destino, fecha_ida, fecha_vuelta, hora_minima_ida, hora_minima_vuelta)` que devuelve dict con `operador="Iryo"`, `precio_total`, `hora_ida`, `hora_vuelta` (igual contrato que Ouigo).
2. En `main.py`:
   - Importar `from buscador_iryo import buscar as buscar_iryo, ruta_disponible as iryo_disponible`.
   - Agregar bloque `if iryo_disponible(destino): ...` igual al de Ouigo dentro de `procesar_ruta`.
3. La lógica de alertas en `main.py` ya está preparada: como Iryo va a filtrar por hora real (igual que Ouigo), tratarlo como "Ouigo" en el `if operador == "Ouigo"` — o sea, alertar por umbral O mínimo histórico. Para eso, cambiar la condición a:
   ```python
   if operador in ("Ouigo", "Iryo"):
       debe_alertar = (mejor["precio_total"] < umbral) or es_min
   else:  # Renfe (sin garantía de hora)
       debe_alertar = es_min
   ```
4. Si Iryo cubre rutas nuevas no listadas en `config.yaml`, podemos agregarlas (Iryo cubre Cuenca, p.ej.).
5. Commitear en esta misma rama y pushear.

### Información de referencia útil

- Iryo cubre actualmente (consultar al implementar): Madrid - Barcelona, Madrid - Valencia, Madrid - Sevilla, Madrid - Málaga, Madrid - Albacete/Alicante, Madrid - Córdoba, Madrid - Zaragoza, Madrid - Cuenca.
- En `buscador_ouigo.py:25` está el contrato a respetar — devolver siempre `precio_total`, `hora_ida`, `hora_vuelta` para que `enviar_alerta_tren` los pinte bien en Telegram.

---

## Otras cosas que el usuario mencionó pero no se hicieron

- Reverse-engineer la **API DWR de Renfe** (`venta.renfe.com/vol/dwr/.../trainEnlacesManager.getTrainsList.dwr`) para que Renfe también filtre por hora real en lugar de devolver el precio mínimo del día. Pendiente porque requiere manejo de sesión + token DWR + ~3 llamadas previas; no se puede testear desde este entorno sin secrets y con red restringida. Quedó decisión del usuario: dejarlo así por ahora.
- Otros repos del usuario (`vuelos-europa`, `vuelos-cerdeña`, `vuelos-buenos-aires`) tampoco le llegan mensajes a Telegram. **No se pueden revisar desde esta sesión** porque el MCP de GitHub está restringido a `lpaissanidis-source/trenes-espana`. El usuario tiene que abrir una sesión de Claude desde cada uno de esos repos. La causa más probable: GitHub desactiva workflows cron tras 60 días de inactividad — basta con ir a Actions → Enable workflow.
