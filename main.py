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
    """
    Install basic SIGINT/SIGTERM handlers that trigger a clean shutdown.
    """

    def handler(signum, frame):
        print(f"[broker] Caught signal {signum}, initiating shutdown...")
        shutdown_callback()

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)


def main():
    print(f"[broker] Starting broker...")
    print(f"[broker] RPC address: {RPC_ADDR}")

    # ExitStack lets us manage multiple context managers and ensure graceful teardown.
    with ExitStack() as stack:
        # Stream publisher (PUB socket)
        stream_publisher = stack.enter_context(StreamPublisher())

        # Device manager (simulated BLE devices) with access to publish function
        device_manager = DeviceManager(publish_fn=stream_publisher.publish)

        # RPC server (REP socket) using the device manager
        rpc_server = RpcServer(device_manager=device_manager)
        rpc_server.start()

        # Shutdown coordination
        shutdown_event = threading.Event()

        def shutdown():
            if not shutdown_event.is_set():
                shutdown_event.set()
                print("[broker] Shutting down RPC server...")
                rpc_server.stop()
                print("[broker] Shutdown complete.")

        _install_signal_handlers(shutdown)

        print("[broker] Broker is up and running. Press Ctrl+C to stop.")

        # Block until a shutdown is requested
        try:
            shutdown_event.wait()
        except KeyboardInterrupt:
            # Fallback if signal handlers didn't run for some reason
            shutdown()

    print("[broker] Exited cleanly.")


if __name__ == "__main__":
    # Ensure unhandled exceptions don't leave things half-open.
    try:
        main()
    except Exception as exc:
        print(f"[broker] Fatal error: {exc}", file=sys.stderr)
        sys.exit(1)
