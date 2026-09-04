# Modelo de Datos — Serial Manager (MySQL 8+)

Motor: **InnoDB**, charset `utf8mb4`, colación `utf8mb4_0900_ai_ci`. Migraciones con **Alembic**.

## 1. Diagrama entidad-relación (resumen)

```
countries ──< laboratories ──< consecutives
    │              │
    │              └────────────────┐
    └──────────────┐                │
                   ▼                ▼
equipment_types ──< equipment_tags >── users (created_by)
                        │   │
                        │   └──< equipment_status_history
                        └──< print_jobs >── label_sizes
serial_formats (por país/laboratorio)
users >── roles            audit_log            sync_log
```

> Las tablas `users` y `roles` solo se usan plenamente en modo `AUTH_PROVIDER=local`. En modo externo se conservan como **caché/espejo** de identidades (ver `AUTENTICACION_CONECTABLE.md`).

---

## 2. Tablas

> Cada tabla incluye **🎯 Para qué / Por qué existe** y una **fila de ejemplo** para que el diseño se entienda sin leer código.

### 2.1 `countries` — Países (multi-país)

**🎯 Para qué / Por qué:** El sistema es multi-país desde el primer día. Esta tabla guarda cada país de operación y el **prefijo** que el cliente quiere ver en el serial. Existe como tabla (y no como texto suelto) para no repetir el nombre/prefijo en miles de equipos, evitar errores de tipeo y poder activar/desactivar un país sin borrar su historial.

| Campo | Tipo | Notas |
|-------|------|-------|
| `code` | `CHAR(3)` PK | ISO país (CO, US, CL) |
| `name` | `VARCHAR(100)` | Nombre |
| `prefix` | `VARCHAR(10)` | Prefijo del serial definido por el cliente |
| `is_active` | `BOOLEAN` | |
| `created_at` | `DATETIME` | |

**Ejemplo de datos:**
| code | name | prefix | is_active |
|------|------|--------|-----------|
| CO | Colombia | CO | true |
| US | Estados Unidos | US | true |
| CL | Chile | CL | true |

> *Por qué `code` como PK y no un id numérico:* el código ISO ya es único, estable y legible; se usa directamente en el serial (`CO-000123-...`).

### 2.2 `laboratories` — Laboratorios por país

**🎯 Para qué / Por qué:** Un mismo país puede tener varios laboratorios/sedes que generan etiquetas. La cotización pide estructura *País + Laboratorio + Consecutivo*: el laboratorio permite que cada sede tenga su propia numeración y prefijo. Está separada de `countries` porque la relación es *uno a muchos* (un país → varios laboratorios).

| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | `BIGINT` PK AI | |
| `country_code` | `CHAR(3)` FK→countries | |
| `code` | `VARCHAR(20)` | Código de laboratorio (parte del prefijo) |
| `name` | `VARCHAR(120)` | |
| `is_active` | `BOOLEAN` | |
| | | `UNIQUE(country_code, code)` |

**Ejemplo de datos:**
| id | country_code | code | name | is_active |
|----|--------------|------|------|-----------|
| 1 | CO | BOG | Laboratorio Bogotá | true |
| 2 | CO | MED | Laboratorio Medellín | true |
| 3 | US | NYC | Lab New York | true |

> *Por qué `UNIQUE(country_code, code)`:* el código `BOG` puede existir en Colombia; el mismo código podría reutilizarse en otro país sin chocar.

### 2.3 `consecutives` — Consecutivo por país/laboratorio (concurrencia)

**🎯 Para qué / Por qué:** Guarda el **último número consecutivo** asignado por cada combinación país/laboratorio. Es el "contador" del sistema. Existe como tabla propia (una fila por contador) para poder **bloquear solo esa fila** cuando dos operadores generan un serial al mismo tiempo (`SELECT ... FOR UPDATE`), garantizando que nunca se repita un consecutivo ni se salten números. Sin esta tabla habría riesgo de duplicados bajo uso simultáneo.

| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | `BIGINT` PK AI | |
| `country_code` | `CHAR(3)` FK | |
| `laboratory_id` | `BIGINT` FK (nullable) | NULL = consecutivo a nivel país |
| `current_value` | `BIGINT UNSIGNED` | Último consecutivo asignado |
| `updated_at` | `DATETIME` | |
| | | `UNIQUE(country_code, laboratory_id)` |

