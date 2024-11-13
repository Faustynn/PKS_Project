import socket
import struct
import threading
import time
import os
from classes.header import calculate_checksum
from classes.keep_alive import send_keep_alive
from classes.hand_shake import send_SYN, send_ACK, send_FIN, send_RST, send_NACK, send_SYN_ACK
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

    def receive_messages(self, s):
        last_received_time = time.time()
        fragments_buffer = {}
        file_names = {}

        while self.running:
            try:
                data, addr = s.recvfrom(self.config.MAX_UDP_SIZE)
                header = data[:self.config.HEADER_SIZE]
                payload = data[self.config.HEADER_SIZE:]

                seq_num, ack_num, header_len, flags, window, recv_checksum, reserved = struct.unpack(self.config.HEADER_FORMAT, header)

                header_for_checksum = struct.pack(self.config.HEADER_FORMAT, seq_num, ack_num, header_len, flags, self.config.WINDOW_SIZE, 0, 0)
                calculated_checksum = calculate_checksum(header_for_checksum)

                if self.error:
                    calculated_checksum = 0

                if recv_checksum != calculated_checksum:
                    print(f"Checksums dont match! {recv_checksum} != {calculated_checksum}")
                    break

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

                    elif flags == self.config.FLAGS_KEEP_ALIVE:
                        if self.config.DEBUG:
                            print("DEBUG: Received KEEP_ALIVE message")

                    elif flags == self.config.FLAGS_FIN:
                        print(f"FIN received from {addr}. Sending FIN-ACK...")
                        send_ACK(self.config, s, addr[0], addr[1], seq_num, seq_num + 1)
                        self.connection_state_out = self.config.STATE_OUT_DISCONNECTED
                        self.connection_state_in = self.config.STATE_IN_LISTEN
                        self.connection_event.set()
                        self.running = False
                        break

                    elif flags == self.config.FLAGS_RST:
                        print(f"RST received from {addr}. Sending RST-ACK...")
                        send_ACK(self.config, s, addr[0], addr[1], seq_num, seq_num + 1)
                        self.connection_state_out = self.config.STATE_OUT_SYN_SENT
                        self.connection_state_in = self.config.STATE_IN_LISTEN
                        self.connection_event.clear()
                        self.connection_event.wait(self.config.TIMEOUT_HANDSHAKE)
                        self.running = False
                        break

                    elif payload.startswith(b'Fragment size has been resized into'):
                        self.fragment_size = int(payload.decode('utf-8').split()[-1])
                        self.fragmenter = Fragmentation(self.fragment_size, self.config.HEADER_SIZE, self.config)
                        print(f"Fragment size updated to {self.fragment_size} by User {addr[1]}")

                    else:
                        if addr not in fragments_buffer:
                            fragments_buffer[addr] = b''
                        fragments_buffer[addr] += payload

                        if addr not in file_names and b'\x00' in fragments_buffer[addr]:  # only file has null byte
                            file_name, file_data = fragments_buffer[addr].split(b'\x00', 1)
                            file_names[addr] = file_name.decode('utf-8')
                            fragments_buffer[addr] = file_data

                        if len(payload) < self.fragment_size:
                            if addr in file_names:
                                file_path = os.path.join(self.config.SAVE_DIR, file_names[addr])
                                with open(file_path, 'wb') as file:
                                    file.write(fragments_buffer[addr])
                                print(f"File {file_names[addr]} received from User {addr[1]} and saved to {file_path}")
                                del file_names[addr]
                            else:
                                message = fragments_buffer[addr].decode('utf-8')
                                print(f"\nMessage from User {addr[1]}: {message}")
                            fragments_buffer[addr] = b''

            except socket.timeout:
                if time.time() - last_received_time > self.config.KEEP_ALIVE_INTERVAL:
                    print("Keep Alive: Closing connection due to inactivity")
                    self.running = False
                    break
                continue
            except Exception as e:
                print(f"Error: {e}")
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
                data = input(f"User {peer1_port}: ")

                if data.lower() == '!q':
                    send_FIN(self.config, s, dest_ip, peer2_port, seq_num, seq_num + 1)
                    print(f"Connection closed by User {peer1_port}.")
                    self.running = False
                    break
                elif data.lower() == '!r':
                    send_RST(self.config, s, dest_ip, peer2_port, seq_num, seq_num + 1)
                    print(f"Trying to reset connection by User {peer1_port}.")
                    self.connection_state_out = self.config.STATE_OUT_SYN_SENT
                    break
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
                                self.fragmenter.send_fragments(s, dest_ip, peer2_port, seq_num, ack_num, full_data)
                                break
                        except FileNotFoundError:
                            print("File not found!")
                else:
                    self.fragmenter = Fragmentation(self.fragment_size, self.config.HEADER_SIZE, self.config)
                    self.fragmenter.send_fragments(s, dest_ip, peer2_port, seq_num, ack_num, data.encode('utf-8'))
        finally:
            if not self.socket_closed:
                if self.keep_alive_timer is not None:
                    self.keep_alive_timer.cancel()

                    print("Keep alive disconnect.")
                    s.close()
                    self.socket_closed = True
            print("Stopping connection.")
