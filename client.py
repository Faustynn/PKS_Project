import socket
import struct
import zlib
import os
import threading

DEBUG = True

MAX_UDP_SIZE = 65507

# Типы сообщений
DATA_TYPE_TEXT = 0      # Текст
DATA_TYPE_IMAGE = 1     # Изображение
DATA_TYPE_VIDEO = 2     # Видео
DATA_TYPE_KEEP_ALIVE = 6

TYPE_OF_SERVICE_DATA = 0        # Данные
TYPE_OF_SERVICE_ACK = 1         # Подтверждение
TYPE_OF_SERVICE_SYN = 2         # SYN
TYPE_OF_SERVICE_SYN_ACK = 3     # SYN-ACK
TYPE_OF_SERVICE_FIN = 5         # FIN
TYPE_OF_SERVICE_KEEP_ALIVE = 6  # Keep-Alive

HEADER_FORMAT = '!IIBBHH'
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 14 байт

# Состояния исходящего соединения
STATE_OUT_DISCONNECTED = 0
STATE_OUT_SYN_SENT = 1
STATE_OUT_ESTABLISHED = 2

# Состояния входящего соединения
STATE_IN_DISCONNECTED = 0
STATE_IN_SYN_RECEIVED = 1
STATE_IN_ESTABLISHED = 2

# Глобальные переменные состояния
connection_state_out = STATE_OUT_DISCONNECTED
connection_state_in = STATE_IN_DISCONNECTED
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

def receive_messages(s, dest_ip, dest_port):
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

            with state_lock:
                # SYN received
                if service_type == TYPE_OF_SERVICE_SYN:
                    if connection_state_in == STATE_IN_DISCONNECTED:
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
                        connection_state_in = STATE_IN_DISCONNECTED
                    connection_event.set()

        except socket.timeout:
            continue
        except Exception as e:
            print(f"Error: {e}")

def connect(src_ip, dest_ip, local_port, peer_port):
    global connection_state_out, connection_state_in
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((src_ip, local_port))
    s.settimeout(1.0)  # timeout 1 sec

    receive_thread = threading.Thread(target=receive_messages, args=(s, dest_ip, peer_port))
    receive_thread.daemon = True  # close when main thread closes
    receive_thread.start()

    seq_num = 1
    ack_num = 0

    with state_lock:
        if connection_state_out == STATE_OUT_DISCONNECTED:
            send_SYN(s, dest_ip, peer_port, seq_num, ack_num)
            connection_state_out = STATE_OUT_SYN_SENT

    # Waiting for outgoing connection to be established
    if not connection_event.wait(timeout=10):
        print("Timeout waiting for outgoing connection.")
    connection_event.clear()

    # Waiting for incoming connection to be established
    if not connection_event.wait(timeout=10):
        print("Timeout waiting for incoming connection.")
    connection_event.clear()

    if connection_state_out != STATE_OUT_ESTABLISHED and connection_state_in != STATE_IN_ESTABLISHED:
        print("Timeout waiting for connection.")
        s.close()
        return

    print("Connection established.")

    # Keep Alive mechanismus
    keep_alive_interval = 5  # messages
    keep_alive_counter = 0
    timer_value = 10  # таймер

    while True:
        data = input(f"User {local_port}: ")
        if data.lower() == 'exit':
            print("Closing the chat...")
            custom_header = create_MY_header(seq_num, ack_num, TYPE_OF_SERVICE_FIN, DATA_TYPE_KEEP_ALIVE, timer_value)
            s.sendto(custom_header, (dest_ip, peer_port))
            if DEBUG:
                print("DEBUG: Sent FIN, closing connection.")
            break

        payload = data.encode('utf-8')
        custom_header = create_MY_header(seq_num, ack_num, TYPE_OF_SERVICE_DATA, DATA_TYPE_TEXT, timer_value)
        packet = custom_header + payload

        try:
            s.sendto(packet, (dest_ip, peer_port))
            if DEBUG:
                print(f"DEBUG: Sent packet with sequence number {seq_num} and payload '{data}'")
            seq_num += 1
            keep_alive_counter += 1
        except Exception as e:
            print(f"Error with packet: {e}")

        # Send Keep Alive
        if keep_alive_counter >= keep_alive_interval:
            custom_header = create_MY_header(seq_num, ack_num, TYPE_OF_SERVICE_KEEP_ALIVE, DATA_TYPE_KEEP_ALIVE, timer_value)
            s.sendto(custom_header, (dest_ip, peer_port))
            if DEBUG:
                print("DEBUG: Sent Keep Alive message.")
            keep_alive_counter = 0

    s.close()

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

    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except socket.gaierror:
        local_ip = '127.0.0.1'

    connect(local_ip, peer_host, local_port, peer_port)
