"""Two-engine OCR (RapidOCR reads, Tesseract checks): it must only ADD flags, never change a value, fall back to
the working engine when one fails, and flag every disagreement. Synthetic pages only."""
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


def _boom(*a):
    raise RuntimeError("engine failed")


def _setup(monkeypatch, rapid=None, rapid_error=False, unavailable=None):
    """Fake engines: `rapid` is what RapidOCR reads, the tesseract callable is passed to run()."""
    monkeypatch.setattr(crosscheck, "unavailable", lambda: unavailable)
    monkeypatch.setattr(crosscheck, "read", _boom if rapid_error else (lambda img: rapid))


def test_rapidocr_is_primary_and_tesseract_checks_it(monkeypatch):
    _setup(monkeypatch, rapid=_result(efw_g=445, bpd_mm=45.0))
    r = crosscheck.run(None, lambda img: _result(efw_g=448, bpd_mm=45.0))
    assert r["values"]["efw_g"] == 445  # the reviewer sees RapidOCR's value, never Tesseract's
    assert r["crosscheck"] == dict(status="ok", primary="rapidocr", disagree=["U"])
    assert "448" in r["issues"]["U"][0]["msg"]


def test_a_box_RapidOCR_left_empty_is_not_filled_from_tesseract(monkeypatch):
    _setup(monkeypatch, rapid=_result(ac_d=None))
    r = crosscheck.run(None, lambda img: _result(ac_d=6))
    assert r["values"]["ac_d"] is None and r["crosscheck"]["disagree"] == ["I"]  # flagged, not guessed


def test_off_by_env_var_uses_tesseract_alone(monkeypatch):
    monkeypatch.setenv("USREPORT_CROSSCHECK", "0")
    _setup(monkeypatch, rapid_error=True)  # would fail if called
    r = crosscheck.run(None, lambda img: _result(efw_g=1))
    assert r["values"]["efw_g"] == 1 and r["crosscheck"]["status"] == "off" and r["issues"] == {}


def test_missing_rapidocr_falls_back_to_tesseract(monkeypatch):
    _setup(monkeypatch, unavailable="RapidOCR is not installed")
    r = crosscheck.run(None, lambda img: _result(efw_g=1))
    assert r["values"]["efw_g"] == 1 and r["crosscheck"]["status"] == "unavailable" and r["issues"] == {}


def test_rapidocr_crash_falls_back_to_tesseract(monkeypatch):
    _setup(monkeypatch, rapid_error=True)
    r = crosscheck.run(None, lambda img: _result(efw_g=1))
    assert r["values"]["efw_g"] == 1 and r["crosscheck"]["status"] == "error" and r["crosscheck"]["primary"] == "tesseract"


def test_tesseract_crash_keeps_rapidocr_values_without_a_check(monkeypatch):
    _setup(monkeypatch, rapid=_result(efw_g=445))
    r = crosscheck.run(None, _boom)
    assert r["values"]["efw_g"] == 445 and r["crosscheck"]["status"] == "error" and r["crosscheck"]["primary"] == "rapidocr"


@needs_rapidocr
@pytest.mark.parametrize("unit,seed,key", [("mm", 20018, "efw_g"), ("cm", 20072, "ac_d")])
def test_pages_where_tesseract_alone_made_a_silent_error(unit, seed, key):
    """Tesseract 4.1 on the dev machine read these fields wrong without a flag (tools/bench_flags.py, 2026-11-17).
    Other Tesseract versions read them differently, so the test checks invariants, not that Tesseract is wrong."""
    img, truth = make_sample(seed, unit, False, 0)
    letter = SLOT_BY_KEY[key].letter
    both = extract(img)
    assert both["crosscheck"]["status"] == "ok" and both["crosscheck"]["primary"] == "rapidocr"
    assert both["values"] == crosscheck.read(img)["values"]  # the values are RapidOCR's, unchanged by the check
    right = compare(both["values"], truth["values"])[key]
    assert right or letter in both["issues"] or letter in both["low_conf"]  # right, or flagged: never silent
    tess = extract(img, crosscheck=False)
    assert tess["crosscheck"]["primary"] == "tesseract"
    if tess["values"][key] != both["values"][key]:
        assert letter in both["crosscheck"]["disagree"]  # whenever the engines differ, the reviewer is told
