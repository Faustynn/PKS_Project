import configparser
import socket
import struct
import zlib
import os
import threading

# Load config
config = configparser.ConfigParser()
config.read('config/config.txt')

DEBUG = config.getboolean('MODE', 'DEBUG')
MAX_UDP_SIZE = config.getint('HEADER', 'MAX_UDP_SIZE')

# Message Types
DATA_TYPE_TEXT = config.getint('DATA_TYPE', 'DATA_TYPE_TEXT')
DATA_TYPE_IMAGE = config.getint('DATA_TYPE', 'DATA_TYPE_IMAGE')
DATA_TYPE_VIDEO = config.getint('DATA_TYPE', 'DATA_TYPE_VIDEO')
DATA_TYPE_KEEP_ALIVE = config.getint('DATA_TYPE', 'DATA_TYPE_KEEP_ALIVE')

# Service Types
TYPE_OF_SERVICE_DATA = config.getint('TYPE_OF_SERVICE', 'TYPE_OF_SERVICE_DATA')
TYPE_OF_SERVICE_KEEP_ALIVE = config.getint('TYPE_OF_SERVICE', 'TYPE_OF_SERVICE_KEEP_ALIVE')
TYPE_OF_SERVICE_FIN = config.getint('TYPE_OF_SERVICE', 'TYPE_OF_SERVICE_FIN')
TYPE_OF_SERVICE_ACK = config.getint('TYPE_OF_SERVICE', 'TYPE_OF_SERVICE_ACK')
TYPE_OF_SERVICE_SYN = config.getint('TYPE_OF_SERVICE', 'TYPE_OF_SERVICE_HANDSHAKE')  # Synchronized
TYPE_OF_SERVICE_SYN_ACK = 4  # ACK для SYN

HEADER_FORMAT = config.get('HEADER', 'HEADER_FORMAT')
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

# Connection States
STATE_OUT_DISCONNECTED = config.getint('STATES', 'STATE_OUT_DISCONNECTED')
STATE_OUT_SYN_SENT = config.getint('STATES', 'STATE_OUT_SYN_SENT')
STATE_OUT_ESTABLISHED = config.getint('STATES', 'STATE_OUT_ESTABLISHED')

STATE_IN_LISTEN = config.getint('STATES', 'STATE_IN_LISTEN')
STATE_IN_SYN_RECEIVED = config.getint('STATES', 'STATE_IN_SYN_RECEIVED')
STATE_IN_ESTABLISHED = config.getint('STATES', 'STATE_IN_ESTABLISHED')

# Timeouts
TIMEOUT_HANDSHAKE = config.getint('TIMEOUTS', 'TIMEOUT_HANDSHAKE')
TIMEOUT_KEEP_ALIVE = config.getint('TIMEOUTS', 'TIMEOUT_KEEP_ALIVE')
KEEP_ALIVE_INTERVAL = config.getint('TIMEOUTS', 'KEEP_ALIVE_INTERVAL')

# Global state variables
connection_state_out = STATE_OUT_DISCONNECTED
connection_state_in = STATE_IN_LISTEN
state_lock = threading.Lock()
connection_event = threading.Event()

def create_MY_header(seq_num, ack_num, service_type, data_type, timer):
    checksum = 0
    header_length = HEADER_SIZE
    combined_service_data = (service_type << 4) | (data_type & 0x0F)

    header = struct.pack(
        HEADER_FORMAT,
        seq_num,            # Sequence number
        ack_num,            # Acknowledgment number
        header_length,      # Header length
        combined_service_data, # Type of service и Data type code
        checksum,           # сhecksum placeholder
        timer               # Timer
    )
    checksum = calculate_checksum(header)

    header = struct.pack(
        HEADER_FORMAT,
        seq_num,
        ack_num,
        header_length,
        combined_service_data,
        checksum,
        timer
    )

    return header

def calculate_checksum(data):
    return zlib.crc32(data) & 0xFFFF

def send_SYN(s, dest_ip, dest_port, seq_num, ack_num):
    custom_header = create_MY_header(seq_num, ack_num, TYPE_OF_SERVICE_SYN, DATA_TYPE_KEEP_ALIVE, 0)
    s.sendto(custom_header, (dest_ip, dest_port))
    if DEBUG:
        print("DEBUG: Sent SYN, waiting for SYN-ACK...")

def send_SYN_ACK(s, dest_ip, dest_port, seq_num, ack_num):
    custom_header = create_MY_header(seq_num, ack_num, TYPE_OF_SERVICE_SYN_ACK, DATA_TYPE_KEEP_ALIVE, 0)
    s.sendto(custom_header, (dest_ip, dest_port))
    if DEBUG:
        print("DEBUG: Sent SYN-ACK.")

def send_ACK(s, dest_ip, dest_port, seq_num, ack_num):
    custom_header = create_MY_header(seq_num, ack_num, TYPE_OF_SERVICE_ACK, DATA_TYPE_KEEP_ALIVE, 0)
    s.sendto(custom_header, (dest_ip, dest_port))
    if DEBUG:
        print("DEBUG: Sent ACK, connection established.")

