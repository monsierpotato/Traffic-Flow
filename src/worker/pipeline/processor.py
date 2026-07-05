"""Frame processing pipeline: stabilize → crop → polygon mask → resize → JPEG encode."""

from typing import Tuple, Optional, List
import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)


class FrameProcessor:
    """Transforms a raw video frame into an AI-ready JPEG.

    Pipeline order:
      1. Camera stabilization (phase-correlation warp)
      2. ROI crop (annotation_roi)
      3. Polygon mask (roi_polygon → zero-out outside)
      4. Resize longest side to target dimension
      5. JPEG encode
    """

    def __init__(self, ai_resize_dim: int = 640,
                 enable_stabilization: bool = True):
        self.ai_resize_dim = ai_resize_dim
        self.enable_stabilization = enable_stabilization
        self._ref_gray: Optional[np.ndarray] = None

    def set_reference_frame(self, frame: np.ndarray):
        """Capture the first (reference) frame for stabilization."""
        self._ref_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
        logger.info(f"Reference frame captured ({frame.shape[1]}x{frame.shape[0]})")

    def process_for_ai(self, frame: np.ndarray,
                       crop_rect: Optional[Tuple[int, int, int, int]] = None,
                       poly_mask: Optional[np.ndarray] = None,
                       ) -> Tuple[np.ndarray, np.ndarray, int, int, int, int]:
        """Run the full processing pipeline on one frame.

        Args:
            frame: Raw BGR frame.
            crop_rect: (min_x, min_y, max_x, max_y) or None.
            poly_mask: Integer polygon points (N×2) in cropped coords or None.

        Returns:
            cropped_frame: The processed frame (after crop + mask, before resize).
            ai_frame: The resized JPEG-ready frame.
            orig_w, orig_h: Dimensions of cropped_frame.
            ai_w, ai_h: Dimensions of ai_frame.
        """
        # 1. Stabilization
        if self._ref_gray is not None:
            frame = self._stabilize(frame)

        # 2. Crop
        if crop_rect:
            min_x, min_y, max_x, max_y = crop_rect
            if max_y > min_y and max_x > min_x:
                cropped = frame[min_y:max_y, min_x:max_x]
            else:
                cropped = frame
        else:
            cropped = frame

        orig_h, orig_w = cropped.shape[:2]

        # 3. Polygon mask
        if poly_mask is not None and len(poly_mask) >= 3:
            mask = np.zeros(cropped.shape[:2], dtype=np.uint8)
            cv2.fillPoly(mask, [poly_mask], 255)
            cropped = cv2.bitwise_and(cropped, cropped, mask=mask)

        # 4. Resize
        if self.ai_resize_dim > 0 and max(orig_w, orig_h) > self.ai_resize_dim:
            if orig_w >= orig_h:
                ai_w, ai_h = self.ai_resize_dim, int(orig_h * self.ai_resize_dim / orig_w)
            else:
                ai_h, ai_w = self.ai_resize_dim, int(orig_w * self.ai_resize_dim / orig_h)
            ai_frame = cv2.resize(cropped, (ai_w, ai_h), interpolation=cv2.INTER_LINEAR)
        else:
            ai_frame = cropped
            ai_w, ai_h = orig_w, orig_h

        return cropped, ai_frame, orig_w, orig_h, ai_w, ai_h

    def encode_jpeg(self, ai_frame: np.ndarray, quality: int = 85) -> Optional[bytes]:
        success, buf = cv2.imencode('.jpg', ai_frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not success:
            return None
        return buf.tobytes()

    def _stabilize(self, frame: np.ndarray) -> np.ndarray:
        if self._ref_gray is None:
            return frame
        try:
            current_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
            shift, _ = cv2.phaseCorrelate(self._ref_gray, current_gray)
            dx, dy = -shift[0], -shift[1]
            if abs(dx) > 0.3 or abs(dy) > 0.3:
                warp = np.float32([[1, 0, dx], [0, 1, dy]])
                frame = cv2.warpAffine(frame, warp, (frame.shape[1], frame.shape[0]),
                                      borderMode=cv2.BORDER_REPLICATE)
        except cv2.error:
            pass
        return frame
