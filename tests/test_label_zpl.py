"""Pruebas del render ZPL: el contenido tiene que caber en la etiqueta.

Estas pruebas no necesitan impresora: verifican la geometría del ZPL generado,
que es justo donde estaba el error (la plantilla vieja ponía el pie en y=210
sobre una etiqueta de 25mm, que mide 200 puntos de alto).
"""
import math
import re

from app.models.catalog import EquipmentType, LabelSize
from app.models.equipment import EquipmentTag
from app.services import label_service


def _type(model="EliteBook 840 G8", category="Portátil"):
    return EquipmentType(category=category, model=model)


def _size(width_mm=63, height_mm=25, dpi=203, template="", barcode="code128"):
    return LabelSize(
        name=f"{width_mm}x{height_mm}",
        width_mm=width_mm,
        height_mm=height_mm,
        dpi=dpi,
        zpl_template=template,
        barcode_type=barcode,
    )


def _tag(serial="T567P8JXDX8S"):
    return EquipmentTag(serial_code=serial, country_code="PA")


def _dots(mm, dpi=203):
    return math.floor(mm / 25.4 * dpi + 0.5)


def _elements(zpl: str):
    """(x, y, alto) de cada elemento posicionado del ZPL."""
    out = []
    for line in zpl.splitlines():
        pos = re.search(r"\^FO(\d+),(\d+)", line)
        if not pos:
            continue
        font = re.search(r"\^A0N,(\d+),", line)
        code = re.search(r"\^BCN,(\d+),", line)
        qr = re.search(r"\^BQN,\d+,(\d+)", line)
        if font:
            height = int(font.group(1))
        elif code:
            height = int(code.group(1))
        elif qr:
            # El QR es cuadrado: ~ 25 módulos por el factor de magnificación.
            height = int(qr.group(1)) * 25
        else:
            height = 0
        out.append((int(pos.group(1)), int(pos.group(2)), height))
    return out


def test_declara_ancho_y_largo_del_medio():
    """Sin ^PW/^LL la impresora usa su propia calibración, que puede estar mal."""
    zpl = label_service.render_zpl(_tag(), _size(63, 25), None)
    assert f"^PW{_dots(63)}" in zpl
    assert f"^LL{_dots(25)}" in zpl


def test_el_contenido_cabe_en_la_etiqueta():
    zpl = label_service.render_zpl(_tag(), _size(63, 25), None)
    w, h = _dots(63), _dots(25)
    for x, y, height in _elements(zpl):
        assert x < w, f"elemento en x={x} se sale del ancho {w}"
        assert y + height <= h, f"elemento en y={y} (alto {height}) se sale de {h}"


def test_el_contenido_cabe_en_varios_tamanos():
    for width_mm, height_mm, barcode in [
        (50, 25, "code128"),
        (63, 25, "code128"),
        (100, 50, "both"),
        (38, 19, "qr"),
        # Angostas: el Code128 no escala con la etiqueta, así que el módulo ^BY
        # tiene que achicarse solo o el código se sale.
        (30, 25, "code128"),
        (38, 25, "code128"),
        (45, 20, "both"),
    ]:
        size = _size(width_mm, height_mm, barcode=barcode)
        zpl = label_service.render_zpl(_tag(), size, None)
        w, h = _dots(width_mm), _dots(height_mm)
        for x, y, height in _elements(zpl):
            assert x < w, f"{width_mm}x{height_mm}: x={x} fuera de {w}"
            assert y + height <= h, f"{width_mm}x{height_mm}: y={y}+{height} fuera de {h}"


def test_el_qr_no_se_monta_sobre_el_pie_ni_sobre_las_barras():
    """El lado del QR es magnificación x módulos, no el alto del código.

    Al derivarlo de `code_h` (como se hacía antes), en etiquetas bajas el QR
    crecía más que su hueco y se montaba sobre la fecha.
    """
    for width_mm, height_mm in [(50, 10), (50, 12), (50, 25), (63, 25), (100, 50)]:
        zpl = label_service.render_zpl(
            _tag(), _size(width_mm, height_mm, barcode="both"), None
        )
        qr = re.search(r"\^FO(\d+),(\d+)\^BQN,2,(\d+)", zpl)
        assert qr, f"{width_mm}x{height_mm}: no se generó el QR"
        qx, qy, mag = int(qr.group(1)), int(qr.group(2)), int(qr.group(3))
        side = mag * 25

        bc = re.search(r"\^FO(\d+),(\d+)\^BY(\d+)\^BCN,(\d+)", zpl)
        assert bc, f"{width_mm}x{height_mm}: no se generó el código de barras"
        bx, module_w = int(bc.group(1)), int(bc.group(3))
        bw = (len(_tag().serial_code) * 11 + 35) * module_w

        assert bx + bw <= qx, f"{width_mm}x{height_mm}: las barras invaden el QR"

        # El pie es el elemento de texto más bajo.
        foot_y = max(int(m.group(2)) for m in re.finditer(r"\^FO(\d+),(\d+)\^A0N", zpl))
        assert qy + side <= foot_y, f"{width_mm}x{height_mm}: el QR se monta sobre el pie"


