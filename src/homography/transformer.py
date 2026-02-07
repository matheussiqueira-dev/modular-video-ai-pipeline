from __future__ import annotations

import logging
from typing import Iterable, Tuple

import cv2
import numpy as np


class PerspectiveTransformer:
    """Map camera coordinates to a top-down plane using homography."""

    def __init__(self, src_points: np.ndarray | None = None, dst_points: np.ndarray | None = None):
        self.logger = logging.getLogger(__name__)
        self.homography_matrix: np.ndarray | None = None

        if src_points is not None and dst_points is not None:
            self.compute_homography(src_points, dst_points)

    def compute_homography(self, src_points: np.ndarray, dst_points: np.ndarray) -> None:
        src = self._normalize_points(src_points)
        dst = self._normalize_points(dst_points)

        if src.shape[0] < 4 or dst.shape[0] < 4:
            raise ValueError("At least 4 point correspondences are required for homography")
        if src.shape != dst.shape:
            raise ValueError("src_points and dst_points must have the same shape")

        matrix, _ = cv2.findHomography(src, dst)
        if matrix is None:
            self.logger.warning("Could not compute homography matrix. Keeping previous matrix.")
            return

        self.homography_matrix = matrix
        self.logger.info("Homography matrix computed successfully.")

    def transform_point(self, point: Tuple[int, int]) -> Tuple[int, int]:
        if self.homography_matrix is None:
            return int(point[0]), int(point[1])

        source = np.array([[[float(point[0]), float(point[1])]]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(source, self.homography_matrix)
        x, y = transformed[0, 0]
        return int(round(float(x))), int(round(float(y)))

    def transform_points(self, points: np.ndarray) -> np.ndarray:
        if self.homography_matrix is None:
            return np.asarray(points, dtype=np.float32)

        normalized = self._normalize_points(points)
        transformed = cv2.perspectiveTransform(normalized.reshape(1, -1, 2), self.homography_matrix)
        return transformed.reshape(-1, 2)

    @staticmethod
    def _normalize_points(points: Iterable) -> np.ndarray:
        arr = np.asarray(points, dtype=np.float32)
        if arr.ndim == 1:
            if arr.shape[0] != 2:
                raise ValueError("Single point must have shape (2,)")
            arr = arr.reshape(1, 2)

        if arr.ndim != 2 or arr.shape[1] != 2:
            raise ValueError("Points must have shape (N, 2)")
        return arr
