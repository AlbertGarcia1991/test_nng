
# NNG Broker Demo – Multi‑Client, Multi‑Device RPC + Streaming

This project is a learning playground for using **nanomsg‑NG (NNG)** from Python via **pynng**.

The design is:

- A **broker** (single process, on one machine) that:
  - Exposes an **RPC interface** (REQ/REP) to multiple clients.
  - Publishes **streaming data** (PUB/SUB) to any interested clients.
  - Manages a set of **simulated devices**.
- **Devices**:
  - All devices support **RPC** (e.g. `get_status`, `start_stream`, `stop_stream`).
  - Some devices have **IMU feed** support.
  - Some have **colour feed** support.
  - Some have **gesture feed** support.
  - A device may expose **0, 1, 2, or all 3** feeds.
- **Clients**:
  - Can be **local or remote**.
  - Use RPC for control.
  - Use PUB/SUB streams for continuous data (IMU/colour/gestures).

The goal is to explore patterns and practical usage rather than to model real hardware perfectly.

---

## 1. High‑Level Architecture

### 1.1 Components

- **Broker** (`main.py`, `broker/…`):
  - Runs on a server machine.
  - Manages all devices.
  - Exposes:
    - A `Rep0` socket for **JSON‑based RPC**.
    - A `Pub0` socket for **streaming data**.

- **Devices** (`broker/devices/…`):
  - Python classes representing BLE‑like devices.
  - Each device:
    - Has a `device_id` string.
    - Implements RPC logic in `handle_command(...)`.
    - Optionally generates IMU/colour/gesture samples in background threads.
    - Publishes samples through the broker’s `StreamPublisher`.

- **Clients** (`rpc_client.py`, `cli_client.py`, `stream_client.py`):
  - `RpcClient`: A helper that hides NNG’s REQ semantics and JSON encoding.
  - `cli_client.py`: Interactive CLI to send arbitrary RPC commands.
  - `stream_client.py`: SUB client for streaming data.

- **Common utilities** (`common/…`):
  - `config.py`: Central addresses for RPC and streaming sockets.
  - `protocol.py`: JSON framing and helper functions.

### 1.2 Socket Patterns

- **RPC: `Req0` ↔ `Rep0`**
  - Broker: `Rep0` socket (`listen`).
  - Clients: `Req0` sockets (`dial`).
  - Strict pattern: `send → recv → send → recv`.

- **Streaming: `Pub0` → `Sub0`**
  - Broker: `Pub0` socket (`listen`).
  - Clients: `Sub0` sockets (`dial`, `subscribe`).
  - Pattern: `send` (PUB) → zero or more `recv` (SUBs).

---

## 2. Installation and Setup

### 2.1 Prerequisites

- Python 3.10+ recommended.
- `libnng` installed on your system (if `pynng` is not using vendored NNG). On many systems:

```bash
# Debian/Ubuntu example (adjust as needed)
sudo apt-get install -y cmake ninja-build
# then install pynng via pip; it will compile NNG if needed
```

### 2.2 Create and Activate Virtualenv (optional but recommended)

From the project root:

```bash
cd /home/agplaza/Desktop/courses/nanomesg_NG

python -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate
```

### 2.3 Install Python Dependencies

Dependencies are defined in `requirements.txt`:

```/home/agplaza/Desktop/courses/nanomesg_NG/requirements.txt#L1-10
pynng>=0.8.0
```

Install:

```bash
pip install -r requirements.txt
```

---

## 3. Configuration

Central configuration lives in `common/config.py`:

```/home/agplaza/Desktop/courses/nanomesg_NG/common/config.py#L1-4
RPC_ADDR = "tcp://0.0.0.0:5555"  # broker RPC REP endpoint
STREAM_PUB_ADDR = "tcp://0.0.0.0:5556"  # broker PUB endpoint

# For clients:
RPC_DIAL = "tcp://127.0.0.1:5555"
STREAM_DIAL = "tcp://127.0.0.1:5556"
```

- **Server/broker**:
  - Binds RPC on `RPC_ADDR`.
  - Binds stream PUB on `STREAM_PUB_ADDR`.
- **Clients**:
  - Dial `RPC_DIAL` for RPC.
  - Dial `STREAM_DIAL` for streams.

To support **remote clients**:

- On the broker machine, leaving `0.0.0.0` is fine (binds to all interfaces).
- On client machines, set `RPC_DIAL` / `STREAM_DIAL` to the **server’s IP**, e.g.:

