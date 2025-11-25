import time

import pynng
from pynng import Rep0

# print(pynng.__version__)

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

def main():
    with Rep0() as sock:
        # Listen on TCP port 5555 on all interfaces.
        # This means local and remote clients can connect, assuming firewall/network allow it.
        broker_endpoint = 'tcp://0.0.0.0:5555'
        sock.listen(broker_endpoint)
        print(f"Broker (REP) listening on {broker_endpoint}")
        
        while True:
            # Wait for a req from any connected REQ client. This call blocks until a msg arrives
            msg = sock.recv()
            print(f"[BROKER] Received message: {msg}")
        
            # For now, just respond with a stating "pong" message
            reply = b"pong"
            print(f"[BROKER] Sending reply: {reply}")
            sock.send(reply)
            
            # Sleep a bit just so logs are readable when testing
            time.sleep(0.5)
            
if __name__ == "__main__":
    main()