"""Direct test for the optional ZXing-C++ QR decoder integration."""
import cv2
import numpy as np
import pytest

from app.dock_vision.service import _ZXING_AVAILABLE, _zxing
from tests.dock.qr_frames import frame_with_qr


def test_zxing_cpp_decodes_a_clean_qr():
    if not _ZXING_AVAILABLE:
        pytest.skip("zxing-cpp is not installed in this environment")

    encoded = frame_with_qr("zxing-cpp-decoder-test", side=210)
    frame = cv2.imdecode(np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    assert frame is not None
    assert _zxing(frame) == "zxing-cpp-decoder-test"
