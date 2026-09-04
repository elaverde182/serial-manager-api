# Arquitectura del Frontend — Vue 3 + Vite + PWA + Tauri

Un solo código Vue que se entrega de **dos formas**: como **PWA web** (servida en CapRover) y como **app instalable** (`.exe`/`.msi`) empaquetada con **Tauri**.

```
                Código Vue 3 (único)
                        │
              npm run build → dist/ (estáticos)
                        │
        ┌───────────────┴────────────────┐
        ▼                                 ▼
   WEB / PWA                           TAURI
 dist/ servido en CapRover     npm run tauri build →
 (navegador, instalable PWA)   instalador .exe/.msi/.dmg/.AppImage
```

## 1. Stack
- **Vue 3** (`<script setup>` + TypeScript) + **Vite 5**.
- **Vue Router** (navegación) + **Pinia** (estado: sesión, cola offline).
- **vite-plugin-pwa** (Service Worker + manifest → offline e instalable).
- **Tauri 2** (envoltura nativa ligera; usa el WebView del sistema).
- Estilos: CSS propio (sin dependencias pesadas) siguiendo el mockup de la cotización.

## 2. Por qué un solo código sirve para web e instalable
Vue compila a HTML/CSS/JS estáticos. Esos mismos archivos:
- **Web:** se suben a CapRover/Nginx → PWA instalable desde el navegador.
- **Tauri:** se empaquetan en un binario que abre una ventana con el WebView del sistema (WebView2 en Windows). Instalador de ~3–10 MB.

## 3. Capa de abstracción por entorno (clave)
Igual que el backend abstrae la identidad, el frontend abstrae lo que cambia entre web y nativo:

```
src/services/
├── runtime.ts      → isTauri(): ¿corremos dentro de Tauri o en navegador?
└── print.ts        → printLabel(zpl): elige implementación
       ├── web   → Zebra Browser Print / WebUSB
       └── tauri → impresión nativa (USB/serial/TCP, vía comando Rust)
```
El resto de la app **no sabe** en qué entorno corre. Se decide en un solo punto.

## 4. Conexión con el backend
- Cliente HTTP central (`src/api/client.ts`) que adjunta el **JWT** y renueva token.
- Base de la API por variable de entorno `VITE_API_BASE`:
  - **Dev:** vacío → usa el **proxy de Vite** (`/api` → `http://localhost:8080`), evita CORS.
  - **Web prod:** URL del backend en CapRover.
  - **Tauri:** URL completa del backend.
- El backend ya tiene `CORS_ORIGINS` configurable (añadir el origen de Tauri `tauri://localhost` cuando se empaquete).

## 5. Offline tipo Outlook
- **Service Worker** (vite-plugin-pwa) cachea la app → carga sin conexión.
- **IndexedDB** guarda equipos, catálogos y una **cola de operaciones** pendientes.
- Al reconectar, la cola se envía a `POST /api/v1/sync/push` (idempotente por `client_op_id`) y se trae el delta con `GET /api/v1/sync/pull`. El backend **ya implementa ambos**.
- Indicador permanente Online/Offline + "pendientes por sincronizar".

## 6. Estructura del proyecto
```
frontend/
├── index.html
├── vite.config.ts          # plugin Vue + PWA + proxy a la API
├── package.json            # scripts: dev, build, preview, tauri
├── .env.example            # VITE_API_BASE
├── src/
│   ├── main.ts             # arranque Vue + router + pinia
│   ├── App.vue
│   ├── router/             # rutas y guard de autenticación
│   ├── stores/auth.ts      # sesión (token, usuario, login/logout)
│   ├── api/                # client.ts + auth.ts + serials.ts + catalogs.ts
│   ├── services/           # runtime.ts (isTauri) + print.ts (web/nativo)
│   ├── views/              # Login, AppLayout (sidebar), Dashboard, GenerarSerial…
│   └── components/
└── src-tauri/              # configuración y binario Tauri (Rust)
```

## 7. Cómo se despliega cada salida
| Salida | Comando | Resultado |
|--------|---------|-----------|
| **Web / PWA** | `npm run build` → subir `dist/` | App web instalable en CapRover |
| **Instalable Windows** | `npm run tauri build` | `.exe` / `.msi` en `src-tauri/target/release/bundle/` |
| **Desarrollo web** | `npm run dev` | http://localhost:5173 (proxy a la API) |
| **Desarrollo nativo** | `npm run tauri dev` | Ventana nativa con hot-reload |

## 8. Mapa de pantallas → endpoints
La interfaz cubre el backend al 100% (ver [`INTERFAZ_MODULOS.md`](INTERFAZ_MODULOS.md)). Orden de construcción sugerido:
1. **Login** → `POST /auth/login` ✅ (incluido en este scaffold)
2. **Dashboard** (métricas) → `GET /equipment-tags` ✅
3. **Generar Serial** → `POST /equipment-tags` + catálogos ✅
4. Lista de Seriales, Equipos (ficha/ciclo de vida), Impresión, Descartados, Usuarios, Configuración, Auditoría.

> Este scaffold entrega los puntos 1–3 funcionando contra el backend; el resto sigue el mismo patrón.