**Ejemplo de datos:**
| id | country_code | laboratory_id | current_value |
|----|--------------|---------------|---------------|
| 1 | CO | 1 (Bogotá) | 123 |
| 2 | CO | 2 (Medellín) | 8 |
| 3 | US | 3 (New York) | 45 |

> El próximo equipo en Bogotá tomará el consecutivo **124**; Medellín lleva su propia cuenta (9). Así dos sedes del mismo país no comparten numeración.

### 2.4 `serial_formats` — Plantilla de serial parametrizable

**🎯 Para qué / Por qué:** La cotización describe el serial como *País+Lab+Consecutivo* pero los ejemplos muestran *País-Consecutivo-Aleatorio*. En vez de "quemar" un formato en el código, esta tabla guarda la **plantilla** como texto editable. Así el cliente decide el formato final (con o sin laboratorio, longitud del aleatorio, separadores) **sin reprogramar**. Permite un formato global por defecto y formatos específicos por país/laboratorio.

| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | `BIGINT` PK AI | |
| `country_code` | `CHAR(3)` FK (nullable) | NULL = formato global por defecto |
| `laboratory_id` | `BIGINT` FK (nullable) | |
| `template` | `VARCHAR(120)` | Ej: `{country}-{consecutive:06d}-{random6}` |
| `random_length` | `TINYINT` | Long. del código aleatorio (def. 6) |
| `random_alphabet` | `VARCHAR(40)` | Alfabeto sin ambigüedad |
| `is_active` | `BOOLEAN` | |

**Ejemplo de datos:**
| id | country_code | laboratory_id | template | random_length |
|----|--------------|---------------|----------|---------------|
| 1 | NULL | NULL | `{country}-{consecutive:06d}-{random6}` | 6 |
| 2 | CO | 1 | `{country}-{lab}-{consecutive:06d}-{random6}` | 6 |

- Formato **1** (global) genera: `US-000045-X9L2P1`
- Formato **2** (CO/Bogotá, incluye laboratorio) genera: `CO-BOG-000123-A7F2K8`

> *random_alphabet* típico: `ABCDEFGHJKLMNPQRSTUVWXYZ23456789` (sin `O/0` ni `I/1` para evitar confusión al leer la etiqueta).

### 2.5 `equipment_types` — Catálogo (categoría + modelo, del Excel)

**🎯 Para qué / Por qué:** Es el catálogo de tipos de equipo que el operador elige al generar la etiqueta. Se alimenta del Excel del cliente (categorías *Data* y *Video*). Existe como tabla para estandarizar los modelos (lista cerrada, sin que cada operador escriba el nombre a mano) y poder agregar modelos nuevos sin tocar código.

| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | `BIGINT` PK AI | |
| `category` | `VARCHAR(50)` | `Data` / `Video` |
| `model` | `VARCHAR(100)` | TG2492, eSTREAM 4k, … |
| `is_active` | `BOOLEAN` | |
| | | `UNIQUE(category, model)` |

**Ejemplo de datos:**
| id | category | model | is_active |
|----|----------|-------|-----------|
| 1 | Data | TG2492 | true |
| 7 | Video | VIP6102 | true |
| 12 | Data | Adtran 424RG 1 | true |

### 2.6 `equipment_tags` — **Tabla principal** (equipos identificados)

**🎯 Para qué / Por qué:** Es el **corazón del sistema**: una fila por cada equipo identificado. Guarda el ID único global, el serial legible impreso en la etiqueta, el estado actual y la trazabilidad básica (quién y cuándo). Todas las demás tablas giran alrededor de ésta. El `id` es ULID/UUID v7 (no autoincremental) para que pueda **generarse offline sin colisionar** al sincronizar y para que sea único a nivel global multi-país.

| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | `CHAR(26)` PK | **ULID / UUID v7** (único global, ordenable) |
| `serial_code` | `VARCHAR(60)` `UNIQUE` | Serial legible: `CO-000123-A7F2K8` |
| `country_code` | `CHAR(3)` FK→countries | |
| `laboratory_id` | `BIGINT` FK→laboratories (nullable) | |
| `consecutive` | `BIGINT UNSIGNED` | Consecutivo asignado |
| `random_code` | `VARCHAR(12)` | Código aleatorio |
| `equipment_type_id` | `BIGINT` FK→equipment_types (nullable) | |
| `status` | `ENUM('active','discarded')` | Estado actual |
| `reason` | `VARCHAR(255)` | Motivo: sin serial, ilegible, dañado, otro |
| `notes` | `VARCHAR(500)` | Observación opcional |
| `created_by` | FK→users (nullable) | Operador que generó el serial |
| `created_at` | `DATETIME` | |
| `updated_at` | `DATETIME` | Última modificación |
| `client_op_id` | `CHAR(36)` (nullable) | Idempotencia para sync offline |

**Índices:** `idx_country`, `idx_status`, `idx_created_at`, `idx_type`, `UNIQUE(serial_code)`, `UNIQUE(client_op_id)`.

**Ejemplo de datos:**
| id (ULID) | serial_code | country_code | laboratory_id | consecutive | random_code | type_id | status | reason | created_by |
|-----------|-------------|--------------|---------------|-------------|-------------|---------|--------|--------|------------|
| 01J9Z3K8QF7M2A… | CO-000123-A7F2K8 | CO | 1 | 123 | A7F2K8 | 7 | active | sin serial | 12 |
| 01J9Z4P1RT9N5B… | US-000045-X9L2P1 | US | 3 | 45 | X9L2P1 | 1 | discarded | dañado | 12 |

> *Por qué `status` separado de `reason`:* `status` controla la lógica (activo/descartado); `reason` explica el motivo (sin serial al crear, o dañado/ilegible/obsoleto al descartar).

### 2.7 `equipment_status_history` — Historial de cambios

**🎯 Para qué / Por qué:** La cotización exige *trazabilidad completa desde el ingreso hasta el descarte* e *historial de cambios por equipo*. `equipment_tags` solo guarda el estado **actual**; esta tabla guarda **cada transición** (creación, ingreso, descarte, edición) con quién y cuándo. Es un registro de solo-inserción (append-only): nunca se edita, solo se agregan filas, para que la auditoría sea confiable.

| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | `BIGINT` PK AI | |
| `equipment_id` | `CHAR(26)` FK→equipment_tags | |
| `event` | `ENUM('created','inbound','discarded','updated')` | Tipo de evento |
| `from_status` | `VARCHAR(20)` (nullable) | |
| `to_status` | `VARCHAR(20)` (nullable) | |
| `reason` | `VARCHAR(255)` | |
| `changed_by` | FK→users (nullable) | |
| `changed_at` | `DATETIME` | |

**Ejemplo de datos (vida de un mismo equipo `01J9Z4P1…`):**
| id | equipment_id | event | from_status | to_status | reason | changed_by | changed_at |
|----|--------------|-------|-------------|-----------|--------|------------|------------|
| 1 | 01J9Z4P1… | created | — | active | sin serial | 12 | 2026-05-23 16:46 |
| 2 | 01J9Z4P1… | inbound | active | active | ingreso bodega | 12 | 2026-05-24 09:10 |
| 3 | 01J9Z4P1… | discarded | active | discarded | dañado | 15 | 2026-06-01 11:30 |

> Leyendo estas 3 filas se reconstruye toda la historia del equipo: cuándo nació, cuándo ingresó y cuándo (y por qué) se descartó.

### 2.8 `label_sizes` — Tamaños de etiqueta paramétricos

**🎯 Para qué / Por qué:** La cotización pide *tamaños de etiqueta paramétricos* (el operario elige el tamaño al imprimir). Cada fila define un tamaño físico (mm), la resolución (dpi) y la **plantilla ZPL** que arma la etiqueta. Existe como tabla para soportar equipos grandes y pequeños y agregar tamaños nuevos sin reprogramar el render.

| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | `BIGINT` PK AI | |
| `name` | `VARCHAR(60)` | Ej: "50mm x 25mm" |
| `width_mm` | `DECIMAL(6,2)` | |
| `height_mm` | `DECIMAL(6,2)` | |
| `dpi` | `INT` | 203 / 300 |
| `zpl_template` | `TEXT` | Plantilla ZPL con placeholders |
| `barcode_type` | `ENUM('code128','qr','both')` | |
| `is_default` | `BOOLEAN` | |
| `is_active` | `BOOLEAN` | |