```python
RPC_DIAL = "tcp://192.168.1.10:5555"
STREAM_DIAL = "tcp://192.168.1.10:5556"
```

Or override via CLI arguments (for the stream client) where available.

---

## 4. JSON Protocol

Everything between clients and broker (for RPC and meta‑data of streaming) is JSON.

### 4.1 RPC Request

Defined in `common/protocol.py`:

```/home/agplaza/Desktop/courses/nanomesg_NG/common/protocol.py#L1-36
from typing import Any, Dict, Optional, Literal
import json
import uuid

MessageType = Literal["rpc", "stream_subscribe", "stream_unsubscribe"]

def new_request_id() -> str:
    return str(uuid.uuid4())

def make_rpc_request(
    device_id: str,
    command: str,
    params: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    if params is None:
        params = {}
    if request_id is None:
        request_id = new_request_id()
    return {
        "type": "rpc",
        "device_id": device_id,
        "command": command,
        "params": params,
        "request_id": request_id,
    }
```

Typical RPC request:

```json
{
  "type": "rpc",
  "device_id": "dev_imu_color_1",
  "command": "get_status",
  "params": {},
  "request_id": "uuid-..."
}
```

### 4.2 RPC Reply

```/home/agplaza/Desktop/courses/nanomesg_NG/common/protocol.py#L38-60
def make_ok_reply(request_id: str, result: Any) -> Dict[str, Any]:
    return {
        "request_id": request_id,
        "status": "OK",
        "error": None,
        "result": result,
    }

def make_error_reply(request_id: Optional[str], code: str, message: str) -> Dict[str, Any]:
    return {
        "request_id": request_id,
        "status": "ERROR",
        "error": {
            "code": code,
            "message": message,
        },
        "result": None,
    }
```

Typical RPC reply (OK):

```json
{
  "request_id": "uuid-...",
  "status": "OK",
  "error": null,
  "result": {
    "device_id": "dev_imu_color_1",
    "status": "READY",
    "feeds": {
      "imu": true,
      "color": true,
      "gestures": false
    },
    "streaming": {
      "imu": true,
      "color": false,
      "gestures": false
    }
  }
}
```

Typical RPC reply (ERROR):

```json
{
  "request_id": "uuid-...",
  "status": "ERROR",
  "error": {
    "code": "INVALID_COMMAND",
    "message": "Unknown command: start_color_stream on device dev_imu_only_2"
  },
  "result": null
}
```

### 4.3 Streaming Frames

For streaming, the broker sends a single NNG frame per message with this **wire format**:

- Raw bytes:
  - `b"<topic> " + b"<json>"`
- Where `<json>` is UTF‑8 encoded JSON:
  - `{"topic": "<topic-string>", "payload": { ... }}`

Example:

```json
{
  "topic": "dev_imu_color_1/imu",
  "payload": {
    "device_id": "dev_imu_color_1",
    "feed": "imu",
    "timestamp": 1234567890.123,
    "accel": [0.1, -0.2, 0.0],
    "gyro": [0.5, 0.0, -0.5]
  }
}
```

This design lets us:

- Use **topic prefix subscription** in NNG (`sub.subscribe(b"dev_imu_color_1/imu")`).
- Still have structured JSON that explicitly encodes `topic` and `payload`.

---

## 5. Devices Model

> Important: There are **no separate IMUDevice/ColourDevice/GestureDevice** classes in this conceptual design.  
> Instead:
> - Each **device instance** can have **any combination** of available feeds:
>   - IMU feed
>   - Colour feed
>   - Gestures feed
> - **All devices support RPC**, regardless of feeds.

The current code includes a single `ImuDevice` as a concrete example. You’d extend this pattern to composite devices like `MultiSensorDevice` that can enable/disable each feed.

### 5.1 Device Base Class

```python
from typing import Any, Dict


class BaseDevice:
    def __init__(self, device_id: str):
        self.device_id = device_id

    def handle_command(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Implement in subclasses.
        Return a dict-like result payload (NOT the full reply wrapper).
        Can raise ValueError for unsupported commands.
        """
        raise NotImplementedError
```

Every device:

- Has `device_id`.
- Implements `handle_command(...)`, which:
  - **Does NOT** wrap in `status`/`error` (broker handles that).
  - Returns a dict on success.
  - Raises `ValueError` if the command is invalid, or uses other exceptions as needed.

### 5.2 Example Device with One Feed (IMU)

