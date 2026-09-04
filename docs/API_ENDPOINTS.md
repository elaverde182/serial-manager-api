# API REST — Serial Manager

- **Base URL:** `/api/v1`
- **Formato:** JSON. **Auth:** `Authorization: Bearer <JWT>` (salvo `/auth/login` y `/health`).
- **Documentación interactiva:** `/docs` (Swagger UI), `/redoc` (ReDoc), `/openapi.json`.
- **Roles:** 🔓 público · 👤 operator · 🛡️ admin.

Convenciones: paginación `?page=&size=`; filtros por query params; errores con estructura `{ "detail": "...", "code": "..." }`; fechas ISO-8601 UTC.

---

## 1. Autenticación y sesión

| Método | Ruta | Rol | Descripción |
|--------|------|-----|-------------|
| POST | `/auth/login` | 🔓 | Login. Devuelve `access_token` + `refresh_token`. Funciona con cualquier `AUTH_PROVIDER`. |
| POST | `/auth/refresh` | 🔓 | Renueva el access token. |
| POST | `/auth/logout` | 👤 | Invalida el refresh token. |
| GET | `/auth/me` | 👤 | Perfil e identidad del usuario autenticado (rol, provider). |

**`POST /auth/login`**
```jsonc
// request
{ "username": "operador1", "password": "••••••" }
// response 200
{
  "access_token": "eyJhbGci...",
  "refresh_token": "eyJhbGci...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": { "id": 12, "username": "operador1", "role": "operator", "provider": "local" }
}
```
> En `AUTH_PROVIDER=oidc` el front puede usar el flujo OIDC directo; este endpoint también acepta validar un token externo. Ver `AUTENTICACION_CONECTABLE.md`.

---

