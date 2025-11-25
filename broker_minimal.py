import pynng

print(pynng.__version__)

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
