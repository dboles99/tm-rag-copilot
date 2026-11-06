"""Parse a TBX term base into TermEntry records.

Each <termEntry> carries one source <langSet> (English by default) and one or
more target <langSet> elements. The target language defaults to zh-CN and falls
back to the first non-source langSet. Alternative target terms marked with
<termNote type="forbiddenTerm"> inside the target tig are collected as
forbidden strings: translations that must not use them.
"""

from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
FORBIDDEN_NOTE_TYPE = "forbiddenTerm"


@dataclass
class TermEntry:
    source: str
    target: str
    forbidden: list[str] = field(default_factory=list)
    id: str = ""
    tgt_lang: str = ""


def parse_tbx(
    path: str | Path,
    src_lang: str = "en",
    tgt_lang: str = "zh-CN",
) -> list[TermEntry]:
    """Parse a TBX file into TermEntry records."""
    root = ET.parse(str(path)).getroot()
    entries: list[TermEntry] = []
    for term_entry in root.iter("termEntry"):
        lang_sets: dict[str, ET.Element] = {}
        for lang_set in term_entry.findall("langSet"):
            lang = lang_set.get(XML_LANG) or lang_set.get("lang") or ""
            if lang:
                lang_sets[lang] = lang_set
        source_set = lang_sets.get(src_lang)
        if source_set is None:
            continue
        source_tig = source_set.find("tig")
        if source_tig is None or not (source_tig.findtext("term") or "").strip():
            continue
        source = source_tig.findtext("term").strip()

        target_set = lang_sets.get(tgt_lang)
        if target_set is None:
            for lang, lang_set in lang_sets.items():
                if lang != src_lang:
                    target_set = lang_set
                    tgt_lang_used = lang
                    break
            else:
                continue
        else:
            tgt_lang_used = tgt_lang
        target_tig = target_set.find("tig")
        if target_tig is None:
            continue
        target = (target_tig.findtext("term") or "").strip()
        if not target:
            continue
        forbidden = [
            (note.text or "").strip()
            for note in target_tig.findall("termNote")
            if note.get("type") == FORBIDDEN_NOTE_TYPE and (note.text or "").strip()
        ]
        entries.append(
            TermEntry(
                source=source,
                target=target,
                forbidden=forbidden,
                id=term_entry.get("id") or "",
                tgt_lang=tgt_lang_used,
            )
        )
    return entries
