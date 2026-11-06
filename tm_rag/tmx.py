"""Parse TMX 1.4 translation memories into TranslationUnit records.

A <tu> may carry several <tuv> language variants. The variant matching the
header srclang (or the first variant when the header omits it) is the source;
each remaining variant becomes its own TranslationUnit. When a <tu> has a
single target variant the unit keeps the plain tuid; extra variants get a
"<tuid>@<lang>" id so every unit id stays unique.
"""

from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


@dataclass
class TranslationUnit:
    source: str
    target: str
    src_lang: str
    tgt_lang: str
    id: str = ""


def _tuv_text(tuv: ET.Element) -> str:
    seg = tuv.find("seg")
    if seg is None:
        return ""
    return "".join(seg.itertext()).strip()


def parse_tmx(path: str | Path) -> list[TranslationUnit]:
    """Parse a TMX 1.4 file into a list of TranslationUnit."""
    root = ET.parse(str(path)).getroot()
    header = root.find("header")
    header_src = header.get("srclang") if header is not None else None

    units: list[TranslationUnit] = []
    for tu in root.iter("tu"):
        tuid = tu.get("tuid") or tu.get("id") or ""
        variants: list[tuple[str, str]] = []
        for tuv in tu.findall("tuv"):
            lang = tuv.get(XML_LANG) or tuv.get("lang") or ""
            variants.append((lang, _tuv_text(tuv)))
        if not variants:
            continue
        src_lang = header_src or variants[0][0]
        source = next((text for lang, text in variants if lang == src_lang), None)
        if source is None:
            continue
        targets = [(lang, text) for lang, text in variants if lang != src_lang and text]
        for index, (tgt_lang, target) in enumerate(targets):
            if len(targets) == 1:
                uid = tuid
            elif index == 0:
                uid = tuid
            else:
                uid = f"{tuid}@{tgt_lang}"
            units.append(
                TranslationUnit(
                    source=source,
                    target=target,
                    src_lang=src_lang,
                    tgt_lang=tgt_lang,
                    id=uid,
                )
            )
    return units


def load_units(path: str | Path) -> list[TranslationUnit]:
    """Alias for parse_tmx kept for readability at call sites."""
    return parse_tmx(path)
