# Módulos de la Interfaz (Frontend) — Serial Manager

> Mapa de **todo lo que la interfaz debe tener** para usar el backend **al 100%**. Cada módulo explica **🎯 para qué / por qué** existe, **qué pantallas** incluye, **qué endpoints consume** y **qué rol** lo usa. La navegación sigue el mockup de la cotización (sidebar: Dashboard · Generar Serial · Lista de Seriales · Equipos · Descartados · Impresiones · Usuarios · Configuración).

La interfaz objetivo es una **PWA** (Progressive Web App) híbrida offline/online, tipo Outlook. Roles: 🛡️ Administrador · 👤 Operador.

---

## 0. Mapa de navegación (sidebar)

```
┌───────────────────────┐
│ 🏷  Serial Manager     │
├───────────────────────┤
│ 📊 Dashboard          │ ← resumen y métricas
│ ➕ Generar Serial     │ ← núcleo operativo
│ 📋 Lista de Seriales  │ ← búsqueda y consulta
│ 💻 Equipos            │ ← ficha y ciclo de vida
│ 🗑  Descartados        │ ← vista filtrada de bajas
│ 🖨  Impresiones        │ ← historial de impresión
│ 👥 Usuarios           │ 🛡 solo admin
│ ⚙  Configuración       │ 🛡 solo admin (catálogos)
├───────────────────────┤
│ 🔌 Estado: Online/Off │ ← indicador de sincronización
│ 🚪 Cerrar sesión      │
└───────────────────────┘
```

> **Por qué este orden:** lo que el operador usa todo el día arriba (Generar/Lista/Equipos); lo administrativo abajo y restringido por rol. El indicador de conexión es permanente porque el sistema trabaja offline.

---

## 1. Módulo de Sesión y Autenticación

**🎯 Para qué / Por qué:** Es la puerta de entrada. Sin login no se puede operar, y el backend exige un **JWT** en cada llamada. Este módulo obtiene el token, lo guarda de forma segura, lo renueva antes de que expire y lo adjunta a cada request automáticamente. **Por qué importa:** también debe soportar el caso en que el cliente conecte **su propio sistema de usuarios** (OIDC/LDAP), así que la pantalla de login debe poder redirigir al IdP del cliente o pedir usuario/clave según la configuración.

**Pantallas / componentes:**
- Pantalla de **Login** (usuario + contraseña) o botón "Ingresar con [IdP del cliente]" según `AUTH_PROVIDER`.
- Interceptor HTTP que adjunta `Authorization: Bearer` y renueva el token con el refresh.
- Manejo de sesión expirada (redirige a login sin perder trabajo offline).

**Endpoints:** `POST /auth/login` · `POST /auth/refresh` · `POST /auth/logout` · `GET /auth/me` · `GET /meta/config` (para saber qué proveedor mostrar).

**Rol:** todos.

---

## 2. Dashboard

**🎯 Para qué / Por qué:** Da una **foto rápida** del estado del sistema apenas se entra (igual que el mockup de la propuesta: total generados, activos, descartados, impresiones). **Por qué:** el cliente quiere control y visibilidad; un resumen evita tener que buscar para saber "cuántos equipos llevo". También muestra los últimos seriales generados como acceso rápido.

**Pantallas / componentes:**
- Tarjetas de métricas: **Generados · Activos · Descartados · Impresiones**.
- Tabla "Últimos seriales generados" con acceso directo a la ficha.
- Filtro por país (para operaciones multi-país).

**Endpoints:** `GET /equipment-tags` (con filtros/conteos) · `GET /print-jobs` · `GET /meta/config`.

**Rol:** todos (el operador ve sus métricas; el admin, las globales).

---

## 3. Generar Serial (núcleo operativo)

**🎯 Para qué / Por qué:** Es **la razón de ser del sistema**: crear el identificador único e imprimir la etiqueta. **Por qué su propio módulo:** es la acción más frecuente del operador y debe ser rapidísima (pocos clics): elegir país/laboratorio, tipo y motivo, y obtener el serial listo para imprimir. Debe funcionar **offline**.

