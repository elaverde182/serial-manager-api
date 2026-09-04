# Despliegue Manual sin Docker — Servidor Linux

Guía completa para instalar y desplegar el backend **Serial Manager** en un servidor Linux sin usar Docker. Esta guía cubre Ubuntu/Debian y CentOS/RHEL.

---

## 📋 Tabla de Contenidos

1. [Requisitos previos](#1-requisitos-previos)
2. [Instalación de dependencias del sistema](#2-instalación-de-dependencias-del-sistema)
3. [Instalación de MySQL](#3-instalación-de-mysql)
4. [Configuración de la base de datos](#4-configuración-de-la-base-de-datos)
5. [Instalación del backend](#5-instalación-del-backend)
6. [Configuración del entorno](#6-configuración-del-entorno)
7. [Migraciones y datos iniciales](#7-migraciones-y-datos-iniciales)
8. [Ejecución manual (pruebas)](#8-ejecución-manual-pruebas)
9. [Despliegue con systemd (producción)](#9-despliegue-con-systemd-producción)
10. [Configuración de Nginx](#10-configuración-de-nginx)
11. [SSL con Let's Encrypt](#11-ssl-con-lets-encrypt)
12. [Mantenimiento y operaciones](#12-mantenimiento-y-operaciones)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Requisitos previos

### Hardware mínimo recomendado:

| Componente | Mínimo | Recomendado |
|------------|--------|-------------|
| CPU | 2 cores | 4 cores |
| RAM | 2 GB | 4 GB |
| Disco | 20 GB | 50 GB |
| Red | 10 Mbps | 100 Mbps |

### Software:

- **Sistema Operativo:** Linux (Ubuntu 20.04+, Debian 11+, CentOS 8+, RHEL 8+)
- **Python:** 3.11 o superior
- **MySQL:** 8.0 o superior
- **Git:** Para clonar el repositorio
- **Acceso root o sudo**

---

## 2. Instalación de dependencias del sistema

### Ubuntu/Debian:

```bash
# Actualizar repositorios
sudo apt update
sudo apt upgrade -y

# Instalar Python 3.11+ y herramientas de desarrollo
sudo apt install -y \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip \
    build-essential \
    libssl-dev \
    libffi-dev \
    git \
    curl \
    nginx

# Verificar versión de Python
python3.11 --version
```

### CentOS/RHEL 8+:

```bash
# Actualizar sistema
sudo dnf update -y

# Instalar Python 3.11+
sudo dnf install -y python3.11 python3.11-devel python3-pip git nginx

# Instalar herramientas de desarrollo
sudo dnf groupinstall -y "Development Tools"

# Verificar versión
python3.11 --version
```

---

## 3. Instalación de MySQL

### Ubuntu/Debian:

```bash
# Instalar MySQL Server
sudo apt install -y mysql-server

# Iniciar y habilitar MySQL
sudo systemctl start mysql
sudo systemctl enable mysql

# Verificar estado
sudo systemctl status mysql
```

### CentOS/RHEL:

```bash
# Instalar MySQL Server
sudo dnf install -y mysql-server

# Iniciar y habilitar MySQL
sudo systemctl start mysqld
sudo systemctl enable mysqld

# Verificar estado
sudo systemctl status mysqld
```

### Configuración inicial segura:

```bash
sudo mysql_secure_installation
```

Responde a las preguntas:
- **VALIDATE PASSWORD COMPONENT:** `y` (sí)
- **Password validation policy:** `2` (STRONG)
- **New password:** `[tu-contraseña-root-segura]`
- **Remove anonymous users:** `y`
- **Disallow root login remotely:** `y`
- **Remove test database:** `y`
- **Reload privilege tables:** `y`

---

## 4. Configuración de la base de datos

### Crear base de datos y usuario:

```bash
# Conectar a MySQL como root
sudo mysql -u root -p
```

Ejecutar los siguientes comandos SQL:

```sql
-- Crear base de datos con codificación UTF-8
CREATE DATABASE serial_manager 
    CHARACTER SET utf8mb4 
    COLLATE utf8mb4_unicode_ci;

-- Crear usuario para la aplicación
CREATE USER 'serial'@'localhost' IDENTIFIED BY 'TuContraseñaSegura2024!';

-- Otorgar todos los permisos
GRANT ALL PRIVILEGES ON serial_manager.* TO 'serial'@'localhost';

-- Aplicar cambios
FLUSH PRIVILEGES;

-- Verificar que se creó
SHOW DATABASES;
SELECT user, host FROM mysql.user WHERE user='serial';

-- Salir
EXIT;
```

### Probar conexión:

```bash
mysql -u serial -p serial_manager
# Ingresa la contraseña
# Si conecta exitosamente, escribe: EXIT;
```

---

## 5. Instalación del backend

### Paso 1: Crear directorio y clonar repositorio

```bash
# Crear directorio para la aplicación
sudo mkdir -p /opt/etiquetas
cd /opt/etiquetas

# Clonar repositorio (ajusta la URL)
sudo git clone https://tu-repositorio.git .

# Cambiar permisos al usuario actual
sudo chown -R $USER:$USER /opt/etiquetas
```

### Paso 2: Crear entorno virtual

```bash
cd /opt/etiquetas

# Crear entorno virtual con Python 3.11
python3.11 -m venv venv

# Activar entorno virtual
source venv/bin/activate

# Deberías ver (venv) al inicio de tu prompt
```

### Paso 3: Actualizar pip

```bash
pip install --upgrade pip setuptools wheel
```

### Paso 4: Instalar dependencias de Python

```bash
# Instalar todas las dependencias
pip install -e .

# Verificar instalación
pip list | grep fastapi
pip list | grep sqlalchemy
pip list | grep alembic
```

**Salida esperada:** Deberías ver las versiones instaladas de fastapi, sqlalchemy, alembic, etc.

---

## 6. Configuración del entorno

### Paso 1: Crear archivo .env

```bash
cd /opt/etiquetas

# Copiar ejemplo
cp .env.example .env

# Editar con nano o vim
nano .env
```

### Paso 2: Configurar variables de producción

Edita `.env` con los siguientes valores:

```bash
# ==================== ENTORNO ====================
APP_ENV=production

# ==================== BASE DE DATOS ====================
DATABASE_URL=mysql+pymysql://serial:TuContraseñaSegura2024!@localhost:3306/serial_manager

# ==================== ADMIN INICIAL ====================
ADMIN_USERNAME=admin
ADMIN_PASSWORD=Admin!Produccion2024$Seguro
ADMIN_FULLNAME=Administrador del Sistema

# ==================== JWT (CAMBIAR EN PRODUCCIÓN) ====================
# Genera un secreto aleatorio largo:
# python3 -c "import secrets; print(secrets.token_urlsafe(32))"
JWT_SECRET=aqui-va-tu-secreto-aleatorio-muy-largo-minimo-32-caracteres
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_MINUTES=10080

# ==================== CORS ====================
# Ajusta a tu dominio real
CORS_ORIGINS=https://tudominio.com,https://www.tudominio.com

# ==================== AUTENTICACIÓN ====================
AUTH_PROVIDER=local
# Opciones: local, oidc, ldap, external_api

# ==================== RATE LIMITING ====================
LOGIN_MAX_ATTEMPTS=20
LOGIN_WINDOW_S=60

# ==================== OIDC (si usas OAuth2/OpenID Connect) ====================
# OIDC_ISSUER=https://tu-proveedor.com
# OIDC_AUDIENCE=tu-client-id
# OIDC_JWKS_URL=https://tu-proveedor.com/.well-known/jwks.json
# OIDC_ROLE_CLAIM=realm_access.roles

# ==================== LDAP (si usas Active Directory) ====================
# LDAP_URL=ldap://tu-servidor-ldap:389
# LDAP_BASE_DN=dc=ejemplo,dc=com
# LDAP_BIND_TEMPLATE=uid={username},ou=users,dc=ejemplo,dc=com
# LDAP_ADMIN_GROUP=cn=admins,ou=groups,dc=ejemplo,dc=com
```

### Paso 3: Generar secreto JWT seguro

```bash
# Ejecuta esto para generar un secreto aleatorio
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Copia el resultado y pégalo en JWT_SECRET en .env
```

### Paso 4: Verificar configuración

```bash
# Verificar que las variables se carguen correctamente
source venv/bin/activate
python3 -c "from app.core.config import settings; print(f'App: {settings.app_name}, Env: {settings.app_env}')"
```

**Salida esperada:** `App: Serial Manager, Env: production`

---

## 7. Migraciones y datos iniciales

### Paso 1: Aplicar migraciones (crear tablas)

```bash
cd /opt/etiquetas
source venv/bin/activate

# Aplicar todas las migraciones
python -m alembic upgrade head
```

**Salida esperada:**
```
INFO  [alembic.runtime.migration] Context impl MySQLImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> abc123, initial migration
INFO  [alembic.runtime.migration] Running upgrade abc123 -> def456, add audit tables
...
```

### Paso 2: Verificar que las tablas se crearon

```bash
mysql -u serial -p serial_manager -e "SHOW TABLES;"
```

**Salida esperada:** Lista de 13 tablas (users, roles, countries, equipment_types, etc.)

### Paso 3: Insertar datos iniciales (seeds)

```bash
python -m app.seeds.run
```

**Salida esperada:**
```
[OK] Seeds aplicados correctamente.
```

### Paso 4: Verificar datos insertados

```bash
# Verificar roles
mysql -u serial -p serial_manager -e "SELECT * FROM roles;"

# Verificar usuario admin
mysql -u serial -p serial_manager -e "SELECT username, full_name FROM users;"

# Verificar países
mysql -u serial -p serial_manager -e "SELECT code, name FROM countries;"

# Contar tipos de equipos
mysql -u serial -p serial_manager -e "SELECT COUNT(*) as total FROM equipment_types;"
```

**Resultado esperado:** 3 roles, 1 usuario (admin), 9 países, 51 tipos de equipos

---

## 8. Ejecución manual (pruebas)

### Paso 1: Iniciar el servidor de desarrollo

```bash
cd /opt/etiquetas
source venv/bin/activate

# Iniciar con uvicorn en modo desarrollo
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

### Paso 2: Probar la API

Desde otro terminal o navegador:

```bash
# Health check
curl http://localhost:8080/health

# Health check de base de datos
curl http://localhost:8080/health/db

# Documentación Swagger
# Abre en navegador: http://tu-servidor:8080/docs
```

### Paso 3: Probar login

```bash
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "Admin!Produccion2024$Seguro"
  }'
```

**Salida esperada:** JSON con `access_token` y `refresh_token`

### Paso 4: Detener servidor

Presiona `Ctrl+C` en la terminal donde está corriendo uvicorn.

---

## 9. Despliegue con systemd (producción)

### Paso 1: Crear usuario del sistema

```bash
# Crear usuario sin shell para mayor seguridad
sudo useradd -r -s /bin/false serialmanager

# Cambiar permisos del directorio
sudo chown -R serialmanager:serialmanager /opt/etiquetas

# El usuario actual debe seguir teniendo acceso para actualizaciones
sudo usermod -a -G serialmanager $USER
```

### Paso 2: Crear servicio systemd

```bash
sudo nano /etc/systemd/system/serial-manager.service
```

Contenido del archivo:

```ini
[Unit]
Description=Serial Manager API - Sistema de Identificación de Equipos
Documentation=https://github.com/tu-repo/serial-manager
After=network.target mysql.service
Wants=mysql.service

[Service]
Type=simple
User=serialmanager
Group=serialmanager
WorkingDirectory=/opt/etiquetas

# Entorno virtual
Environment="PATH=/opt/etiquetas/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="VIRTUAL_ENV=/opt/etiquetas/venv"

# Variables de entorno (opcional, se pueden leer de .env)
EnvironmentFile=/opt/etiquetas/.env

# Comando de ejecución
# Opción A: Uvicorn (más simple)
ExecStart=/opt/etiquetas/venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8080 \
    --workers 4

# Opción B: Gunicorn con workers de Uvicorn (más robusto)
# ExecStart=/opt/etiquetas/venv/bin/gunicorn app.main:app \
#     --workers 4 \
#     --worker-class uvicorn.workers.UvicornWorker \
#     --bind 0.0.0.0:8080 \
#     --timeout 120 \
#     --access-logfile /var/log/serial-manager/access.log \
#     --error-logfile /var/log/serial-manager/error.log

# Reiniciar automáticamente si falla
Restart=always
RestartSec=10

# Límites de recursos
LimitNOFILE=65536

# Seguridad adicional
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

### Paso 3: Crear directorio de logs (si usas Gunicorn)

```bash
sudo mkdir -p /var/log/serial-manager
sudo chown serialmanager:serialmanager /var/log/serial-manager
```

### Paso 4: Instalar Gunicorn (opcional pero recomendado)

```bash
cd /opt/etiquetas
source venv/bin/activate
pip install gunicorn
```

Si usas Gunicorn, descomenta la línea `ExecStart` de Gunicorn en el servicio.

### Paso 5: Habilitar e iniciar el servicio

```bash
# Recargar systemd para reconocer el nuevo servicio
sudo systemctl daemon-reload

# Habilitar inicio automático
sudo systemctl enable serial-manager

# Iniciar el servicio
sudo systemctl start serial-manager

# Verificar estado
sudo systemctl status serial-manager
```

**Salida esperada:**
```
● serial-manager.service - Serial Manager API
   Loaded: loaded (/etc/systemd/system/serial-manager.service; enabled)
   Active: active (running) since ...
```

### Paso 6: Ver logs

```bash
# Ver logs en tiempo real
sudo journalctl -u serial-manager -f

# Ver últimas 100 líneas
sudo journalctl -u serial-manager -n 100

# Ver logs de hoy
sudo journalctl -u serial-manager --since today
```

### Paso 7: Comandos de control

```bash
# Detener servicio
sudo systemctl stop serial-manager

# Reiniciar servicio
sudo systemctl restart serial-manager

# Recargar configuración (sin detener)
sudo systemctl reload serial-manager

# Ver estado
sudo systemctl status serial-manager

# Deshabilitar inicio automático
sudo systemctl disable serial-manager
```

---

## 10. Configuración de Nginx

Nginx actúa como proxy reverso, manejando SSL, compresión, y balanceo de carga.

### Paso 1: Instalar Nginx (si no lo hiciste antes)

```bash
# Ubuntu/Debian
sudo apt install -y nginx

# CentOS/RHEL
sudo dnf install -y nginx

# Iniciar y habilitar
sudo systemctl start nginx
sudo systemctl enable nginx
```

### Paso 2: Crear configuración del sitio

```bash
sudo nano /etc/nginx/sites-available/serial-manager
```

Contenido:

```nginx
# Serial Manager API - Configuración de Nginx

upstream serial_api {
    # Backend de la API
    server 127.0.0.1:8080 fail_timeout=10s max_fails=3;
    keepalive 32;
}

# Redirigir HTTP a HTTPS (después de configurar SSL)
server {
    listen 80;
    listen [::]:80;
    server_name tudominio.com www.tudominio.com;

    # Redirigir todo a HTTPS (descomentar después de configurar SSL)
    # return 301 https://$server_name$request_uri;

    # Temporal: permite HTTP mientras configuras
    location / {
        proxy_pass http://serial_api;
        proxy_http_version 1.1;
        
        # Headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Buffer
        proxy_buffering off;
    }
}

# Servidor HTTPS (descomentar después de configurar SSL)
# server {
#     listen 443 ssl http2;
#     listen [::]:443 ssl http2;
#     server_name tudominio.com www.tudominio.com;
#
#     # Certificados SSL (Let's Encrypt los configurará aquí)
#     ssl_certificate /etc/letsencrypt/live/tudominio.com/fullchain.pem;
#     ssl_certificate_key /etc/letsencrypt/live/tudominio.com/privkey.pem;
#     ssl_protocols TLSv1.2 TLSv1.3;
#     ssl_ciphers HIGH:!aNULL:!MD5;
#     ssl_prefer_server_ciphers on;
#
#     # Logs
#     access_log /var/log/nginx/serial-manager-access.log;
#     error_log /var/log/nginx/serial-manager-error.log;
#
#     # Compresión
#     gzip on;
#     gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
#
#     location / {
#         proxy_pass http://serial_api;
#         proxy_http_version 1.1;
#         
#         # Headers
#         proxy_set_header Host $host;
#         proxy_set_header X-Real-IP $remote_addr;
#         proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
#         proxy_set_header X-Forwarded-Proto $scheme;
#         proxy_set_header Connection "";
#         
#         # Timeouts
#         proxy_connect_timeout 60s;
#         proxy_send_timeout 60s;
#         proxy_read_timeout 60s;
#         
#         # Buffer
#         proxy_buffering off;
#     }
#
#     # Health checks (opcional)
#     location /health {
#         proxy_pass http://serial_api/health;
#         access_log off;
#     }
# }
```

### Paso 3: Habilitar el sitio

```bash
# Crear enlace simbólico (Ubuntu/Debian)
sudo ln -s /etc/nginx/sites-available/serial-manager /etc/nginx/sites-enabled/

# En CentOS/RHEL, incluir el archivo en nginx.conf:
# Editar /etc/nginx/nginx.conf y agregar:
# include /etc/nginx/sites-available/serial-manager;
```

### Paso 4: Probar configuración

```bash
# Verificar sintaxis
sudo nginx -t

# Si todo está OK:
sudo systemctl restart nginx
```

### Paso 5: Configurar firewall

```bash
# Ubuntu/Debian (ufw)
sudo ufw allow 'Nginx Full'
sudo ufw allow 22/tcp  # SSH
sudo ufw enable

# CentOS/RHEL (firewalld)
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

### Paso 6: Probar acceso

```bash
# Desde el servidor
curl http://localhost/health

# Desde otro equipo
curl http://tudominio.com/health
```

---

## 11. SSL con Let's Encrypt

### Paso 1: Instalar Certbot

```bash
# Ubuntu/Debian
sudo apt install -y certbot python3-certbot-nginx

# CentOS/RHEL
sudo dnf install -y certbot python3-certbot-nginx
```

### Paso 2: Obtener certificado SSL

```bash
# Certbot configurará automáticamente Nginx
sudo certbot --nginx -d tudominio.com -d www.tudominio.com

# Sigue las instrucciones:
# - Email: tu-email@ejemplo.com
# - Términos: A (aceptar)
# - Compartir email: N (no)
# - Redirigir HTTP a HTTPS: 2 (sí, recomendado)
```

### Paso 3: Verificar renovación automática

```bash
# Certbot instala un timer de systemd para renovar automáticamente
sudo systemctl status certbot.timer

# Probar renovación (dry-run)
sudo certbot renew --dry-run
```

### Paso 4: Probar HTTPS

```bash
curl https://tudominio.com/health
```

---

## 12. Mantenimiento y operaciones

### Actualizar el backend

```bash
cd /opt/etiquetas

# Pull de los últimos cambios
git pull origin main

# Activar entorno virtual
source venv/bin/activate

# Actualizar dependencias
pip install -e . --upgrade

# Aplicar nuevas migraciones
python -m alembic upgrade head

# Reiniciar servicio
sudo systemctl restart serial-manager

# Verificar que funcionó
sudo systemctl status serial-manager
curl http://localhost:8080/health
```

### Backup de base de datos

```bash
# Crear directorio de backups
sudo mkdir -p /var/backups/serial-manager

# Backup manual
sudo mysqldump -u serial -p serial_manager > /var/backups/serial-manager/backup-$(date +%Y%m%d-%H%M%S).sql

# Backup automático con cron (diario a las 2am)
sudo crontab -e

# Agregar:
0 2 * * * /usr/bin/mysqldump -u serial -pTuContraseña serial_manager > /var/backups/serial-manager/backup-$(date +\%Y\%m\%d).sql

# Mantener solo los últimos 7 días
0 3 * * * find /var/backups/serial-manager/ -name "backup-*.sql" -mtime +7 -delete
```

### Restaurar backup

```bash
# Restaurar desde backup
mysql -u serial -p serial_manager < /var/backups/serial-manager/backup-20240904.sql
```

### Logs y monitoreo

```bash
# Ver logs de la aplicación
sudo journalctl -u serial-manager -f

# Ver logs de Nginx
sudo tail -f /var/log/nginx/serial-manager-access.log
sudo tail -f /var/log/nginx/serial-manager-error.log

# Ver logs de MySQL
sudo tail -f /var/log/mysql/error.log

# Monitorear uso de recursos
htop  # o: sudo apt install htop

# Ver conexiones activas
ss -tulpn | grep 8080
```

---

## 13. Troubleshooting

### Problema: El servicio no inicia

```bash
# Ver error detallado
sudo journalctl -u serial-manager -n 50 --no-pager

# Verificar permisos
ls -la /opt/etiquetas

# Verificar que el entorno virtual existe
ls -la /opt/etiquetas/venv

# Probar iniciar manualmente
cd /opt/etiquetas
source venv/bin/activate
python -m app.main
```

### Problema: Error de conexión a MySQL

```bash
# Verificar que MySQL está corriendo
sudo systemctl status mysql

# Probar conexión manual
mysql -u serial -p serial_manager

# Verificar DATABASE_URL en .env
cat /opt/etiquetas/.env | grep DATABASE_URL

# Ver logs de MySQL
sudo tail -f /var/log/mysql/error.log
```

### Problema: Nginx retorna 502 Bad Gateway

```bash
# Verificar que el backend está corriendo
sudo systemctl status serial-manager

# Verificar puerto 8080
ss -tulpn | grep 8080

# Ver logs de Nginx
sudo tail -f /var/log/nginx/error.log

# Probar conexión directa al backend
curl http://localhost:8080/health
```

### Problema: Migraciones fallan

```bash
# Ver estado actual de migraciones
cd /opt/etiquetas
source venv/bin/activate
python -m alembic current

# Ver historial
python -m alembic history

# Intentar migración específica
python -m alembic upgrade [revision_id]

# En caso extremo, recrear todo (⚠️ borra datos)
# python -m alembic downgrade base
# python -m alembic upgrade head
```

### Problema: Seeds no insertan datos

```bash
# Verificar APP_ENV
grep APP_ENV /opt/etiquetas/.env

# Ejecutar seeds con output detallado
cd /opt/etiquetas
source venv/bin/activate
python -c "
from app.core.database import SessionLocal
from app.seeds.run import seed
db = SessionLocal()
seed(db)
"
```

### Problema: Error 413 (Request Entity Too Large)

```bash
# Aumentar límite en Nginx
sudo nano /etc/nginx/nginx.conf

# Agregar en sección http {}:
client_max_body_size 20M;

# Reiniciar Nginx
sudo systemctl restart nginx
```

---

## 14. Checklist final de producción

Antes de poner en producción, verifica:

- [ ] `APP_ENV=production` en `.env`
- [ ] `ADMIN_PASSWORD` cambiada a contraseña segura
- [ ] `JWT_SECRET` generado aleatoriamente (32+ caracteres)
- [ ] Base de datos MySQL configurada y corriendo
- [ ] Migraciones aplicadas: `alembic upgrade head`
- [ ] Seeds ejecutados: `python -m app.seeds.run`
- [ ] Servicio systemd habilitado y corriendo
- [ ] Nginx configurado como proxy reverso
- [ ] SSL/HTTPS configurado con Let's Encrypt
- [ ] Firewall configurado (puertos 80, 443 abiertos)
- [ ] Backup automático de BD configurado
- [ ] CORS configurado con dominio correcto
- [ ] Logs siendo monitoreados
- [ ] Health checks funcionando: `/health` y `/health/db`
- [ ] Login funciona con usuario admin
- [ ] Documentación accesible en `/docs`

---

## 15. Comparación Docker vs Manual

| Aspecto | Manual (esta guía) | Docker |
|---------|-------------------|--------|
| **Instalación** | ~30-45 min | ~15 min |
| **Pasos** | 15+ comandos | 1-2 comandos |
| **Recursos (RAM)** | ~500 MB | ~1 GB |
| **Control** | Total | Abstracto |
| **Portabilidad** | Solo Linux | Cualquier SO |
| **Actualizaciones** | Manual | `docker compose pull` |
| **Rollback** | Git + restart | Cambiar imagen |
| **Debugging** | Más fácil (acceso directo) | Requiere `docker exec` |
| **Múltiples instancias** | Difícil | Fácil |
| **Integración systemd** | Nativa | Via Docker |

---

## 16. Soporte y recursos adicionales

- **Documentación del proyecto:** Ver `README.md` principal
- **Documentación técnica:** Carpeta `docs/`
- **Herramientas auxiliares:** Ver `README_ADICIONAL.md`
- **Colección de Postman:** Carpeta `postman/`
- **Logs de la aplicación:** `sudo journalctl -u serial-manager -f`
- **Health checks:** `http://tudominio.com/health`
- **Documentación API:** `http://tudominio.com/docs`

---

*Guía de despliegue manual sin Docker · Serial Manager · Versión 1.0*
