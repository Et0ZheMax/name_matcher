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
