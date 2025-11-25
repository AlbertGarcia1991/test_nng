import threading
import time
import random
from typing import Any, Callable, Dict

from .base_device import BaseDevice


class ImuDevice(BaseDevice):
    def __init__(self, device_id: str, publish_fn: Callable[[str, dict], None]):
        super().__init__(device_id)
        self.is_streaming = False
        self._publish = publish_fn
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while not self._stop_event.is_set():
            if self.is_streaming:
                # fake IMU data
                payload = {
                    "device_id": self.device_id,
                    "stream": "imu",
                    "timestamp": time.time(),
                    "accel": [random.uniform(-1, 1) for _ in range(3)],
                    "gyro": [random.uniform(-180, 180) for _ in range(3)],
                }
                topic = f"{self.device_id}/imu"
                self._publish(topic, payload)
            time.sleep(0.01)  # 100 Hz

    def handle_command(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if command == "get_status":
            return {
                "device_id": self.device_id,
                "status": "READY",
                "streaming": self.is_streaming,
            }
        elif command == "start_stream":
            self.is_streaming = True
            return {
                "device_id": self.device_id,
                "streaming": True,
            }
        elif command == "stop_stream":
            self.is_streaming = False
            return {
                "device_id": self.device_id,
                "streaming": False,
            }
        else:
            raise ValueError(f"Unknown command: {command}")

    def shutdown(self):
        self._stop_event.set()
        self._thread.join(timeout=1.0)
