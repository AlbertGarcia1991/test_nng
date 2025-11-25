1. Internal Components of the NNG Service Container

Within this container, I’d model at least these logical components:

1. **RPC Interface Component**
   - Code: `broker.rpc_server.RpcServer`
   - Responsibilities:
     - Owns the **NNG `Rep0` socket** bound to the RPC address.
     - Receives JSON RPC requests from clients.
     - Validates basic request structure (`type`, `device_id`, `command`, `params`).
     - Delegates to the `DeviceManager` for business logic.
     - Wraps device responses into standard OK/ERROR JSON replies.
   - Key interfaces:
     - **Inbound**: `Req0` clients (external).
     - **Outbound**: Calls `DeviceManager.handle_rpc(...)`.

2. **Streaming Interface Component**
   - Code: `broker.stream.StreamPublisher`
   - Responsibilities:
     - Owns the **NNG `Pub0` socket** bound to the streaming address.
     - Exposes a simple `publish(topic: str, payload: dict)` method.
     - Converts `(topic, payload)` into wire format:
       - `b"<topic> " + b"<json>"` where JSON is `{ "topic": ..., "payload": ... }`.
     - Sends frames to all interested `Sub0` clients.
   - Key interfaces:
     - **Inbound**: Called by device components (via `DeviceManager` or directly).
     - **Outbound**: `Sub0` clients (external).

3. **Device Manager Component**
   - Code: `broker.device_manager.DeviceManager`
   - Responsibilities:
     - Registry of all **devices** in the system.
       - Mapping `device_id -> Device` instance.
     - Orchestrates device lifecycle (init, optional shutdown).
     - Dispatches RPC calls to the appropriate device:
       - `handle_rpc(device_id, command, params)`.
     - Holds the **publish callback** provided by `StreamPublisher`, and passes it to devices that generate streams.
   - Key interfaces:
     - **Inbound**: Called by `RPC Interface` component.
     - **Outbound**: Calls individual **device** objects; uses `StreamPublisher.publish` indirectly through devices.

4. **Device Components (Device Instances / Types)**
   - Code: `broker.devices.*` (e.g. `ImuDevice`, and conceptually MultiSensor/Colour/Gesture devices).
   - Responsibilities:
     - Implement **per‑device business logic**, including:
       - RPC command handling: `handle_command(command, params)`.
       - Optional background data generation loops (IMU/colour/gestures).
     - For devices with feeds:
       - Run background threads/timers that periodically generate samples.
       - Invoke `publish(topic, payload)` (via the callback from `DeviceManager`) to push data to the streaming interface.
   - Key interfaces:
     - **Inbound**:
       - Called by `DeviceManager.handle_rpc(...)` to execute commands.
     - **Outbound**:
       - Use provided `publish_fn(topic, payload)` to forward streaming data to `StreamPublisher`.
   - Variability (per device type):
     - Some devices:
       - Have **all three feeds** (IMU, colour, gestures).
       - Some only a subset.
       - Some with **no streaming feeds at all**, but still full RPC support (e.g. config‑only devices).

5. **Configuration & Protocol Utilities (Shared Internal Library)**
   - Code:
     - `common.config` – addresses and configuration.
     - `common.protocol` – JSON helpers and message structure.
   - Responsibilities:
     - Central configuration of NNG endpoints.
     - Standardized JSON encoding/decoding and RPC envelope creation.
   - Key interfaces:
     - Used by:
       - `RPC Interface` component.
       - `Streaming Interface` component.
       - Device components (for structured results).
       - Test clients (outside this container).

6. **Process / Lifecycle Orchestrator**
   - Code: `main.py`
   - Responsibilities:
     - Boots all the other components:
       - Instantiates the `StreamPublisher`.
       - Creates `DeviceManager` with the `publish` callback.
       - Creates and starts `RpcServer` (RPC interface).
     - Installs signal handlers (SIGINT/SIGTERM).
     - Coordinates **graceful shutdown** (stop RPC loop, close sockets, optionally stop device threads).
   - Key interfaces:
     - Calls into all the other components’ constructors and lifecycle methods.

---

## 2. External Dependencies (For This Container)

These are things **outside** this container boundary that it depends on or interacts with:

1. **NNG Library (via `pynng`)**
   - The core messaging engine.
   - Exposes:
     - `pynng.Rep0`
     - `pynng.Pub0`
     - `pynng.SocketBase` behaviors like `send`, `recv`, `dial`, `listen`, timeouts.
   - This is a **technical infrastructure dependency**: the container will not function without it.

