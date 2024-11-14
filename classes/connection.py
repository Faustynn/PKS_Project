import socket
import struct
import threading
import time
import os

from classes.header import calculate_checksum,create_header
from classes.keep_alive import send_keep_alive
from classes.hand_shake import send_SYN, send_ACK, send_FIN, send_NACK, send_SYN_ACK
from classes.fragmentation import Fragmentation

class Connection:
    def __init__(self, config):
        self.config = config
        self.connection_state_out = config.STATE_OUT_DISCONNECTED
        self.connection_state_in = config.STATE_IN_LISTEN
        self.state_lock = threading.Lock()
        self.connection_event = threading.Event()
        self.keep_alive_timer = None
        self.running = True
        self.socket_closed = False
        self.error = False
        self.fragment_size = 1500 - int(config.HEADER_SIZE)
        self.fragmenter = Fragmentation(self.fragment_size, config.HEADER_SIZE, config)
        self.fragments_buffer = {}
        self.unacknowledged_fragments = {}
        self.total_fragments = None

    def receive_messages(self, s):
        last_received_time = time.time()
        file_names = {}

        while self.running:
            try:
                data, addr = s.recvfrom(self.config.MAX_UDP_SIZE)
                last_received_time = time.time()

                header = data[:self.config.HEADER_SIZE]
                payload = data[self.config.HEADER_SIZE:]

                seq_num, ack_num, header_len, flags, window, recv_checksum, total_fragments,reserved = struct.unpack(self.config.HEADER_FORMAT, header)

                header_for_checksum = struct.pack(self.config.HEADER_FORMAT, seq_num, ack_num, header_len, flags, self.config.WINDOW_SIZE, 0,total_fragments, 0)
                calculated_checksum = calculate_checksum(header_for_checksum)

                self.total_fragments = total_fragments

                if flags != 1:
                    print(f"Received: {data} a {flags}")
                if flags == 8:
                    recv_checksum = 0

                if recv_checksum != calculated_checksum:
                    print(f"Checksums dont match! {recv_checksum} != {calculated_checksum}")
                    send_NACK(self.config, s, addr[0], addr[1], seq_num)
                    continue

                with self.state_lock:

                    if flags == self.config.FLAGS_SYN:
                        if self.connection_state_in == self.config.STATE_IN_LISTEN:
                            if self.config.DEBUG:
                                print(f"Received SYN from {addr}. Sending SYN-ACK...")
                            send_SYN_ACK(self.config, s, addr[0], addr[1], seq_num, seq_num + 1)
                            self.connection_state_in = self.config.STATE_IN_SYN_RECEIVED

                    elif flags == self.config.FLAGS_SYN_ACK:
                        if self.connection_state_out == self.config.STATE_OUT_SYN_SENT:
                            if self.config.DEBUG:
                                print(f"Received SYN-ACK from {addr}. Sending ACK...")
                            send_ACK(self.config, s, addr[0], addr[1], seq_num, seq_num + 1)
                            self.connection_state_out = self.config.STATE_OUT_ESTABLISHED
                            self.connection_event.set()

                    elif flags == self.config.FLAGS_ACK:
                        if self.connection_state_in == self.config.STATE_IN_SYN_RECEIVED:
                            if self.config.DEBUG:
                                print(f"Received ACK from {addr}. Connection established.")
                            self.connection_state_in = self.config.STATE_IN_ESTABLISHED
                            self.connection_event.set()
                        else:
                          #  print(f"ACK debug: {self.unacknowledged_fragments}")

                            if seq_num in self.unacknowledged_fragments:
                                del self.unacknowledged_fragments[seq_num]
                                print(f"ACK received for fragment {seq_num}")
                            else:
                                print(f"Error ACK from {addr}")

                    elif flags == self.config.FLAGS_NACK:
                        if self.config.DEBUG:
                            print(f"Received NACK from {addr}. Resending fragment {seq_num}")

                        # Проверка наличия фрагмента в буфере неполученных фрагментов
                        if seq_num in self.unacknowledged_fragments:
                            fragment = self.unacknowledged_fragments[seq_num]

                            # Создание заголовка и повторная отправка фрагмента
                            header = create_header(self.config, seq_num, ack_num, 0, self.config.WINDOW_SIZE, 0,
                                                   self.total_fragments, 0)
                            time.sleep(1)
                            print(f"Data: {header + fragment}")
                            s.sendto(header + fragment, (addr[0], addr[1]))

                            print(f"Resent fragment {seq_num} with payload {fragment}")
                        else:
                            print(f"Received NACK for fragment {seq_num}, but fragment not found in buffer!")

                    elif flags == self.config.FLAGS_FIN:
                        print(f"FIN received from {addr}. Sending FIN-ACK...")
                        send_ACK(self.config, s, addr[0], addr[1], seq_num, seq_num + 1)
                        self.connection_state_out = self.config.STATE_OUT_DISCONNECTED
                        self.connection_state_in = self.config.STATE_IN_LISTEN
                        self.connection_event.set()
                        self.running = False
                        break

                    elif payload.startswith(b'Fragment size has been resized into'):
                        self.fragment_size = int(payload.decode('utf-8').split()[-1])
                        self.fragmenter = Fragmentation(self.fragment_size, self.config.HEADER_SIZE, self.config)
                        print(f"Fragment size updated to {self.fragment_size} by User {addr[1]}")

                    elif flags == self.config.FLAGS_KEEP_ALIVE:
                        if self.config.DEBUG:
                            print("DEBUG: Received KEEP_ALIVE message")
                        continue

                    else:
                        print(f"Payload: {payload} from {addr}")

                        if payload:
                            # Отправляем ACK для полученного фрагмента
                            send_ACK(self.config, s, addr[0], addr[1], seq_num, seq_num + 1)
                            print(f"ACK sent for fragment {seq_num}")

                            if seq_num <= self.total_fragments:
                                self.fragments_buffer[seq_num] = payload
                                print(f"Received fragment {seq_num} / {self.total_fragments}")

                                if len(self.fragments_buffer) == self.total_fragments:
                                    assembled_message = b''.join(self.fragments_buffer.values())
                                    self.fragments_buffer.clear()
                                else:
                                    continue

                                # Process file
                                if b'\x00' in assembled_message and addr not in file_names:
                                    file_name, file_data = assembled_message.split(b'\x00', 1)
                                    file_names[addr] = file_name.decode('utf-8')

                                    with open(os.path.join(self.config.SAVE_DIR, file_names[addr]), 'wb') as file:
                                        file.write(file_data)

                                    print(f"File {file_names[addr]} received from User {addr[1]}")
                                    del file_names[addr]


                                # Process text message
                                else:
                                    try:
                                        message = assembled_message.decode('utf-8')
                                        print(f"\nMessage from User {addr[1]}: {message}")
                                        print(f"User {s.getsockname()[1]}: ", end='',
                                              flush=True)  # Restore input prompt
                                    except UnicodeDecodeError:
                                        print(f"Error decoding message from User {addr[1]}")



            except socket.timeout:
                if time.time() - last_received_time > self.config.KEEP_ALIVE_INTERVAL:
                    print("Keep Alive: Closing connection due to inactivity")
                    self.running = False
                    break
                continue
            except Exception as e:
                print(f"Error in receive: {e}")
                continue

    def connect(self, src_ip, dest_ip, peer1_port, peer2_port):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # IPv4, UDP
        s.bind((src_ip, peer1_port))
        s.settimeout(self.config.TIMEOUT_HANDSHAKE)

        if self.fragment_size == 1500 - int(self.config.HEADER_SIZE):
            print(f"Enter start max fragment throw '!ef' command, start size init: {1500 - int(self.config.HEADER_SIZE)}")

        receive_thread = threading.Thread(target=self.receive_messages, args=(s,))
        receive_thread.daemon = True
        receive_thread.start()

        seq_num = 1
        ack_num = 0

        with self.state_lock:
            if self.connection_state_out == self.config.STATE_OUT_DISCONNECTED:
                send_SYN(self.config, s, dest_ip, peer2_port, seq_num, ack_num)
                self.connection_state_out = self.config.STATE_OUT_SYN_SENT

        self.connection_event.clear()
        self.connection_event.wait(self.config.TIMEOUT_HANDSHAKE)

        if self.connection_state_out != self.config.STATE_OUT_ESTABLISHED and self.connection_state_in != self.config.STATE_IN_ESTABLISHED:
            print("Connection failed.")
            s.close()
            return

        print("Connection established.")

        self.keep_alive_timer = send_keep_alive(self.config, s, dest_ip, peer2_port, seq_num, ack_num)

        try:
            while self.running:
                data = input(f"User{peer1_port}: ")

                if data.lower() == '!f':
                    send_FIN(self.config, s, dest_ip, peer2_port, seq_num, seq_num + 1)
                    print(f"Connection closed by User {peer1_port}.")
                    self.running = False
                    break

                elif data.lower() == '!err':
                    self.error = True
                    print("Error mode enabled!!")

                elif data.lower() == '!ef':
                    while True:
                        try:
                            max_fragment_size_input = input('Enter new max fragment size from 1 to 1480: ').strip()
                            if int(max_fragment_size_input) < 1 or int(max_fragment_size_input) > 1480:
                                raise ValueError
                            max_fragment_size = int(max_fragment_size_input)
                            notification_message = f"Fragment size has been resized into {max_fragment_size} "
                            self.fragmenter.send_fragments(s, dest_ip, peer2_port, seq_num, ack_num, notification_message.encode('utf-8'))
                            break
                        except ValueError:
                            print("Write correct fragment size!")
                    self.fragment_size = max_fragment_size

                elif data.lower() == '!file':
                    while True:
                        try:
                            path_file = input('Enter path to file: ').strip()

                            file_name = os.path.basename(path_file).encode('utf-8')
                            with open(path_file, 'rb') as file:
                                file_data = file.read()
                                full_data = file_name + b'\x00' + file_data

                                self.fragmenter = Fragmentation(self.fragment_size, self.config.HEADER_SIZE, self.config)

                                if not self.error:
                                    fragments = self.fragmenter.send_fragments(s, dest_ip, peer2_port, seq_num, ack_num,full_data)
                                else:
                                    fragments = self.fragmenter.send_fragments(s, dest_ip, peer2_port, seq_num, ack_num,full_data, True)
                                    self.error = False

                                for fragment in fragments:
                                    if isinstance(fragment, tuple) and len(fragment) == 2:
                                        fragment_data, seq = fragment
                                        self.unacknowledged_fragments[seq] = fragment_data
                                    else:
                                        print(f"Unexpected fragment structure: {fragment}")

                        except FileNotFoundError:
                            print("File not found!")
                else:
                    self.fragmenter = Fragmentation(self.fragment_size, self.config.HEADER_SIZE, self.config)
                    if not self.error:
                        fragments = self.fragmenter.send_fragments(s, dest_ip, peer2_port, seq_num, ack_num,
                                                               data.encode('utf-8'))
                    else:
                        fragments = self.fragmenter.send_fragments(s, dest_ip, peer2_port, seq_num, ack_num,
                                                               data.encode('utf-8'), True)
                        self.error = False

                    for fragment in fragments:
                        if isinstance(fragment, tuple) and len(fragment) == 2:
                            fragment_data, seq = fragment
                            self.unacknowledged_fragments[seq] = fragment_data
                        else:
                            print(f"Unexpected fragment structure: {fragment}")

        finally:
            if not self.socket_closed:
                if self.keep_alive_timer:
                    self.keep_alive_timer.cancel()
                if self.running:
                    send_FIN(self.config, s, dest_ip, peer2_port, seq_num, seq_num + 1)
                    self.running = False
                    print("Keep alive disconnect.")
                    s.close()
                    self.socket_closed = True
            print("Stopping connection.")

