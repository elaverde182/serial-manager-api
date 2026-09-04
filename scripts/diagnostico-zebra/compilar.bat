@echo off
REM Compila DiagnosticoZebra.exe con el compilador de C# que ya trae Windows
REM (.NET Framework 4.x). No hace falta instalar nada.

setlocal
set CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe
if not exist "%CSC%" set CSC=C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe
if not exist "%CSC%" (
  echo No se encontro el compilador de C# de Windows.
  exit /b 1
)

"%CSC%" /nologo /target:exe /platform:anycpu /optimize+ ^
  /out:"%~dp0DiagnosticoZebra.exe" ^
  /reference:System.Management.dll ^
  "%~dp0DiagnosticoZebra.cs"

if errorlevel 1 (
  echo.
  echo FALLO la compilacion.
  exit /b 1
)

echo.
echo Listo: %~dp0DiagnosticoZebra.exe
endlocal
