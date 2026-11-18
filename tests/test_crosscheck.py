"""The second-engine cross-check: it must only ADD flags, must never break extraction, and must catch the
silent errors Tesseract alone made in tools/bench_flags.py. Synthetic pages only."""
import pytest

from usreport import crosscheck
from usreport.extract import compare, extract
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
def test_pipeline_leaves_no_silent_error_on_pages_tesseract_alone_failed(unit, seed, key):
    """With the Tesseract 4.1 on the dev machine these pages gave a wrong, unflagged value (tools/bench_flags.py,
    2026-11-17). Other Tesseract versions read them differently, so the test checks the invariant, not that
    Tesseract is wrong: after the cross-check the field is either right or flagged, and no value changes."""
    img, truth = make_sample(seed, unit, False, 0)
    letter = SLOT_BY_KEY[key].letter
    alone = extract(img, crosscheck=False)
    both = extract(img)
    assert both["crosscheck"]["status"] == "ok"
    assert both["values"] == alone["values"]  # the cross-check adds flags and never changes a value
    right = compare(both["values"], truth["values"])[key]
    assert right or letter in both["issues"] or letter in both["low_conf"]
    if alone["values"][key] != truth["values"][key] and letter not in alone["issues"]:
        assert letter in both["crosscheck"]["disagree"]  # a silent error is caught by the second engine
