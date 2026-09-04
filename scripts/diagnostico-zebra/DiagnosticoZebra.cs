// Diagnostico de impresion ZPL en impresoras Zebra (GK420t y similares).
//
// Pensado para que lo ejecute el operador con doble clic: no pide comandos ni
// parametros, detecta la impresora Zebra sola y guia con un menu en espanol.
//
// Envia los datos CRUDOS (RAW) por el mismo camino que el app de escritorio
// (OpenPrinter -> StartDocPrinter datatype "RAW" -> WritePrinter, igual que
// src-tauri/src/printer.rs), asi lo que pase aqui es exactamente lo que le pasa
// a la aplicacion.
//
// Compilar:  compilar.bat   (usa el csc.exe que ya viene con Windows)

using System;
using System.Collections.Generic;
using System.IO;
using System.Management;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Text;

namespace DiagnosticoZebra
{
    // ---------------------------------------------------------------------
    // Envio RAW al spooler de Windows
    // ---------------------------------------------------------------------
    internal static class RawPrinter
    {
        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private class DOCINFOW
        {
            [MarshalAs(UnmanagedType.LPWStr)] public string pDocName;
            [MarshalAs(UnmanagedType.LPWStr)] public string pOutputFile;
            [MarshalAs(UnmanagedType.LPWStr)] public string pDataType;
        }

