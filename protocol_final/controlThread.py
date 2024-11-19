import socket
import time
import threading
from blackBox import blackBox, sendMSG

# Use a lock to protect shared state
connection_lock = threading.Lock()

# Shared state variables
expectingResponse = False
hasConnectionToPeer = False
ConnectionManuallyInterrupted = False

def sendControlPacket(ip: str, port: int):
    global expectingResponse, hasConnectionToPeer, ConnectionManuallyInterrupted
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    while True:
        with connection_lock:
            current_connection_state = hasConnectionToPeer
            current_manual_interrupt = ConnectionManuallyInterrupted

        if not current_connection_state:
            time.sleep(0.35)
            continue

        if current_manual_interrupt:
            with connection_lock:
                ConnectionManuallyInterrupted = False
            time.sleep(5)
            continue

        with connection_lock:
            if expectingResponse:
                print("Lost connection to peer")
                hasConnectionToPeer = False
                expectingResponse = False
                time.sleep(5)
                continue

        message = blackBox(1, flags=4)  # generate an alive message
        sendMSG(sock, message, ip, port)

        with connection_lock:
            expectingResponse = True

        time.sleep(5)