**Ejemplo de datos:**
| id | name | width_mm | height_mm | dpi | barcode_type | is_default |
|----|------|----------|-----------|-----|--------------|------------|
| 1 | 50mm x 25mm | 50.00 | 25.00 | 203 | code128 | true |
| 2 | 100mm x 50mm | 100.00 | 50.00 | 203 | both | false |

> `zpl_template` ejemplo (id 1): `^XA^FO40,30^A0N,40,40^FD{serial}^FS^FO40,90^BCN,90,Y,N,N^FD{serial}^FS^FO40,200^A0N,24,24^FD{country_name}  {model}  {date}^FS^XZ` — los `{...}` se reemplazan al imprimir. Placeholders: `serial`, `country` / `country_name`, `country_code`, `model` (modelo del equipo) y `date`.
>
> Sin `zpl_template` se usa el render paramétrico de `label_service.build_zpl`, cuyo pie va en una línea: **país (izq) · modelo (centro) · fecha (der)**. El modelo se recorta si no cabe entre los otros dos.

### 2.9 `print_jobs` — Impresiones / reimpresiones

**🎯 Para qué / Por qué:** Registra **cada vez que se imprime** una etiqueta (original o reimpresión), guardando el ZPL exacto enviado. Sirve para auditoría ("¿quién reimprimió esta etiqueta y cuándo?") y para diagnosticar problemas de impresión. La reimpresión es un requisito explícito de la cotización.

| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | `BIGINT` PK AI | |
| `equipment_id` | `CHAR(26)` FK→equipment_tags | |
| `label_size_id` | `BIGINT` FK→label_sizes | |
| `copies` | `INT` | |
| `darkness` | `INT` | 1–30 |
| `zpl_generated` | `TEXT` | ZPL exacto enviado |
| `is_reprint` | `BOOLEAN` | |
| `printed_by` | FK→users (nullable) | |
| `printed_at` | `DATETIME` | |

**Ejemplo de datos:**
| id | equipment_id | label_size_id | copies | darkness | is_reprint | printed_by | printed_at |
|----|--------------|---------------|--------|----------|------------|------------|------------|
| 1 | 01J9Z3K8… | 1 | 1 | 15 | false | 12 | 2026-05-23 16:47 |
| 2 | 01J9Z3K8… | 1 | 1 | 20 | true | 15 | 2026-05-30 08:15 |

> La fila 2 (`is_reprint=true`) muestra que la etiqueta se volvió a imprimir días después, p. ej. porque se dañó la original.

### 2.10 `users` — Usuarios (modo local / espejo en modo externo)

**🎯 Para qué / Por qué:** Guarda los usuarios del sistema. En modo `local` (desarrollo) contiene la contraseña cifrada. En modo externo (cuando el cliente conecta su propio sistema) actúa como **espejo/caché**: guarda `provider`+`external_id` para tener una referencia estable a la que apuntan `created_by`/`printed_by`, sin almacenar contraseñas. Así la app tiene FK válidas aunque el usuario "viva" fuera. (Detalle en `AUTENTICACION_CONECTABLE.md`.)

| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | `BIGINT` PK AI | |
| `username` | `VARCHAR(80)` `UNIQUE` | |
| `email` | `VARCHAR(160)` (nullable) | |
| `full_name` | `VARCHAR(160)` (nullable) | |
| `password_hash` | `VARCHAR(255)` (nullable) | NULL en modo externo |
| `role_id` | `BIGINT` FK→roles | |
| `provider` | `VARCHAR(30)` | `local`/`oidc`/`ldap`/`external_api` |
| `external_id` | `VARCHAR(160)` (nullable) | ID del usuario en el sistema del cliente |
| `is_active` | `BOOLEAN` | |
| `last_login_at` | `DATETIME` (nullable) | |
| `created_at` | `DATETIME` | |
| | | `UNIQUE(provider, external_id)` |