```python
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
                    "feed": "imu",
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
                "feeds": {
                    "imu": True,
                    "color": False,
                    "gestures": False,
                },
                "streaming": {
                    "imu": self.is_streaming,
                    "color": False,
                    "gestures": False,
                },
            }
        elif command == "start_stream":
            self.is_streaming = True
            return {
                "device_id": self.device_id,
                "streaming": {
                    "imu": True,
                    "color": False,
                    "gestures": False,
                },
            }
        elif command == "stop_stream":
            self.is_streaming = False
            return {
                "device_id": self.device_id,
                "streaming": {
                    "imu": False,
                    "color": False,
                    "gestures": False,
                },
            }
        else:
            raise ValueError(f"Unknown command: {command}")

    def shutdown(self):
        self._stop_event.set()
        self._thread.join(timeout=1.0)
```

**Conceptually**, you’d implement:

- `MultiSensorDevice` (IMU + colour + gestures).
- `ColorDevice` (colour only).
- `GestureDevice` (gestures only).
- `PlainDevice` (no feeds, but still supports RPC like `get_status`, `set_config`, etc.).

All of them:

- Inherit from `BaseDevice`.
- Use `publish_fn` to emit feed data if applicable.
- Implement `handle_command`.

### 5.3 DeviceManager

`DeviceManager` is the central registry and dispatch:

```python
from __future__ import annotations

from typing import Any, Callable, Dict

from broker.devices.imu_device import ImuDevice

PublishFn = Callable[[str, Dict[str, Any]], None]


class DeviceManager:
    """
    Central registry and façade for all simulated BLE devices.
    ...
    """

    def __init__(self, publish_fn: PublishFn) -> None:
        self._publish_fn = publish_fn
        self._devices: Dict[str, Any] = {}
        self._init_devices()

    def _init_devices(self) -> None:
        """
        Instantiate and register all simulated devices.
        """
        # Example: two IMU-only devices
        self._devices["imu_1"] = ImuDevice("imu_1", publish_fn=self._publish_fn)
        self._devices["imu_2"] = ImuDevice("imu_2", publish_fn=self._publish_fn)

        # Here is where you'd add more composite devices, e.g.:
        # self._devices["dev_full_1"] = MultiSensorDevice("dev_full_1", publish_fn=self._publish_fn)
        # self._devices["dev_color_only_1"] = ColorDevice("dev_color_only_1", publish_fn=self._publish_fn)
        # self._devices["dev_plain_1"] = PlainDevice("dev_plain_1")

        print(f"[devices] Initialised devices: {list(self._devices.keys())}")

    def handle_rpc(
        self, device_id: str, command: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        device = self._devices.get(device_id)
        if not device:
            raise KeyError(f"Unknown device_id: {device_id}")

        return device.handle_command(command, params)

    def shutdown(self) -> None:
        for dev_id, dev in self._devices.items():
            shutdown_method = getattr(dev, "shutdown", None)
            if callable(shutdown_method):
                try:
                    shutdown_method()
                except Exception as exc:
                    print(f"[devices] Error while shutting down {dev_id}: {exc}")
```

**Key idea**: the **broker never knows** which feeds a device has; it just forwards:

- `device_id`, `command`, and `params` to `DeviceManager`.
- `DeviceManager` calls the device, and the device decides what to do.

---

## 6. Broker Implementation

Top‑level broker entrypoint is `main.py`:

```python
from __future__ import annotations

import signal
import sys
import threading
from contextlib import ExitStack

from broker.device_manager import DeviceManager
from broker.rpc_server import RpcServer
from broker.stream import StreamPublisher
from common.config import RPC_ADDR


def _install_signal_handlers(shutdown_callback):
    def handler(signum, frame):
        print(f"[broker] Caught signal {signum}, initiating shutdown...")
        shutdown_callback()

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)


def main():
    print(f"[broker] Starting broker...")
    print(f"[broker] RPC address: {RPC_ADDR}")

    with ExitStack() as stack:
        stream_publisher = stack.enter_context(StreamPublisher())
        device_manager = DeviceManager(publish_fn=stream_publisher.publish)
        rpc_server = RpcServer(device_manager=device_manager)
        rpc_server.start()

        shutdown_event = threading.Event()

        def shutdown():
            if not shutdown_event.is_set():
                shutdown_event.set()
                print("[broker] Shutting down RPC server...")
                rpc_server.stop()
                print("[broker] Shutdown complete.")

        _install_signal_handlers(shutdown)

        print("[broker] Broker is up and running. Press Ctrl+C to stop.")

        try:
            shutdown_event.wait()
        except KeyboardInterrupt:
            shutdown()

    print("[broker] Exited cleanly.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[broker] Fatal error: {exc}", file=sys.stderr)
        sys.exit(1)
```

