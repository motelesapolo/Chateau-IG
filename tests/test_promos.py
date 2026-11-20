from datetime import date

from autopilot import config, promos

P = [{"titulo": "Martes de jacuzzi", "detalle": "Jacuzzi 3 horas a $40.000", "desde": "2026-12-01",
      "hasta": "2026-12-08", "condiciones": "Solo martes"},
     {"titulo": "Secreta", "detalle": "X", "desde": "2026-12-01", "hasta": "2026-12-31", "mencionar": "si_preguntan"}]


def test_active_by_date():
    assert [p["titulo"] for p in promos.active(date(2026, 12, 8), P)] == ["Martes de jacuzzi", "Secreta"]
    assert [p["titulo"] for p in promos.active(date(2026, 12, 9), P)] == ["Secreta"]
    assert promos.active(date(2026, 11, 30), P) == []


def test_markdown_without_promos_says_none():
    md = promos.as_markdown(date(2026, 11, 20), [])
    assert "No hay promociones vigentes" in md
    md = promos.as_markdown(date(2026, 12, 2), P)
    assert "Martes de jacuzzi" in md and "Solo confirmarla si el cliente pregunta" in md


def test_validate():
    assert promos.validate(P) == []
    assert promos.validate([{"titulo": "x", "detalle": "y", "desde": "2026-12-10", "hasta": "2026-12-01"}])
    assert promos.validate([{"titulo": "x"}])


def test_repo_file_is_valid_and_persona_gets_promos():
    assert promos.validate() == []
    text = config.load_persona()
    assert "Promociones vigentes hoy" in text and "6x3" not in text