**Ejemplo de datos:**
| id | username | full_name | password_hash | role_id | provider | external_id | is_active |
|----|----------|-----------|---------------|---------|----------|-------------|-----------|
| 1 | admin | Administrador | `$2b$12$…` | 1 (admin) | local | NULL | true |
| 12 | operador1 | Juan Pérez | `$2b$12$…` | 2 (operator) | local | NULL | true |
| 31 | jgomez | Julia Gómez | NULL | 2 (operator) | oidc | `a3f1-9c…` | true |

> Filas 1 y 12 = modo local (con `password_hash`). Fila 31 = usuario que entró por el IdP del cliente (sin contraseña local, identificado por `external_id`).

### 2.11 `roles` — Roles (RBAC)

**🎯 Para qué / Por qué:** Define los roles que controlan los permisos (control de acceso basado en roles). La cotización pide roles **Administrador** y **Operador**. Tabla aparte para no repetir el nombre del rol en cada usuario y poder describir qué hace cada uno.

| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | `BIGINT` PK AI | |
| `name` | `VARCHAR(40)` `UNIQUE` | `admin` / `operator` |
| `description` | `VARCHAR(160)` | |

**Ejemplo de datos:**
| id | name | description |
|----|------|-------------|
| 1 | admin | Gestiona catálogos, usuarios y configuración. |
| 2 | operator | Genera seriales, imprime e ingresa/descarta equipos. |

### 2.12 `audit_log` — Auditoría

**🎯 Para qué / Por qué:** Bitácora de **acciones sensibles** (login, generación de serial, descarte, cambios de catálogo). Responde "¿quién hizo qué y cuándo?". Es distinta de `equipment_status_history` (que sigue al equipo): aquí se registra **toda** acción relevante del sistema, incluso login o cambios de configuración. Guarda `actor_label` para que el registro siga siendo legible aunque el usuario viva en un sistema externo.

| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | `BIGINT` PK AI | |
| `actor_id` | `BIGINT` (nullable) | Usuario (o external_id) |
| `actor_label` | `VARCHAR(160)` | Identidad legible (útil en modo externo) |
| `action` | `VARCHAR(60)` | `login`, `serial.generate`, `equipment.discard`, … |
| `entity_type` | `VARCHAR(60)` | |
| `entity_id` | `VARCHAR(60)` | |
| `metadata` | `JSON` | Detalle del evento |
| `ip_address` | `VARCHAR(45)` | |
| `created_at` | `DATETIME` | |

**Ejemplo de datos:**
| id | actor_label | action | entity_type | entity_id | metadata | created_at |
|----|-------------|--------|-------------|-----------|----------|------------|
| 1 | operador1 | login | session | — | `{"ok":true}` | 2026-05-23 16:40 |
| 2 | operador1 | serial.generate | equipment_tag | 01J9Z3K8… | `{"serial":"CO-000123-A7F2K8"}` | 2026-05-23 16:46 |
| 3 | jgomez | equipment.discard | equipment_tag | 01J9Z4P1… | `{"reason":"dañado"}` | 2026-06-01 11:30 |

### 2.13 `sync_log` — Bitácora de sincronización offline/online

**🎯 Para qué / Por qué:** La app funciona offline (tipo Outlook) y sincroniza al recuperar conexión. Esta tabla registra cada operación que llega desde un dispositivo offline y **evita aplicarla dos veces** gracias a `client_op_id` (idempotencia). También deja constancia de conflictos (p. ej. descartar algo ya descartado), apoyando la *resolución de conflictos* que pide la cotización.

| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | `BIGINT` PK AI | |
| `client_op_id` | `CHAR(36)` `UNIQUE` | Idempotencia |
| `device_id` | `VARCHAR(80)` | |
| `operation` | `VARCHAR(40)` | `create`/`update`/`discard`/`print` |
| `entity_id` | `CHAR(26)` | |
| `status` | `ENUM('applied','conflict','rejected')` | |
| `conflict_detail` | `JSON` (nullable) | |
| `synced_at` | `DATETIME` | |

