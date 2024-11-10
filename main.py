import os
from classes.config import Config
from classes.connection import Connection

if __name__ == '__main__':
    os.system('cls' if os.name == 'nt' else 'clear')
    print('Chat started successfully!')

    peer_2_ip = input('Enter Listener IP: ').strip()
    local_ip = input('Enter Your IP: ').strip()

    while True:
        try:
            peer_port_input = input('Enter Listener Port: ').strip()
            peer_port = int(peer_port_input)
            break
        except ValueError:
            print("Write correct port!")
    while True:
        try:
            local_port_input = input('Enter Your Port: ').strip()
            local_port = int(local_port_input)
            break
        except ValueError:
            print("Write correct port!")
    while True:
        try:
            max_fragment_size_input = input('Enter max fragment size from 1 to 1480: ').strip()
            if int(max_fragment_size_input) < 1 or int(max_fragment_size_input) > 1480:
                raise ValueError
            max_fragment_size = int(max_fragment_size_input)
            break
        except ValueError:
            print("Write correct fragment size!")

    config = Config('config/config.txt')
    connection = Connection(config)
    connection.connect(local_ip, peer_2_ip, local_port, peer_port, max_fragment_size)
