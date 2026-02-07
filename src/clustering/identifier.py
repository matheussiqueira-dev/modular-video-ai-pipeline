from __future__ import annotations

import logging
from typing import List

import cv2
import numpy as np
from sklearn.cluster import KMeans


class VisualIdentifier:
    """
    Embedding and clustering module.
    In mock mode, embeddings are deterministic vectors derived from crops.
    """

    def __init__(
        self,
        model_name: str = "google/siglip-base-patch16-224",
        device: str = "cuda",
        mock_mode: bool = True,
    ):
        self.logger = logging.getLogger(__name__)
        self.device = device
        self.model_name = model_name
        self.model = None
        self.processor = None
        self.mock_mode = bool(mock_mode)
        self.kmeans: KMeans | None = None

        self._load_model()

    def _load_model(self) -> None:
        self.logger.info("Loading embedding model '%s'", self.model_name)
        if self.mock_mode:
            self.logger.info("Visual identifier running in deterministic mock mode.")
            return

        try:
            # Real inference scaffold.
            # from transformers import AutoProcessor, AutoModel
            # import torch
            # self.processor = AutoProcessor.from_pretrained(self.model_name)
            # self.model = AutoModel.from_pretrained(self.model_name).to(self.device)
            self.mock_mode = True
            self.logger.warning("Real model loading disabled. Falling back to mock mode.")
        except Exception as exc:
            self.logger.exception("Failed to load embedding model. Falling back to mock mode: %s", exc)
            self.mock_mode = True

    def extract_embeddings(self, crops: List[np.ndarray]) -> np.ndarray:
        if not crops:
            return np.empty((0, 768), dtype=np.float32)

        if self.mock_mode:
            vectors = [self._deterministic_embedding(crop) for crop in crops]
            return np.stack(vectors, axis=0).astype(np.float32)

        # Real inference hook
        return np.empty((0, 768), dtype=np.float32)

    def cluster_embeddings(self, embeddings: np.ndarray, n_clusters: int = 2) -> np.ndarray:
        if embeddings.size == 0:
            return np.array([], dtype=np.int32)

        n_samples = int(len(embeddings))
        if n_samples <= 1:
            return np.zeros(n_samples, dtype=np.int32)

        n_clusters = max(1, min(int(n_clusters), n_samples))
        if n_clusters == 1:
            return np.zeros(n_samples, dtype=np.int32)

        if np.allclose(embeddings, embeddings[0]):
            return np.zeros(n_samples, dtype=np.int32)

        self.kmeans = KMeans(n_clusters=n_clusters, n_init=10, random_state=42)
        labels = self.kmeans.fit_predict(embeddings)
        return labels.astype(np.int32)

    @staticmethod
    def _deterministic_embedding(crop: np.ndarray) -> np.ndarray:
        if crop is None or crop.size == 0:
            return np.zeros(768, dtype=np.float32)

        resized = cv2.resize(crop, (16, 16), interpolation=cv2.INTER_AREA)
        if resized.ndim == 2:
            resized = cv2.cvtColor(resized, cv2.COLOR_GRAY2BGR)

        vector = resized.astype(np.float32).reshape(-1) / 255.0
        if vector.shape[0] != 768:
            padded = np.zeros(768, dtype=np.float32)
            limit = min(768, vector.shape[0])
            padded[:limit] = vector[:limit]
            return padded
        return vector.astype(np.float32)
