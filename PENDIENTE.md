# Estado del bot — Trenes España

## Operadores activos

| Operador | Estado | Lógica de alerta |
|---|---|---|
| **Ouigo** | ✅ Activo | Filtra por hora ≥ 14:30 ida, ≥ 16:00 vuelta. Alerta si precio < umbral O mínimo histórico. |
| **Renfe** | ✅ Activo | Precio mínimo del día sin hora. Alerta si precio < umbral O mínimo histórico. El mensaje aclara "ver renfe.com para horario". |
| **Iryo** | 🛑 Desactivado | Cloudflare bloquea las IPs de GitHub Actions. Para reactivar (desde VPS o con proxy): setear secret `IRYO_ENABLED=true`. |

## Horarios de corrida (cron en GitHub Actions)

`30 23,2,5,8,11,14,17,20 * * *` (UTC) → en Madrid hora local (CEST):

| UTC | Madrid (CEST) |
|---|---|
| 23:30 | **01:30** |
| 02:30 | **04:30** |
| 05:30 | **07:30** |
| 08:30 | **10:30** |
| 11:30 | **13:30** |
| 14:30 | **16:30** |
| 17:30 | **19:30** |
| 20:30 | **22:30** |

Cada ~3 horas. Si te molestan los avisos nocturnos (01:30 y 04:30), editá el cron.

## Configuración

- `config.yaml`: rutas + umbrales + horas mínimas + ausencias.
- Secrets necesarios en GitHub:
  - `TELEGRAM_BOT_TOKEN`
  - `TELEGRAM_CHAT_ID`
- Secrets opcionales:
  - `IRYO_ENABLED=true` (solo si se mueve a VPS con IP limpia)
  - `IRYO_COOKIES` (cf_clearance + __cf_bm, solo si IRYO_ENABLED=true)
  - `IRYO_CFG_TOKEN` (override del token de Iryo, expira cada ~24h)

## Histórico

- `precios.db` se commitea automáticamente tras cada corrida. Sirve para detectar nuevos mínimos históricos.

## Si Iryo se quiere reactivar en el futuro

1. Mover el bot a un VPS chico (~$5/mes Hetzner/DigitalOcean) o pagar proxy (ScrapingBee/Scrapfly).
2. Setear `IRYO_ENABLED=true` como secret.
3. Reinstalar Chromium en el workflow (agregar step `python -m playwright install --with-deps chromium` antes del patcheo de ouigo).
4. Capturar cookies frescas de iryo.eu cuando se necesite renovar (cada ~24h).
5. El código de `buscador_iryo.py` ya está armado y solo se activa con `IRYO_ENABLED=true`.

## Otros repos del usuario (fuera del scope de esta sesión)

- `vuelos-europa`, `vuelos-cerdeña`, `vuelos-buenos-aires`: revisar uno por uno en sesiones separadas. Causa más probable de mensajes que no llegan: workflows cron desactivados por GitHub tras 60 días de inactividad (Actions → Enable workflow), o tokens de Telegram inválidos.
