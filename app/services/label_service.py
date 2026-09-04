"""Servicio de etiquetas: render ZPL paramétrico y vista previa PNG."""
from __future__ import annotations

import base64
import math
from datetime import datetime, timezone
from io import BytesIO

from app.models.catalog import Country, EquipmentType, LabelSize
from app.models.equipment import EquipmentTag

# Plantilla histórica, con coordenadas fijas calculadas para 50x25mm @203dpi.
# Se conserva SOLO para reconocerla: los tamaños sembrados con ella pasan al
# render paramétrico, porque en cualquier otro tamaño su contenido se sale del
# medio (el pie iba en y=210 y una etiqueta de 25mm mide 200 puntos de alto).
LEGACY_ZPL = (
    "^XA"
    "^FO40,30^A0N,40,40^FD{serial}^FS"
    "^FO40,90^BCN,90,Y,N,N^FD{serial}^FS"
    "^FO40,210^A0N,24,24^FD{country}  {date}^FS"
    "^XZ"
)


def _r(value: float) -> int:
    """Redondeo compatible con `Math.round` de JS (mitad hacia arriba).

    Importa para que este render y el `buildZpl()` del frontend (usado sin
    conexión) produzcan exactamente el mismo ZPL; `round()` de Python usa
    redondeo bancario y diferiría en los .5.
    """
    return math.floor(value + 0.5)


def _dots(mm: float, dpi: int) -> int:
    return _r(mm / 25.4 * dpi)


def fit_footer_model(
    model: str, country_name: str, date_str: str, w: int, pad: int, foot_h: int
) -> str:
    """Recorta el modelo a lo que quede libre entre el país y la fecha.

    El pie tiene tres bloques en una sola línea (país · modelo · fecha) y el
    modelo es el único de largo imprevisible, así que se acorta si no cabe en
    vez de encimarse con los otros dos. El ancho de carácter de la fuente
    escalable A0 es ~0.6 de su alto.

    Al ir centrado, el modelo crece hacia ambos lados por igual: el límite es
    el doble del bloque más ancho (país o fecha), no la suma de los dos.

    Réplica de `fitFooterModel()` en frontend/src/services/labelRender.ts.
    """
    if not model:
        return ""
    char_w = max(1.0, foot_h * 0.6)
    # 4 caracteres de separación mínima (dos a cada lado del modelo).
    budget = (
        int((w - pad * 2) / char_w) - max(len(country_name), len(date_str)) * 2 - 4
    )
    if budget < 3:
        return ""
    if len(model) <= budget:
        return model
    return model[: budget - 1].rstrip() + "."