### 6.1 RPC Server (`Rep0`)

```python
from __future__ import annotations

import threading
from typing import Any, Dict

import pynng

from broker.device_manager import DeviceManager
from common.config import RPC_ADDR
from common.protocol import (
    from_bytes,
    make_error_reply,
    make_ok_reply,
    to_bytes,
)


class RpcServer:
    """
    RPC server built on top of a single NNG Rep0 socket.
    ...
    """

    def __init__(self, device_manager: DeviceManager) -> None:
        self._device_manager = device_manager
        self._sock: pynng.Rep0 | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread is not None:
            return

        self._sock = pynng.Rep0(listen=RPC_ADDR)
        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._run_loop,
            name="RpcServerLoop",
            daemon=True,
        )
        self._thread.start()
        print(f"[rpc] REP listening on {RPC_ADDR}")

    def stop(self) -> None:
        self._stop_event.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception as exc:
                print(f"[rpc] Error while closing socket: {exc}")
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _run_loop(self) -> None:
        assert self._sock is not None
        sock = self._sock

        while not self._stop_event.is_set():
            try:
                raw = sock.recv()
            except pynng.NNGError as exc:
                if self._stop_event.is_set():
                    break
                print(f"[rpc] NNGError on recv: {exc}")
                continue
            except Exception as exc:
                print(f"[rpc] Unexpected error on recv: {exc}")
                continue

            reply_bytes = self._handle_raw_message(raw)

            try:
                sock.send(reply_bytes)
            except pynng.NNGError as exc:
                if self._stop_event.is_set():
                    break
                print(f"[rpc] NNGError on send: {exc}")
            except Exception as exc:
                print(f"[rpc] Unexpected error on send: {exc}")

        print("[rpc] Loop exiting")

    def _handle_raw_message(self, raw: bytes) -> bytes:
        try:
            request = from_bytes(raw)
        except Exception as exc:
            print(f"[rpc] Failed to decode JSON: {exc}")
            reply_obj = make_error_reply(
                request_id=None,
                code="BAD_JSON",
                message=str(exc),
            )
            return to_bytes(reply_obj)

        print(f"[rpc] Received request: {request!r}")

        request_id = request.get("request_id")
        msg_type = request.get("type")
        device_id = request.get("device_id")
        command = request.get("command")
        params = request.get("params") or {}

        if msg_type != "rpc":
            reply_obj = make_error_reply(
                request_id=request_id,
                code="UNSUPPORTED_TYPE",
                message=f"Unsupported message type: {msg_type!r}",
            )
            return to_bytes(reply_obj)

        if not isinstance(device_id, str) or not isinstance(command, str):
            reply_obj = make_error_reply(
                request_id=request_id,
                code="BAD_REQUEST",
                message="Missing or invalid 'device_id' or 'command'",
            )
            return to_bytes(reply_obj)

        if not isinstance(params, dict):
            reply_obj = make_error_reply(
                request_id=request_id,
                code="BAD_REQUEST",
                message="'params' must be an object",
            )
            return to_bytes(reply_obj)

        try:
            result: Dict[str, Any] = self._device_manager.handle_rpc(
                device_id=device_id,
                command=command,
                params=params,
            )
            reply_obj = make_ok_reply(request_id=request_id, result=result)
        except KeyError as exc:
            reply_obj = make_error_reply(
                request_id=request_id,
                code="UNKNOWN_DEVICE",
                message=str(exc),
            )
        except ValueError as exc:
            reply_obj = make_error_reply(
                request_id=request_id,
                code="INVALID_COMMAND",
                message=str(exc),
            )
        except Exception as exc:
            print(f"[rpc] Internal error while handling RPC: {exc}")
            reply_obj = make_error_reply(
                request_id=request_id,
                code="INTERNAL_ERROR",
                message="Internal server error",
            )

        print(f"[rpc] Replying: {reply_obj!r}")
        return to_bytes(reply_obj)
```

### 6.2 Stream Publisher (`Pub0`)

