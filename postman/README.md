# Postman — Serial Manager

Colección y entorno para testear el backend.

## Archivos
- `Serial_Manager.postman_collection.json` — 37 requests en 8 carpetas (Health, Auth, Usuarios, Catálogos, Equipos, Impresión, Sync, Auditoría/Meta).
- `Serial_Manager.local.postman_environment.json` — entorno apuntando a `http://localhost:8080`.

## Uso en la app de Postman
1. **Import** → arrastra ambos archivos.
2. Selecciona el entorno **"Serial Manager — Local (Docker)"** (arriba a la derecha).
3. Ejecuta en orden:
   - **Auth → Login** (guarda el token automáticamente).
   - **Catálogos → Crear laboratorio** (guarda `lab_id`).
   - **Equipos → Generar serial** (guarda `tag_id` y `serial_code`).
   - El resto ya usa esas variables.

Los scripts capturan token e IDs solos; no copies/pegues nada. Cada request valida que el backend no devuelva error de servidor (status < 500).

## Uso por línea de comandos (newman)
```bash
npx newman run Serial_Manager.postman_collection.json \
  -e Serial_Manager.local.postman_environment.json
```
O desde la raíz del proyecto: `.\scripts\verify.ps1` (genera reporte HTML).

Resultado esperado: **37 requests · 40 assertions · 0 failed**.