def build_zpl(
    *,
    serial: str,
    country_name: str,
    date_str: str,
    width_mm: float,
    height_mm: float,
    dpi: int,
    barcode_type: str,
    model_name: str = "",
) -> str:
    """Construye el ZPL escalado al tamaño real de la etiqueta.

    Todas las posiciones son proporcionales al alto/ancho, así que cambiar los
    milímetros en Configuración basta para que la etiqueta se reacomode. Emite
    `^PW`/`^LL` para no depender de cómo esté calibrada cada impresora.

    Réplica de `buildZpl()` en frontend/src/services/labelRender.ts, que es el
    camino que se usa sin conexión: ambos deben generar el mismo resultado.
    """
    w = _dots(width_mm, dpi)
    h = _dots(height_mm, dpi)
    pad = _r(w * 0.04)

    show_code = barcode_type in ("code128", "both")
    show_qr = barcode_type in ("qr", "both")

    code_top = _r(h * 0.4)
    code_h = _r(h * 0.4)
    head_h = _r(h * 0.08)
    serial_h = _r(h * 0.16)
    foot_h = _r(h * 0.07)
    foot_y = _r(h * 0.88)

    parts = [
        "^XA",
        "^CI28",  # UTF-8: sin esto los acentos salen mal ("Panamá").
        f"^PW{w}",
        f"^LL{h}",
        f"^FO0,{head_h}^FB{w},1,0,C,0^A0N,{head_h},{head_h}^FDSERIAL / ID EQUIPO^FS",
        f"^FO0,{_r(h * 0.2)}^FB{w},1,0,C,0^A0N,{serial_h},{serial_h}^FD{serial}^FS",
    ]

    # El lado real del QR es (magnificación × módulos), no `code_h`: un QR
    # modelo 2 con estos datos llega a 25 módulos. Se calcula antes que el
    # código de barras porque le quita ancho disponible.
    qr_side = 0
    qr_mag = 0
    if show_qr:
        # Que quepa a lo ancho de su hueco y a lo alto entre el código y el pie.
        max_side = min(code_h, foot_y - code_top)
        qr_mag = max(1, min(10, max_side // 25))
        qr_side = qr_mag * 25

    if show_code:
        # El ancho del Code128 lo fija el módulo (^BY), no la etiqueta: son 11
        # módulos por carácter más start/check/stop. Con un ^BY fijo, una
        # etiqueta angosta con un serial largo desborda. Elegimos el módulo más
        # grande que quepa, que además aprovecha mejor las etiquetas anchas.
        avail = w - pad * 2 - ((qr_side + pad) if show_qr else 0)
        modules = len(serial) * 11 + 35
        module_w = max(1, min(4, avail // modules))
        # El ancho del código está cuantizado (módulos enteros), así que casi
        # nunca llena el espacio: se centra para que no quede corrido a la
        # izquierda, igual que el encabezado y el serial. Con QR no se centra,
        # porque ahí el código ocupa la izquierda y el QR la derecha.
        bar_w = modules * module_w
        bar_x = pad if show_qr else pad + max(0, (avail - bar_w) // 2)
        parts.append(
            f"^FO{bar_x},{code_top}^BY{module_w}^BCN,{code_h},N,N,N^FD{serial}^FS"
        )
    if show_qr:
        parts.append(
            f"^FO{w - pad - qr_side},{code_top}^BQN,2,{qr_mag}^FDLA,{serial}^FS"
        )

    # Pie: país (izq) · modelo (centro) · fecha (der).
    country_txt = country_name.upper()
    parts.append(f"^FO{pad},{foot_y}^A0N,{foot_h},{foot_h}^FD{country_txt}^FS")
    model_txt = fit_footer_model(
        model_name.upper(), country_txt, date_str, w, pad, foot_h
    )
    if model_txt:
        parts.append(
            f"^FO0,{foot_y}^FB{w},1,0,C,0^A0N,{foot_h},{foot_h}^FD{model_txt}^FS"
        )
    parts.append(
        f"^FO0,{foot_y}^FB{w - pad},1,0,R,0^A0N,{foot_h},{foot_h}^FD{date_str}^FS"
    )
    parts.append("^XZ")
    return "\n".join(parts)


def _is_legacy_template(template: str) -> bool:
    """¿Es la plantilla vieja de coordenadas fijas (no una hecha a medida)?"""
    return "".join(template.split()) == "".join(LEGACY_ZPL.split())


def render_zpl(
    tag: EquipmentTag,
    size: LabelSize,
    country: Country | None,
    equipment_type: EquipmentType | None = None,
) -> str:
    date_str = datetime.now(tz=timezone.utc).strftime("%d/%m/%Y")
    country_name = country.name if country else tag.country_code
    model_name = equipment_type.model if equipment_type else ""

    # Una plantilla propia (cargada a mano para un caso especial) se respeta tal
    # cual. La histórica y la ausencia de plantilla van al render paramétrico.
    template = (size.zpl_template or "").strip()
    if template and not _is_legacy_template(template):
        return template.format(
            serial=tag.serial_code,
            country=country_name,
            country_name=country_name,
            country_code=tag.country_code,
            model=model_name,
            date=date_str,
        )

    return build_zpl(
        serial=tag.serial_code,
        country_name=country_name,
        date_str=date_str,
        width_mm=float(size.width_mm),
        height_mm=float(size.height_mm),
        dpi=size.dpi or 203,
        barcode_type=size.barcode_type or "code128",
        model_name=model_name,
    )


def render_preview_png(
    tag: EquipmentTag, size: LabelSize, equipment_type: EquipmentType | None = None
) -> str:
    """Genera una imagen PNG simple de la etiqueta (base64) para vista previa.

    No reemplaza el render real de la impresora; sirve para previsualizar en la UI.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return ""

    # Escala mm → px a la resolución dada.
    px_per_mm = (size.dpi or 203) / 25.4
    w = max(200, int(float(size.width_mm) * px_per_mm))
    h = max(100, int(float(size.height_mm) * px_per_mm))
    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, w - 1, h - 1], outline="black", width=2)
    draw.text((10, 8), "SERIAL / ID EQUIPO", fill="black")
    draw.text((10, 30), tag.serial_code, fill="black")

    # Pseudo código de barras (barras proporcionales al serial) para la vista previa.
    x = 10
    y0, y1 = 60, h - 30
    for i, ch in enumerate(tag.serial_code):
        bar_w = 2 + (ord(ch) % 3)
        if i % 2 == 0:
            draw.rectangle([x, y0, x + bar_w, y1], fill="black")
        x += bar_w + 2
        if x > w - 10:
            break
    foot = tag.country_code
    if equipment_type and equipment_type.model:
        foot = f"{foot}   {equipment_type.model}"
    draw.text((10, h - 22), foot, fill="black")

    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")
