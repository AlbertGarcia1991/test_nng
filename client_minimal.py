import time
from pynng import Req0

def main():
    broker_endpoint = 'tcp://0.0.0.0:5555'
    
    # Create a Req0 socket and connect to the broker
    with Req0() as sock:
        # Connect to the broker address
        sock.dial(broker_endpoint)
        print(f"[CLIENT] Connected to broker at: {broker_endpoint}")
        
        while True:
            # Send a message to the broker
            msg = b"ping"
            print(f"[CLIENT] Received reply: {msg}")
            sock.send(msg)
            
            # Receive the reply
            reply = sock.recv()
            print(f"[CLIENT] Received reply: {reply}")
    
            # Sleep a bit just so logs are readable when testing
            time.sleep(0.5)

if __name__ == "__main__":
    main()