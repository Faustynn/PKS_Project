import socket
import struct
import zlib
import os
import threading

MAX_UDP_SIZE = 65507

# Типы сообщений
DATA_TYPE_TEXT = 0  # Текст
DATA_TYPE_FILES = 1  # Файлы

TYPE_OF_SERVICE = 0  # Обычный тип сервиса

# '!IIIBBBHI3x' => 4+4+4+1+1+1+2+4+3 = 24 байта
HEADER_FORMAT = '!IIIBBBHI3x'
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)


def create_MY_header(seq_num, ack_num, service_type, data_type, timer):
    reserved = 0
    checksum = 0

    header = struct.pack(
        HEADER_FORMAT,
        seq_num,  # Sequence number (4 байта)
        ack_num,  # Acknowledgment number (4 байта)
        HEADER_SIZE,  # Header length (4 байта)
        reserved,  # Reserved (1 байт)
        service_type,  # Type of service (1 байт)
        data_type,  # Type of data (1 байт)
        checksum,  # Checksum placeholder (2 байта)
        timer  # Timer (4 байта)
    )
    checksum = calculate_checksum(header)

    header = struct.pack(
        HEADER_FORMAT,
        seq_num,
        ack_num,
        HEADER_SIZE,
        reserved,
        service_type,
        data_type,
        checksum,
        timer
    )

    return header


def calculate_checksum(data):
    return zlib.crc32(data) & 0xFFFF  # Возвращает 16-bit сумму


def receive_messages(s):
    while True:
        try:
            data, addr = s.recvfrom(MAX_UDP_SIZE)

            header = data[:HEADER_SIZE]
            payload = data[HEADER_SIZE:]

            unpacked = struct.unpack(HEADER_FORMAT, header)
            seq_num, ack_num, header_len, reserved, service_type, data_type, recv_checksum, timer = unpacked

            header_for_checksum = struct.pack(
                HEADER_FORMAT,
                seq_num,
                ack_num,
                header_len,
                reserved,
                service_type,
                data_type,
                0,  # Checksum в 0
                timer
            )
            calculated_checksum = calculate_checksum(header_for_checksum)
            if recv_checksum != calculated_checksum:
                print(f"Checksums do not match! {recv_checksum} != {calculated_checksum}")
                continue

            if data_type == DATA_TYPE_TEXT:
                try:
                    message = payload.decode('utf-8')
                    print(f"Message from {addr}: {message}")
                except UnicodeDecodeError:
                    print(f"Error while decoding!")
            elif data_type == DATA_TYPE_FILES:
                print(f"File from {addr}, with size: {len(payload)} bytes")
        except socket.timeout:
            continue
        except Exception as e:
            print(f"Error: {e}")


def connect(src_ip, dest_ip, local_port, peer_port):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((src_ip, local_port))
    s.settimeout(1.0)

    receive_thread = threading.Thread(target=receive_messages, args=(s,))
    receive_thread.daemon = True  # завершить поток при закрытии программы
    receive_thread.start()

    seq_num = 1
    ack_num = 0

    while True:
        data = input(f"User {local_port}: ")
        if data.lower() == 'exit':
            print("Closing the chat...")
            break

        payload = data.encode('utf-8')

        timer = 10  #таймер
        custom_header = create_MY_header(seq_num, ack_num, TYPE_OF_SERVICE, DATA_TYPE_TEXT, timer)
        packet = custom_header + payload

        try:
            s.sendto(packet, (dest_ip, peer_port))
           # print(f"Packet: {packet.hex()}")
            seq_num += 1
        except Exception as e:
            print(f"Error with packet: {e}")

    s.close()


if __name__ == '__main__':
    os.system('clear')
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