def receive_messages(s):
    global connection_state_out, connection_state_in
    while True:
        try:
            data, addr = s.recvfrom(MAX_UDP_SIZE)
            header = data[:HEADER_SIZE]
            payload = data[HEADER_SIZE:]

            unpacked = struct.unpack(HEADER_FORMAT, header)
            seq_num, ack_num, header_len, combined_service_data, recv_checksum, timer = unpacked

            service_type = (combined_service_data >> 4) & 0x0F
            data_type = combined_service_data & 0x0F

            # Checksum verification
            header_for_checksum = struct.pack(
                HEADER_FORMAT,
                seq_num,
                ack_num,
                header_len,
                combined_service_data,
                0,
                timer
            )
            calculated_checksum = calculate_checksum(header_for_checksum)

            if recv_checksum != calculated_checksum:
                print(f"Checksums do not match! {recv_checksum} != {calculated_checksum}")
                continue

            if DEBUG:
                print(f"DEBUG: Received {service_type} from {addr}. Current states: Out: {connection_state_out}, In: {connection_state_in}")

            with state_lock:
                # SYN received
                if service_type == TYPE_OF_SERVICE_SYN:
                    if connection_state_in == STATE_IN_LISTEN:
                        print(f"Received SYN from {addr}. Sending SYN-ACK...")
                        send_SYN_ACK(s, addr[0], addr[1], seq_num, seq_num + 1)
                        connection_state_in = STATE_IN_SYN_RECEIVED

                # SYN-ACK received
                elif service_type == TYPE_OF_SERVICE_SYN_ACK:
                    if connection_state_out == STATE_OUT_SYN_SENT:
                        print(f"Received SYN-ACK from {addr}. Sending ACK...")
                        send_ACK(s, addr[0], addr[1], seq_num, seq_num + 1)
                        connection_state_out = STATE_OUT_ESTABLISHED
                        connection_event.set()

                # ACK received
                elif service_type == TYPE_OF_SERVICE_ACK:
                    if connection_state_in == STATE_IN_SYN_RECEIVED:
                        print(f"Received ACK from {addr}. Connection established.")
                        connection_state_in = STATE_IN_ESTABLISHED
                        connection_event.set()

                # Data received
                elif service_type == TYPE_OF_SERVICE_DATA:
                    if data_type == DATA_TYPE_TEXT:
                        try:
                            message = payload.decode('utf-8')
                            print(f"Message from {addr}: {message}")
                        except UnicodeDecodeError:
                            print(f"Error while decoding!")
                    elif data_type == DATA_TYPE_IMAGE:
                        print(f"Image from {addr}")
                    elif data_type == DATA_TYPE_VIDEO:
                        print(f"Video from {addr}")

                # Keep Alive received
                elif service_type == TYPE_OF_SERVICE_KEEP_ALIVE:
                    print(f"Keep Alive from {addr}.")

                # Fin received
                elif service_type == TYPE_OF_SERVICE_FIN:
                    print(f"FIN received from {addr}. Closing connection.")
                    with state_lock:
                        connection_state_out = STATE_OUT_DISCONNECTED
                        connection_state_in = STATE_IN_LISTEN
                    connection_event.set()

        except socket.timeout:
            continue
        except Exception as e:
            print(f"Error: {e}")

def connect(src_ip, dest_ip, peer1_port, peer2_port):
    global connection_state_out, connection_state_in
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((src_ip, peer1_port))
    s.settimeout(2.0)  # timeout 2 seconds

    receive_thread = threading.Thread(target=receive_messages, args=(s,))
    receive_thread.daemon = True  # close when main thread closes
    receive_thread.start()

    seq_num = 1
    ack_num = 0

    with state_lock:
        if connection_state_out == STATE_OUT_DISCONNECTED:
            send_SYN(s, dest_ip, peer2_port, seq_num, ack_num)
            connection_state_out = STATE_OUT_SYN_SENT

    # Waiting for outgoing connection to be established
    if not connection_event.wait(timeout=TIMEOUT_HANDSHAKE):
        print("Timeout waiting for outgoing connection.")
    connection_event.clear()

    # Waiting for incoming connection to be established
    if not connection_event.wait(timeout=TIMEOUT_HANDSHAKE):
        print("Timeout waiting for incoming connection.")
    connection_event.clear()

    if connection_state_out != STATE_OUT_ESTABLISHED and connection_state_in != STATE_IN_ESTABLISHED:
        print("Timeout waiting for connection.")
        s.close()
        return

    print("Connection established.")

    keep_alive_counter = 0
    while True:
        data = input(f"User {peer1_port}: ")
        if data.lower() == 'exit':
            send_ACK(s, dest_ip, peer2_port, seq_num, seq_num + 1)  # Send FIN
            print("Connection closed.")
            break
        elif keep_alive_counter >= KEEP_ALIVE_INTERVAL:
            custom_header = create_MY_header(seq_num, ack_num, TYPE_OF_SERVICE_KEEP_ALIVE, DATA_TYPE_KEEP_ALIVE, TIMEOUT_KEEP_ALIVE)
            s.sendto(custom_header, (dest_ip, peer2_port))
            keep_alive_counter = 0

        keep_alive_counter += 1

    s.close()
    print("Socket closed.")


if __name__ == '__main__':
    os.system('cls' if os.name == 'nt' else 'clear')
    print('Chat started successfully!')

    peer_host = input('Listener IP: ').strip()

    while True:
        try:
            peer_port_input = input('Listener Port: ').strip()
            peer_port = int(peer_port_input)
            break
        except ValueError:
            print("Write correct port number!")

    while True:
        try:
            local_port_input = input('Your Port: ').strip()
            local_port = int(local_port_input)
            break
        except ValueError:
            print("Write correct port number!")

    local_ip = socket.gethostbyname(socket.gethostname())


    connect(local_ip, peer_host, local_port, peer_port)
