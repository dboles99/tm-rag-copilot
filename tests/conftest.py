import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MINI_TMX = """<?xml version="1.0" encoding="UTF-8"?>
<tmx version="1.4">
  <header creationtool="test" segtype="sentence" adminlang="en" srclang="en" datatype="PlainText"/>
  <body>
    <tu tuid="u1">
      <tuv xml:lang="en"><seg>New Game</seg></tuv>
      <tuv xml:lang="zh-CN"><seg>新游戏</seg></tuv>
    </tu>
    <tu tuid="u2">
      <tuv xml:lang="en"><seg>Settings</seg></tuv>
      <tuv xml:lang="zh-CN"><seg>设置</seg></tuv>
      <tuv xml:lang="zh-TW"><seg>設定</seg></tuv>
    </tu>
    <tu tuid="u3">
      <tuv xml:lang="en"><seg>Welcome, {name}!</seg></tuv>
      <tuv xml:lang="zh-CN"><seg>欢迎,{name}!</seg></tuv>
    </tu>
    <tu tuid="u4">
      <tuv xml:lang="en"><seg>Save Game</seg></tuv>
      <tuv xml:lang="zh-CN"><seg>保存游戏</seg></tuv>
    </tu>
    <tu tuid="u5">
      <tuv xml:lang="en"><seg>Quit Game</seg></tuv>
      <tuv xml:lang="zh-CN"><seg>退出游戏</seg></tuv>
    </tu>
    <tu tuid="u6">
      <tuv xml:lang="en"><seg>You have %d messages</seg></tuv>
      <tuv xml:lang="zh-CN"><seg>你有 %d 条消息</seg></tuv>
    </tu>
  </body>
</tmx>
"""

MINI_TBX = """<?xml version="1.0" encoding="UTF-8"?>
<tbx type="TBX" style="dca">
  <text>
    <body>
      <termEntry id="T1">
        <langSet xml:lang="en"><tig><term>Mana</term></tig></langSet>
        <langSet xml:lang="zh-CN"><tig><term>法力</term><termNote type="forbiddenTerm">魔力</termNote></tig></langSet>
      </termEntry>
      <termEntry id="T2">
        <langSet xml:lang="en"><tig><term>Health Potion</term></tig></langSet>
        <langSet xml:lang="zh-CN"><tig><term>生命药水</term><termNote type="forbiddenTerm">红药水</termNote></tig></langSet>
      </termEntry>
    </body>
  </text>
</tbx>
"""

MINI_GOLD = [
    {"query": "begin a new adventure", "expected_id": "u1"},
    {"query": "change the options", "expected_id": "u2"},
    {"query": "greeting shown to a player", "expected_id": "u3"},
]


@pytest.fixture
def mini_tmx_path(tmp_path):
    path = tmp_path / "mini.tmx"
    path.write_text(MINI_TMX, encoding="utf-8")
    return path


@pytest.fixture
def mini_data_dir(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "tm.tmx").write_text(MINI_TMX, encoding="utf-8")
    (data_dir / "terms.tbx").write_text(MINI_TBX, encoding="utf-8")
    with open(data_dir / "gold.jsonl", "w", encoding="utf-8") as fh:
        for item in MINI_GOLD:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    return data_dir
