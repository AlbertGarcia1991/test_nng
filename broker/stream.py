import json
from typing import Any, Dict

import pynng

from common.config import STREAM_PUB_ADDR


class StreamPublisher:
    def __init__(self):
        self.sock = pynng.Pub0(listen=STREAM_PUB_ADDR)
        print(f"[stream] PUB listening on {STREAM_PUB_ADDR}")

    def __enter__(self) -> "StreamPublisher":
        # Support use as a context manager (with ... as publisher)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # Ensure the underlying socket is closed when leaving the context
        try:
            self.sock.close()
        except Exception as exc:
            print(f"[stream] Error while closing PUB socket: {exc}")

    def publish(self, topic: str, message: Dict[str, Any]):
        """
        Publish as a single frame with a topic prefix for NNG SUB filtering.

        Wire format (bytes):
            b"<topic> " + b"<json>"

        Where JSON is:
            {
              "topic": "<topic-string>",
              "payload": { ... original message ... }
            }

        Subscribers should:
          - sub.subscribe(b"<topic>")  # prefix match
          - recv()
          - strip the "<topic> " prefix
          - json.loads(remaining_bytes)
        """
        frame_obj: Dict[str, Any] = {
            "topic": topic,
            "payload": message,
        }
        json_bytes: bytes = json.dumps(frame_obj).encode("utf-8")
        prefix: bytes = topic.encode("utf-8") + b" "
        wire: bytes = prefix + json_bytes
        self.sock.send(wire)
