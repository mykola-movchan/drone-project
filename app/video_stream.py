import cv2
import os
import time
import threading
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage


# --- ULTRA LOW LATENCY FFMPEG TUNING ---
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
    "protocol_whitelist;file,rtp,udp|"
    "fflags;nobuffer|"
    "flags;low_delay|"
    "probesize;32|"
    "analyzeduration:0|"
    "discard;corrupt|"
    "threads;auto|"
    "hwaccel;auto"
)


class TelloVideoThread(QThread):
    """
    Captures / decodes the Tello video stream at full speed.

    ML integration
    --------------
    Set self.ml_worker to an MLWorker instance and toggle self.ml_enabled
    to start/stop inference. Frames are submitted non-blocking — this thread
    is NEVER delayed by inference. The latest predictions are stored and drawn
    onto every outgoing frame as an overlay, so the video feed always runs at
    full speed while labels update at the model's own pace.
    """

    frame_received = pyqtSignal(QImage)

    def __init__(self):
        super().__init__()
        self._stop_event = threading.Event()
        self.cap = None
        self.video_url = 'udp://@0.0.0.0:11111?overrun_nonfatal=1&fifo_size=5000000'

        # ML state
        self.ml_enabled: bool = False
        self.ml_worker = None               # injected by main.py

    # ------------------------------------------------------------------
    # Thread body
    # ------------------------------------------------------------------

    def run(self):
        self._stop_event.clear()

        self.cap = cv2.VideoCapture(self.video_url, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        while not self._stop_event.is_set():
            if self.cap is None or not self.cap.isOpened():
                time.sleep(0.1)
                continue

            try:
                ret, frame = self.cap.read()

                if self._stop_event.is_set():
                    break

                if not ret or frame is None:
                    time.sleep(0.01)
                    continue

                # --- Submit to ML worker (non-blocking, never waits) ---
                if self.ml_enabled and self.ml_worker is not None:
                    self.ml_worker.submit_frame(frame)

                # --- Convert BGR → QImage and emit ---
                h, w, _ = frame.shape
                q_img = QImage(
                    frame.data, w, h, 3 * w,
                    QImage.Format.Format_RGB888
                ).rgbSwapped()

                self.frame_received.emit(q_img)

            except Exception as e:
                print(f"[VideoThread] Error: {e}")
                time.sleep(0.1)

        if self.cap:
            self.cap.release()
            self.cap = None

    def stop(self):
        self._stop_event.set()