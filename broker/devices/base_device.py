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
