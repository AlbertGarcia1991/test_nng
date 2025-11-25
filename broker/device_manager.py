from __future__ import annotations

from typing import Any, Callable, Dict

from broker.devices.imu_device import ImuDevice

# from broker.devices.color_device import ColourDevice
# from broker.devices.gesture_device import GestureDevice


PublishFn = Callable[[str, Dict[str, Any]], None]


class DeviceManager:
    """
    Central registry and façade for all simulated BLE devices.

    It is constructed with a `publish_fn` callback, which is passed down to
    devices that support streaming (e.g. IMU, colour, gesture). The callback
    will typically be `StreamPublisher.publish`, which knows how to publish
    messages on the broker's PUB socket.

    Public responsibilities:
      - Maintain an in-memory mapping of device_id -> device instance.
      - Provide a single `handle_rpc` method used by the RPC server to
        dispatch RPC commands to the correct device.
    """

    def __init__(self, publish_fn: PublishFn) -> None:
        self._publish_fn = publish_fn
        self._devices: Dict[str, Any] = {}
        self._init_devices()

    # ------------------------------------------------------------------ #
    # Initialisation
    # ------------------------------------------------------------------ #

    def _init_devices(self) -> None:
        """
        Instantiate and register all simulated devices.

        For now this is hard-coded, but it could be loaded from config
        or discovered dynamically.
        """
        # IMU devices use streaming, so they receive the publish callback.
        self._devices["imu_1"] = ImuDevice("imu_1", publish_fn=self._publish_fn)
        self._devices["imu_2"] = ImuDevice("imu_2", publish_fn=self._publish_fn)

        # Example placeholders for future devices:
        # self._devices["colour_1"] = ColourDevice("colour_1", publish_fn=self._publish_fn)
        # self._devices["gesture_1"] = GestureDevice("gesture_1", publish_fn=self._publish_fn)

        print(f"[devices] Initialised devices: {list(self._devices.keys())}")

    # ------------------------------------------------------------------ #
    # RPC Dispatch
    # ------------------------------------------------------------------ #

    def handle_rpc(
        self, device_id: str, command: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Dispatch an RPC command to the appropriate device instance.

        Raises:
            KeyError: if the device_id is unknown.
            ValueError: if the device rejects the command as invalid.
        """
        device = self._devices.get(device_id)
        if not device:
            raise KeyError(f"Unknown device_id: {device_id}")

        return device.handle_command(command, params)

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def shutdown(self) -> None:
        """
        Optional: allow devices to perform cleanup (e.g. stop threads).
        """
        for dev_id, dev in self._devices.items():
            shutdown_method = getattr(dev, "shutdown", None)
            if callable(shutdown_method):
                try:
                    shutdown_method()
                except Exception as exc:  # pragma: no cover - best-effort cleanup
                    print(f"[devices] Error while shutting down {dev_id}: {exc}")
