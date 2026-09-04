# Serial Manager — Sistema de Identificación y Trazabilidad de Equipos

> Plataforma modular, multi-país, para generar **identificadores únicos** de equipos sin número de serie, gestionar su **ciclo de vida** (ingreso → descarte) e **imprimir etiquetas térmicas** (ZPL / Zebra). Backend en **Python + FastAPI**, base de datos **MySQL 8+**, API **REST documentada con OpenAPI/Swagger** y autenticación **JWT con proveedor de identidad conectable**.

> 💡 **¿Tienes dudas sobre los archivos JSON o el script verify.ps1?** Lee primero [`README_ADICIONAL.md`](README_ADICIONAL.md) — explica las herramientas auxiliares de verificación y diagnóstico.

---

## 📑 Índice de la documentación

| Documento | Contenido |
|-----------|-----------|
| **README.md** (este archivo) | Visión general, stack, instalación y despliegue |
| [`DESPLIEGUE_MANUAL.md`](DESPLIEGUE_MANUAL.md) | **⭐ Despliegue sin Docker**: instalación manual en servidor Linux |
| [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) | Arquitectura por capas, módulos, diagrama de componentes |
| [`docs/BASE_DE_DATOS.md`](docs/BASE_DE_DATOS.md) | Modelo de datos completo, DDL MySQL, índices, migraciones |
| [`docs/API_ENDPOINTS.md`](docs/API_ENDPOINTS.md) | Catálogo completo de endpoints REST con request/response |
| [`docs/INTERFAZ_MODULOS.md`](docs/INTERFAZ_MODULOS.md) | Módulos/pantallas que debe tener la interfaz para usar el backend al 100% |
| [`docs/FRONTEND_ARQUITECTURA.md`](docs/FRONTEND_ARQUITECTURA.md) | Arquitectura del frontend Vue 3 + PWA + Tauri (web e instalable) |
| [`docs/DESPLIEGUE_CAPROVER.md`](docs/DESPLIEGUE_CAPROVER.md) | Despliegue en producción con CapRover |

---

## 1. Problema que resuelve

- Equipos **sin número de serie** que ingresan a operación sin identificación formal.
- Imposibilidad de **rastrear el historial** de un equipo (ingreso, estado, descarte).
- Errores manuales en el registro de activos.
- Falta de trazabilidad en equipos descartados o con serial ilegible.
- Ausencia de un **identificador único global** para operaciones **multi-país**.

## 2. Solución (módulos del MVP)

| # | Módulo | Descripción |
|---|--------|-------------|
| 1 | **Generación de seriales** | ID único global (UUID v7 / ULID) + serial legible `PAÍS-LAB-CONSECUTIVO-ALEATORIO`, validación anti-duplicados, consecutivo por país/laboratorio con control de concurrencia. |
| 2 | **Gestión de equipos** | CRUD, estados `activo`/`descartado`, motivos configurables, búsqueda y filtrado, historial de cambios. |
| 3 | **Impresión térmica** | Generación de comandos ZPL, Code 128 / QR, tamaños de etiqueta paramétricos, vista previa, reimpresión. |
| 4 | **Usuarios y roles** | Autenticación, roles Administrador/Operador, **proveedor de identidad conectable** (local o sistema del cliente), auditoría. |
| 5 | **API REST** | Endpoints documentados (OpenAPI/Swagger), JWT, backend independiente del frontend, listo para integrarse con ERP/WMS del cliente. |
| 6 | **Soporte offline/online** | Endpoints de sincronización (push/pull) que habilitan la PWA híbrida tipo Outlook con resolución de conflictos. |

## 3. Catálogo de equipos (del archivo del cliente)

El Excel `serializado de equipo proyecto.xlsx` define las categorías y modelos iniciales que alimentan el catálogo `equipment_types`:

| Categoría | Modelos |
|-----------|---------|
| **Data** | TG2492, TG2482, F@ST3890, F@ST3896, FG1100, IP3442, Adtran 424RG 1, Adtran 424RG 2 |
| **Video** | eSTREAM 4k, Fuse 4k, DMS1004, DCX3520, DCX525, VIP6102 |