```python
import json
from typing import Any, Dict

import pynng

from common.config import STREAM_PUB_ADDR


class StreamPublisher:
    def __init__(self):
        self.sock = pynng.Pub0(listen=STREAM_PUB_ADDR)
        print(f"[stream] PUB listening on {STREAM_PUB_ADDR}")

    def __enter__(self) -> "StreamPublisher":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            self.sock.close()
        except Exception as exc:
            print(f"[stream] Error while closing PUB socket: {exc}")

    def publish(self, topic: str, message: Dict[str, Any]):
        """
        Publish as a single frame with a topic prefix for NNG SUB filtering.

        Wire format (bytes):
            b"<topic> " + b"<json>"

        JSON:
            {
              "topic": "<topic-string>",
              "payload": { ... original message ... }
            }
        """
        frame_obj: Dict[str, Any] = {
            "topic": topic,
            "payload": message,
        }
        json_bytes: bytes = json.dumps(frame_obj).encode("utf-8")
        prefix: bytes = topic.encode("utf-8") + b" "
        wire: bytes = prefix + json_bytes
        self.sock.send(wire)
```

---

## 7. Clients

### 7.1 RpcClient helper

```python
from __future__ import annotations

import threading
from typing import Any, Dict, Optional

import pynng

from common.config import RPC_DIAL
from common.protocol import (
    from_bytes,
    make_rpc_request,
    new_request_id,
    to_bytes,
)


class RpcError(Exception):
    ...


class RpcTimeoutError(RpcError):
    ...


class RpcClient:
    """
    Helper for JSON-based RPC over an NNG Req0 socket.
    """

    def __init__(
        self, addr: str = RPC_DIAL, recv_timeout_ms: Optional[int] = 5000
    ) -> None:
        self._addr = addr
        self._sock: Optional[pynng.Req0] = None
        self._lock = threading.Lock()
        self._recv_timeout_ms = recv_timeout_ms

    def __enter__(self) -> "RpcClient":
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def open(self) -> None:
        if self._sock is not None:
            return
        sock = pynng.Req0(dial=self._addr)
        if self._recv_timeout_ms is not None:
            sock.recv_timeout = self._recv_timeout_ms
        self._sock = sock
        print(f"[rpc_client] Connected to broker at {self._addr}")

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception as exc:
                print(f"[rpc_client] Error while closing socket: {exc}")
        self._sock = None

    def send_rpc(
        self,
        device_id: str,
        command: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self._sock is None:
            self.open()
        assert self._sock is not None

        with self._lock:
            if request_id is None:
                request_id = new_request_id()

            request_obj = make_rpc_request(
                device_id=device_id,
                command=command,
                params=params,
                request_id=request_id,
            )
            raw = to_bytes(request_obj)
            print(f"[rpc_client] Sending request: {request_obj!r}")

            try:
                self._sock.send(raw)
            except Exception as exc:
                raise RpcError(f"Failed to send RPC request: {exc}") from exc

            try:
                reply_raw = self._sock.recv()
            except pynng.Timeout:
                raise RpcTimeoutError(
                    f"RPC call timed out after {self._recv_timeout_ms} ms"
                )
            except Exception as exc:
                raise RpcError(f"Failed to receive RPC reply: {exc}") from exc

            try:
                reply_obj = from_bytes(reply_raw)
            except Exception as exc:
                raise RpcError(f"Failed to decode RPC reply JSON: {exc}") from exc

            print(f"[rpc_client] Received reply: {reply_obj!r}")

            return reply_obj
```

The bottom of the file contains a simple test `main()` which:

- `get_status` on `imu_1`
- `start_stream` on `imu_1`
- Waits 2s
- `stop_stream` on `imu_1`

You can run:

```bash
python rpc_client.py
```

### 7.2 CLI RPC client

`cli_client.py` (at root) gives you an interactive shell (and one‑shot mode).  
Example usages:

```bash
# One-shot RPC:
python cli_client.py once imu_1 get_status
python cli_client.py once imu_1 start_stream
python cli_client.py once imu_1 stop_stream

# Interactive shell:
python cli_client.py shell
```

Inside the shell:

- `imu_1 get_status`
- `imu_1 start_stream`
- `imu_1 stop_stream`

You can also pass key=value params:

- `dev_full_1 set_config rate=100.0 enabled=true`

(The device must implement such a command.)

### 7.3 Stream client

```python
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
    ...
    with pynng.Sub0() as sub:
        sub.recv_timeout = 5000
        sub.dial(dial_addr)
        sub.subscribe(topic_bytes)

        while True:
            try:
                wire = sub.recv()
            except pynng.Timeout:
                continue
            except KeyboardInterrupt:
                print("\n[stream_client] Interrupted by user, exiting.")
                break
            except Exception as exc:
                print(f"[stream_client] Error while receiving: {exc}", file=sys.stderr)
                break

            if not wire.startswith(topic_bytes):
                print(f"[stream_client] WARNING: received message without topic prefix")
                raw_json = wire
            else:
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
            print()
```