**Pantallas / componentes:**
- Formulario: **País** y **Laboratorio** (selector), **Tipo de equipo** (catálogo), **Motivo** (sin serial/ilegible/dañado/otro), **Observación**.
- Botón **Generar Serial** → muestra el serial creado (`CO-000123-A7F2K8`) en grande.
- Panel de **Vista previa de etiqueta** + botón **Imprimir** (ver módulo 7).
- Confirmación visual de "guardado" (y de "guardado offline, pendiente de sincronizar" cuando no hay conexión).

**Endpoints:** `POST /equipment-tags` · `GET /countries` · `GET /laboratories` · `GET /equipment-types` · `POST /labels/preview`.

**Rol:** 👤 Operador (y admin).

---

## 4. Lista de Seriales (búsqueda y consulta)

**🎯 Para qué / Por qué:** Permite **encontrar cualquier equipo** rápidamente. **Por qué:** con miles de equipos, sin búsqueda y filtros el sistema sería inutilizable; la cotización pide *búsqueda y filtrado por serial, país, fecha y estado*. Es la vista de trabajo para consultar y navegar.

**Pantallas / componentes:**
- Tabla paginada con: serial, país, laboratorio, tipo, estado, fecha, acciones.
- **Filtros:** por serial, país, laboratorio, tipo, estado (activo/descartado), rango de fechas, texto libre.
- Acciones por fila: ver ficha, imprimir/reimprimir.
- **Descarte masivo** (bandera `ENABLE_BULK_DISCARD`): casillas de selección sobre el resultado filtrado. Está aquí, y no en Equipos, porque acotar el grupo a descartar necesita justo estos filtros.
- (Opcional) Exportar la vista actual.

> ⚠️ Esta es la **única** pantalla de búsqueda. Equipos (módulo 5) es la ficha de un equipo a la vez; si vuelve a crecer una tabla con filtros allí, las dos pantallas se vuelven indistinguibles (ya pasó una vez).

**Endpoints:** `GET /equipment-tags` (con todos los filtros) · `GET /equipment-tags/by-serial/{serial}`.

**Rol:** todos.

---

## 5. Equipos — Ficha y Ciclo de Vida

**🎯 Para qué / Por qué:** Muestra **toda la información de un equipo** y permite operar su ciclo de vida (ingreso → descarte) con **trazabilidad completa**. **Por qué módulo dedicado:** la cotización exige *historial de cambios por equipo*; aquí se ve la línea de tiempo completa y se ejecutan las acciones de estado.

**Pantallas / componentes:**
- **Ficha del equipo:** serial, país, laboratorio, tipo, estado, motivo, quién lo creó y cuándo.
- **Línea de tiempo / historial:** creado → ingreso → descarte (cada evento con usuario y fecha).
- Acciones: **Registrar ingreso** (inbound), **Descartar** (con motivo), **Editar** (tipo/motivo/notas), **Reimprimir**.
- **Escáner de código de barras/QR** para abrir la ficha escaneando la etiqueta física.
- Atajo con los **últimos equipos registrados** (sin filtros) para abrir una ficha sin escanear, y enlace a Lista de Seriales para buscar.

**Endpoints:** `GET /equipment-tags/{id}` · `GET /equipment-tags/by-serial/{serial}` · `GET /equipment-tags/{id}/history` · `POST /equipment-tags/{id}/inbound` · `POST /equipment-tags/{id}/discard` · `PATCH /equipment-tags/{id}` · `POST /equipment-tags/{id}/reprint`.

**Rol:** 👤 Operador (y admin).

---

## 6. Descartados

**🎯 Para qué / Por qué:** Vista filtrada de los equipos **dados de baja**, con su motivo. **Por qué separada:** facilita auditar las bajas (¿qué se descartó y por qué?) sin tener que filtrar manualmente cada vez; aparece como sección propia en el mockup. Es trazabilidad de salida.

**Pantallas / componentes:**
- Tabla de equipos `discarded` con motivo (dañado/ilegible/obsoleto/otro), fecha y operador.
- Filtros por motivo, país, rango de fechas.