> Estos datos se cargan vía *seed* inicial; el catálogo es administrable por API.

## 4. Estructura del serial

```
CO - 000123 - A7F2K8
│     │         │
│     │         └─ Código aleatorio alfanumérico (anti-colisión / no adivinable)
│     └─────────── Consecutivo por país + laboratorio (control de concurrencia)
└───────────────── Prefijo País (+ Laboratorio) definido por el cliente
```

- **ID interno:** UUID v7 / ULID (clave primaria, ordenable en el tiempo, único global).
- **Serial legible:** plantilla **parametrizable** por país/laboratorio (ver [`docs/BASE_DE_DATOS.md`](docs/BASE_DE_DATOS.md) → tabla `serial_formats`). El formato por defecto es `{country}-{consecutive:06d}-{random6}`.

> ⚠️ Nota de diseño: la estructura del serial es una **plantilla configurable**, de modo que el cliente decide si el laboratorio va embebido en el prefijo, como segmento propio, o se omite.

## 5. Stack tecnológico

| Componente | Tecnología |
|------------|------------|
| Lenguaje / Framework | **Python 3.12 + FastAPI** |
| ORM / Migraciones | **SQLAlchemy 2.x + Alembic** |
| Base de datos | **MySQL 8+** (SQLite para desarrollo rápido) |
| Validación / Schemas | **Pydantic v2** |
| Identificadores | UUID v7 / ULID (`python-ulid`) |
| Autenticación | **JWT** (`PyJWT`) + proveedor de identidad conectable |
| Impresión | Generación **ZPL** + integración **Zebra Browser Print** (lado cliente) |
| Documentación API | **OpenAPI / Swagger** (nativo de FastAPI) + ReDoc |
| Códigos de barras (preview server-side) | `python-barcode`, `qrcode` |
| Servidor ASGI | **Uvicorn** (tras Nginx en producción) |
| Contenedores | **Docker + docker-compose** |
| Pruebas | **pytest** + httpx |
| Frontend (fase posterior) | PWA (Vue/React/Angular — a definir con el cliente) + IndexedDB + Service Worker |

---

## 6. Instalación y desarrollo

### Requisitos

- **Python 3.11+** (probado en 3.12 y 3.13)
- **MySQL 8+** (o Docker) para producción; SQLite para smoke-test local
- **Docker Desktop** para Windows (opcional, recomendado)

### Instalación local (sin Docker)

```bash
# Crear entorno virtual y activar
python -m venv .venv
.venv\Scripts\Activate.ps1    # PowerShell en Windows

# Instalar dependencias
pip install -e .[dev]

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus configuraciones
```

### Correr con SQLite (desarrollo rápido, sin MySQL)

```bash
# En .env configurar: DATABASE_URL=sqlite:///./serial_manager.db

# Crear tablas y datos iniciales
python -m app.seeds.run

# Iniciar servidor de desarrollo
uvicorn app.main:app --reload --port 8080
```

- **Swagger:** http://localhost:8080/docs
- **Health:** http://localhost:8080/health

---

## 7. Despliegue con Docker (Recomendado)

### Levantar todo (MySQL + API con hot reload)

Desde la raíz del proyecto:

```powershell
docker compose up -d --build
```

Esto:
1. Construye la imagen de la API
2. Levanta **MySQL 8** (`serial_db`) con volumen persistente
3. Espera a que MySQL esté listo, aplica **migraciones** (`alembic upgrade head`)
4. Siembra **datos iniciales** (roles, admin, países, catálogo del Excel, etiquetas, formatos)
5. Arranca la API con **uvicorn --reload**

La primera vez tarda un poco (compila la imagen). Las siguientes son inmediatas.

### Verificar que está corriendo

```powershell
# Ver estado de contenedores
docker compose ps

# Verificar salud
curl http://localhost:8080/health        # {"status":"ok",...}
curl http://localhost:8080/health/db     # {"database":"up"}
```

