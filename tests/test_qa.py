from tm_rag.qa import (
    all_passed,
    check_character_limit,
    check_forbidden_terms,
    check_numbers,
    check_placeholders,
    check_required_terms,
    check_tags,
    required_terms,
    run_qa,
)
from tm_rag.tbx import TermEntry

MANA = TermEntry(source="Mana", target="法力", forbidden=["魔力"], id="T1")
POTION = TermEntry(source="Health Potion", target="生命药水", forbidden=["红药水"], id="T2")
TERMS = [MANA, POTION]


def _by_check(findings):
    return {f.check: f for f in findings}


def test_good_translation_passes_all_checks():
    source = "Welcome, {name}! You have 3 messages. <b>New</b> quest."
    translation = "欢迎,{name}!你有 3 条消息。<b>新</b>任务。"
    findings = run_qa(source, translation, TERMS)
    assert len(findings) == 6
    assert all_passed(findings), [f for f in findings if not f.passed]


def test_required_term_used_when_source_mentions_term():
    source = "Costs 20 mana"
    translation = "消耗 20 点法力"
    findings = _by_check(run_qa(source, translation, TERMS))
    assert findings["required_term_used"].passed
    assert findings["number_preservation"].passed
    assert required_terms(source, TERMS) == [MANA]


def test_missing_placeholder_fails():
    finding = check_placeholders("Welcome, {name}!", "欢迎!")
    assert not finding.passed
    assert "{name}" in finding.detail


def test_missing_tag_fails():
    finding = check_tags("<b>Warning:</b> boss", "<b>警告:</b>首领")
    assert finding.passed
    finding = check_tags("<b>Warning:</b> boss", "警告:首领")
    assert not finding.passed


def test_missing_number_fails():
    finding = check_numbers("Level %d is 5", "等级 %d 是 6")
    assert not finding.passed
    assert "5" in finding.detail
    assert check_numbers("Level 5", "等级 5").passed


def test_forbidden_term_present_fails():
    finding = check_forbidden_terms("消耗 20 点魔力", TERMS)
    assert not finding.passed
    assert "魔力" in finding.detail
    assert check_forbidden_terms("消耗 20 点法力", TERMS).passed


def test_required_term_missing_fails():
    finding = check_required_terms("Costs 20 mana", "消耗 20 点能量", TERMS)
    assert not finding.passed
    assert "法力" in finding.detail


def test_character_limit():
    assert check_character_limit("你好", 5).passed
    finding = check_character_limit("你好呀朋友", 4)
    assert not finding.passed
    assert "5/4" in finding.detail
    assert check_character_limit("anything", None).passed


def test_run_qa_reports_each_failure_independently():
    source = "Mana: {amount} <b>20</b>"
    translation = "魔力: 能量"  # drops placeholder, tag and number; uses forbidden term; misses required term
    findings = _by_check(run_qa(source, translation, TERMS))
    assert not findings["placeholder_preservation"].passed
    assert not findings["tag_preservation"].passed
    assert not findings["number_preservation"].passed
    assert not findings["forbidden_term_absent"].passed
    assert not findings["required_term_used"].passed
    assert findings["character_limit"].passed
    assert not all_passed(run_qa(source, translation, TERMS))
