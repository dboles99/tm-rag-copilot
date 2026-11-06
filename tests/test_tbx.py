from tm_rag.index import DATA_DIR
from tm_rag.tbx import parse_tbx


def test_parse_entries_and_forbidden(tmp_path):
    path = tmp_path / "terms.tbx"
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<tbx type="TBX" style="dca">
  <text><body>
    <termEntry id="T1">
      <langSet xml:lang="en"><tig><term>Mana</term></tig></langSet>
      <langSet xml:lang="zh-CN"><tig><term>法力</term><termNote type="forbiddenTerm">魔力</termNote><termNote type="forbiddenTerm">魔能</termNote></tig></langSet>
    </termEntry>
  </body></text>
</tbx>
""",
        encoding="utf-8",
    )
    entries = parse_tbx(path)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.source == "Mana"
    assert entry.target == "法力"
    assert entry.forbidden == ["魔力", "魔能"]
    assert entry.id == "T1"
    assert entry.tgt_lang == "zh-CN"


def test_parse_falls_back_to_first_non_source_langset(tmp_path):
    path = tmp_path / "terms.tbx"
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<tbx type="TBX" style="dca">
  <text><body>
    <termEntry id="T9">
      <langSet xml:lang="en"><tig><term>Quit</term></tig></langSet>
      <langSet xml:lang="th"><tig><term>ออก</term></tig></langSet>
    </termEntry>
  </body></text>
</tbx>
""",
        encoding="utf-8",
    )
    entries = parse_tbx(path)
    assert entries[0].target == "ออก"
    assert entries[0].tgt_lang == "th"
    assert entries[0].forbidden == []


def test_parse_real_term_base():
    entries = parse_tbx(DATA_DIR / "terms.tbx")
    assert len(entries) == 32
    assert all(e.source and e.target for e in entries)
    assert all(e.forbidden for e in entries)