- **Swagger (documentación interactiva):** http://localhost:8080/docs
- **ReDoc:** http://localhost:8080/redoc

**Login inicial:** usuario `admin` / contraseña según `ADMIN_PASSWORD` en `.env` (por defecto `admin123` en docker-compose).

### Recarga automática en caliente (hot reload)

El `docker-compose.yml` **monta tu carpeta `./app` de Windows dentro del contenedor**:

```yaml
volumes:
  - ./app:/app/app
  - ./migrations:/app/migrations
  - ./alembic.ini:/app/alembic.ini
```

Y arranca uvicorn con `--reload` + `WATCHFILES_FORCE_POLLING=true`.

**Prueba:**
1. Edita cualquier archivo en `app\` (por ejemplo un endpoint)
2. Guarda
3. En unos segundos, uvicorn recarga solo — **sin reconstruir la imagen**

```powershell
docker compose logs -f api      # observa la recarga en vivo
```

> ⚠️ Si **agregas dependencias** nuevas (editas `pyproject.toml`) o **cambias los modelos** (nuevas tablas/columnas), sí necesitas reconstruir/migrar.

### Comandos útiles

| Acción | Comando |
|--------|---------|
| Ver estado | `docker compose ps` |
| Ver logs de la API | `docker compose logs -f api` |
| Ver logs de MySQL | `docker compose logs -f db` |
| Detener (mantiene datos) | `docker compose stop` |
| Reanudar | `docker compose start` |
| Apagar y borrar contenedores | `docker compose down` |
| Apagar y **borrar también los datos** | `docker compose down -v` |
| Reconstruir tras cambiar dependencias | `docker compose up -d --build` |
| Reiniciar solo la API | `docker compose restart api` |

---

## 8. Migraciones de base de datos (Alembic)

### Con Docker

```powershell
# Crear una nueva migración tras cambiar los modelos
docker compose exec api python -m alembic revision --autogenerate -m "descripcion"

# Aplicar migraciones pendientes
docker compose exec api python -m alembic upgrade head
```

### Sin Docker (entorno local)

```bash
# Aplicar migraciones
python -m alembic upgrade head

# Crear nueva migración
python -m alembic revision --autogenerate -m "mensaje"
```

> Las migraciones se aplican **automáticamente al arrancar** el contenedor Docker.

---

## 9. Datos iniciales (seeds)

Los seeds son **idempotentes** (no duplican). Para re-ejecutarlos:

### Con Docker
```powershell
docker compose exec api python -m app.seeds.run
```

### Sin Docker
```bash
python -m app.seeds.run
```

### Para empezar de cero (borra la BD)
```powershell
docker compose down -v
docker compose up -d --build
```

---

## 10. Pruebas

### Pruebas unitarias / integración (pytest)

```bash
# Sin Docker (usa SQLite en memoria)
python -m pytest -q
```

Resultado esperado: **15 passed**. Cubren: auth/RBAC, generación de seriales, consecutivos, ciclo de vida, historial, impresión/reimpresión y sincronización offline.

### Verificación completa con Postman/Newman

En la carpeta [`postman/`](postman/) hay:
- `Serial_Manager.postman_collection.json` — colección con **37 requests** organizados
- `Serial_Manager.local.postman_environment.json` — entorno apuntando a `http://localhost:8080`

#### Opción A — Verificación automática (recomendada)

```powershell
.\scripts\verify.ps1
```

Ejecuta los **37 endpoints** contra la API en Docker y genera un reporte HTML en **`reports\newman-report.html`**.

> Requiere Node.js (para `newman`, vía `npx`). Resultado esperado: **37 requests · 40 assertions · 0 failed**.

#### Opción B — Uso manual con Postman

1. Abre Postman → **Import** → arrastra ambos archivos
2. Selecciona el entorno **"Serial Manager — Local (Docker)"**
3. Ejecuta en orden:
   - **Auth → Login** (guarda el token automáticamente)
   - **Catálogos → Crear laboratorio** (guarda `lab_id`)
   - **Equipos → Generar serial** (guarda `tag_id` y `serial_code`)
   - El resto de requests ya usan esas variables

