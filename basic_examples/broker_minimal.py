"""
Quick NNG Concepts
    - Req0 / Rep0: Used for requests/reponse (RPC) semantics. Client sends request; server receives
        it and must send a reply before it can receive the next one on that socket.
    - Pub0 / Sub0: Used for publish/subscribe semantics. Subscribers can apply filters by topic, a
        string that is prepended to the message. Publishers can send messages to multiple
        subscribers.
    - Bind vs Dial:
        - sock.listen('tcp://*:5555') binds (listens for incoming connections)
        - sock.dial('tcp://localhost:5555') dials (connects to a remote listening endpoint)
"""

import json
import pynng


BROKER_ADDR = "tcp://0.0.0.0:5555"


def handle_rpc(request_obj: dict) -> dict:
    """
    Dummy handler for an RPC-like request.
    For now we just echo and simulate a BLE device response.
    """

    request_id = request_obj.get("request_id")
    device_id = request_obj.get("device_id")
    command = request_obj.get("command")
    params = request_obj.get("params", {})

    # Simulated BLE device routing:
    # In a richer design, you'd dispatch based on device_id and command
    # to a "device manager". For now, keep it simple.

    if command == "ping":
        result = {
            "device_id": device_id,
            "reply": "pong",
        }
        return {
            "request_id": request_id,
            "status": "OK",
            "error": None,
            "result": result,
        }

    elif command == "get_status":
        # Fake status
        result = {
            "device_id": device_id,
            "status": "READY",
            "battery": 95,
        }
        return {
            "request_id": request_id,
            "status": "OK",
            "error": None,
            "result": result,
        }

    else:
        # Unknown command
        return {
            "request_id": request_id,
            "status": "ERROR",
            "error": {
                "code": "UNKNOWN_COMMAND",
                "message": f"Command '{command}' not supported for device '{device_id}'",
            },
            "result": None,
        }


def main():
    print(f"[broker] Starting broker at {BROKER_ADDR}")

    with pynng.Rep0(listen=BROKER_ADDR) as sock:
        # REP sockets must always: recv → send → recv → send ...
        while True:
            try:
                raw = sock.recv()  # bytes
                print(f"[broker] Raw message: {raw!r}")

                try:
                    request_obj = json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError as e:
                    print(f"[broker] JSON decode error: {e}")
                    # For REP pattern, must still return *something*
                    error_reply = {
                        "request_id": None,
                        "status": "ERROR",
                        "error": {
                            "code": "BAD_JSON",
                            "message": str(e),
                        },
                        "result": None,
                    }
                    sock.send(json.dumps(error_reply).encode("utf-8"))
                    continue

                print(f"[broker] Parsed request: {request_obj}")

                msg_type = request_obj.get("type")
                if msg_type != "rpc":
                    # For now only support 'rpc'. Later we add 'stream_subscribe', etc.
                    error_reply = {
                        "request_id": request_obj.get("request_id"),
                        "status": "ERROR",
                        "error": {
                            "code": "UNSUPPORTED_TYPE",
                            "message": f"Unsupported message type: {msg_type}",
                        },
                        "result": None,
                    }
                    sock.send(json.dumps(error_reply).encode("utf-8"))
                    continue

                # Handle RPC
                reply_obj = handle_rpc(request_obj)
                reply_raw = json.dumps(reply_obj).encode("utf-8")
                print(f"[broker] Sending reply: {reply_obj}")
                sock.send(reply_raw)

            except Exception as e:
                # If anything goes wrong, ensure REP still sends a reply
                print(f"[broker] Unexpected error: {e}")
                fallback = {
                    "request_id": None,
                    "status": "ERROR",
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": str(e),
                    },
                    "result": None,
                }
                try:
                    sock.send(json.dumps(fallback).encode("utf-8"))
                except Exception as e2:
                    print(f"[broker] Failed to send error reply: {e2}")


if __name__ == "__main__":
    main()
