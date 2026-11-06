from tm_rag.index import DATA_DIR
from tm_rag.tmx import parse_tmx


def test_parse_single_target_unit(mini_tmx_path):
    units = parse_tmx(mini_tmx_path)
    by_id = {u.id: u for u in units}
    u1 = by_id["u1"]
    assert u1.source == "New Game"
    assert u1.target == "新游戏"
    assert u1.src_lang == "en"
    assert u1.tgt_lang == "zh-CN"
    assert u1.id == "u1"


def test_parse_multi_target_unit_gets_lang_suffix(mini_tmx_path):
    units = parse_tmx(mini_tmx_path)
    by_id = {u.id: u for u in units}
    assert by_id["u2"].target == "设置"
    assert by_id["u2"].tgt_lang == "zh-CN"
    assert by_id["u2@zh-TW"].target == "設定"
    assert by_id["u2@zh-TW"].tgt_lang == "zh-TW"
    assert by_id["u2@zh-TW"].source == "Settings"


def test_parse_keeps_placeholders_and_count(mini_tmx_path):
    units = parse_tmx(mini_tmx_path)
    assert len(units) == 7
    by_id = {u.id: u for u in units}
    assert by_id["u3"].source == "Welcome, {name}!"
    assert by_id["u6"].source == "You have %d messages"
    ids = [u.id for u in units]
    assert len(set(ids)) == len(ids)


def test_parse_real_data_file():
    units = parse_tmx(DATA_DIR / "tm.tmx")
    assert len(units) == 133
    assert all(u.src_lang == "en" for u in units)
    ids = [u.id for u in units]
    assert len(set(ids)) == len(ids)
    langs = {u.tgt_lang for u in units}
    assert langs == {"zh-CN", "zh-TW", "th"}