#### Opción C — Uso con Swagger (navegador)

1. Abre http://localhost:8080/docs
2. **Authorize** → pega el `access_token` que devuelve `POST /auth/login`
3. Prueba cualquier endpoint con "Try it out"

---

## 11. Variables de entorno clave (`.env`)

| Variable | Descripción | Valor por defecto |
|----------|-------------|-------------------|
| `DATABASE_URL` | Conexión a BD (MySQL o SQLite) | `mysql+pymysql://...` |
| `AUTH_PROVIDER` | Proveedor de identidad: `local` / `oidc` / `ldap` / `external_api` | `local` |
| `JWT_SECRET` | Secreto de firma JWT (≥32 bytes en prod) | — |
| `JWT_ALGORITHM` | Algoritmo JWT | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Duración del token de acceso | `30` |
| `ADMIN_PASSWORD` | Contraseña inicial del usuario admin | `admin123` |
| `RUN_SEEDS` | `1` para sembrar al arrancar el contenedor | `0` |

---

## 12. Estructura del proyecto

```
etiquetas/
├── README.md                      # Este archivo
├── docs/                          # Documentación técnica completa
│   ├── ARQUITECTURA.md
│   ├── BASE_DE_DATOS.md
│   ├── API_ENDPOINTS.md
│   ├── AUTENTICACION_CONECTABLE.md
│   ├── FRONTEND_ARQUITECTURA.md
│   └── DESPLIEGUE_CAPROVER.md
├── requerimientos/                # Insumos del cliente (cotización + Excel)
├── postman/                       # Colección de pruebas Postman
├── scripts/                       # Scripts de verificación y utilidades
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── pyproject.toml
├── alembic.ini
├── migrations/                    # Migraciones Alembic
├── tests/                         # Pruebas pytest
└── app/
    ├── main.py                    # Arranque FastAPI, routers, middlewares
    ├── core/
    │   ├── config.py              # Settings (Pydantic Settings, .env)
    │   ├── database.py            # Engine, sesión SQLAlchemy
    │   ├── security.py            # JWT, hashing, dependencias de auth
    │   ├── middleware.py          # CORS, error handlers
    │   └── json_type.py           # Tipo JSON personalizado para SQLAlchemy
    ├── models/                    # Modelos ORM (13 tablas)
    │   ├── user.py
    │   ├── catalog.py
    │   ├── equipment.py
    │   ├── printing.py
    │   ├── sync.py
    │   └── audit.py
    ├── schemas/                   # Esquemas Pydantic (request/response)
    ├── services/                  # Lógica de negocio
    │   ├── serial_service.py      # Generación de seriales + consecutivos
    │   ├── equipment_service.py   # Ciclo de vida del equipo
    │   ├── label_service.py       # Render ZPL / preview
    │   ├── sync_service.py        # Sincronización offline/online
    │   └── audit_service.py       # Auditoría y trazabilidad
    ├── identity/                  # ⭐ Proveedores de identidad conectables
    │   ├── base.py                # Interfaz IdentityProvider (contrato)
    │   ├── local_provider.py      # BD propia (desarrollo / standalone)
    │   ├── oidc_provider.py       # OAuth2 / OpenID Connect del cliente
    │   ├── ldap_provider.py       # Directorio LDAP / AD del cliente
    │   ├── external_api_provider.py # API de usuarios propia del cliente
    │   └── factory.py             # Selección por configuración (AUTH_PROVIDER)
    ├── api/v1/                    # Routers REST versionados
    │   ├── router.py
    │   └── endpoints/
    │       ├── auth.py
    │       ├── users.py
    │       ├── catalogs.py
    │       ├── equipment.py
    │       ├── labels.py
    │       ├── sync.py
    │       └── audit.py
    └── seeds/                     # Datos iniciales
        └── run.py
```

---

## 13. Sistema de autenticación conectable

> **Este es el requisito arquitectónico más importante del proyecto.**

