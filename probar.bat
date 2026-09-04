@echo off
setlocal
cd /d "%~dp0"

echo ===============================================================
echo   Serial Manager - pruebas de etiquetas
echo ===============================================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo ERROR: no se encontro Python en el PATH.
  goto :fin
)

REM --- 1. Suite automatica ---------------------------------------------------
echo [1/3] Pruebas automaticas ^(geometria del ZPL^)...
echo.
python -m pytest tests -q
if errorlevel 1 (
  echo.
  echo   ^>^> FALLARON PRUEBAS. Revisa el detalle de arriba.
  set "HUBO_FALLO=1"
) else (
  echo.
  echo   ^>^> Todas las pruebas pasan.
)
echo.

REM --- 2. Render del tamano en uso -------------------------------------------
if not exist "preview" mkdir "preview"
echo [2/3] Render de la etiqueta 63 x 25 mm...
echo.
python scripts\preview_zpl.py --width 63 --height 25 --out preview\63x25.png
if errorlevel 1 set "HUBO_FALLO=1"
echo.

REM --- 3. Barrido de tamanos --------------------------------------------------
echo [3/3] Comprobando otros tamanos...
echo.
for %%S in ("30 25" "50 25" "63 25" "100 50") do (
  for /f "tokens=1,2" %%a in (%%S) do (
    python scripts\preview_zpl.py --width %%a --height %%b --out preview\%%ax%%b.png >nul 2>&1
    if errorlevel 1 (
      echo   %%a x %%b mm  -^> SE SALE CONTENIDO
      set "HUBO_FALLO=1"
    ) else (
      echo   %%a x %%b mm  -^> ok
    )
  )
)
echo.

echo ===============================================================
if defined HUBO_FALLO (
  echo   HAY PROBLEMAS - revisa el detalle de arriba.
) else (
  echo   TODO CORRECTO.
)
echo ===============================================================
echo.
echo Imagenes generadas en: %CD%
echo.

:fin
pause