## 2. Usuarios y roles  🛡️

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/users` | Lista usuarios (paginado, filtro por rol/estado). |
| POST | `/users` | Crea usuario (modo local). En modo externo: provisiona/mapea rol. |
| GET | `/users/{id}` | Detalle. |
| PATCH | `/users/{id}` | Actualiza rol/estado/datos. |
| DELETE | `/users/{id}` | Desactiva (soft-delete). |
| GET | `/roles` | Lista roles disponibles. |

---

## 3. Catálogos (multi-país y configuración)

| Método | Ruta | Rol | Descripción |
|--------|------|-----|-------------|
| GET | `/countries` | 👤 | Lista países. |
| POST | `/countries` | 🛡️ | Crea país (code, name, prefix). |
| PATCH | `/countries/{code}` | 🛡️ | Actualiza. |
| GET | `/laboratories` | 👤 | Lista laboratorios (filtro `?country=`). |
| POST | `/laboratories` | 🛡️ | Crea laboratorio. |
| PATCH | `/laboratories/{id}` | 🛡️ | Actualiza. |
| GET | `/equipment-types` | 👤 | Catálogo de equipos (filtro `?category=`). |
| POST | `/equipment-types` | 🛡️ | Crea categoría/modelo. |
| PATCH | `/equipment-types/{id}` | 🛡️ | Actualiza. |
| GET | `/serial-formats` | 🛡️ | Lista plantillas de serial. |
| POST | `/serial-formats` | 🛡️ | Crea/ajusta plantilla por país/lab. |

---

## 4. Seriales y equipos (núcleo)

| Método | Ruta | Rol | Descripción |
|--------|------|-----|-------------|
| POST | `/equipment-tags` | 👤 | **Genera** un nuevo serial + equipo. |
| GET | `/equipment-tags` | 👤 | Lista/búsqueda con filtros. |
| GET | `/equipment-tags/{id}` | 👤 | Detalle por ID (ULID). |
| GET | `/equipment-tags/by-serial/{serial}` | 👤 | Detalle por serial legible (para escaneo). |
| PATCH | `/equipment-tags/{id}` | 👤 | Edita tipo/motivo/notas. |
| POST | `/equipment-tags/{id}/inbound` | 👤 | Registra ingreso (escaneo). |
| POST | `/equipment-tags/{id}/discard` | 👤 | Descarta (cambia a `discarded` + motivo). |
| GET | `/equipment-tags/{id}/history` | 👤 | Historial de cambios del equipo. |

**`POST /equipment-tags`** (generación)
```jsonc
// request
{
  "country_code": "CO",
  "laboratory_id": 3,
  "equipment_type_id": 7,        // opcional
  "reason": "sin serial",        // opcional
  "notes": "Ingreso bodega norte", // opcional
  "client_op_id": "9f3c...-uuid"  // opcional (idempotencia offline)
}
// response 201
{
  "id": "01J9Z3K8QF7M2A...",       // ULID
  "serial_code": "CO-000123-A7F2K8",
  "country_code": "CO",
  "laboratory_id": 3,
  "consecutive": 123,
  "random_code": "A7F2K8",
  "status": "active",
  "equipment_type": { "id": 7, "category": "Video", "model": "VIP6102" },
  "created_by": { "id": 12, "username": "operador1" },
  "created_at": "2026-05-23T16:46:00Z"
}
```

**`GET /equipment-tags`** — filtros soportados:
`?serial=` · `?country=` · `?laboratory_id=` · `?type_id=` · `?status=active|discarded` · `?date_from=` · `?date_to=` · `?q=` (texto libre) · `?page=` · `?size=` · `?sort=`.

**`POST /equipment-tags/{id}/discard`**
```jsonc
{ "reason": "dañado" }   // dañado | ilegible | obsoleto | otro
```

---

## 5. Impresión de etiquetas (ZPL térmico)

| Método | Ruta | Rol | Descripción |
|--------|------|-----|-------------|
| GET | `/label-sizes` | 👤 | Tamaños de etiqueta disponibles. |
| POST | `/label-sizes` | 🛡️ | Crea tamaño paramétrico (mm, dpi, plantilla ZPL). |
| POST | `/labels/preview` | 👤 | Devuelve ZPL + vista previa (PNG base64) sin registrar impresión. |
| POST | `/labels/print` | 👤 | Genera ZPL para imprimir y registra el `print_job`. |
| POST | `/equipment-tags/{id}/reprint` | 👤 | Reimprime una etiqueta existente. |
| GET | `/print-jobs` | 👤 | Historial de impresiones (filtros por equipo/fecha). |

**`POST /labels/preview`**
```jsonc
// request
{ "equipment_id": "01J9Z3K8...", "label_size_id": 1, "barcode_type": "code128" }
// response 200
{
  // La etiqueta incluye: texto legible (serial) + código de barras + país de origen + fecha
  "zpl": "^XA^FO40,30^A0N,40,40^FDCO-000123-A7F2K8^FS^FO40,90^BCN,90,Y,N,N^FDCO-000123-A7F2K8^FS^FO40,200^A0N,24,24^FDCOLOMBIA   23/05/2026^FS^XZ",
  "preview_png_base64": "iVBORw0KGgo...",
  "label_size": { "name": "50mm x 25mm", "width_mm": 50, "height_mm": 25, "dpi": 203 }
}
```

**`POST /labels/print`**
```jsonc
{ "equipment_id": "01J9Z3K8...", "label_size_id": 1, "copies": 1, "darkness": 15 }
// response 200 → { "print_job_id": 998, "zpl": "^XA...^XZ" }
```
> La impresión física la realiza el navegador del operador vía **Zebra Browser Print** con el ZPL devuelto. El backend genera el ZPL y deja la traza; no habla directamente con la impresora (también funciona offline).

---

## 6. Sincronización offline/online

| Método | Ruta | Rol | Descripción |
|--------|------|-----|-------------|
| GET | `/sync/pull?since=<cursor>` | 👤 | Entrega cambios (delta) desde el cursor/fecha dado. |
| POST | `/sync/push` | 👤 | Envía operaciones hechas offline (idempotentes vía `client_op_id`). |
| GET | `/sync/status` | 👤 | Estado de sincronización del dispositivo. |

**`POST /sync/push`**
```jsonc
{
  "device_id": "tablet-bodega-01",
  "operations": [
    { "client_op_id": "uuid-1", "type": "create", "payload": { /* equipment_tag */ } },
    { "client_op_id": "uuid-2", "type": "discard", "entity_id": "01J9...", "payload": { "reason": "dañado" } }
  ]
}
// response 200
{ "applied": ["uuid-1"], "conflicts": [], "rejected": [{ "client_op_id":"uuid-2", "reason":"already discarded" }] }
```

---

## 7. Auditoría y metadatos

| Método | Ruta | Rol | Descripción |
|--------|------|-----|-------------|
| GET | `/audit-logs` | 🛡️ | Bitácora de acciones (filtros por actor/acción/fecha). |
| GET | `/meta/config` | 👤 | Config pública (provider de auth activo, versiones, formatos). |
| GET | `/health` | 🔓 | Liveness. |
| GET | `/health/db` | 🔓 | Readiness (conexión a MySQL). |

---
