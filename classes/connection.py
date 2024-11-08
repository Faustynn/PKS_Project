import socket
import struct
import threading
from classes.header import create_header, calculate_checksum
from classes.keep_alive import send_keep_alive
from classes.hand_shake import send_SYN, send_SYN_ACK, send_ACK

class Connection:
    def __init__(self, config):
        self.config = config
        self.connection_state_out = config.STATE_OUT_DISCONNECTED
        self.connection_state_in = config.STATE_IN_LISTEN
        self.state_lock = threading.Lock()
        self.connection_event = threading.Event()
        self.keep_alive_timer = None

    def receive_messages(self, s):
        while True:
            try:
                data, addr = s.recvfrom(self.config.MAX_UDP_SIZE)
                header = data[:self.config.HEADER_SIZE]
                payload = data[self.config.HEADER_SIZE:]

                seq_num, ack_num, header_len, combined_service_data, recv_checksum, timer = struct.unpack(
                    self.config.HEADER_FORMAT, header
                )

                service_type = (combined_service_data >> 4) & 0x0F
                data_type = combined_service_data & 0x0F

                header_for_checksum = struct.pack(
                    self.config.HEADER_FORMAT, seq_num, ack_num, header_len, combined_service_data, 0, timer
                )
                calculated_checksum = calculate_checksum(header_for_checksum)

                if recv_checksum != calculated_checksum:
                    print(f"Checksums do not match! {recv_checksum} != {calculated_checksum}")
                    continue

                with self.state_lock:
                    if service_type == self.config.TYPE_OF_SERVICE_SYN:
                        if self.connection_state_in == self.config.STATE_IN_LISTEN:
                            print(f"Received SYN from {addr}. Sending SYN-ACK...")
                            send_SYN_ACK(self.config, s, addr[0], addr[1], seq_num, seq_num + 1)
                            self.connection_state_in = self.config.STATE_IN_SYN_RECEIVED

                    elif service_type == self.config.TYPE_OF_SERVICE_SYN_ACK:
                        if self.connection_state_out == self.config.STATE_OUT_SYN_SENT:
                            print(f"Received SYN-ACK from {addr}. Sending ACK...")
                            send_ACK(self.config, s, addr[0], addr[1], seq_num, seq_num + 1)
                            self.connection_state_out = self.config.STATE_OUT_ESTABLISHED
                            self.connection_event.set()

                    elif service_type == self.config.TYPE_OF_SERVICE_ACK:
                        if self.connection_state_in == self.config.STATE_IN_SYN_RECEIVED:
                            print(f"Received ACK from {addr}. Connection established.")
                            self.connection_state_in = self.config.STATE_IN_ESTABLISHED
                            self.connection_event.set()

                    elif service_type == self.config.TYPE_OF_SERVICE_DATA:
                        if data_type == self.config.DATA_TYPE_TEXT:
                            try:
                                message = payload.decode('utf-8')
                                print(f"\nMessage from User {addr[1]}: {message}")
                            except UnicodeDecodeError:
                                print("Error decoding the message.")
                        elif data_type == self.config.DATA_TYPE_IMAGE:
                            pass
                        elif data_type == self.config.DATA_TYPE_VIDEO:
                            pass

                    elif service_type == self.config.TYPE_OF_SERVICE_KEEP_ALIVE:
                        if self.config.DEBUG:
                            print("DEBUG: Received KEEP_ALIVE message")

                    elif service_type == self.config.TYPE_OF_SERVICE_FIN:
                        print(f"FIN received from {addr}. Closing connection.")
                        self.connection_state_out = self.config.STATE_OUT_DISCONNECTED
                        self.connection_state_in = self.config.STATE_IN_LISTEN
                        self.connection_event.set()

            except socket.timeout:
                continue
            except Exception as e:
                print(f"Error: {e}")

    def connect(self, src_ip, dest_ip, peer1_port, peer2_port):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind((src_ip, peer1_port))
        s.settimeout(2.0)

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
            print("Timeout waiting for connection.")
            s.close()
            return

        print("Connection established.")
        self.keep_alive_timer = send_keep_alive(self.config, s, dest_ip, peer2_port, seq_num, ack_num)

        try:
            while True:
                data = input(f"User {peer1_port}: ")

                if data.lower() == 'exit':
                    send_ACK(self.config, s, dest_ip, peer2_port, seq_num, seq_num + 1)
                    print("Connection closed.")
                    break
                else:
                    custom_header = create_header(self.config, seq_num, ack_num, self.config.TYPE_OF_SERVICE_DATA, self.config.DATA_TYPE_TEXT, 0)
                    s.sendto(custom_header + data.encode('utf-8'), (dest_ip, peer2_port))

        finally:
            if self.keep_alive_timer:
                self.keep_alive_timer.cancel()
            s.close()
