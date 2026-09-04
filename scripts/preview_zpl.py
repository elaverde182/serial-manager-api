"""Renderiza a PNG el ZPL que genera la app, sin impresora y sin internet.

Para qué sirve: ver si el contenido cabe en la etiqueta y si queda centrado,
que es exactamente donde estaba el error de las coordenadas fijas. Interpreta
solo el subconjunto de ZPL que emite `label_service.build_zpl`.

NO es un emulador de Zebra: las posiciones y los tamaños son exactos, pero el
código de barras se dibuja como un bloque del ancho real (las barras no son
legibles). Para una prueba de lectura hace falta la impresora o Labelary.

Uso:
    # a partir de un tamaño de etiqueta
    python scripts/preview_zpl.py --width 63 --height 25
    python scripts/preview_zpl.py --width 50 --height 25 --barcode both

    # a partir de un .zpl/.prn ya generado (p. ej. el de la impresora virtual)
    python scripts/preview_zpl.py --file C:\\zpl\\salida.prn
"""
from __future__ import annotations

import argparse
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.label_service import build_zpl  # noqa: E402

# La A0 de Zebra es una sans escalable; Arial es un sustituto razonable para
# juzgar si el texto cabe.
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _font(height_dots: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            # En ZPL el alto es la celda del carácter; el cuerpo va algo menor.
            return ImageFont.truetype(path, max(6, int(height_dots * 0.78)))
    return ImageFont.load_default()


class Field:
    def __init__(self) -> None:
        self.x = 0
        self.y = 0
        self.font_h: int | None = None
        self.block_w: int | None = None
        self.justify = "L"
        self.barcode_h: int | None = None
        self.qr_mag: int | None = None
        self.text = ""


def parse(zpl: str, size: tuple[int, int] | None = None) -> tuple[int, int, list[Field], bool]:
    """Devuelve (ancho, alto, campos, declara_medidas).

    Si el ZPL no trae ^PW/^LL —como la plantilla antigua de coordenadas fijas—
    hay que darle el tamaño real por `size`; si no, se mediría contra un valor
    por defecto enorme y cualquier etiqueta parecería caber.
    """
    pw = re.search(r"\^PW(\d+)", zpl)
    ll = re.search(r"\^LL(\d+)", zpl)
    declared = bool(pw and ll)
    if declared:
        width, length = int(pw.group(1)), int(ll.group(1))
    elif size:
        width, length = size
    else:
        width, length = 812, 1218

    fields: list[Field] = []
    for chunk in zpl.split("^FS"):
        pos = re.search(r"\^FO(\d+),(\d+)", chunk)
        data = re.search(r"\^FD(.*)", chunk, re.DOTALL)
        if not pos or not data:
            continue
        f = Field()
        f.x, f.y = int(pos.group(1)), int(pos.group(2))
        f.text = data.group(1).strip()
        if fb := re.search(r"\^FB(\d+),(\d+),(-?\d+),([LCRJ])", chunk):
            f.block_w = int(fb.group(1))
            f.justify = fb.group(4)
        if fo := re.search(r"\^A0N,(\d+),", chunk):
            f.font_h = int(fo.group(1))
        if bc := re.search(r"\^BCN,(\d+),", chunk):
            f.barcode_h = int(bc.group(1))
        if qr := re.search(r"\^BQN,\d+,(\d+)", chunk):
            f.qr_mag = int(qr.group(1))
            f.text = re.sub(r"^[A-Z]{2},", "", f.text)  # quita el prefijo "LA,"
        fields.append(f)
    return width, length, fields, declared


def code128_width(text: str, module: int = 2) -> int:
    """Ancho real de un Code128-B: 11 módulos por carácter, más start/check/stop."""
    return (len(text) * 11 + 11 + 11 + 13) * module


def render(
    zpl: str, scale: int = 3, size: tuple[int, int] | None = None
) -> tuple[Image.Image, list[str], bool]:
    width, length, fields, declared = parse(zpl, size)
    module = int(m.group(1)) if (m := re.search(r"\^BY(\d+)", zpl)) else 2

    img = Image.new("RGB", (width * scale, length * scale), "white")
    d = ImageDraw.Draw(img)
    # Borde de la etiqueta (no se imprime; marca dónde termina el medio).
    d.rectangle([0, 0, width * scale - 1, length * scale - 1], outline="#bbbbbb")

    warnings: list[str] = []

    def check(name: str, x0: int, y0: int, x1: int, y1: int) -> None:
        if x1 > width or y1 > length or x0 < 0 or y0 < 0:
            warnings.append(
                f"{name}: ocupa ({x0},{y0})-({x1},{y1}) y la etiqueta es {width}x{length}"
            )

    for f in fields:
        if f.barcode_h is not None:
            bw = code128_width(f.text, module)
            check(f"barras '{f.text}'", f.x, f.y, f.x + bw, f.y + f.barcode_h)
            # Bloque con rayas: el ancho total es exacto, las barras no.
            for i in range(0, bw, module * 3):
                d.rectangle(
                    [
                        (f.x + i) * scale,
                        f.y * scale,
                        (f.x + i + module) * scale,
                        (f.y + f.barcode_h) * scale,
                    ],
                    fill="black",
                )
        elif f.qr_mag is not None:
            side = f.qr_mag * 25
            check(f"QR '{f.text}'", f.x, f.y, f.x + side, f.y + side)
            d.rectangle(
                [f.x * scale, f.y * scale, (f.x + side) * scale, (f.y + side) * scale],
                outline="black",
                width=max(1, scale),
            )
            d.text(
                ((f.x + side // 2) * scale, (f.y + side // 2) * scale),
                "QR",
                fill="black",
                anchor="mm",
            )
        elif f.font_h is not None:
            # La fuente se pide ya escalada; el ancho medido se devuelve a puntos
            # para poder comparar con ^PW/^LL, que están en puntos.
            font = _font(f.font_h * scale)
            text_w = int(d.textlength(f.text, font=font) / scale)
            x = f.x
            if f.block_w:
                if f.justify == "C":
                    x = f.x + max(0, (f.block_w - text_w) // 2)
                elif f.justify == "R":
                    x = f.x + max(0, f.block_w - text_w)
            check(f"texto '{f.text}'", x, f.y, x + text_w, f.y + f.font_h)
            d.text((x * scale, f.y * scale), f.text, fill="black", font=font)

    return img, warnings, declared


def labelary(zpl: str, width_mm: float, height_mm: float, dpi: int, out: str) -> str:
    """Renderiza con Labelary, que interpreta ZPL igual que una Zebra real.

    A diferencia del render local de este script, el código de barras que
    devuelve es auténtico y se puede escanear desde la pantalla.

    El ZPL viaja a labelary.com, así que conviene usar seriales de prueba.
    """
    import urllib.request

    dpmm = {152: 6, 203: 8, 300: 12, 600: 24}.get(dpi, 8)
    # Labelary pide el tamaño en pulgadas.
    w_in, h_in = round(width_mm / 25.4, 2), round(height_mm / 25.4, 2)
    url = f"https://api.labelary.com/v1/printers/{dpmm}dpmm/labels/{w_in}x{h_in}/0/"

    req = urllib.request.Request(
        url, data=zpl.encode("utf-8"), headers={"Accept": "image/png"}
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        png = resp.read()
    with open(out, "wb") as fh:
        fh.write(png)
    return os.path.abspath(out)


def main() -> int:
    p = argparse.ArgumentParser(description="Vista previa local del ZPL.")
    # Posicional para poder ARRASTRAR un .prn/.zpl sobre el ejecutable: Windows
    # lo pasa como primer argumento.
    p.add_argument("archivo", nargs="?", help="archivo .zpl/.prn (o arrástralo sobre el .exe)")
    p.add_argument("--file", help="archivo .zpl/.prn a renderizar")
    p.add_argument("--width", type=float, default=63.0, help="ancho en mm")
    p.add_argument("--height", type=float, default=25.0, help="alto en mm")
    p.add_argument("--dpi", type=int, default=203)
    # Serial de prueba a propósito: este script puede enviar el ZPL a Labelary,
    # y no queremos que salga un serial real de cliente por defecto.
    p.add_argument("--serial", default="PRUEBA1234567")
    p.add_argument("--country", default="Panama")
    p.add_argument("--barcode", default="code128", choices=["code128", "qr", "both"])
    # Sin --out: si se arrastro un archivo, la imagen se guarda A SU LADO (es
    # donde el usuario la va a buscar); si no, en el directorio actual.
    p.add_argument("--out", default=None)
    p.add_argument(
        "--labelary",
        action="store_true",
        help="renderizar con Labelary (fiel a una Zebra, con código de barras real). "
        "OJO: envía el contenido de la etiqueta a labelary.com. Usa seriales de prueba.",
    )
    args = p.parse_args()

    # Modo interactivo: doble clic o archivo arrastrado sobre el .exe. Hay que
    # mantener la ventana abierta y mostrar el resultado, o no se ve nada.
    interactivo = not any(a.startswith("--") for a in sys.argv[1:])

    origen = args.file or args.archivo
    if not args.out:
        args.out = (
            os.path.splitext(origen)[0] + ".png" if origen else "preview.png"
        )

    if origen:
        with open(origen, "r", encoding="utf-8", errors="replace") as fh:
            zpl = fh.read()
    else:
        zpl = build_zpl(
            serial=args.serial,
            country_name=args.country,
            date_str="11/08/2026",
            width_mm=args.width,
            height_mm=args.height,
            dpi=args.dpi,
            barcode_type=args.barcode,
        )

    print(zpl)
    print()

    if args.labelary:
        out = labelary(zpl, args.width, args.height, args.dpi, args.out)
        print(f"Imagen (Labelary): {out}")
        return 0

    # Tamaño real esperado, en puntos: sirve de referencia cuando el ZPL no lo
    # declara, y para avisar si lo declara distinto del rollo que se va a usar.
    esperado = (
        int(args.width / 25.4 * args.dpi + 0.5),
        int(args.height / 25.4 * args.dpi + 0.5),
    )
    img, warnings, declared = render(zpl, size=esperado)
    img.save(args.out)
    print(f"Imagen: {os.path.abspath(args.out)}  ({img.width}x{img.height} px)")

    if not declared:
        print(
            f"\nAVISO: el ZPL no declara ^PW/^LL. Se midio contra "
            f"{args.width}x{args.height} mm ({esperado[0]}x{esperado[1]} puntos).\n"
            "       Sin ^PW/^LL la impresora usa su propia calibracion, que "
            "puede no coincidir."
        )
    elif (img.width // 3, img.height // 3) != esperado:
        print(
            f"\nAVISO: el ZPL declara {img.width // 3}x{img.height // 3} puntos, "
            f"pero se esperaban {esperado[0]}x{esperado[1]} "
            f"({args.width}x{args.height} mm)."
        )

    if warnings:
        print("\nPROBLEMAS: contenido fuera de la etiqueta")
        for w in warnings:
            print(f"  - {w}")
        codigo = 1
    else:
        print("\nOK: todo el contenido cabe dentro de la etiqueta.")
        codigo = 0

    if interactivo:
        # Abrir la imagen: si llegaron aqui por doble clic o arrastrando, lo
        # que quieren ver es la etiqueta, no el texto de la consola.
        try:
            os.startfile(os.path.abspath(args.out))  # type: ignore[attr-defined]
        except Exception:
            pass
        if not origen:
            print(
                "\nSugerencia: arrastra un archivo .zpl o .prn sobre este "
                "programa para ver esa etiqueta."
            )
        print()
        try:
            input("Pulsa Enter para cerrar...")
        except EOFError:
            pass  # sin consola interactiva (tuberia, tarea programada, etc.)

    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