Run:

```bash
python stream_client.py --topic imu_1/imu
```

Or for a multi‑feed device:

- IMU: `--topic dev_full_1/imu`
- Colour: `--topic dev_full_1/color`
- Gestures: `--topic dev_full_1/gestures`
- Everything for device: `--topic dev_full_1` (because NNG topic is prefix‑based).

---

## 8. Running the Full Demo

### 8.1 Start broker (Terminal 1)

```bash
cd /home/agplaza/Desktop/courses/nanomesg_NG
python main.py
```

You should see logs like:

- `[broker] Starting broker...`
- `[stream] PUB listening on tcp://0.0.0.0:5556`
- `[devices] Initialised devices: ['imu_1', 'imu_2']`
- `[rpc] REP listening on tcp://0.0.0.0:5555`
- `[broker] Broker is up and running. Press Ctrl+C to stop.`

### 8.2 Start stream client (Terminal 2)

```bash
cd /home/agplaza/Desktop/courses/nanomesg_NG
python stream_client.py --topic imu_1/imu
```

Wait – nothing prints yet (no stream started).

### 8.3 Start RPC client (Terminal 3)

Use the built‑in test:

```bash
cd /home/agplaza/Desktop/courses/nanomesg_NG
python rpc_client.py
```

During the “IMU stream is active” period, Terminal 2 should print JSON IMU samples.

You can also use `cli_client.py` for interactive experiments.

---

## 9. Adapting to Realistic “Multi‑Feed” Devices

Currently the code has an `ImuDevice` as a concrete device. To model your actual use case (devices that have 0/1/2/3 of IMU/colour/gestures feeds, all with RPC), you’d:

1. Create a `MultiSensorDevice` that:
   - Accepts a configuration like `feeds={"imu": True, "color": False, "gestures": True}`.
   - Spawns background threads or internal loops for each enabled feed.
   - Publishes to topics:
     - `f"{device_id}/imu"`
     - `f"{device_id}/color"`
     - `f"{device_id}/gestures"`

2. Implement RPC commands such as:
   - `get_status`
   - `start_feed` / `stop_feed` (with a `feed` param).
   - `set_config`, `calibrate`, etc.

3. Register instances in `DeviceManager._init_devices()` with varying combinations of feeds:
   - `dev_full_1`: IMU + colour + gestures.
   - `dev_imu_only_1`: IMU only.
   - `dev_color_gestures_1`: colour + gestures.
   - `dev_plain_1`: no feeds, but still has RPC like `get_status`, `reset`, etc.

The rest of the stack (broker, `RpcClient`, `stream_client`) **does not change**.

---

## 10. Notes and Limitations

- **Ordering / reliability**:
  - RPC (`Req0`/`Rep0`) is strictly request/response, relatively straightforward.
  - Streaming (`Pub0`/`Sub0`) is:
    - **Best‑effort**: subscribers may drop messages if they can’t keep up.
    - **One‑way**: no acknowledgements.
- **Security**:
  - This demo has **no authentication, encryption, or authorization**.
  - For real deployments, put it behind a secure tunnel or extend messages with auth tokens and use NNG TLS or an additional secure layer.
- **Back‑pressure**:
  - PUB/SUB has limited back‑pressure; if streams are too fast, you may drop data.
  - For critical data, consider `Push0`/`Pull0` or `Pair0` patterns.

---

## 11. Summary

This project gives you a complete NNG‑based architecture:

- Broker with:
  - JSON RPC over `Req0`/`Rep0`.
  - Streaming feeds over `Pub0`/`Sub0`.
- Devices modeled as flexible, multi‑feed entities:
  - 0/1/2/3 feeds (IMU/colour/gestures) per device.
  - RPC control surface on every device.
- Clients:
  - A reusable `RpcClient` helper.
  - A CLI for ad‑hoc RPC testing.
  - A SUB client for streaming feeds.

From here, you can:

- Extend devices and RPC commands.
- Add more realistic data generation for IMU/colour/gestures.
- Introduce configuration persistence, authentication, or better error reporting.

If you want, I can next:

- Add a `MultiSensorDevice` class with all three feeds, plus:
  - Example RPC commands per feed.
  - Device instances in `DeviceManager` matching your intended topology.