**Ejemplo de datos:**
| id | client_op_id | device_id | operation | entity_id | status | conflict_detail | synced_at |
|----|--------------|-----------|-----------|-----------|--------|-----------------|-----------|
| 1 | 9f3c…-uuid | tablet-bodega-01 | create | 01J9Z3K8… | applied | NULL | 2026-05-23 18:00 |
| 2 | a1b2…-uuid | tablet-bodega-01 | discard | 01J9Z4P1… | rejected | `{"reason":"already discarded"}` | 2026-05-23 18:00 |

> La fila 2 muestra una operación hecha offline que ya no aplica al sincronizar: queda registrada como `rejected` con el motivo, sin romper datos.

---

## 3. DDL de referencia (extracto principal)

```sql
CREATE TABLE countries (
  code       CHAR(3) PRIMARY KEY,
  name       VARCHAR(100) NOT NULL,
  prefix     VARCHAR(10)  NOT NULL,
  is_active  BOOLEAN NOT NULL DEFAULT TRUE,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE laboratories (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  country_code CHAR(3) NOT NULL,
  code         VARCHAR(20) NOT NULL,
  name         VARCHAR(120) NOT NULL,
  is_active    BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE KEY uq_lab (country_code, code),
  CONSTRAINT fk_lab_country FOREIGN KEY (country_code) REFERENCES countries(code)
) ENGINE=InnoDB;

CREATE TABLE consecutives (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  country_code  CHAR(3) NOT NULL,
  laboratory_id BIGINT NULL,
  current_value BIGINT UNSIGNED NOT NULL DEFAULT 0,
  updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_seq (country_code, laboratory_id),
  CONSTRAINT fk_seq_country FOREIGN KEY (country_code) REFERENCES countries(code),
  CONSTRAINT fk_seq_lab FOREIGN KEY (laboratory_id) REFERENCES laboratories(id)
) ENGINE=InnoDB;

CREATE TABLE equipment_types (
  id        BIGINT AUTO_INCREMENT PRIMARY KEY,
  category  VARCHAR(50) NOT NULL,
  model     VARCHAR(100) NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE KEY uq_type (category, model)
) ENGINE=InnoDB;

CREATE TABLE equipment_tags (
  id                CHAR(26) PRIMARY KEY,                 -- ULID
  serial_code       VARCHAR(60) NOT NULL,
  country_code      CHAR(3) NOT NULL,
  laboratory_id     BIGINT NULL,
  consecutive       BIGINT UNSIGNED NOT NULL,
  random_code       VARCHAR(12) NOT NULL,
  equipment_type_id BIGINT NULL,
  status            ENUM('active','discarded') NOT NULL DEFAULT 'active',
  reason            VARCHAR(255) NULL,
  notes             VARCHAR(500) NULL,
  created_by        BIGINT NULL,
  created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  client_op_id      CHAR(36) NULL,
  UNIQUE KEY uq_serial (serial_code),
  UNIQUE KEY uq_client_op (client_op_id),
  KEY idx_country (country_code),
  KEY idx_status (status),
  KEY idx_created_at (created_at),
  KEY idx_type (equipment_type_id),
  CONSTRAINT fk_tag_country FOREIGN KEY (country_code) REFERENCES countries(code),
  CONSTRAINT fk_tag_lab FOREIGN KEY (laboratory_id) REFERENCES laboratories(id),
  CONSTRAINT fk_tag_type FOREIGN KEY (equipment_type_id) REFERENCES equipment_types(id)
) ENGINE=InnoDB;
```

*(El DDL completo de las 13 tablas se genera vía Alembic a partir de los modelos SQLAlchemy.)*

## 4. Datos iniciales (seeds)

1. **Roles:** `admin`, `operator`.
2. **Usuario admin** inicial (solo modo `local`).
3. **Países** ejemplo: CO, US, CL (prefijos a confirmar con el cliente).
4. **Catálogo `equipment_types`** cargado desde el Excel del cliente:
   - *Data:* TG2492, TG2482, F@ST3890, F@ST3896, FG1100, IP3442, Adtran 424RG 1, Adtran 424RG 2.
   - *Video:* eSTREAM 4k, Fuse 4k, DMS1004, DCX3520, DCX525, VIP6102.
5. **`label_sizes`** por defecto: `50mm x 25mm @203dpi` (Code 128), según la cotización.
6. **`serial_formats`** global por defecto: `{country}-{consecutive:06d}-{random6}`.

