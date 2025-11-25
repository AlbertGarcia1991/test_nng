import json
import uuid
import pynng


BROKER_ADDR = "tcp://127.0.0.1:5555"


def send_rpc(sock: pynng.Req0, device_id: str, command: str, params: dict | None = None) -> dict:
    if params is None:
        params = {}

    request_id = str(uuid.uuid4())
    request_obj = {
        "type": "rpc",
        "device_id": device_id,
        "command": command,
        "params": params,
        "request_id": request_id,
    }

    raw = json.dumps(request_obj).encode("utf-8")
    print(f"[client] Sending: {request_obj}")
    sock.send(raw)

    reply_raw = sock.recv()  # bytes
    print(f"[client] Raw reply: {reply_raw!r}")

    reply_obj = json.loads(reply_raw.decode("utf-8"))
    print(f"[client] Parsed reply: {reply_obj}")

    # Optional: verify request_id matches
    if reply_obj.get("request_id") != request_id:
        print("[client] WARNING: request_id mismatch")

    return reply_obj


def main():
    with pynng.Req0(dial=BROKER_ADDR) as sock:
        # Basic RPCs
        send_rpc(sock, device_id="imu_1", command="ping")
        send_rpc(sock, device_id="imu_1", command="get_status")
        send_rpc(sock, device_id="imu_1", command="unknown_cmd")


if __name__ == "__main__":
    main()
