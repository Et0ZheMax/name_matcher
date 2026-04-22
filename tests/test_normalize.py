from app.pipeline.normalize import normalize_org_name


def test_normalize_replaces_common_abbrev() -> None:
    n = normalize_org_name('  ФГБОУ ВО "МГУ им. Ломоносова"  ')
    assert "федеральное государственное бюджетное образовательное учреждение" in n.normalized
    assert "имени" in n.normalized
    assert n.raw.startswith("ФГБОУ")


def test_normalize_collapses_spaces() -> None:
    n = normalize_org_name("Институт   химии   СО   РАН")
    assert "  " not in n.normalized
    assert "сибирское отделение" in n.normalized


def test_normalize_extracts_service_parts() -> None:
    n = normalize_org_name("Филиал ФГБУН Институт катализа СО РАН им. Г.К. Борескова")
    assert "branch" in n.service_parts
    assert "ran_branch" in n.service_parts
    assert "имени" not in n.core_text
    assert n.search_text