def test_escala_con_el_tamano_configurado():
    """Cambiar los mm en Configuración tiene que cambiar el ZPL."""
    a = label_service.render_zpl(_tag(), _size(50, 25), None)
    b = label_service.render_zpl(_tag(), _size(63, 25), None)
    assert f"^PW{_dots(50)}" in a
    assert f"^PW{_dots(63)}" in b
    assert a != b


def test_la_plantilla_vieja_de_coordenadas_fijas_se_ignora():
    """Los tamaños sembrados con la plantilla histórica pasan al render nuevo."""
    size = _size(63, 25, template=label_service.LEGACY_ZPL)
    zpl = label_service.render_zpl(_tag(), size, None)
    assert "^PW" in zpl and "^LL" in zpl
    assert "^FO40,210" not in zpl  # el pie que se salía del medio


def test_una_plantilla_propia_se_respeta():
    size = _size(63, 25, template="^XA^FO10,10^FD{serial}^FS^XZ")
    zpl = label_service.render_zpl(_tag("ABC123"), size, None)
    assert zpl == "^XA^FO10,10^FDABC123^FS^XZ"


def test_declara_utf8_para_los_acentos():
    """Sin ^CI28 'Panamá' sale con el acento roto."""
    zpl = label_service.render_zpl(_tag(), _size(), None)
    assert "^CI28" in zpl


def test_el_modelo_va_centrado_en_el_pie():
    """El modelo se imprime entre el país (izq) y la fecha (der)."""
    zpl = label_service.render_zpl(_tag(), _size(63, 25), None, _type())
    assert "^FDELITEBOOK 840 G8^FS" in zpl
    foot_y = max(int(m.group(2)) for m in re.finditer(r"\^FO(\d+),(\d+)\^A0N", zpl))
    modelo = re.search(
        rf"\^FO0,{foot_y}\^FB\d+,1,0,C,0\^A0N,\d+,\d+\^FDELITEBOOK 840 G8\^FS", zpl
    )
    assert modelo, "el modelo no quedó centrado a la altura del pie"


def test_sin_modelo_el_pie_no_cambia():
    """Un equipo sin modelo imprime exactamente lo de antes (país + fecha)."""
    assert label_service.render_zpl(_tag(), _size(63, 25), None) == (
        label_service.render_zpl(_tag(), _size(63, 25), None, _type(model=""))
    )


def test_el_modelo_largo_se_recorta_y_no_pisa_pais_ni_fecha():
    """El modelo es el único de largo imprevisible: se acorta, no se encima."""
    largo = "ThinkPad X1 Carbon Gen 11 Ultra Business Edition"
    for width_mm in (30, 38, 50, 63, 100):
        size = _size(width_mm, 25)
        zpl = label_service.render_zpl(_tag(), size, None, _type(model=largo))
        w = _dots(width_mm)
        foot_h = math.floor(_dots(25) * 0.07 + 0.5)
        pad = math.floor(w * 0.04 + 0.5)
        char_w = max(1.0, foot_h * 0.6)

        foot_y = max(int(x.group(2)) for x in re.finditer(r"\^FO(\d+),(\d+)\^A0N", zpl))
        # Solo el bloque centrado a la altura del pie: el encabezado y el serial
        # también van centrados, pero más arriba.
        m = re.search(
            rf"\^FO0,{foot_y}\^FB\d+,1,0,C,0\^A0N,\d+,\d+\^FD([^^]+)\^FS", zpl
        )
        if not m:
            continue  # no cabía: se omite, que es el comportamiento esperado
        model_w = len(m.group(1)) * char_w
        # Va centrado: cada lado libre tiene que dar para el país y la fecha.
        libre = (w - model_w) / 2
        assert libre >= pad + len("PA") * char_w, f"{width_mm}mm: el modelo pisa el país"
        assert libre >= pad + len("01/01/2026") * char_w, (
            f"{width_mm}mm: el modelo pisa la fecha"
        )


def test_la_plantilla_propia_puede_usar_el_modelo():
    size = _size(63, 25, template="^XA^FD{serial}|{model}^FS^XZ")
    zpl = label_service.render_zpl(_tag("ABC123"), size, None, _type())
    assert zpl == "^XA^FDABC123|EliteBook 840 G8^FS^XZ"
