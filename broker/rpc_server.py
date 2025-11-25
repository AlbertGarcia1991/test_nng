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

    Responsibilities:
      - Listen for JSON-encoded RPC requests from clients.
      - Decode/validate basic structure.
      - Delegate actual command handling to DeviceManager.
      - Wrap responses in the standard OK/ERROR reply envelope.
    """

    def __init__(self, device_manager: DeviceManager) -> None:
        self._device_manager = device_manager
        self._sock: pynng.Rep0 | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #

    def start(self) -> None:
        """
        Start the REP socket and background loop thread.
        Safe to call only once.
        """
        if self._thread is not None:
            # Already started
            return

        # Create and bind the REP socket
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
        """
        Request the loop to stop and close the socket.
        """
        self._stop_event.set()

        # Closing the socket will unblock any blocking recv() call
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception as exc:  # pragma: no cover - best-effort
                print(f"[rpc] Error while closing socket: {exc}")

        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    # --------------------------------------------------------------------- #
    # Internal loop
    # --------------------------------------------------------------------- #

    def _run_loop(self) -> None:
        """
        Main REP loop: recv → handle → send, until stop_event is set.
        """
        assert self._sock is not None, "Socket must be created before starting loop"

        sock = self._sock

        while not self._stop_event.is_set():
            try:
                raw = sock.recv()  # blocks until message or socket closed
            except pynng.NNGError as exc:
                # If the socket was closed as part of shutdown, just exit loop
                if self._stop_event.is_set():
                    break
                print(f"[rpc] NNGError on recv: {exc}")
                continue
            except Exception as exc:
                print(f"[rpc] Unexpected error on recv: {exc}")
                continue

            # At this point we have some bytes; attempt to process them.
            reply_bytes = self._handle_raw_message(raw)

            # With REP we must still send a reply even if it's an error
            try:
                sock.send(reply_bytes)
            except pynng.NNGError as exc:
                if self._stop_event.is_set():
                    break
                print(f"[rpc] NNGError on send: {exc}")
            except Exception as exc:
                print(f"[rpc] Unexpected error on send: {exc}")

        print("[rpc] Loop exiting")

    # --------------------------------------------------------------------- #
    # Request handling
    # --------------------------------------------------------------------- #

    def _handle_raw_message(self, raw: bytes) -> bytes:
        """
        Convert raw bytes into a reply bytes payload.
        Always returns a valid JSON reply (OK or ERROR envelope).
        """
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

        # Basic validation
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

        # Delegate to DeviceManager
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
            # Used by devices to signal unsupported commands etc.
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
