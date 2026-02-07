from __future__ import annotations

import logging

import cv2
import numpy as np


class SceneTextReader:
    """
    OCR facade.
    Mock mode uses deterministic heuristics so outputs remain stable for a given crop.
    """

    def __init__(
        self,
        model_name: str = "HuggingFaceTB/SmolVLM2-500M-Instruct",
        device: str = "cuda",
        mock_mode: bool = True,
    ):
        self.logger = logging.getLogger(__name__)
        self.device = device
        self.model_name = model_name
        self.model = None
        self.processor = None
        self.mock_mode = bool(mock_mode)
        self._cache: dict[int, str] = {}

        self._load_model()

    def _load_model(self) -> None:
        self.logger.info("Loading OCR/VLM model '%s'", self.model_name)
        if self.mock_mode:
            self.logger.info("OCR reader running in deterministic mock mode.")
            return

        try:
            # Real inference scaffold.
            # from transformers import AutoProcessor, AutoModelForVision2Seq
            # self.processor = AutoProcessor.from_pretrained(self.model_name)
            # self.model = AutoModelForVision2Seq.from_pretrained(self.model_name).to(self.device)
            self.mock_mode = True
            self.logger.warning("Real OCR loading disabled. Falling back to mock mode.")
        except Exception as exc:
            self.logger.exception("Failed to load OCR model. Falling back to mock mode: %s", exc)
            self.mock_mode = True

    def read_text(
        self,
        crop: np.ndarray,
        prompt: str = "What number is written on the jersey?",
        track_id: int | None = None,
        force_refresh: bool = False,
    ) -> str:
        if crop is None or crop.size == 0:
            return ""

        if track_id is not None and not force_refresh and track_id in self._cache:
            return self._cache[track_id]

        if self.mock_mode:
            text = self._mock_ocr(crop)
        else:
            text = ""
            # Real inference hook.

        if track_id is not None and text:
            self._cache[track_id] = text
        return text

    @staticmethod
    def _mock_ocr(crop: np.ndarray) -> str:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
        gray = cv2.resize(gray, (24, 24), interpolation=cv2.INTER_AREA)
        mean_intensity = float(np.mean(gray))
        edge_strength = float(np.mean(cv2.Laplacian(gray, cv2.CV_32F)))

        if mean_intensity < 15:
            return ""

        value = int((mean_intensity * 0.37 + abs(edge_strength) * 11.0) % 99)
        value = max(1, value)
        return f"{value:02d}"
