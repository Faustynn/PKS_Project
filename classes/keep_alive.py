import threading
from classes.header import create_header

def send_keep_alive(config, s, dest_ip, dest_port, seq_num, ack_num):
    custom_header = create_header(config, seq_num, ack_num, config.TYPE_OF_SERVICE_KEEP_ALIVE,config.DATA_TYPE_KEEP_ALIVE, 0)
    s.sendto(custom_header, (dest_ip, dest_port))
    if config.DEBUG:
        print(f"DEBUG: Sent KEEP ALIVE to {dest_ip}:{dest_port}")

    keep_alive_timer = threading.Timer(config.KEEP_ALIVE_INTERVAL, send_keep_alive, [config, s, dest_ip, dest_port, seq_num, ack_num])
    keep_alive_timer.start()
    return keep_alive_timer