2. **Client Applications**
   - Not inside this container; they live in other containers / processes.
   - Types:
     - RPC clients using `Req0`:
       - `rpc_client.py`
       - CLI client, GUI, or any other service.
     - Streaming clients using `Sub0`:
       - `stream_client.py`
       - Potential dashboards/visualizers.
   - Responsibilities:
     - Forming proper JSON RPC requests.
     - Handling RPC responses.
     - Subscribing to appropriate topics and processing streaming data.

3. **Operating System / Network Stack**
   - The OS’s TCP/IP stack (for `tcp://` transports).
   - Manages sockets, ports, addresses.

4. **(Optional) Configuration / Deployment Environment**
   - Environment variables, config management, containers (Docker/Kubernetes), etc.
   - Not explicit in code, but relevant for the C4 model depending on your scope.

You can show `pynng/NNG` as a **“Messaging Middleware / Library”** that this container uses, and “RPC Client” / “Stream Client” containers as external systems that connect via TCP.

---

## 3. Relationships Between Internal Components

Here’s how you can show the relationships in the C3 component diagram.

### 3.1 Overview Relationships

- **Process Orchestrator** (`main.py`):
  - Creates:
    - `Streaming Interface` (`StreamPublisher`) component.
    - `Device Manager` component, passing it the `publish` function.
    - `RPC Interface` (`RpcServer`) component, passing it the `DeviceManager`.
  - Manages lifetime / shutdown.

- **RPC Interface Component** (`RpcServer`):
  - **Uses NNG Rep0 socket** (via `pynng`).
  - **Calls** `DeviceManager.handle_rpc(device_id, command, params)` when requests come in.
  - **Uses** `common.protocol` to decode/encode JSON.

- **Streaming Interface Component** (`StreamPublisher`):
  - **Uses NNG Pub0 socket** (via `pynng`).
  - Provides `publish(topic, payload)` used by devices.
  - **Uses** JSON to encode frames (internal protocol format).

- **Device Manager Component** (`DeviceManager`):
  - Maintains `device_id -> Device` mapping.
  - **Calls** `device.handle_command(command, params)` for RPC dispatch.
  - **Provides** `publish_fn` to devices (a closure to `StreamPublisher.publish`).

- **Device Components** (`BaseDevice` subclasses):
  - **Called by** `DeviceManager` for each RPC.
  - **Call back** into the `Streaming Interface` via the `publish_fn` when generating streaming data.
  - Some may run background threads to continually push data.

- **Common Utilities Component** (`common.config`, `common.protocol`):
  - Shared by:
    - `RPC Interface` (for decoding/encoding requests and replies).
    - `Streaming Interface` (for JSON serialization).
    - Devices (for consistent result structure, if desired).

### 3.2 Direction of Dependencies

In a diagram, you can show arrows like:

- `Process Orchestrator` → `RPC Interface`
- `Process Orchestrator` → `Streaming Interface`
- `Process Orchestrator` → `Device Manager`
- `RPC Interface` → `Device Manager`
- `Device Manager` → `Device Components` (polymorphic)
- `Device Components` → `Streaming Interface` (via callback, but conceptually they depend on streaming)
- All components → `NNG / pynng library` (technical dependency)
- `Common Utilities` → used by RPC/Stream/Devices

And externally:

- `RPC Clients (Req0)` → **talk to** → `RPC Interface (Rep0)`
- `Streaming Clients (Sub0)` ← **receive from** ← `Streaming Interface (Pub0)`
- `NNG library` is a dependency for both the `RPC Interface` and `Streaming Interface` internal components.

---

## 4. How to Name Components in a C3 Diagram

Here’s one way to label them in a C4 C3 diagram (for the NNG service container):

**Internal components:**

1. **RPC Interface**
   - *“Handles JSON RPC via NNG Req/Rep. Validates and routes requests to devices.”*
2. **Streaming Interface**
   - *“Publishes IMU/colour/gestures streams over NNG Pub/Sub to subscribers.”*
3. **Device Manager**
   - *“Registry and dispatcher for all simulated devices; bridges RPC and streaming.”*
4. **Device Components**
   - *“Per-device logic (RPC commands, optional feeds). Some devices provide IMU, colour, and/or gesture streams; some only expose RPC with no feeds.”*
5. **Configuration & Protocol**
   - *“Shared JSON protocol helpers and endpoint configuration.”*
6. **Process / Lifecycle**
   - *“Bootstraps all components and coordinates startup/shutdown.”*

**External dependencies in the C3 view:**

- **NNG / pynng Library**
  - *“Messaging middleware providing Req/Rep and Pub/Sub semantics over TCP, IPC, etc.”*
- **RPC Clients**
  - *“External applications and tools calling RPC operations via NNG Req0.”*
- **Streaming Clients**
  - *“External applications subscribed to IMU/colour/gesture topics via NNG Sub0.”*
- **Operating System / Network**
  - *“Provides TCP/IP transport for NNG sockets.”#
  
