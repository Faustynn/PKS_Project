import threading
from classes.header import create_header

def send_keep_alive(config, socket, dest_ip, dest_port, seq_num, ack_num):
    custom_header = create_header(config, seq_num, ack_num, config.FLAGS_KEEP_ALIVE,0, 0)

    try:
        socket.sendto(custom_header, (dest_ip, dest_port))
        if config.DEBUG:
            print(f"DEBUG: Sent KEEP ALIVE to {dest_ip}:{dest_port}")
    except Exception as e:
        print(f"Error: {e}")
        return

    keep_alive_timer = threading.Timer(config.KEEP_ALIVE_INTERVAL, send_keep_alive, [config, socket, dest_ip, dest_port, seq_num, ack_num])
    keep_alive_timer.start()
    return keep_alive_timer
