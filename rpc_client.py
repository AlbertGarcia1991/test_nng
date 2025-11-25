from __future__ import annotations

import threading
from typing import Any, Dict, Optional

import pynng

from common.config import RPC_DIAL
from common.protocol import (
    from_bytes,
    make_error_reply,
    make_rpc_request,
    new_request_id,
    to_bytes,
)


class RpcError(Exception):
    """Base class for RPC-related errors."""


class RpcTimeoutError(RpcError):
    """Raised when an RPC call times out."""


class RpcClient:
    """
    Helper for JSON-based RPC over an NNG Req0 socket.

    Responsibilities:
      - Manage a single Req0 socket connected to the broker.
      - Send JSON-encoded RPC requests using the shared protocol helpers.
      - Receive and decode JSON replies.
      - Provide a simple send_rpc() method for callers.

    Pattern:
      - For Req0 sockets, the pattern is strictly: send() → recv() → send() → recv().
      - This client should therefore be used from a single thread at a time, or
        with an external lock around send_rpc().
    """

    def __init__(
        self, addr: str = RPC_DIAL, recv_timeout_ms: Optional[int] = 5000
    ) -> None:
        """
        Args:
            addr: Address to dial, e.g. "tcp://127.0.0.1:5555".
            recv_timeout_ms: Optional timeout for recv() in milliseconds.
                             If None, recv() blocks indefinitely.
        """
        self._addr = addr
        self._sock: Optional[pynng.Req0] = None
        self._lock = threading.Lock()
        self._recv_timeout_ms = recv_timeout_ms

    # ------------------------------------------------------------------ #
    # Context manager & lifecycle
    # ------------------------------------------------------------------ #

    def __enter__(self) -> "RpcClient":
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def open(self) -> None:
        """Open the underlying Req0 socket if it is not already open."""
        if self._sock is not None:
            return

        sock = pynng.Req0(dial=self._addr)
        if self._recv_timeout_ms is not None:
            sock.recv_timeout = self._recv_timeout_ms
        self._sock = sock
        print(f"[rpc_client] Connected to broker at {self._addr}")

    def close(self) -> None:
        """Close the underlying Req0 socket."""
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception as exc:  # pragma: no cover - best-effort cleanup
                print(f"[rpc_client] Error while closing socket: {exc}")
        self._sock = None

    # ------------------------------------------------------------------ #
    # Core RPC call
    # ------------------------------------------------------------------ #

    def send_rpc(
        self,
        device_id: str,
        command: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a single RPC request and wait for the reply.

        This method is synchronous and blocks until a reply is received or
        the socket times out.

        Args:
            device_id: Target device identifier.
            command: Command name to execute on the device.
            params: Optional dict of parameters.
            request_id: Optional explicit request_id. If not provided, a new
                        UUID-based ID will be generated.

        Returns:
            The decoded reply object (dict) from the broker. The reply will
            contain:
              - "status": "OK" or "ERROR"
              - "result": payload if "OK"
              - "error": error object if "ERROR"
              - "request_id": should match the original request_id

        Raises:
            RpcTimeoutError: If the call times out.
            RpcError: On other transport or protocol-level issues.
        """
        # Ensure socket is ready
        if self._sock is None:
            self.open()
        assert self._sock is not None  # for type checkers

        # Ensure we respect Req0 send→recv ordering using a lock
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

            # Optional: basic request_id verification
            reply_req_id = reply_obj.get("request_id")
            if reply_req_id != request_id:
                print(
                    f"[rpc_client] WARNING: request_id mismatch "
                    f"(sent {request_id!r}, received {reply_req_id!r})"
                )

            return reply_obj


# ---------------------------------------------------------------------- #
# Simple CLI/test entrypoint
# ---------------------------------------------------------------------- #


def main() -> None:
    """
    Simple manual test to exercise the RpcClient against a running broker.

    This assumes:
      - The broker is running and listening on RPC_DIAL.
      - The broker has at least an 'imu_1' device that supports:
          - get_status
          - start_stream
          - stop_stream
    """
    from time import sleep

    with RpcClient() as client:
        # Basic status check
        print("\n--- get_status ---")
        reply = client.send_rpc("imu_1", "get_status")
        print("Reply:", reply)

        # Start the IMU stream
        print("\n--- start_stream ---")
        reply = client.send_rpc("imu_1", "start_stream")
        print("Reply:", reply)

        # Wait a bit while stream runs (stream data handled by stream_client)
        print("\nWaiting 2 seconds while IMU stream is active...")
        sleep(2.0)

        # Stop the IMU stream
        print("\n--- stop_stream ---")
        reply = client.send_rpc("imu_1", "stop_stream")
        print("Reply:", reply)


if __name__ == "__main__":
    main()
