import os
import sys
from classes.config import Config
from classes.connection import Connection

if __name__ == '__main__':
    os.system('cls' if os.name == 'nt' else 'clear')
    print('Chat started successfully!')


    if len(sys.argv) != 6:
        print("Usage: python main.py ip_my port1 port2 ip_peer peer_port")
        sys.exit(1)

    local_ip = sys.argv[1].strip()  # Ваш IP
    local_port = int(sys.argv[2].strip())  # Ваш порт
    peer_port = int(sys.argv[3].strip())  # Порт для слушателя
    peer_2_ip = sys.argv[4].strip()  # IP слушателя
    peer_2_port = int(sys.argv[5].strip())  # Порт слушателя

    config = Config('config/config.txt')
    connection = Connection(config)
    connection.connect(local_ip, peer_2_ip, local_port, peer_2_port)