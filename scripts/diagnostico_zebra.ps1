<#
.SYNOPSIS
  Diagnostico de impresion ZPL en impresoras Zebra (GK420t y similares).

.DESCRIPTION
  Envia datos CRUDOS (RAW) al spooler de Windows exactamente por el mismo camino
  que usa el app de escritorio (OpenPrinter / StartDocPrinter datatype "RAW" /
  WritePrinter). Sirve para aislar si el problema esta en la app, en el driver,
  en la cola de impresion o en la impresora.

  Ejecutar en la PC que TIENE la impresora conectada.

.EXAMPLE
  # 1) Ver que impresoras hay, su estado, puerto, driver y trabajos atascados
  .\diagnostico_zebra.ps1 -Listar

.EXAMPLE
  # 2) Prueba minima de ZPL (debe salir una etiqueta que diga "PRUEBA ZPL")
  .\diagnostico_zebra.ps1 -Impresora "ZDesigner GK420t" -Prueba

.EXAMPLE
  # 3) Etiqueta de configuracion de la impresora (dice en que lenguaje esta)
  .\diagnostico_zebra.ps1 -Impresora "ZDesigner GK420t" -Config

.EXAMPLE
  # 4) Forzar la impresora a modo ZPL (si quedo en EPL)
  .\diagnostico_zebra.ps1 -Impresora "ZDesigner GK420t" -ForzarZpl

.EXAMPLE
  # 5) Enviar el .zpl que descargo la app (fallback) tal cual
  .\diagnostico_zebra.ps1 -Impresora "ZDesigner GK420t" -Archivo "$HOME\Downloads\etiqueta.zpl"
#>
[CmdletBinding(DefaultParameterSetName = 'Listar')]
param(
    [Parameter(ParameterSetName = 'Listar')]
    [switch]$Listar,

    [Parameter(Mandatory, ParameterSetName = 'Prueba')]
    [Parameter(Mandatory, ParameterSetName = 'Config')]
    [Parameter(Mandatory, ParameterSetName = 'ForzarZpl')]
    [Parameter(Mandatory, ParameterSetName = 'Archivo')]
    [string]$Impresora,

    [Parameter(Mandatory, ParameterSetName = 'Prueba')]
    [switch]$Prueba,

    [Parameter(Mandatory, ParameterSetName = 'Config')]
    [switch]$Config,

    [Parameter(Mandatory, ParameterSetName = 'ForzarZpl')]
    [switch]$ForzarZpl,

    [Parameter(Mandatory, ParameterSetName = 'Archivo')]
    [string]$Archivo
)

$ErrorActionPreference = 'Stop'

# --------------------------------------------------------------------------
# Envio RAW por el spooler (mismo camino que printer.rs::print_raw en el app)
# --------------------------------------------------------------------------
$rawHelper = @'
using System;
using System.IO;
using System.Runtime.InteropServices;

public class RawPrinter
{
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public class DOCINFOW
    {
        [MarshalAs(UnmanagedType.LPWStr)] public string pDocName;
        [MarshalAs(UnmanagedType.LPWStr)] public string pOutputFile;
        [MarshalAs(UnmanagedType.LPWStr)] public string pDataType;
    }

