from classes.header import create_header

def send_SYN(config, s, dest_ip, dest_port, seq_num, ack_num):
    custom_header = create_header(config, seq_num, ack_num, config.TYPE_OF_SERVICE_SYN, config.DATA_TYPE_KEEP_ALIVE, 0)
    s.sendto(custom_header, (dest_ip, dest_port))
    if config.DEBUG:
        print("DEBUG: Sent SYN, waiting for SYN-ACK...")

def send_SYN_ACK(config, s, dest_ip, dest_port, seq_num, ack_num):
    custom_header = create_header(config, seq_num, ack_num, config.TYPE_OF_SERVICE_SYN_ACK, config.DATA_TYPE_KEEP_ALIVE, 0)
    s.sendto(custom_header, (dest_ip, dest_port))
    if config.DEBUG:
        print("DEBUG: Sent SYN-ACK.")

def send_ACK(config, s, dest_ip, dest_port, seq_num, ack_num):
    custom_header = create_header(config, seq_num, ack_num, config.TYPE_OF_SERVICE_ACK, config.DATA_TYPE_KEEP_ALIVE, 0)
    s.sendto(custom_header, (dest_ip, dest_port))
    if config.DEBUG:
        print("DEBUG: Sent ACK, connection established.")
