# Despliegue en CapRover — Serial Manager (Backend)

Guía paso a paso para desplegar el backend en **CapRover**. El repo ya incluye `Dockerfile`, `captain-definition`, `docker/entrypoint.sh` (corre migraciones al arrancar) y `.dockerignore`.

## 1. Requisitos
- Servidor con CapRover instalado y la CLI: `npm i -g caprover`.
- Acceso al panel de CapRover (`https://captain.tu-dominio.com`).

## 2. Provisionar MySQL en CapRover
1. Panel → **Apps** → **One-Click Apps/Databases** → **MySQL** (8.x).
2. Define contraseña root y **habilita volumen persistente** (los datos sobreviven a redeploys).
3. Anota el host interno: `srv-captain--<nombre-app-mysql>`, puerto `3306`, usuario, contraseña y base.
4. (Opcional) crea base/usuario dedicados para la app.

## 3. Crear la app del backend
1. Panel → **Apps** → **Create New App** → nombre `serial-manager-api`. (Sin "Has Persistent Data" salvo que guardes archivos en disco.)
2. Pestaña **App Configs** → **Environmental Variables**:

   | Variable | Valor |
   |----------|-------|
   | `DATABASE_URL` | `mysql+pymysql://USER:PASS@srv-captain--mysql:3306/serial_manager` |
   | `APP_ENV` | `production` |
   | `AUTH_PROVIDER` | `local` (o `oidc`/`ldap`/`external_api`) |
   | `JWT_SECRET` | cadena larga y aleatoria (≥32 bytes) |
   | `JWT_EXPIRES_MIN` | `60` |
   | `CORS_ORIGINS` | dominio del frontend |
   | `RUN_SEEDS` | `1` (solo el primer despliegue, luego ponlo en `0`) |
   | `ADMIN_USERNAME` / `ADMIN_PASSWORD` | credenciales del admin inicial |
   | `WEB_CONCURRENCY` | `2` |

   > Si usas OIDC/LDAP/API externa, añade las variables del bloque correspondiente (ver `AUTENTICACION_CONECTABLE.md`).
3. **Container HTTP Port**: `8080` (lo expone el Dockerfile).

## 4. Desplegar
Desde la raíz del repo:
```bash
caprover login                 # una vez
caprover deploy                # selecciona el server y la app serial-manager-api
```
Alternativas: subir un tarball desde el panel, o conectar el repositorio Git (deploy automático por webhook/rama).

El `entrypoint.sh` ejecuta `alembic upgrade head` en cada arranque; con `RUN_SEEDS=1` además siembra roles, admin y catálogos (idempotente).

## 5. HTTPS y dominio
1. Pestaña **HTTP Settings** → asigna dominio o subdominio de CapRover.
2. **Enable HTTPS** (Let's Encrypt automático) y **Force HTTPS**.

## 6. Verificación post-deploy
```bash
curl https://serial-manager-api.tu-dominio.com/health        # {"status":"ok"}
curl https://serial-manager-api.tu-dominio.com/health/db     # {"database":"up"}
```
- Swagger: `https://serial-manager-api.tu-dominio.com/docs`
- Login del admin con las credenciales sembradas → `POST /api/v1/auth/login`.
- Tras confirmar los seeds, cambia `RUN_SEEDS=0` y redeploy (evita re-ejecutar el seed en cada arranque).

## 7. Operación
- **Logs:** pestaña de la app en el panel.
- **Escalado:** Instance Count / límites de recursos en App Configs.
- **Backups MySQL:** programar volcado del volumen (cron + `mysqldump`) y guardar fuera del servidor.
- **Rollback:** CapRover conserva versiones anteriores de la imagen para revertir.

## 8. Cambiar de proveedor de identidad en producción
Editar variables de entorno (`AUTH_PROVIDER` + bloque del proveedor) y redeploy. **No requiere cambios de código** — ver `AUTENTICACION_CONECTABLE.md`.
