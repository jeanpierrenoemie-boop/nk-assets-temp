"""Générateur PDF minimaliste (stdlib uniquement, pas de dépendance externe).

Charte NK-SYSTEMS noir/or : logo NK-SYSTEMS en en-tête sur bande or,
filigrane logo pâle incliné au centre de chaque page, titres or sombre,
pied de page avec les coordonnées de Noémie K. Multi-pages, diagnostic
PUBLIC uniquement (jamais le brief admin ni 7/30/90).
"""
from __future__ import annotations

import os
import struct
import textwrap

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_PATH = os.path.join(BASE, "static", "img", "logo-noemiek.jpg")
WM_PATH = os.path.join(BASE, "static", "img", "watermark.jpg")

PIED = "NK-SYSTEMS.IA  ·  noemie-k.fr  ·  contact@noemie-k.fr  ·  SIRET 794 778 365 00013  ·  TVA non applicable"

# Couleurs (RGB 0-1) : or #d4af37, or sombre #a8842a, noir #14100a, gris #6b665c
OR = "0.831 0.686 0.216"
OR_SOMBRE = "0.659 0.518 0.165"
NOIR = "0.078 0.063 0.039"
GRIS = "0.42 0.40 0.36"

_caches = {}


def _read(path: str) -> bytes:
    if path not in _caches:
        try:
            with open(path, "rb") as f:
                _caches[path] = f.read()
        except OSError:
            _caches[path] = b""
    return _caches[path]


def _jpeg_dims(data: bytes):
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            break
        marker = data[i + 1]
        if marker in (0xC0, 0xC2):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    return None, None


def _esc(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _latin(text: str) -> str:
    repl = {"…": "...", "’": "'", "«": "\u00ab", "»": "\u00bb", "—": "-", "–": "-", "→": "->", "°": "\u00b0", "€": "\u20ac"}
    for k, v in repl.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")


def _wrap_lines(sections):
    out = []
    for sec_title, sec_lines in sections:
        out.append(("h", _latin(sec_title)))
        for ln in sec_lines:
            for wrapped in textwrap.wrap(_latin(ln), width=88):
                out.append(("b", wrapped))
        out.append(("b", ""))
    return out


def _page_content(title: str, items, first: bool):
    parts = []
    # filigrane : logo pâle incliné, DERRIERE le texte (image ~400x50 pt, ~18 deg)
    wm = _read(WM_PATH)
    if wm:
        a_, b_, c_, d_ = 380.0, 123.6, -15.45, 47.55
        e_ = 297 - (a_ + c_) / 2
        f_ = 450 - (b_ + d_) / 2
        parts.append(f"q {a_} {b_:.2f} {c_} {d_:.2f} {e_:.2f} {f_:.2f} cm /WM Do Q")
    if first:
        parts.append(f"q {OR} rg 0 792 595 50 re f Q")
        tx = 50
        if _read(LOGO_PATH):
            parts.append("q 44 0 0 44 50 794 cm /Logo Do Q")
            tx = 104
        parts.append(f"BT {NOIR} rg 1 0 0 1 {tx} 812 Tm /F2 15 Tf (NK-SYSTEMS) Tj /F1 15 Tf (.IA) Tj ET")
        parts.append(f"BT {NOIR} rg 1 0 0 1 50 756 Tm /F2 16 Tf ({_esc(title)}) Tj ET")
        parts.append(f"q {OR} RG 1.2 w 50 746 m 545 746 l S Q")
        y = 724
    else:
        parts.append(f"BT {OR_SOMBRE} rg 1 0 0 1 50 812 Tm /F2 12 Tf ({_esc(title.upper())}) Tj ET")
        y = 790
    drawn = 0
    for kind, text in items:
        if kind == "h":
            if y < 90:
                break
            parts.append(f"q {OR_SOMBRE} RG 1 w 50 {y + 3} m 60 {y + 3} l S Q")
            parts.append(f"BT {OR_SOMBRE} rg 1 0 0 1 50 {y} Tm /F2 12 Tf ({_esc(text.upper())}) Tj ET")
            y -= 22
            drawn += 1
        else:
            if y < 72:
                break
            parts.append(f"BT {NOIR} rg 1 0 0 1 50 {y} Tm /F1 9 Tf ({_esc(text)}) Tj ET")
            y -= 13
            drawn += 1
    parts.append(f"q {OR} RG 0.8 w 50 52 m 545 52 l S Q")
    parts.append(f"BT {GRIS} rg 1 0 0 1 50 38 Tm /F1 7.5 Tf ({_esc(PIED)}) Tj ET")
    return "\n".join(parts), drawn


def build_pdf(title: str, sections) -> bytes:
    items = _wrap_lines(sections)
    pages_content = []
    idx, first = 0, True
    while idx < len(items) or first:
        content, drawn = _page_content(title, items[idx:], first)
        if drawn == 0 and not first:
            break
        pages_content.append(content)
        idx += drawn
        first = False
        if idx >= len(items):
            break

    n = len(pages_content)
    logo = _read(LOGO_PATH)
    wm = _read(WM_PATH)
    page_ids = [5 + i * 2 for i in range(n)]
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{' '.join(str(p) + ' 0 R' for p in page_ids)}] /Count {n} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    ]
    xobj = ""
    img_objects = []
    next_id = 5 + n * 2
    if logo:
        w, h = _jpeg_dims(logo)
        xobj += f"/Logo {next_id} 0 R "
        img_objects.append(
            f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceRGB "
            f"/BitsPerComponent 8 /Filter /DCTDecode /Length {len(logo)} >>\nstream\n".encode() + logo + b"\nendstream"
        )
        next_id += 1
    if wm:
        w, h = _jpeg_dims(wm)
        xobj += f"/WM {next_id} 0 R "
        img_objects.append(
            f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceRGB "
            f"/BitsPerComponent 8 /Filter /DCTDecode /Length {len(wm)} >>\nstream\n".encode() + wm + b"\nendstream"
        )
    res = f"<< /Font << /F1 3 0 R /F2 4 0 R >> /XObject << {xobj}>> >>" if xobj else "<< /Font << /F1 3 0 R /F2 4 0 R >> >>"
    for content in pages_content:
        cbytes = content.encode("latin-1", "replace")
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources {res} /Contents {len(objects) + 2} 0 R >>".encode()
        )
        objects.append(b"<< /Length " + str(len(cbytes)).encode() + b" >>\nstream\n" + cbytes + b"\nendstream")
    objects.extend(img_objects)

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    return bytes(out)


def diagnostic_pdf(diag: dict) -> bytes:
    sections = [
        ("Votre situation", [diag["summary"]]),
        ("Faits déclarés", [f["statement"] for f in diag["facts"]]),
        ("Vos priorités", [f"{p['rank']}. {p['finding']} - {p['why_it_matters']}" for p in diag["priorities"]]),
        ("Vos 3 opportunités IA", [
            f"{o['rank']}. {o['title']} : {o['problem']} Solution envisagée : {o['conceptual_solution']} "
            f"Bénéfice possible : {o['potential_benefit']}"
            for o in diag["opportunities"]
        ]),
        ("Synthèse", [diag["executive_insights"]["top_leverage"], diag["executive_insights"]["orientation"]]),
        ("Prochaine étape", [diag["meeting_bridge"]["personalized_reason"]]),
    ]
    return build_pdf("Diagnostic IA personnalisé", sections)
