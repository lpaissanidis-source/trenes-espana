# Pendiente — estado del bot

## Lo que YA está hecho y pusheado en `claude/telegram-bot-timing-SN06g`

1. **Horarios actualizados** (`config.yaml`): ida ≥ 14:30, vuelta ≥ 16:00.
2. **Ouigo y Renfe alertan por separado** (`main.py`). Antes solo se mandaba el más barato, y Renfe sin filtro de hora le ganaba siempre a Ouigo.
3. **Iryo agregado como tercer operador** (`buscador_iryo.py`).
   - Endpoint: `POST https://api.iryo.eu/b2c/availability/search`.
   - Códigos UIC: Madrid (X0000), Barcelona (71801), Sevilla (51003), Málaga (54413), Córdoba (50500), Alicante (60911), Zaragoza Delicias (04040), Valencia Joaquín Sorolla (60600).
   - Filtra por hora real, igual que Ouigo. Alerta por umbral o mínimo histórico.
   - `cfgToken` hardcodeado, capturado 2026-05-27, **expira 2026-05-28 14:13 UTC**.
   - Variable de entorno `IRYO_CFG_TOKEN` puede sobreescribirlo desde GitHub Secret sin tocar código.

## Pendientes

### 1) Renovación automática del `cfgToken` de Iryo (Importante)
El token está firmado con HMAC-SHA256 por Iryo, expira cada ~24h. Cuando expire, Iryo va a empezar a devolver 401/403 y el bot va a loguear:
```
[Iryo] 401 — cfgToken probablemente expirado o Cloudflare bloqueó.
```

**Mitigación temporal**: capturar un cfgToken nuevo desde DevTools (Network → request `search` → Payload → copiar valor de `cfgToken`) y o bien:
- Pegarlo en `buscador_iryo.py:CFG_TOKEN_DEFAULT` y commitear, o
- Crear/actualizar el GitHub Secret `IRYO_CFG_TOKEN` con el valor nuevo (no requiere commit).

**Solución definitiva**: averiguar qué endpoint de api.iryo.eu emite el cfgToken al cargar iryo.eu (probablemente un GET a `/b2c/config/...` o similar). Capturar ese request en DevTools (filtro de Network por `iryo.eu` viendo TODOS los requests, no solo "search") y reproducirlo desde Python al inicio de cada corrida.

### 2) Verificar parser de respuesta Iryo
La estructura JSON de la respuesta de `/b2c/availability/search` se infirió por patrones típicos (`travels[].services[].fares[].price`). Si la primera corrida en GitHub Actions devuelve `Sin resultados disponibles` para Iryo pese a haber trenes, hay que revisar el JSON real y ajustar `_extraer_trenes` / `_extraer_min_precio` en `buscador_iryo.py`. Sería útil tener una captura de la pestaña **Preview** del request `search` para confirmar el schema.

### 3) Cloudflare en GitHub Actions
La web iryo.eu está detrás de Cloudflare. La API `api.iryo.eu` puede heredar esa protección. Si los requests desde GitHub Actions reciben 403 sistemático, opciones:
- Usar `cloudscraper` o `curl_cffi` (TLS fingerprinting de browser real).
- Como último recurso, usar Playwright con un Chromium headless.

### 4) Renfe con horarios reales
La API actual de Renfe (`vhi_priceCalendar`) solo da precio mínimo del día sin hora. Para tener horarios reales habría que migrar a la API DWR de `venta.renfe.com/vol/dwr/.../trainEnlacesManager.getTrainsList.dwr` — requiere manejo de sesión + token DWR + ~3 llamadas previas. Pendiente, no urgente.

### 5) Otros repos del usuario sin Telegram
`vuelos-europa`, `vuelos-cerdeña`, `vuelos-buenos-aires`: el MCP de GitHub está restringido a `trenes-espana`, así que hay que abrir sesiones separadas. La causa más probable: GitHub desactiva los workflows cron tras 60 días sin actividad — basta con ir a Actions → Enable workflow en cada repo.