**Endpoints:** `GET /equipment-tags?status=discarded` (+ filtros).

**Rol:** todos.

---

## 7. Impresión de Etiquetas (módulo transversal + historial)

**🎯 Para qué / Por qué:** Convierte el serial en una **etiqueta física**. **Por qué es crítico y transversal:** la impresión se invoca desde Generar Serial y desde la ficha (reimpresión); debe permitir **elegir el tamaño** (paramétrico), **previsualizar antes de imprimir** y funcionar **offline** si la impresora está conectada localmente. Usa **Zebra Browser Print** en el navegador para enviar el ZPL a la impresora térmica.

**Pantallas / componentes:**
- **Vista previa** de la etiqueta (renderizada) con serial, código de barras/QR, país y fecha.
- Selector de **tamaño de etiqueta** (50×25mm, 100×50mm…), **copias** y **oscurecimiento** (darkness 1–30).
- Selector de **impresora** (vía Zebra Browser Print) e indicador "etiqueta lista para imprimir".
- **Historial de Impresiones:** tabla de `print_jobs` (original/reimpresión, quién, cuándo).

**Endpoints:** `GET /label-sizes` · `POST /labels/preview` · `POST /labels/print` · `POST /equipment-tags/{id}/reprint` · `GET /print-jobs`.

**Integración cliente:** **Zebra Browser Print SDK** (envía el ZPL devuelto por el backend a la impresora). El backend genera el ZPL; el navegador lo imprime.

**Rol:** 👤 Operador (y admin).

---

## 8. Usuarios y Roles  🛡️

**🎯 Para qué / Por qué:** Permite al administrador **gestionar quién entra y con qué permisos**. **Por qué:** la cotización define roles Administrador/Operador; el admin debe poder crear operadores, asignar rol y desactivar accesos. **Importante para el caso multi-sistema:** cuando el cliente conecta su propio IdP, esta pantalla pasa a **mapear roles** (qué grupo/claim externo = admin/operador) más que a crear contraseñas.

**Pantallas / componentes:**
- Tabla de usuarios (estado, rol, proveedor de origen: local/oidc/ldap/api).
- Alta/edición de usuario (modo local) o mapeo de rol (modo externo).
- Activar/desactivar usuario.

**Endpoints:** `GET /users` · `POST /users` · `GET /users/{id}` · `PATCH /users/{id}` · `DELETE /users/{id}` · `GET /roles`.

**Rol:** 🛡️ solo Administrador.

---

## 9. Configuración (catálogos)  🛡️

**🎯 Para qué / Por qué:** Centraliza todo lo **parametrizable** para que el sistema se adapte al cliente **sin reprogramar**. **Por qué:** el negocio cambia (nuevos países, laboratorios, modelos de equipo, tamaños de etiqueta, formato del serial); el admin debe poder ajustarlo desde la interfaz. Es lo que hace al sistema *modular y multi-país*.

**Pantallas / componentes (sub-secciones):**
- **Países:** alta/edición (código, nombre, prefijo).
- **Laboratorios:** por país (código, nombre).
- **Tipos de equipo:** catálogo Data/Video (modelos).
- **Tamaños de etiqueta:** mm, dpi, plantilla ZPL, tipo de código (Code128/QR).
- **Formato del serial:** plantilla por país/laboratorio (resuelve País+Lab+Consecutivo vs ejemplos).

**Endpoints:** `GET/POST/PATCH /countries` · `GET/POST/PATCH /laboratories` · `GET/POST/PATCH /equipment-types` · `GET/POST /label-sizes` · `GET/POST /serial-formats`.

**Rol:** 🛡️ solo Administrador.

---

## 10. Auditoría  🛡️

**🎯 Para qué / Por qué:** Da respuesta a **"¿quién hizo qué y cuándo?"**. **Por qué:** la cotización pide *registro de auditoría*; ante cualquier duda (un serial generado de más, una baja indebida) el admin consulta la bitácora. Da confianza y control.

