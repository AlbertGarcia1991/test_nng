from __future__ import annotations

import argparse
import json
import shlex
import sys
from typing import Any, Dict, Optional

from .rpc_client import RpcClient, RpcError, RpcTimeoutError


def parse_kv_pairs(pairs: list[str]) -> Dict[str, Any]:
    """
    Parse key=value pairs from CLI into a dict.

    Examples:
        ["foo=1", "bar=true", "name=alice"]
        -> {"foo": 1, "bar": True, "name": "alice"}

    Values are parsed with a very small heuristic:
        - "true"/"false" (case-insensitive) -> bool
        - "null"/"none" -> None
        - ints and floats are parsed numerically
        - everything else stays as string
    """

    def parse_value(v: str) -> Any:
        vl = v.lower()
        if vl == "true":
            return True
        if vl == "false":
            return False
        if vl in ("null", "none"):
            return None

        # Try int, then float
        try:
            return int(v)
        except ValueError:
            pass
        try:
            return float(v)
        except ValueError:
            pass
        return v

    result: Dict[str, Any] = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"Invalid param '{pair}', expected key=value")
        key, value = pair.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Invalid param '{pair}', empty key")
        result[key] = parse_value(value.strip())
    return result


def print_reply(reply: Dict[str, Any]) -> None:
    """
    Pretty-print a reply from the broker.
    """
    status = reply.get("status")
    request_id = reply.get("request_id")
    print(f"\n[reply] status={status}, request_id={request_id}")

    if status == "OK":
        result = reply.get("result")
        print("[reply] result:")
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        err = reply.get("error") or {}
        code = err.get("code")
        msg = err.get("message")
        print(f"[reply] error code={code}, message={msg}")


def run_single_command(
    device_id: str,
    command: str,
    params: Dict[str, Any],
    addr: Optional[str],
) -> int:
    """
    Run a single RPC command and exit.
    """
    client_kwargs: Dict[str, Any] = {}
    if addr is not None:
        client_kwargs["addr"] = addr

    try:
        with RpcClient(**client_kwargs) as client:
            reply = client.send_rpc(device_id=device_id, command=command, params=params)
            print_reply(reply)
    except RpcTimeoutError as exc:
        print(f"[cli_client] ERROR: {exc}", file=sys.stderr)
        return 1
    except RpcError as exc:
        print(f"[cli_client] ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[cli_client] Unexpected error: {exc}", file=sys.stderr)
        return 1

    return 0


def interactive_shell(addr: Optional[str]) -> int:
    """
    Interactive shell mode.

    Syntax:
        device_id command [key=value ...]
    Examples:
        imu_1 get_status
        imu_1 start_stream
        imu_1 set_mode mode=fast threshold=0.5
    """
    print("NNG Demo CLI")
    print("------------")
    if addr:
        print(f"Broker RPC address: {addr}")
    print("Type 'help' for instructions, 'quit' or 'exit' to leave.\n")

    client_kwargs: Dict[str, Any] = {}
    if addr is not None:
        client_kwargs["addr"] = addr

    with RpcClient(**client_kwargs) as client:
        while True:
            try:
                line = input("rpc> ")
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print()
                break

            line = line.strip()
            if not line:
                continue
            if line.lower() in ("quit", "exit"):
                break
            if line.lower() in ("help", "?"):
                print(
                    "Usage:\n"
                    "  device_id command [key=value ...]\n"
                    "Examples:\n"
                    "  imu_1 get_status\n"
                    "  imu_1 start_stream\n"
                    "  imu_1 set_params rate=100.0 enabled=true\n"
                    "Special commands:\n"
                    "  help, ?, quit, exit\n"
                )
                continue

            # Use shlex to allow quoting values with spaces
            try:
                tokens = shlex.split(line)
            except ValueError as exc:
                print(f"[cli_client] Parse error: {exc}")
                continue

            if len(tokens) < 2:
                print("[cli_client] Expected: device_id command [key=value ...]")
                continue

            device_id, command, *param_tokens = tokens
            try:
                params = parse_kv_pairs(param_tokens)
            except ValueError as exc:
                print(f"[cli_client] Parameter error: {exc}")
                continue

            try:
                reply = client.send_rpc(
                    device_id=device_id, command=command, params=params
                )
                print_reply(reply)
            except RpcTimeoutError as exc:
                print(f"[cli_client] ERROR: {exc}")
            except RpcError as exc:
                print(f"[cli_client] ERROR: {exc}")
            except Exception as exc:
                print(f"[cli_client] Unexpected error: {exc}")

    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Simple CLI client for sending RPC commands to the NNG broker.",
    )
    parser.add_argument(
        "--addr",
        help="Broker RPC address to dial (overrides default from config.RPC_DIAL).",
    )

    subparsers = parser.add_subparsers(dest="mode", required=False)

    # Non-interactive 'once' mode
    once = subparsers.add_parser(
        "once",
        help="Send a single RPC and exit.",
    )
    once.add_argument("device_id", help="Target device ID (e.g. imu_1).")
    once.add_argument("command", help="Command to execute on the device.")
    once.add_argument(
        "params",
        nargs="*",
        help="Optional key=value parameters.",
    )

    # Interactive mode (default if no subcommand)
    subparsers.add_parser(
        "shell",
        help="Start an interactive RPC shell (default if no subcommand is given).",
    )

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    mode = args.mode or "shell"
    addr: Optional[str] = args.addr

    if mode == "once":
        try:
            params = parse_kv_pairs(args.params)
        except ValueError as exc:
            print(f"[cli_client] Parameter error: {exc}", file=sys.stderr)
            return 1
        return run_single_command(
            device_id=args.device_id,
            command=args.command,
            params=params,
            addr=addr,
        )

    # Default: interactive shell
    return interactive_shell(addr=addr)


if __name__ == "__main__":
    raise SystemExit(main())
