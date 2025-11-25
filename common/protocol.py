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

def to_bytes(obj: Dict[str, Any]) -> bytes:
    return json.dumps(obj).encode("utf-8")

def from_bytes(data: bytes) -> Dict[str, Any]:
    return json.loads(data.decode("utf-8"))
