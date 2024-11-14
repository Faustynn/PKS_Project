from classes.header import create_header

def send_SYN(config, socket, dest_ip, dest_port, seq_num, ack_num):
    custom_header = create_header(config, seq_num, ack_num, config.FLAGS_SYN, config.WINDOW_SIZE, 0, 1,0)

    try:
        socket.sendto(custom_header, (dest_ip, dest_port))
        if config.DEBUG:
            print("DEBUG: Sent SYN, waiting for SYN-ACK...")
    except Exception as e:
        print(f"Error: {e}")
        return

def send_ACK(config, socket, dest_ip, dest_port, seq_num, ack_num):
    custom_header = create_header(config, seq_num, ack_num, config.FLAGS_ACK, config.WINDOW_SIZE, 0, 1,0)

    try:
        socket.sendto(custom_header, (dest_ip, dest_port))
        if config.DEBUG:
            print("DEBUG: Sent ACK, connection established.")
    except Exception as e:
        print(f"Error: {e}")
        return

def send_FIN(config, socket, dest_ip, dest_port, seq_num, ack_num):
    custom_header = create_header(config, seq_num, ack_num, config.FLAGS_FIN, config.WINDOW_SIZE, 0, 1,0)

    try:
        socket.sendto(custom_header, (dest_ip, dest_port))
        if config.DEBUG:
            print("DEBUG: Sent FIN, waiting for FIN-ACK...")
    except Exception as e:
        print(f"Error: {e}")
        return

def send_RST(config, socket, dest_ip, dest_port, seq_num, ack_num):
    custom_header = create_header(config, seq_num, ack_num, config.FLAGS_RST, config.WINDOW_SIZE, 0, 1,0)

    try:
        socket.sendto(custom_header, (dest_ip, dest_port))
        if config.DEBUG:
            print("DEBUG: Sent RST, connection reset.")
    except Exception as e:
        print(f"Error: {e}")
        return

def send_NACK(config, socket, dest_ip, dest_port, seq_num):
    custom_header = create_header(config, seq_num, 0, config.FLAGS_NACK, config.WINDOW_SIZE, 0, 1,0)

    try:
        socket.sendto(custom_header, (dest_ip, dest_port))
        if config.DEBUG:
            print("DEBUG: Sent NACK, waiting for data...")
    except Exception as e:
        print(f"Error: {e}")
        return

def send_SYN_ACK(config, socket, dest_ip, dest_port, seq_num, ack_num):
    custom_header = create_header(config, seq_num, ack_num, config.FLAGS_SYN_ACK, config.WINDOW_SIZE, 0, 1,0)

    try:
        socket.sendto(custom_header, (dest_ip, dest_port))
        if config.DEBUG:
            print("DEBUG: Sent SYN-ACK, connection established.")
    except Exception as e:
        print(f"Error: {e}")
        return
