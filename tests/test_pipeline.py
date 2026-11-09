from usreport import hadlock
from usreport.extract import compare, extract
from usreport.synth import make_sample
from usreport.validate import validate


def test_hadlock_matches_real_report():
    # Values read off the real screenshot (IMG_5701 START.png)
    assert hadlock.weeks_to_wd(hadlock.ga_bpd(4.504)) == (19, 4)
    assert hadlock.weeks_to_wd(hadlock.ga_ac(14.783)) == (20, 0)
    assert hadlock.weeks_to_wd(hadlock.ga_fl(3.018)) == (19, 2)
    assert round(hadlock.efw_grams(14.783, 4.504, 3.018, 16.962)) == 308


def test_synthetic_truth_is_self_consistent():
    for seed in range(20):
        _, truth = make_sample(seed, "cm" if seed % 2 else "mm")
        assert validate(truth["values"], truth["repeats"]) == {}


def test_clean_mm_and_cm_roundtrip():
    for unit in ("mm", "cm"):
        img, truth = make_sample(1, unit, photo=False)
        ok = compare(extract(img)["values"], truth["values"])
        assert all(ok.values()), [k for k, v in ok.items() if not v]


def test_validator_catches_unit_error():
    _, truth = make_sample(3)
    issues = validate(dict(truth["values"], bpd_mm=4.5))  # cm typed into an mm field
    assert any(i["level"] == "error" for i in issues["A"])


def test_validator_catches_bad_efw_and_survives_garbage():
    _, truth = make_sample(3)
    assert "U" in validate(dict(truth["values"], efw_g=900))
    validate(dict(truth["values"], hc_mm=1e30, ac_mm=-5, fl_mm=0))  # must not raise


def test_parse_real_photo_ocr_lines():
    """Verbatim Tesseract output from the first real photo (measurements only, no PHI).
    Guards the OCR-noise handling: glued units, 'A'/'é' for digits, dropped decimals."""
    from usreport.extract import parse
    texts = [
        "308g (1102) 245g 19wéd h—t+—ji 13.7%",
        "BPD {Hodlock} a 45.04mm' 4495 _][_4523_] Tove] K++ 18.3% 19w4d",
        "HC (Hodlock) a 169.62 mm{_ 16757 |[_17166 |[ [avg] Fe-+—1 10.5% 19wAd",
        "AC WHadlock) a 147.83 mm[_143,01_|[_147.66 |[_ I-11 316% 20w0d",
        "FL Hodlock} t 30.18mm{_29.91_|{_30.44 [ovg.] K-41 10.5% 19w2d",
        "HL Veanty) a 30.67mm__30.67 ][___| [ova] L/-+++1 40.0% 2owid",
        "Cored (Hill) a 2119mmi “2119 ][______[eva.| F- +4 58.8% 2owad",
    ]
    v, _, _, notes = parse([dict(text=t, conf=90, words=[]) for t in texts])
    assert (v["bpd_mm"], v["bpd_w"], v["bpd_d"]) == (45.04, 19, 4)
    assert (v["hc_mm"], v["hc_w"], v["hc_d"]) == (169.62, 19, 4)
    assert (v["ac_mm"], v["ac_w"], v["ac_d"], v["ac_pct"]) == (147.83, 20, 0, 31.6)
    assert (v["fl_mm"], v["fl_w"], v["fl_d"]) == (30.18, 19, 2)
    assert (v["hl_mm"], v["hl_w"], v["hl_d"]) == (30.67, 20, 1)
    assert (v["efw_g"], v["efw_pct"]) == (308, 13.7)
    assert v["tcd_mm"] == 21.19 and "tcd_mm" in notes and "ac_pct" in notes  # inferred values are flagged
    assert v["tcd_d"] is None  # unreadable day is left empty, never guessed


def test_slot_letters_match_labeled_screenshots():
    from usreport.schema import SLOT_BY_LETTER, SLOTS
    assert [s.letter for s in SLOTS] == [chr(c) for c in range(ord("A"), ord("W") + 1)]
    assert all(s.source for s in SLOTS)
    expect = {"A": "bpd_mm", "B": "bpd_w", "C": "bpd_d", "D": "hc_mm", "G": "ac_mm", "J": "fl_mm", "M": "hl_mm",
              "P": "tcd_mm", "Q": "tcd_w", "R": "tcd_d", "S": "us_w", "T": "us_d", "U": "efw_g", "V": "efw_pct",
              "W": "ac_pct"}
    assert {k: SLOT_BY_LETTER[k].key for k in expect} == expect


def test_age_wwwddd_splits_into_week_and_day_slots():
    from usreport.extract import parse
    values, *_ = parse([dict(text="BPD (Hadlock) 45.04 mm 44.85 45.23 avg. 18.3% 19w4d", conf=90, words=[])])
    assert (values["bpd_w"], values["bpd_d"]) == (19, 4)