        [DllImport("winspool.drv", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool OpenPrinter(string src, out IntPtr hPrinter, IntPtr pd);
        [DllImport("winspool.drv", SetLastError = true)]
        private static extern bool ClosePrinter(IntPtr hPrinter);
        [DllImport("winspool.drv", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool StartDocPrinter(IntPtr hPrinter, int level,
            [In, MarshalAs(UnmanagedType.LPStruct)] DOCINFOW di);
        [DllImport("winspool.drv", SetLastError = true)]
        private static extern bool EndDocPrinter(IntPtr hPrinter);
        [DllImport("winspool.drv", SetLastError = true)]
        private static extern bool StartPagePrinter(IntPtr hPrinter);
        [DllImport("winspool.drv", SetLastError = true)]
        private static extern bool EndPagePrinter(IntPtr hPrinter);
        [DllImport("winspool.drv", SetLastError = true)]
        private static extern bool WritePrinter(IntPtr hPrinter, IntPtr pBytes, int dwCount, out int dwWritten);

        /// <summary>Devuelve null si todo salio bien, o el mensaje de error.</summary>
        public static string Send(string printerName, string data, string docName)
        {
            // ZPL y EPL son ASCII: van tal cual, sin BOM ni reencodings.
            byte[] bytes = Encoding.ASCII.GetBytes(data);

            IntPtr hPrinter;
            if (!OpenPrinter(printerName, out hPrinter, IntPtr.Zero))
            {
                return "No se pudo abrir la impresora (codigo " + Marshal.GetLastWin32Error() +
                       "). Revisa que el nombre sea exacto y que tengas permisos.";
            }

            try
            {
                DOCINFOW di = new DOCINFOW();
                di.pDocName = docName;
                di.pDataType = "RAW";

                if (!StartDocPrinter(hPrinter, 1, di))
                {
                    return "El driver rechazo el envio directo RAW (codigo " +
                           Marshal.GetLastWin32Error() + "). Suele pasar con drivers que no son de Zebra.";
                }
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

                    if (!ok) return "No se pudieron enviar los datos (codigo " + Marshal.GetLastWin32Error() + ").";
                    if (written != bytes.Length)
                        return "Solo se enviaron " + written + " de " + bytes.Length + " bytes.";
                    return null;
                }
                finally { Marshal.FreeCoTaskMem(buf); }
            }
            finally { ClosePrinter(hPrinter); }
        }
    }

    // ---------------------------------------------------------------------
    // Datos del sistema que el operador no sabria describir por telefono
    // ---------------------------------------------------------------------
    internal static class Sistema
    {
        [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
        private static extern int SHGetKnownFolderPath(
            [MarshalAs(UnmanagedType.LPStruct)] Guid rfid, uint flags, IntPtr token, out IntPtr path);

        private static readonly Guid FOLDERID_Downloads =
            new Guid("374DE290-123F-4565-9164-39C4925E467B");

        /// <summary>Carpeta Descargas real (respeta redireccion de OneDrive).</summary>
        public static string CarpetaDescargas()
        {
            IntPtr p = IntPtr.Zero;
            try
            {
                if (SHGetKnownFolderPath(FOLDERID_Downloads, 0, IntPtr.Zero, out p) == 0)
                    return Marshal.PtrToStringUni(p);
            }
            catch { }
            finally { if (p != IntPtr.Zero) Marshal.FreeCoTaskMem(p); }

            string perfil = Environment.GetEnvironmentVariable("USERPROFILE");
            return string.IsNullOrEmpty(perfil) ? null : Path.Combine(perfil, "Downloads");
        }

        public static string VersionWindows()
        {
            try
            {
                using (var b = new ManagementObjectSearcher(
                    "SELECT Caption, Version, BuildNumber, OSArchitecture FROM Win32_OperatingSystem"))
                {
                    foreach (ManagementObject mo in b.Get())
                    {
                        return Convert.ToString(mo["Caption"]).Trim() +
                               "  (version " + mo["Version"] + ", build " + mo["BuildNumber"] +
                               ", " + mo["OSArchitecture"] + ")";
                    }
                }
            }
            catch { }
            return Environment.OSVersion.ToString();
        }

        public static string EstadoServicio(string nombre)
        {
            try
            {
                using (var b = new ManagementObjectSearcher(
                    "SELECT Name, State, StartMode FROM Win32_Service WHERE Name='" + nombre + "'"))
                {
                    foreach (ManagementObject mo in b.Get())
                        return Convert.ToString(mo["State"]) + " (inicio: " + mo["StartMode"] + ")";
                }
            }
            catch { }
            return "no encontrado";
        }

        /// <summary>Servicios cuyo nombre menciona Browser Print, con su estado.</summary>
        public static List<string> ServiciosBrowserPrint()
        {
            var r = new List<string>();
            try
            {
                using (var b = new ManagementObjectSearcher("SELECT Name, State FROM Win32_Service"))
                {
                    foreach (ManagementObject mo in b.Get())
                    {
                        string n = Convert.ToString(mo["Name"]);
                        if (n != null && n.IndexOf("BrowserPrint", StringComparison.OrdinalIgnoreCase) >= 0)
                            r.Add(n + " -> " + mo["State"]);
                    }
                }
            }
            catch { }
            return r;
        }
    }

    internal class PrinterInfo
    {
        public string Name = "";
        public string Driver = "";
        public string Port = "";
        public bool WorkOffline;
        public bool Default;
        public bool Shared;
        public uint PrinterState;
        public uint PrinterStatus;
        public uint ExtendedPrinterStatus;
        public uint Attributes;
        public int Jobs;
        public readonly List<string> Trabajos = new List<string>();

        public bool EsZebra
        {
            get
            {
                string s = (Name + " " + Driver).ToLowerInvariant();
                return s.Contains("zebra") || s.Contains("zdesigner") || s.Contains("gk420")
                    || s.Contains("gx420") || s.Contains("gc420") || s.Contains("zd4")
                    || s.Contains("zd2") || s.Contains("zt2") || s.Contains("zpl")
                    || s.Contains("epl");
            }
        }

        public bool DriverEsEpl
        {
            get { return Driver.ToUpperInvariant().Contains("EPL"); }
        }

        // PrinterState es un mapa de bits (igual que PRINTER_INFO_2.Status);
        // PrinterStatus, en cambio, es un enumerado: 3 = lista, 4 = imprimiendo,
        // 5 = calentando, 6 = detenida, 7 = sin conexion.
        private const uint PAUSED = 0x00000001;
        private const uint ERROR = 0x00000002;
        private const uint PAPER_JAM = 0x00000008;
        private const uint PAPER_OUT = 0x00000010;
        private const uint OFFLINE = 0x00000080;
        private const uint DOOR_OPEN = 0x00400000;

        public bool Pausada { get { return (PrinterState & PAUSED) != 0; } }
        public bool SinConexion { get { return WorkOffline || (PrinterState & OFFLINE) != 0 || PrinterStatus == 7; } }
        public bool EnError { get { return (PrinterState & (ERROR | PAPER_JAM | PAPER_OUT | DOOR_OPEN)) != 0; } }

        /// <summary>Estado en palabras, para que lo entienda cualquiera.</summary>
        public string EstadoTexto
        {
            get
            {
                if (Pausada) return "EN PAUSA";
                if (SinConexion) return "SIN CONEXION";
                if ((PrinterState & PAPER_OUT) != 0) return "SIN ETIQUETAS (se acabo el rollo)";
                if ((PrinterState & PAPER_JAM) != 0) return "ETIQUETA ATASCADA";
                if ((PrinterState & DOOR_OPEN) != 0) return "TAPA ABIERTA";
                if ((PrinterState & ERROR) != 0) return "EN ERROR";
                switch (PrinterStatus)
                {
                    case 3: return "lista";
                    case 4: return "imprimiendo";
                    case 5: return "calentando";
                    case 6: return "DETENIDA";
                    case 7: return "SIN CONEXION";
                    default: return "desconocido";
                }
            }
        }
    }

    internal static class Program
    {
        private const string Version = "1.1";

        private static readonly StringBuilder Informe = new StringBuilder();
        private static readonly List<string> Problemas = new List<string>();
        private static string _impresora = null;
        private static string _rutaInforme = null;

        // -----------------------------------------------------------------
        // Salida por pantalla + acumulacion para el informe
        // -----------------------------------------------------------------
        private static void W(string texto = "", ConsoleColor? color = null)
        {
            if (color.HasValue) Console.ForegroundColor = color.Value;
            Console.WriteLine(texto);
            Console.ResetColor();
            Informe.AppendLine(texto);
        }

        /// <summary>Solo al informe: detalle tecnico que al operador no le sirve.</summary>
        private static void L(string texto = "")
        {
            Informe.AppendLine(texto);
        }

        private static void Titulo(string texto)
        {
            W();
            W("==================================================", ConsoleColor.Cyan);
            W("  " + texto, ConsoleColor.Cyan);
            W("==================================================", ConsoleColor.Cyan);
            W();
        }

        private static void Pausa()
        {
            Console.WriteLine();
            Console.ForegroundColor = ConsoleColor.DarkGray;
            Console.WriteLine("   (presiona cualquier tecla para volver al menu)");
            Console.ResetColor();
            // ReadKey falla si la consola no es interactiva (entrada redirigida).
            try { Console.ReadKey(true); }
            catch (InvalidOperationException) { Console.ReadLine(); }
        }

        // -----------------------------------------------------------------
        // Consulta de impresoras (WMI)
        // -----------------------------------------------------------------
        private static List<PrinterInfo> LeerImpresoras()
        {
            var lista = new List<PrinterInfo>();
            try
            {
                using (var buscador = new ManagementObjectSearcher("SELECT * FROM Win32_Printer"))
                {
                    foreach (ManagementObject mo in buscador.Get())
                    {
                        var p = new PrinterInfo();
                        p.Name = Convert.ToString(mo["Name"]);
                        p.Driver = Convert.ToString(mo["DriverName"]);
                        p.Port = Convert.ToString(mo["PortName"]);
                        p.WorkOffline = mo["WorkOffline"] != null && Convert.ToBoolean(mo["WorkOffline"]);
                        p.Default = mo["Default"] != null && Convert.ToBoolean(mo["Default"]);
                        p.Shared = mo["Shared"] != null && Convert.ToBoolean(mo["Shared"]);
                        p.PrinterState = mo["PrinterState"] != null ? Convert.ToUInt32(mo["PrinterState"]) : 0;
                        p.PrinterStatus = mo["PrinterStatus"] != null ? Convert.ToUInt32(mo["PrinterStatus"]) : 0;
                        p.ExtendedPrinterStatus = mo["ExtendedPrinterStatus"] != null
                            ? Convert.ToUInt32(mo["ExtendedPrinterStatus"]) : 0;
                        p.Attributes = mo["Attributes"] != null ? Convert.ToUInt32(mo["Attributes"]) : 0;
                        lista.Add(p);
                    }
                }

                // Trabajos en cola por impresora.
                using (var buscador = new ManagementObjectSearcher("SELECT * FROM Win32_PrintJob"))
                {
                    foreach (ManagementObject mo in buscador.Get())
                    {
                        string name = Convert.ToString(mo["Name"]); // "Impresora, 12"
                        foreach (var p in lista)
                        {
                            if (name == null || !name.StartsWith(p.Name + ",", StringComparison.OrdinalIgnoreCase))
                                continue;
                            p.Jobs++;
                            p.Trabajos.Add(
                                "doc='" + mo["Document"] + "'" +
                                " estado='" + mo["JobStatus"] + "'" +
                                " tamano=" + mo["Size"] +
                                " enviado=" + Convert.ToString(mo["TimeSubmitted"]) +
                                " tipo=" + mo["DataType"]);
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                W("  No se pudo consultar el sistema de impresion: " + ex.Message, ConsoleColor.Red);
            }
            return lista;
        }

        private static bool PuertoAbierto(int puerto)
        {
            try
            {
                using (var c = new TcpClient())
                {
                    var ar = c.BeginConnect("127.0.0.1", puerto, null, null);
                    bool ok = ar.AsyncWaitHandle.WaitOne(TimeSpan.FromMilliseconds(700));
                    if (ok) { c.EndConnect(ar); return true; }
                    return false;
                }
            }
            catch { return false; }
        }

        // -----------------------------------------------------------------
        // Recoleccion automatica: corre sola al abrir el programa, sin que el
        // operador haga nada. Es el grueso del informe.
        // -----------------------------------------------------------------
        private static void RecolectarDatosTecnicos()
        {
            L();
            L("===========================================================");
            L(" 1. EQUIPO");
            L("===========================================================");
            L("Fecha y hora   : " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));
            L("Equipo         : " + Environment.MachineName);
            L("Usuario        : " + Environment.UserName);
            L("Windows        : " + Sistema.VersionWindows());
            L("Proceso 64-bit : " + Environment.Is64BitProcess);

            L();
            L("===========================================================");
            L(" 2. SISTEMA DE IMPRESION");
            L("===========================================================");
            L("Servicio de cola de impresion (Spooler): " + Sistema.EstadoServicio("Spooler"));
            L();

            var impresoras = LeerImpresoras();
            L("Impresoras instaladas: " + impresoras.Count);
            foreach (var p in impresoras)
            {
                L();
                L("  [" + (p.EsZebra ? "ZEBRA" : "otra") + "] " + p.Name +
                  (p.Default ? "   (predeterminada de Windows)" : ""));
                L("      DriverName            : " + p.Driver);
                L("      PortName              : " + p.Port);
                L("      Estado                : " + p.EstadoTexto);
                L("      WorkOffline           : " + p.WorkOffline);
                L("      Shared                : " + p.Shared);
                L("      PrinterState  (bits)  : 0x" + p.PrinterState.ToString("X8") + "  (" + p.PrinterState + ")");
                L("      PrinterStatus (enum)  : " + p.PrinterStatus + "   [3=lista 4=imprimiendo 5=calentando 6=detenida 7=sin conexion]");
                L("      ExtendedPrinterStatus : " + p.ExtendedPrinterStatus);
                L("      Attributes            : 0x" + p.Attributes.ToString("X8"));
                L("      Trabajos en cola      : " + p.Jobs);
                foreach (var t in p.Trabajos) L("        - " + t);
            }

            L();
            L("===========================================================");
            L(" 3. ZEBRA BROWSER PRINT  (necesario solo en modo navegador)");
            L("===========================================================");
            var svcs = Sistema.ServiciosBrowserPrint();
            if (svcs.Count == 0) L("Servicios instalados: NINGUNO");
            else foreach (var s in svcs) L("Servicio: " + s);
            L("Puerto 127.0.0.1:9100 (http)  : " + (PuertoAbierto(9100) ? "RESPONDE" : "no responde"));
            L("Puerto 127.0.0.1:9101 (https) : " + (PuertoAbierto(9101) ? "RESPONDE" : "no responde"));

            L();
            L("===========================================================");
            L(" 4. ARCHIVOS .ZPL EN LA CARPETA DESCARGAS");
            L("===========================================================");
            L("(Si aparecen archivos aqui, significa que la aplicacion NO pudo");
            L(" imprimir y cayo en el modo de descarga silenciosa.)");
            L();
            RevisarDescargas();

            // Analisis: se calcula una sola vez y encabeza el informe.
            AnalizarProblemas(impresoras);
        }

        private static void RevisarDescargas()
        {
            try
            {
                string dir = Sistema.CarpetaDescargas();
                if (string.IsNullOrEmpty(dir) || !Directory.Exists(dir))
                {
                    L("No se pudo ubicar la carpeta Descargas.");
                    return;
                }
                L("Carpeta: " + dir);

                var archivos = new List<FileInfo>(new DirectoryInfo(dir).GetFiles("*.zpl"));
                archivos.Sort(delegate (FileInfo a, FileInfo b)
                { return b.LastWriteTime.CompareTo(a.LastWriteTime); });

                if (archivos.Count == 0)
                {
                    L("No hay archivos .zpl descargados.");
                    return;
                }

                L("Encontrados: " + archivos.Count + " archivo(s) .zpl");
                for (int i = 0; i < archivos.Count && i < 10; i++)
                {
                    L("  - " + archivos[i].Name + "   " +
                      archivos[i].LastWriteTime.ToString("yyyy-MM-dd HH:mm") + "   " +
                      archivos[i].Length + " bytes");
                }

                // El ZPL exacto que genero la app: es lo que hay que revisar.
                L();
                L("Contenido del mas reciente (" + archivos[0].Name + "):");
                L("-----BEGIN ZPL-----");
                try { L(File.ReadAllText(archivos[0].FullName)); }
                catch (Exception ex) { L("(no se pudo leer: " + ex.Message + ")"); }
                L("-----END ZPL-----");

                Problemas.Add("En la carpeta Descargas hay " + archivos.Count + " archivo(s) .zpl " +
                              "(el mas reciente es del " + archivos[0].LastWriteTime.ToString("yyyy-MM-dd HH:mm") + "). " +
                              "Eso confirma que la aplicacion se uso desde el NAVEGADOR y, al no encontrar " +
                              "Zebra Browser Print, descargo la etiqueta como archivo en vez de imprimirla " +
                              "-- mostrando de todos modos el mensaje de 'impreso correctamente'.");
            }
            catch (Exception ex)
            {
                L("No se pudo revisar Descargas: " + ex.Message);
            }
        }

        private static void AnalizarProblemas(List<PrinterInfo> impresoras)
        {
            bool hayZebra = false;
            foreach (var p in impresoras)
            {
                if (!p.EsZebra) continue;
                hayZebra = true;

                if (p.DriverEsEpl)
                    Problemas.Add("La impresora '" + p.Name + "' esta instalada con un driver EPL, que no " +
                                  "entiende ZPL. Reinstalarla con el driver ZDesigner en su variante ZPL.");
                if (p.SinConexion)
                    Problemas.Add("Windows ve la impresora '" + p.Name + "' SIN CONEXION: revisar cable USB, " +
                                  "que este encendida, y quitar 'Usar impresora sin conexion' en la cola.");
                if (p.Pausada)
                    Problemas.Add("La cola de '" + p.Name + "' esta EN PAUSA: abrirla y quitar 'Pausar impresion'.");
                if (p.EnError)
                    Problemas.Add("La impresora '" + p.Name + "' reporta error fisico (" + p.EstadoTexto + "). " +
                                  "En la GK420t se ve como luz roja: rollo terminado, etiqueta atascada, " +
                                  "tapa sin cerrar o falta de ribbon.");
                if (p.Jobs > 0)
                    Problemas.Add("Hay " + p.Jobs + " trabajo(s) atascado(s) en '" + p.Name + "'. Windows si envia, " +
                                  "pero la impresora no los consume: casi siempre el puerto esta equivocado " +
                                  "(el driver apunta a " + p.Port + ") o la impresora esta en error.");
            }

            if (!hayZebra)
                Problemas.Add("No hay ninguna impresora Zebra instalada en Windows. Sin eso la aplicacion no " +
                              "tiene a donde enviar la etiqueta. Instalar el driver ZDesigner de la GK420t.");

            if (!PuertoAbierto(9100) && !PuertoAbierto(9101))
                Problemas.Add("Zebra Browser Print no esta corriendo. Si usan la aplicacion desde el NAVEGADOR, " +
                              "esa es la causa directa: la app no alcanza la impresora y descarga un archivo " +
                              ".zpl en Descargas en vez de imprimir. Solucion: instalar Browser Print, o usar " +
                              "la aplicacion de escritorio.");
        }

        // -----------------------------------------------------------------
        // Opcion 1: revisar todo
        // -----------------------------------------------------------------
        private static void RevisarTodo()
        {
            Titulo("REVISION COMPLETA");
            W("Fecha: " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));
            W("Equipo: " + Environment.MachineName + "   Usuario: " + Environment.UserName);
            W();

            // Los datos ya se recogieron al abrir el programa; aqui solo se
            // muestran, para que la revision y el informe nunca se contradigan.
            var impresoras = LeerImpresoras();

            W("--- IMPRESORAS INSTALADAS ---", ConsoleColor.Yellow);
            foreach (var p in impresoras)
            {
                W();
                W("  " + p.Name + (p.Default ? "   [predeterminada]" : ""),
                    p.EsZebra ? ConsoleColor.Green : ConsoleColor.Gray);
                W("     Driver : " + p.Driver);
                W("     Puerto : " + p.Port);
                W("     Estado : " + p.EstadoTexto);
                W("     Cola   : " + p.Jobs + " trabajo(s) pendiente(s)");
            }

            W();
            W("--- SERVICIO ZEBRA BROWSER PRINT ---", ConsoleColor.Yellow);
            W("    (solo hace falta si usan la aplicacion desde el navegador)");
            bool bp9100 = PuertoAbierto(9100);
            bool bp9101 = PuertoAbierto(9101);
            W("     127.0.0.1:9100 -> " + (bp9100 ? "responde" : "no responde"), bp9100 ? ConsoleColor.Green : ConsoleColor.Gray);
            W("     127.0.0.1:9101 -> " + (bp9101 ? "responde" : "no responde"), bp9101 ? ConsoleColor.Green : ConsoleColor.Gray);

            W();
            W("--- RESUMEN ---", ConsoleColor.Yellow);
            if (Problemas.Count == 0)
            {
                W("  No se detectaron problemas de configuracion.", ConsoleColor.Green);
                W("  Sigue con la opcion 2 para comprobar si la impresora entiende ZPL.");
            }
            else
            {
                W("  Se encontraron " + Problemas.Count + " problema(s):", ConsoleColor.Red);
                for (int i = 0; i < Problemas.Count; i++)
                {
                    W();
                    W("  " + (i + 1) + ") " + Problemas[i], ConsoleColor.Red);
                }
            }

            W();
            W("  Recuerda: aunque todo esto este bien, la GK420t puede estar en modo EPL");
            W("  (viene asi de fabrica en muchos casos) y entonces ignora todo el ZPL.");
            W("  La opcion 2 lo comprueba y la opcion 3 lo corrige.");
            Pausa();
        }

        // -----------------------------------------------------------------
        // Opcion 2: en que lenguaje esta la impresora
        // -----------------------------------------------------------------
        private static void ProbarLenguaje()
        {
            if (!AsegurarImpresora()) return;
            Titulo("PRUEBA: ¿la impresora entiende ZPL?");
            W("Se van a pedir DOS etiquetas de configuracion a '" + _impresora + "':");
            W("  - una en lenguaje ZPL");
            W("  - otra en lenguaje EPL");
            W("Segun cual salga, sabremos en que modo esta la impresora.");
            W();

            W("1 de 2 - pidiendo la configuracion en ZPL ...", ConsoleColor.Cyan);
            Enviar("~WC", "Config ZPL");
            System.Threading.Thread.Sleep(2000);

            W();
            W("2 de 2 - pidiendo la configuracion en EPL ...", ConsoleColor.Cyan);
            Enviar("\r\nUQ\r\n", "Config EPL");

            W();
            W("MIRA LA IMPRESORA Y COMPARA:", ConsoleColor.Yellow);
            W();
            W("  A) Salio una etiqueta larga que dice \"ZPL II\" o tiene lineas con ^JU");
            W("     -> La impresora SI entiende ZPL. El problema esta en la aplicacion");
            W("        o en la plantilla de la etiqueta, no en la impresora.");
            W();
            W("  B) Salio SOLO la segunda etiqueta (o una que no menciona ZPL)");
            W("     -> La impresora esta en modo EPL. Usa la opcion 3 para cambiarla.", ConsoleColor.Green);
            W();
            W("  C) No salio NINGUNA etiqueta");
            W("     -> No le esta llegando nada a la impresora. Revisa: que este encendida,");
            W("        el cable USB, que no tenga luz roja, y vuelve a la opcion 1.");
            W();
            W("  D) Salieron etiquetas EN BLANCO");
            W("     -> La GK420t es de TRANSFERENCIA TERMICA: necesita RIBBON (cinta).");
            W("        Sin ribbon imprime en blanco. Si usan papel termico directo,");
            W("        hay que cambiarle el modo (avisa y lo agregamos).");

            RegistrarObservacion("Prueba de lenguaje (ZPL / EPL)", new string[] {
                "Salio una etiqueta larga que menciona ZPL  -> la impresora SI entiende ZPL",
                "Salio solo la otra etiqueta, sin mencionar ZPL  -> esta en modo EPL",
                "Salieron las DOS etiquetas",
                "NO salio ninguna etiqueta",
                "Salieron etiquetas pero EN BLANCO",
                "No estoy seguro de lo que salio"
            });
            Pausa();
        }

        // -----------------------------------------------------------------
        // Opcion 3: forzar modo ZPL
        // -----------------------------------------------------------------
        private static void ForzarZpl()
        {
            if (!AsegurarImpresora()) return;
            Titulo("PONER LA IMPRESORA EN MODO ZPL");
            W("Esto le dice a '" + _impresora + "' que a partir de ahora hable ZPL,");
            W("y lo guarda en su memoria (no hay que repetirlo cada vez).");
            W();

            W("Enviando la orden de cambio de lenguaje ...", ConsoleColor.Cyan);
            Enviar("! U1 setvar \"device.languages\" \"zpl\"\r\n", "Modo ZPL");
            System.Threading.Thread.Sleep(1500);

            W();
            W("Guardando el cambio en la memoria de la impresora ...", ConsoleColor.Cyan);
            Enviar("^XA^SZ2^JUS^XZ", "Guardar modo ZPL");

            W();
            W("Listo. Ahora usa la opcion 4 para imprimir una etiqueta de prueba.", ConsoleColor.Green);
            W("Si la etiqueta de prueba sale bien, la aplicacion tambien deberia imprimir.");
            Pausa();
        }

        // -----------------------------------------------------------------
        // Opcion 4: etiqueta de prueba
        // -----------------------------------------------------------------
        private static void EtiquetaPrueba()
        {
            if (!AsegurarImpresora()) return;
            Titulo("IMPRIMIR ETIQUETA DE PRUEBA");
            W("Se envia una etiqueta sencilla, que no depende de la configuracion");
            W("de la aplicacion: solo texto grande y un codigo de barras.");
            W();

            string zpl =
                "^XA\r\n" +
                "^CI28\r\n" +
                "^PW812\r\n" +
                "^LL406\r\n" +
                "^LH0,0\r\n" +
                "^FO40,40^A0N,50,50^FDPRUEBA ZPL^FS\r\n" +
                "^FO40,110^A0N,30,30^FDGK420t 203 dpi^FS\r\n" +
                "^FO40,160^BY2^BCN,100,Y,N,N^FD1234567890^FS\r\n" +
                "^PQ1\r\n" +
                "^XZ\r\n";

            Enviar(zpl, "Etiqueta de prueba");

            W();
            W("RESULTADO:", ConsoleColor.Yellow);
            W("  - Salio la etiqueta con el texto PRUEBA ZPL y el codigo de barras");
            W("    -> La impresora esta perfecta. El problema esta en la aplicacion:", ConsoleColor.Green);
            W("       avisale al equipo de desarrollo con el informe (opcion 6).");
            W();
            W("  - Salio una etiqueta en blanco");
            W("    -> Falta el RIBBON (cinta). La GK420t lo necesita para marcar.");
            W();
            W("  - No salio nada");
            W("    -> Vuelve a la opcion 1 y revisa lo que marque en rojo.");

            RegistrarObservacion("Etiqueta de prueba", new string[] {
                "Salio la etiqueta con el texto PRUEBA ZPL y el codigo de barras",
                "Salio una etiqueta pero con simbolos raros o incompleta",
                "Salio una etiqueta EN BLANCO",
                "NO salio ninguna etiqueta",
                "No estoy seguro de lo que salio"
            });
            Pausa();
        }

        // -----------------------------------------------------------------
        // Opcion 5: elegir impresora
        // -----------------------------------------------------------------
        private static void ElegirImpresora(bool silencioso = false)
        {
            var impresoras = LeerImpresoras();
            var zebras = new List<PrinterInfo>();
            foreach (var p in impresoras) if (p.EsZebra) zebras.Add(p);

            // En modo silencioso solo decidimos si no hay ambiguedad: una sola
            // Zebra se toma sola; si hay varias (o ninguna) se pregunta despues.
            if (silencioso)
            {
                if (zebras.Count == 1) _impresora = zebras[0].Name;
                return;
            }

            var candidatas = zebras.Count > 0 ? zebras : impresoras;

            Titulo("ELEGIR IMPRESORA");
            if (zebras.Count == 0)
            {
                W("  No se detecto ninguna impresora Zebra. Se muestran todas:", ConsoleColor.Yellow);
                W();
            }
            for (int i = 0; i < candidatas.Count; i++)
            {
                Console.WriteLine("   " + (i + 1) + ")  " + candidatas[i].Name);
                Console.WriteLine("       driver: " + candidatas[i].Driver);
            }
            Console.WriteLine();
            Console.Write("   Escribe el numero y presiona Enter: ");
            string s = Console.ReadLine();
            int n;
            if (int.TryParse(s, out n) && n >= 1 && n <= candidatas.Count)
            {
                _impresora = candidatas[n - 1].Name;
                Console.WriteLine();
                Console.ForegroundColor = ConsoleColor.Green;
                Console.WriteLine("   Impresora seleccionada: " + _impresora);
                Console.ResetColor();
            }
            else
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("   Opcion no valida.");
                Console.ResetColor();
            }
            if (!silencioso) Pausa();
        }

        private static bool AsegurarImpresora()
        {
            if (!string.IsNullOrEmpty(_impresora)) return true;
            ElegirImpresora(true);
            if (string.IsNullOrEmpty(_impresora)) ElegirImpresora();
            if (string.IsNullOrEmpty(_impresora))
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine();
                Console.WriteLine("   Primero hay que elegir una impresora (opcion 5).");
                Console.ResetColor();
                Pausa();
                return false;
            }
            return true;
        }

        private static void Enviar(string datos, string nombreTrabajo)
        {
            string error = RawPrinter.Send(_impresora, datos, nombreTrabajo);
            if (error == null)
            {
                W("   OK - Windows acepto el envio a la impresora.", ConsoleColor.Green);
                L("      [informe] envio RAW '" + nombreTrabajo + "' a '" + _impresora + "': ACEPTADO (" +
                  datos.Length + " bytes)");
            }
            else
            {
                W("   FALLO - " + error, ConsoleColor.Red);
                L("      [informe] envio RAW '" + nombreTrabajo + "' a '" + _impresora + "': FALLO -> " + error);
                Problemas.Add("El envio directo a '" + _impresora + "' fallo en Windows: " + error);
            }
        }

        /// <summary>
        /// Pregunta al operador que vio en la impresora y lo deja escrito en el
        /// informe. Es el unico dato que el programa no puede averiguar solo.
        /// </summary>
        private static void RegistrarObservacion(string prueba, string[] opciones)
        {
            Console.WriteLine();
            Console.ForegroundColor = ConsoleColor.Yellow;
            Console.WriteLine("   Cuentame que paso (queda escrito en el informe):");
            Console.ResetColor();
            Console.WriteLine();
            for (int i = 0; i < opciones.Length; i++)
                Console.WriteLine("     " + (i + 1) + ")  " + opciones[i]);
            Console.WriteLine();
            Console.Write("   Escribe el numero y presiona Enter: ");

            string s = (Console.ReadLine() ?? "").Trim();
            int n;
            string respuesta = (int.TryParse(s, out n) && n >= 1 && n <= opciones.Length)
                ? opciones[n - 1]
                : "(sin responder)";

            L();
            L("   >>> OBSERVACION DEL OPERADOR - " + prueba);
            L("       " + respuesta);

            Console.WriteLine();
            Console.ForegroundColor = ConsoleColor.Green;
            Console.WriteLine("   Anotado: " + respuesta);
            Console.ResetColor();
        }

        // -----------------------------------------------------------------
        // Opcion 6: guardar informe
        // -----------------------------------------------------------------
        /// <summary>
        /// Escribe el informe completo. Se llama sola despues de cada paso, asi
        /// el archivo existe aunque el operador cierre la ventana con la X.
        /// Siempre es el mismo archivo por sesion: se reescribe, no se acumula.
        /// </summary>
        private static bool GuardarInforme(bool silencioso)
        {
            try
            {
                if (_rutaInforme == null)
                {
                    string escritorio = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
                    if (string.IsNullOrEmpty(escritorio) || !Directory.Exists(escritorio))
                        escritorio = Environment.GetEnvironmentVariable("USERPROFILE") ?? ".";
                    _rutaInforme = Path.Combine(escritorio,
                        "informe-impresora-" + Environment.MachineName + "-" +
                        DateTime.Now.ToString("yyyyMMdd-HHmm") + ".txt");
                }

                var sb = new StringBuilder();
                sb.AppendLine("===========================================================");
                sb.AppendLine(" INFORME DE DIAGNOSTICO - IMPRESORA ZEBRA");
                sb.AppendLine(" Serial Manager - etiquetas de equipos");
                sb.AppendLine("===========================================================");
                sb.AppendLine();
                sb.AppendLine(" >>> ENVIAR ESTE ARCHIVO AL EQUIPO DE DESARROLLO <<<");
                sb.AppendLine("     No hay que entenderlo: solo adjuntarlo a un correo.");
                sb.AppendLine();
                sb.AppendLine("Generado por      : DiagnosticoZebra v" + Version);
                sb.AppendLine("Ultima escritura  : " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));
                sb.AppendLine("Impresora elegida : " + (_impresora ?? "(ninguna)"));
                sb.AppendLine();
                sb.AppendLine("===========================================================");
                sb.AppendLine(" 0. RESUMEN AUTOMATICO");
                sb.AppendLine("===========================================================");
                if (Problemas.Count == 0)
                {
                    sb.AppendLine("No se detectaron problemas de configuracion en el equipo.");
                    sb.AppendLine("Si aun asi no imprime, revisar las observaciones del");
                    sb.AppendLine("operador mas abajo (seccion de pruebas).");
                }
                else
                {
                    sb.AppendLine("Se detectaron " + Problemas.Count + " problema(s):");
                    for (int i = 0; i < Problemas.Count; i++)
                    {
                        sb.AppendLine();
                        sb.AppendLine("  " + (i + 1) + ") " + Problemas[i]);
                    }
                }
                sb.AppendLine();
                sb.Append(Informe.ToString());
                sb.AppendLine();
                sb.AppendLine("===========================================================");
                sb.AppendLine(" FIN DEL INFORME");
                sb.AppendLine("===========================================================");

                File.WriteAllText(_rutaInforme, sb.ToString(), Encoding.UTF8);

                if (!silencioso)
                {
                    Titulo("INFORME GUARDADO");
                    Console.WriteLine("   Se guardo en tu Escritorio:");
                    Console.WriteLine();
                    Console.ForegroundColor = ConsoleColor.Green;
                    Console.WriteLine("   " + _rutaInforme);
                    Console.ResetColor();
                    Console.WriteLine();
                    Console.WriteLine("   Adjunta ese archivo a un correo y mandalo al equipo");
                    Console.WriteLine("   de desarrollo. Con eso les basta.");
                    Pausa();
                }
                return true;
            }
            catch (Exception ex)
            {
                if (!silencioso)
                {
                    Console.ForegroundColor = ConsoleColor.Red;
                    Console.WriteLine("   No se pudo guardar el informe: " + ex.Message);
                    Console.ResetColor();
                    Pausa();
                }
                return false;
            }
        }

        // -----------------------------------------------------------------
        private static void Menu()
        {
            // Clear falla si la salida esta redirigida; no es motivo para abortar.
            try { Console.Clear(); } catch (IOException) { }
            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine();
            Console.WriteLine("  ==================================================");
            Console.WriteLine("     DIAGNOSTICO DE IMPRESORA ZEBRA  -  GK420t");
            Console.WriteLine("     Serial Manager");
            Console.WriteLine("  ==================================================");
            Console.ResetColor();
            Console.WriteLine();

            if (string.IsNullOrEmpty(_impresora))
            {
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine("     Impresora: (ninguna seleccionada todavia)");
                Console.ResetColor();
            }
            else
            {
                Console.WriteLine("     Impresora: " + _impresora);
            }

            Console.WriteLine();
            Console.WriteLine("     1)  Revisar todo            <- empieza por aqui");
            Console.WriteLine("     2)  ¿La impresora entiende ZPL?");
            Console.WriteLine("     3)  Ponerla en modo ZPL      (arregla el caso mas comun)");
            Console.WriteLine("     4)  Imprimir etiqueta de prueba");
            Console.WriteLine("     5)  Cambiar de impresora");
            Console.WriteLine("     6)  Ver donde quedo el informe");
            Console.WriteLine("     0)  Salir");
            Console.WriteLine();

            if (_rutaInforme != null)
            {
                Console.ForegroundColor = ConsoleColor.DarkGray;
                Console.WriteLine("     El informe se va guardando solo en tu Escritorio:");
                Console.WriteLine("     " + Path.GetFileName(_rutaInforme));
                Console.ResetColor();
                Console.WriteLine();
            }

            Console.Write("     Escribe el numero y presiona Enter: ");
        }

        private static int Main()
        {
            try { Console.OutputEncoding = Encoding.UTF8; } catch { /* consola antigua */ }
            Console.Title = "Diagnostico de impresora Zebra - Serial Manager";

            // Si hay una sola Zebra, la tomamos sola para no preguntar de entrada.
            ElegirImpresora(true);

            // Todo el diagnostico tecnico se recoge al arrancar y se guarda de
            // inmediato: el informe queda util aunque el operador no haga nada.
            Console.WriteLine();
            Console.WriteLine("   Revisando el equipo, un momento...");
            RecolectarDatosTecnicos();
            GuardarInforme(true);

            while (true)
            {
                Menu();
                string op = (Console.ReadLine() ?? "").Trim();
                switch (op)
                {
                    case "1": RevisarTodo(); break;
                    case "2": ProbarLenguaje(); break;
                    case "3": ForzarZpl(); break;
                    case "4": EtiquetaPrueba(); break;
                    case "5": ElegirImpresora(); break;
                    case "6": GuardarInforme(false); break;
                    case "0":
                    case "":
                        GuardarInforme(true);
                        Despedida();
                        return 0;
                    default:
                        Console.ForegroundColor = ConsoleColor.Red;
                        Console.WriteLine();
                        Console.WriteLine("     Opcion no valida. Escribe un numero del 0 al 6.");
                        Console.ResetColor();
                        System.Threading.Thread.Sleep(1200);
                        continue;
                }

                // Tras cada paso se reescribe el informe con lo nuevo.
                GuardarInforme(true);
            }
        }

        private static void Despedida()
        {
            Console.WriteLine();
            Console.WriteLine("  ==================================================");
            Console.ForegroundColor = ConsoleColor.Yellow;
            Console.WriteLine("     FALTA UN ULTIMO PASO");
            Console.ResetColor();
            Console.WriteLine("  ==================================================");
            Console.WriteLine();
            Console.WriteLine("     En tu Escritorio quedo este archivo:");
            Console.WriteLine();
            Console.ForegroundColor = ConsoleColor.Green;
            Console.WriteLine("     " + (_rutaInforme ?? "(no se pudo guardar el informe)"));
            Console.ResetColor();
            Console.WriteLine();
            Console.WriteLine("     Adjuntalo a un correo y mandalo al equipo de");
            Console.WriteLine("     desarrollo. Ahi esta todo lo que necesitan.");
            Console.WriteLine();
            Console.ForegroundColor = ConsoleColor.DarkGray;
            Console.WriteLine("     (presiona cualquier tecla para cerrar)");
            Console.ResetColor();
            try { Console.ReadKey(true); }
            catch (InvalidOperationException) { Console.ReadLine(); }
        }
    }
}