El sistema **NO acopla** la lógica de negocio a una tabla de usuarios concreta. Toda la autenticación pasa por una **interfaz `IdentityProvider`** con varias implementaciones intercambiables por **configuración** (`AUTH_PROVIDER`):

| Modo | `AUTH_PROVIDER` | Uso |
|------|-----------------|-----|
| **Local** | `local` | **Desarrollo / standalone.** Los usuarios viven en *nuestra* BD MySQL. |
| **OIDC** | `oidc` | El cliente ya tiene Keycloak / Azure AD / Auth0 / Google. Delegamos login y validamos JWT contra su JWKS. |
| **LDAP / AD** | `ldap` | El cliente autentica contra su Active Directory / LDAP corporativo. |
| **API externa** | `external_api` | El cliente expone su propio microservicio de usuarios; nos conectamos a su endpoint. |

Cambiar de proveedor **no requiere tocar la lógica de negocio**, solo variables de entorno (y, en su caso, mapeo de roles). El detalle completo está en [`docs/AUTENTICACION_CONECTABLE.md`](docs/AUTENTICACION_CONECTABLE.md).

---

## 14. Solución de problemas

| Síntoma | Causa / Solución |
|---------|------------------|
| `port is already allocated` (8080/3306) | Otro proceso usa el puerto. Cámbialo en `docker-compose.yml` (`"8081:8080"`) o cierra el proceso. |
| La API reinicia en bucle al inicio | MySQL aún inicializando. El contenedor espera con un loop; dale ~20-30s la primera vez. Revisa `docker compose logs db`. |
| El cambio en el código no se refleja | Confirma que editas dentro de `app\`. Si no, revisa que `WATCHFILES_FORCE_POLLING=true` esté en el compose y reinicia: `docker compose restart api`. |
| Error de conexión a BD | `docker compose logs db` para ver si MySQL está `healthy`. Reinicia: `docker compose restart`. |
| Cambié un modelo y falla | Genera y aplica migración (ver §8). |
| Quiero datos limpios | `docker compose down -v && docker compose up -d --build`. |

---

## 15. Alcance del MVP y exclusiones

**Incluye:**
- Generación de seriales con consecutivos y control de concurrencia
- Gestión completa del ciclo de vida de equipos
- Impresión térmica paramétrica (ZPL)
- Usuarios/roles/auditoría con proveedor de identidad conectable
- API REST documentada (OpenAPI/Swagger)
- Soporte de sincronización offline/online

**No incluye (fases futuras):**
- Integración *activa* con sistemas existentes del cliente (la API queda **lista** para ello — Fase 2)
- Aplicación móvil nativa (Fase 3)
- Reportes avanzados / dashboards analíticos (Fase 4)
- Lógica multi-impresora avanzada y zonas de impresión (Fase 5)
- Configuración física de impresoras en sitio

---

## 16. Recursos adicionales

- **Documentación de la API:** Una vez corriendo, visita http://localhost:8080/docs
- **Documentación técnica completa:** Carpeta [`docs/`](docs/)
- **Colección de Postman:** Carpeta [`postman/`](postman/)
- **Scripts de verificación:** Carpeta [`scripts/`](scripts/)

---

## 17. Resumen de comandos rápidos

```powershell
# Desarrollo con Docker (recomendado)
docker compose up -d --build      # Levantar todo
docker compose logs -f api        # Ver logs en tiempo real
docker compose down               # Apagar (conserva datos)
docker compose down -v            # Apagar y borrar datos

# Desarrollo local sin Docker
python -m venv .venv && .venv\Scripts\Activate.ps1
pip install -e .[dev]
cp .env.example .env              # Configurar DATABASE_URL a SQLite
python -m app.seeds.run           # Crear BD y datos iniciales
uvicorn app.main:app --reload --port 8080

# Migraciones
python -m alembic upgrade head    # Aplicar
python -m alembic revision --autogenerate -m "mensaje"  # Crear

# Pruebas
python -m pytest -q               # Unitarias/integración
.\scripts\verify.ps1              # Verificación completa con Newman
```

---

*Documento técnico · Sistema de Identificación y Trazabilidad de Equipos · Confidencial.*
