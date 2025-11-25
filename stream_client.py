from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

import pynng

from common.config import STREAM_DIAL


def run_stream_client(
    addr: Optional[str],
    topic_prefix: str,
) -> int:
    """
    Connect to the broker's PUB socket and subscribe to device streams.

    Wire format produced by the broker:
        b"<topic> " + b"<json>"

    Where JSON is:
        {
          "topic": "<string>",
          "payload": { ... }
        }

    We subscribe on "<topic>" so NNG does prefix-based filtering, then
    strip "<topic> " before decoding the JSON.
    """
    dial_addr = addr or STREAM_DIAL
    topic_bytes = topic_prefix.encode("utf-8")

    print(f"[stream_client] Dialing {dial_addr}")
    print(f"[stream_client] Subscribing to topic prefix {topic_prefix!r}")
    print("Press Ctrl+C to stop.\n")

    with pynng.Sub0() as sub:
        # Configure the SUB socket
        sub.recv_timeout = 5000  # 5 seconds, to periodically unblock on inactivity
        sub.dial(dial_addr)
        sub.subscribe(topic_bytes)

        while True:
            try:
                wire = sub.recv()
            except pynng.Timeout:
                # Just loop again; this keeps the client responsive to Ctrl+C
                continue
            except KeyboardInterrupt:
                print("\n[stream_client] Interrupted by user, exiting.")
                break
            except Exception as exc:
                print(f"[stream_client] Error while receiving: {exc}", file=sys.stderr)
                break

            # Expect wire == b"<topic_prefix> " + json_bytes
            if not wire.startswith(topic_bytes):
                # Should not normally happen if subscription works as expected
                print(f"[stream_client] WARNING: received message without topic prefix")
                raw_json = wire
            else:
                # Strip "<topic_prefix>" and optional space
                # We added exactly one space in the publisher.
                after_prefix = wire[len(topic_bytes):]
                if after_prefix.startswith(b" "):
                    after_prefix = after_prefix[1:]
                raw_json = after_prefix

            try:
                obj = json.loads(raw_json.decode("utf-8"))
            except Exception as exc:
                print(f"[stream_client] Failed to decode JSON frame: {exc}", file=sys.stderr)
                continue

            topic = obj.get("topic", "<no-topic>")
            payload = obj.get("payload")

            print(f"[stream_client] {topic}:")
            print(json.dumps(payload, indent=2, sort_keys=True))
            print()  # blank line between messages

    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="NNG streaming client for IMU (and other) topics.",
    )
    parser.add_argument(
        "--addr",
        help=(
            "Broker stream address to dial "
            "(default: value from common.config.STREAM_DIAL)."
        ),
    )
    parser.add_argument(
        "--topic",
        default="imu_1/imu",
        help=(
            "Topic prefix to subscribe to (NNG uses prefix matching). "
            "Examples: 'imu_1/imu', 'imu_1', 'imu_2/imu'. "
            "Default: %(default)s"
        ),
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    return run_stream_client(
        addr=args.addr,
        topic_prefix=args.topic,
    )


if __name__ == "__main__":
    raise SystemExit(main())
