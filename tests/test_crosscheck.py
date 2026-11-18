"""The second-engine cross-check: it must only ADD flags, must never break extraction, and must catch the
silent errors Tesseract alone made in tools/bench_flags.py. Synthetic pages only."""
import pytest

from usreport import crosscheck
from usreport.extract import extract
from usreport.schema import SLOT_BY_KEY
from usreport.synth import make_sample

needs_rapidocr = pytest.mark.skipif(crosscheck.unavailable() is not None, reason="RapidOCR not installed")


def _result(**values):
    from usreport.schema import SLOTS
    return dict(values={s.key: values.get(s.key) for s in SLOTS}, issues={})


def test_flags_only_fields_where_engines_differ():
    first, second = _result(efw_g=448, bpd_mm=45.0, ac_d=None), _result(efw_g=445, bpd_mm=45.0, ac_d=None)
    assert crosscheck.flag_disagreements(first, second) == ["U"]
    (issue,) = first["issues"]["U"]
    assert issue["level"] == "warn" and "448" in issue["msg"] and "445" in issue["msg"]
    assert "A" not in first["issues"]  # agreeing field untouched; both-unread is not a disagreement


def test_one_engine_not_reading_a_field_is_flagged():
    first, second = _result(ac_d=None), _result(ac_d=2)
    assert crosscheck.flag_disagreements(first, second) == ["I"]
    first, second = _result(ac_d=6), _result(ac_d=None)
    assert crosscheck.flag_disagreements(first, second) == ["I"]


def test_off_by_env_var(monkeypatch):
    monkeypatch.setenv("USREPORT_CROSSCHECK", "0")
    r = crosscheck.apply(_result(efw_g=1), img=None)
    assert r["crosscheck"]["status"] == "off" and r["issues"] == {}


def test_missing_engine_degrades_instead_of_failing(monkeypatch):
    monkeypatch.setattr(crosscheck, "unavailable", lambda: "RapidOCR is not installed")
    r = crosscheck.apply(_result(efw_g=1), img=None)
    assert r["crosscheck"]["status"] == "unavailable" and r["issues"] == {}


def test_engine_crash_degrades_instead_of_failing(monkeypatch):
    monkeypatch.setattr(crosscheck, "unavailable", lambda: None)
    monkeypatch.setattr(crosscheck, "read", lambda img: 1 / 0)
    r = crosscheck.apply(_result(efw_g=1), img=None)
    assert r["crosscheck"]["status"] == "error" and r["issues"] == {}


@needs_rapidocr
@pytest.mark.parametrize("unit,seed,key", [("mm", 20018, "efw_g"), ("cm", 20072, "ac_d")])
def test_catches_silent_errors_tesseract_alone_makes(unit, seed, key):
    """Tesseract alone misreads this field and flags nothing (found by tools/bench_flags.py on 2026-11-17)."""
    img, truth = make_sample(seed, unit, False, 0)
    letter = SLOT_BY_KEY[key].letter
    alone = extract(img, crosscheck=False)
    assert alone["values"][key] != truth["values"][key] and letter not in alone["issues"]  # the silent error
    both = extract(img)
    assert both["crosscheck"]["status"] == "ok"
    assert letter in both["crosscheck"]["disagree"]
    assert any("second OCR engine" in i["msg"] for i in both["issues"][letter])
    assert both["values"] == alone["values"]  # the cross-check adds flags and never changes a value
