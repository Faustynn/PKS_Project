from classes.header import create_header

class Fragmentation:
    def __init__(self, max_fragment_size, header_size, config):
        self.max_fragment_size = max_fragment_size
        self.header_size = header_size
        self.config = config

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
        seq_num = initial_seq_num
        window_size = self.config.WINDOW_SIZE
        buffer_non_ack = {}

        if buffer_non_ack:
            print(f"Resent fragment {seq_num}")

            # Resend fragments that in a buffer
            for seq_num, fragment in buffer_non_ack.items():
                header = create_header(self.config, seq_num, ack_num, 0, window_size, 0,total_fragments, 0)
                s.sendto(header + fragment, (dest_ip, dest_port))
                buffer_non_ack.pop(seq_num)
            return buffer_non_ack

        elif total_fragments == 1:
            print("Sending single fragment")

            # Send the single fragment directly
            fragment = fragments[0]
            header = create_header(self.config, seq_num, ack_num, 0, window_size, 0, total_fragments,0)
            s.sendto(header + fragment, (dest_ip, dest_port))
            print(f"Sent fragment {seq_num}")
            buffer_non_ack[seq_num] = fragment
            return [(fragment, seq_num)]
        else:
            print("Sending multiple fragments")

            # Send fragments and add into buffer_non_ack
            print(f"Total fragments: {fragments}")
            for i, fragment in enumerate(fragments):
                header = create_header(self.config, seq_num, ack_num, 0, window_size, 0, total_fragments,0)
                s.sendto(header + fragment, (dest_ip, dest_port))
                print(f"Sent fragment {seq_num} / {total_fragments}")
                buffer_non_ack[seq_num] = fragment
                seq_num += 1
            return [(fragment, seq) for seq, fragment in buffer_non_ack.items()]

