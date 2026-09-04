# Arquitectura — Serial Manager (Backend)

## 1. Principios de diseño

1. **Backend independiente del frontend.** Toda la funcionalidad se expone vía API REST; cualquier interfaz (PWA, móvil, ERP del cliente) la consume.
2. **Identidad desacoplada.** La autenticación se resuelve por una interfaz `IdentityProvider`; el negocio nunca consulta directamente una tabla de usuarios externa. (Ver `AUTENTICACION_CONECTABLE.md`.)
3. **Arquitectura por capas.** Routers → Servicios → Repositorios → Modelos. La lógica de negocio no conoce HTTP ni SQL crudo.
4. **Multi-país de raíz.** País y laboratorio son entidades de primera clase; el consecutivo se gestiona por combinación país/laboratorio.
5. **Offline-first en el contrato.** El backend expone endpoints de sincronización idempotentes para que la PWA opere sin conexión y reconcilie después.
6. **Todo auditable.** Cada generación de serial y cada cambio de estado deja rastro (quién, qué, cuándo).

## 2. Vista por capas

```
┌─────────────────────────────────────────────────────────────────┐
│                       CLIENTES / CONSUMIDORES                     │
│   PWA (offline/online)   ·   ERP/WMS cliente   ·   App móvil      │
└───────────────────────────────┬─────────────────────────────────┘
                                 │  HTTPS / REST + JWT
┌───────────────────────────────▼─────────────────────────────────┐
│                         API LAYER (FastAPI)                       │
│  Routers v1  ·  Middlewares (CORS, logging, rate-limit)           │
│  Dependencias de auth  ·  Validación Pydantic  ·  OpenAPI/Swagger │
└───────────────────────────────┬─────────────────────────────────┘
                                 │
┌───────────────────────────────▼─────────────────────────────────┐
│                         SERVICE LAYER                             │
│  SerialService · EquipmentService · LabelService · SyncService    │
│  AuditService · UserService                                       │
│                                                                   │
│   ┌─────────────────── IDENTITY (conectable) ────────────────┐    │
│   │  IdentityProvider (interfaz)                             │    │
│   │  ├─ LocalProvider     (nuestra BD)                       │    │
│   │  ├─ OIDCProvider      (Keycloak/Azure AD/Auth0)          │    │
│   │  ├─ LDAPProvider      (Active Directory)                 │    │
│   │  └─ ExternalApiProvider (microservicio del cliente)      │    │
│   └─────────────────────────────────────────────────────────┘    │
└───────────────────────────────┬─────────────────────────────────┘
                                 │
┌───────────────────────────────▼─────────────────────────────────┐
│                     REPOSITORY LAYER (SQLAlchemy)                 │
│  Patrón repositorio · transacciones · bloqueo de consecutivos     │
└───────────────────────────────┬─────────────────────────────────┘
                                 │
┌───────────────────────────────▼─────────────────────────────────┐
│                          MySQL 8+                                 │
│  equipment_tags · countries · laboratories · consecutives ·       │
│  equipment_types · status_history · users · roles · audit_log ·   │
│  label_sizes · print_jobs · serial_formats · sync_log             │
└──────────────────────────────────────────────────────────────────┘
```

## 3. Módulos y responsabilidades

### 3.1 SerialService — Generación de identificadores
- Genera el **ID interno** (UUID v7 / ULID) y el **serial legible** según la plantilla del país/laboratorio.
- Obtiene el siguiente **consecutivo** de forma atómica (ver §4, concurrencia).
- Genera el **código aleatorio** (6 caracteres alfanuméricos sin ambigüedad: sin `O/0`, `I/1`).
- Valida **unicidad** del serial antes de persistir (índice `UNIQUE` + reintento ante colisión del aleatorio).

### 3.2 EquipmentService — Ciclo de vida
- Registro del equipo: país, laboratorio, tipo, motivo, operador.
- Transiciones de estado: `active → discarded` (con motivo) e ingresos (*inbound*).
- Cada transición escribe en `equipment_status_history`.
- Búsqueda y filtrado por serial, país, laboratorio, tipo, estado, fecha.

### 3.3 LabelService — Impresión térmica
- Renderiza **ZPL** a partir de una plantilla y el tamaño de etiqueta seleccionado.
- Soporta **Code 128** y **QR**.
- Genera **vista previa** (imagen PNG server-side o devuelve ZPL para previsualización con Zebra Browser Print).
- Registra cada impresión/reimpresión en `print_jobs`.

### 3.4 SyncService — Offline/Online
- `pull`: entrega cambios desde un `updated_at`/cursor dado (delta).
- `push`: recibe operaciones realizadas offline (idempotentes vía `client_op_id`).
- Resolución de conflictos: **last-write-wins por defecto**, con bitácora en `sync_log` para auditoría; el serial generado offline reserva su ID (ULID) localmente, por lo que no colisiona al sincronizar.

### 3.5 Identity (conectable) — ver documento dedicado
- Contrato `IdentityProvider.authenticate()` / `get_principal()`.
- `factory.py` elige la implementación según `AUTH_PROVIDER`.

### 3.6 AuditService
- Registra acciones sensibles (login, generación de serial, descarte, cambios de catálogo) en `audit_log`.

## 4. Concurrencia del consecutivo (crítico)

El consecutivo por país/laboratorio debe ser correcto bajo **múltiples operadores simultáneos**. Estrategia:

```sql
-- Dentro de una transacción
SELECT current_value FROM consecutives
  WHERE country_code = :c AND laboratory_id = :lab
  FOR UPDATE;                       -- bloqueo de fila (row lock)

UPDATE consecutives SET current_value = current_value + 1
  WHERE country_code = :c AND laboratory_id = :lab;
-- el nuevo consecutivo = current_value (ya incrementado)
COMMIT;
```

- `SELECT ... FOR UPDATE` serializa la asignación del consecutivo evitando duplicados.
- Alternativa para alta concurrencia: tabla de *secuencias* con `INSERT ... ON DUPLICATE KEY UPDATE` y `LAST_INSERT_ID()`.
- En modo **offline** no se asigna consecutivo definitivo hasta sincronizar: el cliente usa el ULID como identidad y el serial legible se confirma/ajusta al hacer `push` (configurable: reservar rango por dispositivo si el cliente lo requiere).

## 5. Seguridad

- **JWT** firmado (HS256 para local; RS256/JWKS cuando se valida contra IdP del cliente).
- Contraseñas (modo local) con **bcrypt/argon2**.
- **RBAC**: roles `admin` y `operator`; dependencias de FastAPI verifican el rol por endpoint.
- **CORS** restringido a orígenes configurados.
- Rate-limiting en endpoints de login.
- Auditoría inmutable de acciones sensibles.
- Secretos vía variables de entorno / *secret manager* (nunca en el repo).

## 6. Despliegue

- **Docker Compose** para desarrollo (API + MySQL).
- Producción: contenedor de la API tras **Nginx** (TLS), MySQL gestionado o contenedor con volumen persistente.
- Migraciones con **Alembic** en el arranque controlado (no automático en prod).
- Health checks (`/health`, `/health/db`) para orquestadores.
- Logs estructurados (JSON) para observabilidad.