## 5. Diagram
+-------------------------------------------------------------+
|                 Container: NNG Service (Broker)             |
|-------------------------------------------------------------|
|                                                             |
|  [Component] Process Orchestrator                           |
|     - Entry point (main.py)                                 |
|     - Wires up and starts RPC Interface, Streaming          |
|       Interface, Device Manager                             |
|                                                             |
|      |                                                      |
|      v                                                      |
|  [Component] RPC Interface (Rep0)                           |
|     - Uses NNG Rep0 socket (listen RPC_ADDR)                |
|     - Receives JSON RPC requests from clients               |
|     - Validates basic structure                             |
|     - Calls Device Manager for business logic               |
|                                                             |
|      |  (handle_rpc(device_id, command, params))            |
|      v                                                      |
|  [Component] Device Manager                                 |
|     - Maintains registry: device_id -> Device instance      |
|     - Dispatches RPC commands to devices                    |
|     - Provides devices with publish_fn for streaming        |
|                                                             |
|      |                             ^                        |
|      | (handle_command(...))       | (publish(topic,payload)) 
|      v                             |                        |
|  [Component] Device Components -----                        |
|     - Implement RPC commands per device                     |
|     - Optionally run background loops (IMU/colour/          |
|       gestures)                                             |
|     - Use publish_fn to send stream data                    |
|                                                             |
|                                      |                      |
|                                      v                      |
|  [Component] Streaming Interface (Pub0)                     |
|     - Uses NNG Pub0 socket (listen STREAM_PUB_ADDR)         |
|     - publish(topic, payload) -> send wire frame            |
|                                                             |
|                                                             |
|  [Component] Configuration & Protocol                       |
|     - Provides RPC/stream JSON helpers and endpoint config  |
|     - Used by RPC Interface, Streaming Interface, Devices   |
|                                                             |
+-------------------------------------------------------------+

---

Inside container (logical dependencies):

Process Orchestrator
    --> RPC Interface
    --> Streaming Interface
    --> Device Manager

RPC Interface
    --> NNG Library (pynng.Rep0)
    --> Configuration & Protocol
    --> Device Manager

Streaming Interface
    --> NNG Library (pynng.Pub0)
    --> Configuration & Protocol

Device Manager
    --> Device Components

Device Components
    --> Streaming Interface (via publish_fn)
    --> Configuration & Protocol (optionally for structured payload)

Configuration & Protocol
    (no internal dependencies, just standard Python libs)


External dependencies:

RPC Client Applications
    --> RPC Interface (over NNG Req0/Rep0 via tcp://)

Streaming Client Applications
    <-- Streaming Interface (over NNG Pub0/Sub0 via tcp://)

NNG Library (pynng)
    <- RPC Interface
    <- Streaming Interface
    (and outside this container, client apps also depend on NNG)

Operating System / Network Stack
    <- NNG Library
    (provides transport for tcp:// endpoints)

---

Container "NNG Service" <<Python>> {
    Component "Process Orchestrator" <<Component>> "Bootstraps all other components and handles lifecycle."
    Component "RPC Interface" <<Component>> "NNG Rep0 endpoint for JSON RPC."
    Component "Streaming Interface" <<Component>> "NNG Pub0 endpoint for streaming."
    Component "Device Manager" <<Component>> "Registry and dispatcher for devices."
    Component "Device Components" <<Component>> "Per-device logic, RPC and streams."
    Component "Configuration & Protocol" <<Component>> "Shared JSON and config helpers."
}

System "NNG Library (pynng)" <<Library>>
System "RPC Client Applications" <<External System>>
System "Streaming Client Applications" <<External System>>

Rel "Process Orchestrator" -> "RPC Interface" "starts and configures"
Rel "Process Orchestrator" -> "Streaming Interface" "starts and configures"
Rel "Process Orchestrator" -> "Device Manager" "instantiates"

Rel "RPC Interface" -> "NNG Library (pynng)" "uses Rep0 socket"
Rel "RPC Interface" -> "Device Manager" "dispatches RPC"
Rel "RPC Interface" -> "Configuration & Protocol" "JSON encode/decode"

Rel "Streaming Interface" -> "NNG Library (pynng)" "uses Pub0 socket"
Rel "Streaming Interface" -> "Configuration & Protocol" "JSON encode"

Rel "Device Manager" -> "Device Components" "invokes handle_command"

Rel "Device Components" -> "Streaming Interface" "publish stream data"
Rel "Device Components" -> "Configuration & Protocol" "builds payloads"

Rel "RPC Client Applications" -> "RPC Interface" "send JSON RPC over Req0/Rep0"
Rel "Streaming Interface" -> "Streaming Client Applications" "broadcast streams over Pub0/Sub0"