    [DllImport("winspool.drv", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern bool OpenPrinter(string src, out IntPtr hPrinter, IntPtr pd);
    [DllImport("winspool.drv", SetLastError = true)]
    public static extern bool ClosePrinter(IntPtr hPrinter);
    [DllImport("winspool.drv", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern bool StartDocPrinter(IntPtr hPrinter, int level, [In, MarshalAs(UnmanagedType.LPStruct)] DOCINFOW di);
    [DllImport("winspool.drv", SetLastError = true)]
    public static extern bool EndDocPrinter(IntPtr hPrinter);
    [DllImport("winspool.drv", SetLastError = true)]
    public static extern bool StartPagePrinter(IntPtr hPrinter);
    [DllImport("winspool.drv", SetLastError = true)]
    public static extern bool EndPagePrinter(IntPtr hPrinter);
    [DllImport("winspool.drv", SetLastError = true)]
    public static extern bool WritePrinter(IntPtr hPrinter, IntPtr pBytes, int dwCount, out int dwWritten);

    // Devuelve null si todo bien, o el mensaje de error.
    public static string Send(string printerName, byte[] bytes, string docName)
    {
        IntPtr hPrinter;
        if (!OpenPrinter(printerName, out hPrinter, IntPtr.Zero))
            return "OpenPrinter fallo (codigo " + Marshal.GetLastWin32Error() + "). Nombre de impresora incorrecto o sin permisos.";

        try
        {
            DOCINFOW di = new DOCINFOW();
            di.pDocName = docName;
            di.pDataType = "RAW";

            if (!StartDocPrinter(hPrinter, 1, di))
                return "StartDocPrinter fallo (codigo " + Marshal.GetLastWin32Error() + "). El driver puede no aceptar datatype RAW.";

            if (!StartPagePrinter(hPrinter))
            {
                EndDocPrinter(hPrinter);
                return "StartPagePrinter fallo (codigo " + Marshal.GetLastWin32Error() + ").";
            }

            IntPtr buf = Marshal.AllocCoTaskMem(bytes.Length);
            try
            {
                Marshal.Copy(bytes, 0, buf, bytes.Length);
                int written;
                bool ok = WritePrinter(hPrinter, buf, bytes.Length, out written);
                EndPagePrinter(hPrinter);
                EndDocPrinter(hPrinter);
                if (!ok) return "WritePrinter fallo (codigo " + Marshal.GetLastWin32Error() + ").";
                if (written != bytes.Length) return "Solo se escribieron " + written + " de " + bytes.Length + " bytes.";
                return null;
            }
            finally { Marshal.FreeCoTaskMem(buf); }
        }
        finally { ClosePrinter(hPrinter); }
    }
}
'@

function Initialize-RawPrinter {
    if (-not ('RawPrinter' -as [type])) {
        Add-Type -TypeDefinition $rawHelper -Language CSharp
    }
}

function Send-Raw {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Data,
        [string]$DocName = 'Diagnostico Zebra'
    )
    Initialize-RawPrinter
    # ZPL/EPL son ASCII: mandamos los bytes tal cual, sin BOM ni reencodings.
    $bytes = [System.Text.Encoding]::ASCII.GetBytes($Data)
    Write-Host "  -> Enviando $($bytes.Length) bytes RAW a '$Name'..." -ForegroundColor DarkGray
    $err = [RawPrinter]::Send($Name, $bytes, $DocName)
    if ($err) {
        Write-Host "  X FALLO: $err" -ForegroundColor Red
        return $false
    }
    Write-Host "  OK: el spooler acepto los datos." -ForegroundColor Green
    Write-Host "     Si NO sale nada por la impresora, el problema esta despues del spooler" -ForegroundColor Yellow
    Write-Host "     (cable/puerto, impresora en pausa u offline, o modo EPL en vez de ZPL)." -ForegroundColor Yellow
    return $true
}

function Show-Printers {
    Write-Host ''
    Write-Host '=== IMPRESORAS INSTALADAS ===' -ForegroundColor Cyan
    $printers = Get-Printer | Sort-Object Name
    foreach ($p in $printers) {
        $esZebra = $p.Name -match 'zebra|zdesigner|gk420|gx420|zd\d|zt\d' -or $p.DriverName -match 'zebra|zdesigner'
        $color = if ($esZebra) { 'Green' } else { 'Gray' }
        Write-Host ''
        Write-Host ("  {0}" -f $p.Name) -ForegroundColor $color
        Write-Host ("     Driver     : {0}" -f $p.DriverName)
        Write-Host ("     Puerto     : {0}" -f $p.PortName)
        Write-Host ("     Estado     : {0}" -f $p.PrinterStatus)
        Write-Host ("     Compartida : {0}" -f $p.Shared)
        if ($esZebra -and $p.DriverName -match 'EPL') {
            Write-Host '     !! El driver dice EPL: ese driver NO habla ZPL.' -ForegroundColor Red
        }
    }

    Write-Host ''
    Write-Host '=== TRABAJOS EN COLA ===' -ForegroundColor Cyan
    $hayJobs = $false
    foreach ($p in $printers) {
        $jobs = @(Get-PrintJob -PrinterName $p.Name -ErrorAction SilentlyContinue)
        if ($jobs.Count -gt 0) {
            $hayJobs = $true
            Write-Host ''
            Write-Host ("  {0}: {1} trabajo(s)" -f $p.Name, $jobs.Count) -ForegroundColor Yellow
            $jobs | ForEach-Object {
                Write-Host ("     #{0} '{1}' - {2} - {3}" -f $_.Id, $_.DocumentName, $_.JobStatus, $_.SubmittedTime)
            }
            Write-Host '     Trabajos encolados = el spooler recibio pero la impresora no consume.' -ForegroundColor Yellow
            Write-Host '     Revisar: cable/puerto, impresora encendida y en linea, sin pausa.' -ForegroundColor Yellow
        }
    }
    if (-not $hayJobs) { Write-Host '  (cola vacia en todas las impresoras)' -ForegroundColor Gray }

    Write-Host ''
    Write-Host '=== SERVICIO ZEBRA BROWSER PRINT (solo hace falta en modo web) ===' -ForegroundColor Cyan
    $svc = Get-Service -Name '*BrowserPrint*' -ErrorAction SilentlyContinue
    if ($svc) {
        $svc | ForEach-Object { Write-Host ("  {0} : {1}" -f $_.Name, $_.Status) }
    } else {
        Write-Host '  No hay servicio Browser Print instalado.' -ForegroundColor Yellow
    }
    foreach ($port in 9100, 9101) {
        $t = Test-NetConnection -ComputerName '127.0.0.1' -Port $port -InformationLevel Quiet -WarningAction SilentlyContinue
        $txt = if ($t) { 'ABIERTO' } else { 'cerrado' }
        $col = if ($t) { 'Green' } else { 'Yellow' }
        Write-Host ("  127.0.0.1:{0} -> {1}" -f $port, $txt) -ForegroundColor $col
    }
    Write-Host ''
    Write-Host 'Siguiente paso:' -ForegroundColor Cyan
    Write-Host '  .\diagnostico_zebra.ps1 -Impresora "<nombre exacto de arriba>" -Config'
    Write-Host ''
}

switch ($PSCmdlet.ParameterSetName) {

    'Listar' { Show-Printers }

    'Config' {
        # ~WC = imprimir etiqueta de configuracion (ZPL).
        # UQ  = imprimir etiqueta de configuracion (EPL2).
        # Mandamos las dos: la que salga indica en que lenguaje esta la impresora.
        Write-Host ''
        Write-Host '1/2 Pidiendo etiqueta de configuracion en ZPL (~WC)...' -ForegroundColor Cyan
        [void](Send-Raw -Name $Impresora -Data "~WC" -DocName 'Config ZPL')
        Start-Sleep -Milliseconds 1500
        Write-Host ''
        Write-Host '2/2 Pidiendo etiqueta de configuracion en EPL (UQ)...' -ForegroundColor Cyan
        [void](Send-Raw -Name $Impresora -Data "`r`nUQ`r`n" -DocName 'Config EPL')
        Write-Host ''
        Write-Host 'LECTURA DEL RESULTADO:' -ForegroundColor Cyan
        Write-Host '  - Salio la etiqueta del paso 1 (larga, con "ZPL II" y valores ^JU) -> la impresora habla ZPL. El problema esta en el ZPL o en la app.'
        Write-Host '  - Salio SOLO la del paso 2 -> la impresora esta en modo EPL. Corregir con: -ForzarZpl'
        Write-Host '  - No salio ninguna -> no llega nada a la impresora (puerto/cable/pausa/driver).'
        Write-Host ''
    }

    'ForzarZpl' {
        Write-Host ''
        Write-Host 'Cambiando el lenguaje de la impresora a ZPL...' -ForegroundColor Cyan
        # setvar en modo linea (funciona aunque este en EPL)
        [void](Send-Raw -Name $Impresora -Data "! U1 setvar `"device.languages`" `"zpl`"`r`n" -DocName 'Set ZPL')
        Start-Sleep -Milliseconds 1000
        # y por si ya estaba en ZPL: ^SZ2 + guardar en memoria permanente
        [void](Send-Raw -Name $Impresora -Data "^XA^SZ2^JUS^XZ" -DocName 'Save ZPL mode')
        Write-Host ''
        Write-Host 'Listo. Ahora verifica con:' -ForegroundColor Cyan
        Write-Host ("  .\diagnostico_zebra.ps1 -Impresora `"{0}`" -Prueba" -f $Impresora)
        Write-Host ''
    }

    'Prueba' {
        # ZPL minimo, sin depender de tamano de etiqueta ni calibracion:
        # ^PW/^LL a 4x2 pulgadas a 203 dpi, texto grande y un Code128.
        $zpl = @"
^XA
^CI28
^PW812
^LL406
^LH0,0
^FO40,40^A0N,50,50^FDPRUEBA ZPL^FS
^FO40,110^A0N,30,30^FDGK420t 203dpi^FS
^FO40,160^BY2^BCN,100,Y,N,N^FD1234567890^FS
^PQ1
^XZ
"@
        Write-Host ''
        Write-Host 'Enviando etiqueta de prueba...' -ForegroundColor Cyan
        [void](Send-Raw -Name $Impresora -Data $zpl -DocName 'Prueba ZPL')
        Write-Host ''
        Write-Host 'Si sale la etiqueta -> el camino app->spooler->impresora funciona;' -ForegroundColor Cyan
        Write-Host 'el problema entonces esta en el ZPL que genera el sistema (plantilla/coordenadas).'
        Write-Host 'Si sale en BLANCO -> la GK420t es de transferencia termica: falta el RIBBON,'
        Write-Host 'o hay que ponerla en modo termica directa (^XA^MTD^JUS^XZ) si usa papel termico.'
        Write-Host ''
    }

    'Archivo' {
        if (-not (Test-Path -LiteralPath $Archivo)) {
            throw "No existe el archivo: $Archivo"
        }
        $data = Get-Content -LiteralPath $Archivo -Raw
        Write-Host ''
        Write-Host ("Enviando {0} ..." -f $Archivo) -ForegroundColor Cyan
        Write-Host '--- contenido ---' -ForegroundColor DarkGray
        Write-Host $data -ForegroundColor DarkGray
        Write-Host '--- fin ---' -ForegroundColor DarkGray
        [void](Send-Raw -Name $Impresora -Data $data -DocName 'ZPL de la app')
        Write-Host ''
    }
}
