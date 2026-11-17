"""OCR engines for tools/bakeoff.py. Each returns the same result dict as usreport.extract.extract(),
because every engine's text goes through the SAME label-anchored parser and validator. So the bake-off
compares recognition quality, not parsing.

All engines are local/offline. An engine whose package is missing reports why and is skipped.
Adapters for apple_vision, rapidocr, paddleocr and easyocr follow those packages' documented output
formats; check each against your installed version the first time you run it.
"""
import platform

import cv2
import numpy as np
from PIL import Image

from usreport import extract as ex


def split_words(text, x0, x1, cy, h, conf):
    """One detected text line with a box -> word dicts, x positions spread by character offset."""
    total, pos, out = max(len(text), 1), 0, []
    for tok in text.split():
        i = text.index(tok, pos)
        pos = i + len(tok)
        out.append(dict(t=tok, x=x0 + (x1 - x0) * i / total, w=(x1 - x0) * len(tok) / total, cy=cy, h=h, conf=conf))
    return out


def poly_words(items):
    """items: (text, polygon points, confidence 0-1) -> word dicts."""
    words = []
    for text, pts, conf in items:
        p = np.asarray(pts, dtype=float).reshape(-1, 2)
        x0, y0, x1, y1 = p[:, 0].min(), p[:, 1].min(), p[:, 0].max(), p[:, 1].max()
        words += split_words(str(text), x0, x1, (y0 + y1) / 2, y1 - y0, float(conf) * 100)
    return words


class Engine:
    name = ""
    note = ""

    def unavailable(self):
        """None when usable, else the reason it is not."""
        return None

    def run(self, img):
        raise NotImplementedError


class TessCurrent(Engine):
    name, note = "tess_current", "what the app does today: upscale, blur, adaptive threshold, deskew"

    def run(self, img):
        return ex.extract(img)


class TessNoBlur(Engine):
    name = "tess_noblur"
    note = "current pipeline minus the Gaussian blur, Lanczos instead of cubic upscale (tests whether smoothing hurts digits)"
    # Tried and dropped: plain grayscale and a global Otsu threshold both read 0% on this page. It is light text
    # on a mid-gray panel inside a dark border, so a global threshold separates panel from border, not text from
    # panel, and Tesseract garbles the row labels the parser anchors on. The local (adaptive) threshold is needed.

    def run(self, img):
        g = cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2GRAY)
        scale = min(3.0, max(0.5, 2400 / g.shape[1]))
        g = cv2.resize(g, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
        if g.mean() < 110:
            g = 255 - g
        bw = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 51, 10)
        pre = Image.fromarray(ex._deskew(bw))
        return ex.extract_lines([ex.ocr_lines(pre, psm) for psm in (6, 11)], pre=pre)


class _Words(Engine):
    """Engines that detect text lines with boxes; one pass, parsed by the shared parser."""

    def words(self, img):
        raise NotImplementedError

    def run(self, img):
        return ex.extract_lines([ex.group_words(self.words(img))])


class AppleVision(_Words):
    name, note = "apple_vision", "macOS Vision framework via ocrmac (offline, Mac only)"

    def unavailable(self):
        if platform.system() != "Darwin":
            return "needs macOS"
        try:
            import ocrmac  # noqa: F401
        except ImportError:
            return "pip install ocrmac"

    def words(self, img):
        from ocrmac import ocrmac
        W, H = img.size
        out = []
        for text, conf, (x, y, w, h) in ocrmac.OCR(img.convert("RGB"), recognition_level="accurate").recognize():
            out += split_words(text, x * W, (x + w) * W, (1 - (y + h / 2)) * H, h * H, conf * 100)  # y is from the bottom
        return out


class RapidOCR(_Words):
    name, note = "rapidocr", "PaddleOCR models on ONNX runtime (pip install rapidocr-onnxruntime)"
    _eng = None

    def unavailable(self):
        try:
            self._load()
        except ImportError:
            return "pip install rapidocr-onnxruntime"

    def _load(self):
        if RapidOCR._eng is None:
            try:
                from rapidocr_onnxruntime import RapidOCR as R
                RapidOCR._eng = ("v1", R())
            except ImportError:
                from rapidocr import RapidOCR as R
                RapidOCR._eng = ("v3", R())
        return RapidOCR._eng

    def words(self, img):
        ver, eng = self._load()
        arr = np.asarray(img.convert("RGB"))[:, :, ::-1]  # BGR
        if ver == "v1":
            res, _ = eng(arr)
            return poly_words([(t, box, float(s)) for box, t, s in (res or [])])
        out = eng(arr)
        if out.boxes is None:
            return []
        return poly_words(list(zip(out.txts, out.boxes, out.scores)))


class PaddleOCR(_Words):
    name, note = "paddleocr", "PaddleOCR (pip install paddlepaddle paddleocr); heavier install"
    _eng = None

    def unavailable(self):
        try:
            import paddleocr  # noqa: F401
        except ImportError:
            return "pip install paddlepaddle paddleocr"

    def words(self, img):
        import paddleocr
        arr = np.asarray(img.convert("RGB"))
        if PaddleOCR._eng is None:
            try:
                PaddleOCR._eng = paddleocr.PaddleOCR(use_doc_orientation_classify=False, use_doc_unwarping=False,
                                                     use_textline_orientation=False)  # 3.x
            except TypeError:
                PaddleOCR._eng = paddleocr.PaddleOCR(use_angle_cls=False, lang="en", show_log=False)  # 2.x
        eng = PaddleOCR._eng
        if hasattr(eng, "predict"):  # 3.x
            items = []
            for page in eng.predict(arr):
                items += list(zip(page["rec_texts"], page["rec_polys"], page["rec_scores"]))
            return poly_words(items)
        res = eng.ocr(arr, cls=False)  # 2.x: [[ [box, (text, score)], ... ]]
        return poly_words([(t, box, s) for box, (t, s) in (res[0] or [])])


class EasyOCR(_Words):
    name, note = "easyocr", "EasyOCR (pip install easyocr); pulls in torch"
    _eng = None

    def unavailable(self):
        try:
            import easyocr  # noqa: F401
        except ImportError:
            return "pip install easyocr"

    def words(self, img):
        import easyocr
        if EasyOCR._eng is None:
            EasyOCR._eng = easyocr.Reader(["en"], gpu=False, verbose=False)
        res = EasyOCR._eng.readtext(np.asarray(img.convert("RGB")))
        return poly_words([(t, box, c) for box, t, c in res])


ALL = [TessCurrent(), TessNoBlur(), AppleVision(), RapidOCR(), PaddleOCR(), EasyOCR()]
