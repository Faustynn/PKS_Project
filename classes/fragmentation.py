from classes.header import create_header


# Fragments max 1500-20=1480 bytes
class Fragmentation:
    def __init__(self, max_fragment_size, header_size, config):
        self.max_fragment_size = max_fragment_size
        self.header_size = header_size
        self.config = config


    def fragment_data(self, data):
        # cut data to frag if they bigger than max frag_size
        fragments = []
        total_size = len(data)

        if total_size <= self.max_fragment_size:
            return [data]  # dont fragment

        # Разбиваем на фрагменты
        for i in range(0, total_size, self.max_fragment_size):
            fragments.append(data[i:i + self.max_fragment_size])

        return fragments

    def send_fragments(self, s, dest_ip, dest_port, seq_num, ack_num, data):
        fragments = self.fragment_data(data)
        for i, fragment in enumerate(fragments):
            # make header for every fragment
            header = create_header(self.config, seq_num, ack_num, 0, 0, 0, 0)
            s.sendto(header + fragment, (dest_ip, dest_port))
            seq_num += len(fragment)  # update seq_num for next fragment