**Pantallas / componentes:**
- Tabla de eventos (login, generación de serial, descarte, cambios de catálogo) con actor, acción, entidad, fecha, IP.
- Filtros por actor, acción y rango de fechas.

**Endpoints:** `GET /audit-logs`.

**Rol:** 🛡️ solo Administrador.

---

## 11. Módulos técnicos transversales (no son pantallas, pero son obligatorios)

Estos módulos **no se ven** como una pantalla, pero sin ellos la interfaz **no cubre el 100%** del backend.

### 11.1 Motor Offline / Sincronización (PWA) — el más importante
**🎯 Para qué / Por qué:** El sistema debe trabajar **sin internet** y sincronizar al reconectar (tipo Outlook). **Por qué:** es un requisito central de la cotización y el operador puede estar en bodegas sin señal. Sin este módulo, Generar/Descartar/Imprimir no funcionarían offline.
- **IndexedDB:** guarda localmente equipos, catálogos y operaciones pendientes.
- **Service Worker:** cachea la app para que cargue sin conexión.
- **Cola de operaciones** con `client_op_id` (idempotencia) que se envía al reconectar.
- **Indicador de estado** Online/Offline y "pendientes por sincronizar".
- **Resolución de conflictos** mostrada al usuario cuando el backend reporta `conflict/rejected`.
- **Endpoints:** `GET /sync/pull?since=` · `POST /sync/push` · `GET /sync/status`.

### 11.2 Integración de Impresión (Zebra Browser Print)
**🎯 Para qué / Por qué:** Es el puente entre el navegador y la impresora térmica. **Por qué:** el backend genera ZPL pero no habla con la impresora; el SDK de Zebra en el cliente envía ese ZPL al hardware, incluso offline.

### 11.3 Escáner de códigos (cámara / lector)
**🎯 Para qué / Por qué:** Permite el flujo de **ingreso y descarte por escaneo** que pide la cotización ("operador escanea la etiqueta"). **Por qué:** teclear seriales es lento y propenso a error; escanear abre la ficha al instante.
- Soporta lector USB (actúa como teclado) y cámara (QR/Code128) en la PWA.

### 11.4 Control de acceso por rol (UI)
**🎯 Para qué / Por qué:** Oculta/deshabilita en la interfaz lo que un rol no puede hacer (p. ej. el operador no ve Usuarios ni Configuración). **Por qué:** refuerza la seguridad del backend en la capa visual y evita confusión. El backend ya valida; la UI lo refleja.

### 11.5 Internacionalización / multi-país (UX)
**🎯 Para qué / Por qué:** Formatos de fecha, idioma y selección de país coherentes en una operación multi-país. **Por qué:** la cotización es multi-país desde el día uno.

---

## 12. Cobertura: cada endpoint tiene su módulo (verificación 100%)

| Endpoint backend | Módulo de la interfaz |
|------------------|-----------------------|
| `POST /auth/login`, `/refresh`, `/logout`, `GET /auth/me` | 1. Sesión y Autenticación |
| `GET /meta/config`, `/health` | 1 / 2 (config y estado) |
| `GET /equipment-tags` (métricas) | 2. Dashboard |
| `POST /equipment-tags` | 3. Generar Serial |
| `GET /equipment-tags` (filtros), `by-serial` | 4. Lista de Seriales |
| `GET /{id}`, `/history`, `inbound`, `discard`, `PATCH` | 5. Equipos (ficha) |
| `GET /equipment-tags?status=discarded` | 6. Descartados |
| `GET /label-sizes`, `labels/preview`, `labels/print`, `reprint`, `print-jobs` | 7. Impresión |
| `GET/POST/PATCH /users`, `/roles` | 8. Usuarios y Roles |
| `countries`, `laboratories`, `equipment-types`, `label-sizes`, `serial-formats` | 9. Configuración |
| `GET /audit-logs` | 10. Auditoría |
| `sync/pull`, `sync/push`, `sync/status` | 11.1 Motor Offline |

> Si un endpoint del backend no aparece arriba, falta una pantalla. Esta tabla es el checklist para garantizar que la interfaz aprovecha el backend **al 100%**.

---

