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

from usreport import crosscheck, extract as ex
from usreport.crosscheck import poly_words, split_words  # noqa: F401  (shared with the app's cross-check)


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
        return ex.extract(img, crosscheck=False)  # Tesseract alone; cross-checks are measured as A+B rows


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
    name, note = "rapidocr", "PaddleOCR models on ONNX runtime (pip install rapidocr-onnxruntime); the app's cross-check engine"

    def unavailable(self):
        return crosscheck.unavailable()

    def words(self, img):
        return crosscheck.words(img)


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
