import socket
import struct
import threading
from classes.header import create_header

class Fragmentation:
    def __init__(self, max_fragment_size, header_size, config):
        self.max_fragment_size = max_fragment_size
        self.header_size = header_size
        self.config = config
        self.ack_received = {}  # Dictionary to track received ACKs

    def fragment_data(self, data):
        fragments = []
        total_size = len(data)

        if total_size <= self.max_fragment_size:
            return [data]  # No fragmentation needed

        # Fragment the data if it is larger than the max size
        for i in range(0, total_size, self.max_fragment_size):
            fragments.append(data[i:i + self.max_fragment_size])

        return fragments

    def send_fragments(self, s, dest_ip, dest_port, initial_seq_num, ack_num, data):
        fragments = self.fragment_data(data)
        total_fragments = len(fragments)
        window_start = 0
        window_size = self.config.WINDOW_SIZE
        unacked_fragments = {}  # Buffer for unacknowledged fragments

        # Event for synchronizing ACK reception
        ack_received = threading.Event()

        def receive_acks():
            while len(unacked_fragments) > 0:
                try:
                    s.settimeout(self.config.TIMEOUT)
                    data, _ = s.recvfrom(self.config.MAX_UDP_SIZE)

                    # Unpack the ACK header
                    header = data[:self.config.HEADER_SIZE]
                    ack_seq_num, _, _, flags, _, _, _ = struct.unpack(self.config.HEADER_FORMAT, header)

                    if flags == self.config.FLAGS_ACK:
                        if ack_seq_num in unacked_fragments:
                            print(f"Received ACK for fragment {ack_seq_num}")
                            del unacked_fragments[ack_seq_num]
                            self.ack_received[ack_seq_num] = True
                            ack_received.set()

                except socket.timeout:
                    # On timeout, retransmit all unacknowledged fragments in the window
                    for seq_num, fragment in unacked_fragments.items():
                        if window_start <= seq_num < window_start + window_size:
                            header = create_header(self.config, seq_num, ack_num, 0, window_size, 0, 0)
                            s.sendto(header + fragment, (dest_ip, dest_port))
                            print(f"Resending fragment {seq_num}")

        # Start the thread for receiving ACKs
        ack_thread = threading.Thread(target=receive_acks)
        ack_thread.daemon = True
        ack_thread.start()

        seq_num = initial_seq_num

        if total_fragments == 1:
            # Send the single fragment directly
            print("Sending single fragment")
            fragment = fragments[0]
            header = create_header(self.config, seq_num, ack_num, 0, window_size, 0, 0)
            s.sendto(header + fragment, (dest_ip, dest_port))
            print(f"Sent fragment {seq_num}")
            return

        while window_start < total_fragments:
            # Send fragments within the window
            while seq_num < min(window_start + window_size, total_fragments):
                if seq_num not in unacked_fragments:
                    fragment = fragments[seq_num]
                    header = create_header(self.config, seq_num, ack_num, 0, window_size, 0, 0)
                    s.sendto(header + fragment, (dest_ip, dest_port))
                    unacked_fragments[seq_num] = fragment
                    print(f"Sent fragment {seq_num}")
                    seq_num += 1

            # Wait for at least one fragment to be acknowledged or timeout
            ack_received.wait(self.config.TIMEOUT)
            ack_received.clear()

            # Slide the window
            while window_start < total_fragments and window_start not in unacked_fragments:
                window_start += 1

        # Wait for all fragments to be acknowledged
        while len(unacked_fragments) > 0:
            ack_received.wait(self.config.TIMEOUT)
            ack_received.clear()

        print("All fragments sent and acknowledged")
