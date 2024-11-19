import socket
import time
import threading
import random
import os
from blackBox import blackBox, sendMSG, WINDOW_SIZE, SenderWindow, Packet, MAX_SEQ_NUM, TIMEOUT, window_manager
import controlThread

fragMaxLen = 1500 - 6
sender_window = None
sender_window_lock = threading.Lock()

message_id_counter = 0
def get_new_message_id():
    global message_id_counter
    message_id_counter += 1
    return message_id_counter

def check_timeouts(sock, ip, port):
    while True:
        current_time = time.time()
        with window_manager.window_lock:
            if window_manager.sender_window:
                for seq_num, packet in list(window_manager.sender_window.packets.items()):
                    if packet.acknowledged:
                        window_manager.sender_window.remove_packet(seq_num)
                        continue

                    if current_time - packet.send_time > TIMEOUT:
                        message = blackBox.fromMessageBytes(packet.payload)
                        # Resend packet
                        print(f"Resending packet {seq_num} due to timeout")
                        sendMSG(sock, message, ip, port)
                        packet.send_time = current_time
        time.sleep(0.1)


def send_file(sock, filepath, ip, port, fragMaxLen=1500 - 6, corrupt=None, window_manager=None):
    try:
        with open(filepath, 'rb') as file:
            filename = os.path.basename(filepath)
            filename_msg = blackBox(4, flags=1, payload=filename.encode('utf-8'),
                                    checksum=blackBox.calculate_checksum(filename.encode('utf-8')))
            print(f"Sending file: {filename}")
            sendMSG(sock, filename_msg, ip, port)

            # Wait for filename ACK
            time.sleep(0.1)

            file_content = file.read()
            file_size = len(file_content)

            size_msg = blackBox(4, flags=2, payload=str(file_size).encode('utf-8'),
                                checksum=blackBox.calculate_checksum(str(file_size).encode('utf-8')))
            print(f"Sending file size: {file_size}")
            sendMSG(sock, size_msg, ip, port)

            # Wait for file size ACK
            time.sleep(0.1)

            fragments = [file_content[i:i + fragMaxLen] for i in range(0, len(file_content), fragMaxLen)]
            corrupt_fragment = None
            corrupted_sent = False

            if corrupt:
                corrupt_fragment = random.randint(0, len(fragments) - 1)
                print(f"Selected fragment {corrupt_fragment} for corruption")

            fragments_count_msg = blackBox(4, flags=3, payload=str(len(fragments)).encode('utf-8'),
                                           checksum=blackBox.calculate_checksum(str(len(fragments)).encode('utf-8')))
            print(f"Sending file fragments count: {len(fragments)}")
            sendMSG(sock, fragments_count_msg, ip, port)

            # Wait for fragments count ACK
            time.sleep(0.1)

            # Initialize sender window if not exists
            with window_manager.window_lock:
                if window_manager.sender_window is None:
                    window_manager.sender_window = SenderWindow(WINDOW_SIZE)

            retransmission_count = {}
            max_retransmissions = 5
            window_base = 0

            while window_base < len(fragments):
                for i in range(window_base, min(window_base + WINDOW_SIZE, len(fragments))):
                    if i not in retransmission_count:
                        retransmission_count[i] = 0

                    with window_manager.window_lock:
                        if window_manager.sender_window.is_full():
                            time.sleep(0.1)
                            continue

                        seq_num = window_manager.sender_window.next_seq_num

                        # Create packet
                        message = blackBox(4, flags=4, fragmentSeq=seq_num, payload=fragments[i],
                                           checksum=blackBox.calculate_checksum(fragments[i]))

                        # Determine if this fragment should be corrupted
                        should_corrupt = (corrupt and
                                          i == corrupt_fragment and
                                          not corrupted_sent and
                                          retransmission_count[i] == 0)

                        # Store original message for potential retransmission
                        packet = Packet(seq_num, message.bytes, time.time())

                        if window_manager.sender_window.add_packet(packet):
                            print(f"Sending fragment {i} (sequence number {seq_num})")

                            if should_corrupt:
                                print(f"Corrupting fragment {i}")
                                corrupted_sent = True

                            sendMSG(sock, message, ip, port, sendBadMessage=should_corrupt)
                            window_manager.sender_window.next_seq_num = (seq_num + 1) % (MAX_SEQ_NUM + 1)

                            # Wait shorter time between sends to prevent overwhelming receiver
                            time.sleep(0.01)
                        else:
                            print(f"Window full, waiting for ACKs...")
                            time.sleep(0.1)
                            break

                # Wait for acknowledgments or timeout
                timeout_start = time.time()
                while time.time() - timeout_start < TIMEOUT / 1000:
                    with window_manager.window_lock:
                        if not window_manager.sender_window.packets:
                            # All packets in current window acknowledged
                            window_base = i + 1
                            break
                    time.sleep(0.1)

                # Check for timeouts and handle retransmissions
                with window_manager.window_lock:
                    current_time = time.time()
                    for seq_num, packet in list(window_manager.sender_window.packets.items()):
                        if current_time - packet.send_time > TIMEOUT / 1000:
                            fragment_index = window_base + seq_num - window_manager.sender_window.base
                            if retransmission_count[fragment_index] >= max_retransmissions:
                                print(f"Failed to send fragment {fragment_index} after {max_retransmissions} attempts")
                                return False

                            retransmission_count[fragment_index] += 1
                            print(
                                f"Timeout for fragment {fragment_index}, attempt {retransmission_count[fragment_index]}")

                            # Resend packet
                            message = blackBox.fromMessageBytes(packet.payload)
                            sendMSG(sock, message, ip, port)
                            packet.send_time = current_time

            print("File transfer completed successfully")
            return True

    except Exception as e:
        print(f"Error sending file: {e}")
        return False
def send_corrupt_file(sock, filepath, ip, port, window_manager):
    if not os.path.exists(filepath):
        print("File does not exist")
        return False

    success = send_file(sock, filepath, ip, port, fragMaxLen=1500 - 6, corrupt=True, window_manager=window_manager)
    if success:
        print("Corrupted file transfer completed")
    else:
        print("Failed to send corrupted file")
    return success

def send_corrupt_message(sock, message_text, ip, port, window_manager):
    fragments = [message_text[i:i + fragMaxLen].encode('utf-8')
                 for i in range(0, len(message_text), fragMaxLen)]

    if len(fragments) == 1:
        # For single fragment messages
        with window_manager.window_lock:
            if window_manager.sender_window is None:
                window_manager.sender_window = SenderWindow(WINDOW_SIZE)
            seq_num = window_manager.sender_window.next_seq_num

            # Create corrupted message with invalid checksum
            message = blackBox(2, flags=1, payload=fragments[0], fragmentSeq=seq_num)
            window_manager.sender_window.add_packet(Packet(seq_num, message.bytes, time.time()))
            # Send corrupted version
            sendMSG(sock, message, ip, port, sendBadMessage=True)

            print(f"Send mess {message.bytes}")
            window_manager.sender_window.next_seq_num = (seq_num + 1) % (MAX_SEQ_NUM + 1)
            print("Sent corrupted single fragment message, with seq ", seq_num)

            #wait for ack
            while True:
                with window_manager.window_lock:
                    if all(packet.acknowledged for packet in window_manager.sender_window.packets.values()):
                        break
                time.sleep(0.1)

    else:
        # Handle multi-fragment messages similarly to normal messages but corrupt one fragment
        message_id = get_new_message_id()
        message = blackBox(3, flags=2, fragmentSeq=len(fragments), timestamp=message_id)
        sendMSG(sock, message, ip, port)

        corrupt_fragment = random.randint(0, len(fragments) - 1)

        for i in range(0, len(fragments), WINDOW_SIZE):
            with window_manager.window_lock:
                for j in range(i, min(i + WINDOW_SIZE, len(fragments))):
                    seq_num = window_manager.sender_window.next_seq_num
                    j_bytes = j.to_bytes(4, byteorder='big')
                    payload_frag = j_bytes + fragments[j]

                    # Create message (corrupted for chosen fragment)
                    message = blackBox(3, flags=4, fragmentSeq=seq_num,
                                       payload=payload_frag,
                                       timestamp=message_id)

                    # Store original message for retransmission
                    window_manager.sender_window.add_packet(Packet(seq_num, message.bytes, time.time()))

                    # Send corrupted or normal version
                    sendMSG(sock, message, ip, port, sendBadMessage=(j == corrupt_fragment))
                    window_manager.sender_window.next_seq_num = (seq_num + 1) % (MAX_SEQ_NUM + 1)

            # Wait for acknowledgments
            while True:
                with window_manager.window_lock:
                    if all(packet.acknowledged for packet in window_manager.sender_window.packets.values()):
                        break
                time.sleep(0.1)

def sendPacket(ip: str, port: int):
    global sender_window, fragMaxLen, fragments
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    with window_manager.window_lock:
        if sender_window is None:
            sender_window = SenderWindow(WINDOW_SIZE)
            window_manager.sender_window = sender_window

    # Start timeout checker in separate thread
    timeout_thread = threading.Thread(target=check_timeouts, args=(sock, ip, port), daemon=True)
    timeout_thread.start()

    synMSG = blackBox(1, flags=2)
    print("To start talking, type !start")

    while True:
        try:
            payload = input("Enter message: ")

            with controlThread.connection_lock:
                is_connected = controlThread.hasConnectionToPeer

            if payload == "!start":
                if is_connected:
                    print("Connection already established")
                    continue

                for i in range(5):
                    with controlThread.connection_lock:
                        if controlThread.hasConnectionToPeer:
                            print("Connection Established")
                            break
                    print("Attempting connection...")
                    sendMSG(sock, synMSG, ip, port)
                    time.sleep(0.5)

                with controlThread.connection_lock:
                    if not controlThread.hasConnectionToPeer:
                        print("Connection failed")
                continue

            if not is_connected:
                print("Connection not established")
                continue

            if payload == "!help":
                print("Commands:")
                print("!start - Establish a connection with the peer")
                print("!end - Cut the connection with the peer")
                print("!file - Send a file to the peer")
                print("!err - Send a corrupted message")
                print("!help - Display this help message")
                continue

            if payload == "!end":
                message = blackBox(1, flags=8)
                sendMSG(sock, message, ip, port)
                print("Cutting Connection")
                with controlThread.connection_lock:
                    controlThread.hasConnectionToPeer = False
                continue

            if payload == "!file":
                filepath = input("Enter the source file path: ")
                if not os.path.exists(filepath):
                    print("File does not exist")
                    continue

                print(f"Sending file: {filepath}")
                if send_file(sock, filepath, ip, port, fragMaxLen,None, window_manager=window_manager):
                    print("File sent successfully")
                    # Reset sender window
                    sender_window = None
                    with window_manager.window_lock:
                        window_manager.sender_window = None
                else:
                    print("Failed to send file")
                continue

            if payload == "!frag":
                while True:
                    try:
                        fragMaxLen = int(input("Enter the maximum fragment length: "))
                        if fragMaxLen < 1:
                            print("Invalid fragment length")
                        elif fragMaxLen > 1500 - 6:
                            print("Fragment length too large")
                        else:
                            print(f"Fragment length set to {fragMaxLen}")
                            break
                    except ValueError:
                        print("Please enter a valid integer")
                continue

            if payload == "!err":
                print("Choose what type of message you want to corrupt:")
                print("1. Corrupt a message")
                print("2. Corrupt a file")
                while True:
                    choice = input("Enter choice: ")
                    if choice == "1":
                        mess = input("Enter the message to corrupt: ")
                        send_corrupt_message(sock, mess, ip, port, window_manager)
                        break
                    elif choice == "2":
                        filepath = input("Enter the source file path: ")
                        send_corrupt_file(sock, filepath, ip, port, window_manager)
                        break
                    else:
                        print("Invalid choice,try again")
                continue

            print(f"Sending message: {payload}")
            fragments = [payload[i:i + fragMaxLen].encode('utf-8')
                         for i in range(0, len(payload), fragMaxLen)]
            calc_checksum = blackBox.calculate_checksum(payload.encode('utf-8'))

            if len(fragments) == 1:
                message = blackBox(2, flags=1,
                                   payload=fragments[0],
                                   fragmentSeq=len(fragments))
                sendMSG(sock, message, ip, port)
                print("Sent single fragment message")

                # Add to unacknowledged messages
                with window_manager.window_lock:
                    if window_manager.sender_window is None:
                        window_manager.sender_window = SenderWindow(WINDOW_SIZE)
                    window_manager.sender_window.add_packet(Packet(0, fragments[0], time.time()))

            else:
                message_id = get_new_message_id()  # Use the new fixed message_id
                message = blackBox(3, flags=2, fragmentSeq=len(fragments), timestamp=message_id)
                sendMSG(sock, message, ip, port)

                for i in range(0, len(fragments), WINDOW_SIZE):
                    with window_manager.window_lock:
                        for j in range(i, min(i + WINDOW_SIZE, len(fragments))):
                            seq_num = (window_manager.sender_window.next_seq_num
                                       if window_manager.sender_window else j)
                            packet = Packet(seq_num, fragments[j], time.time())

                            if (window_manager.sender_window and window_manager.sender_window.add_packet(packet)):
                                print(f"Sending fragment {j} a {seq_num}")
                                j_bytes = j.to_bytes(4, byteorder='big')
                                payload_frag = j_bytes + fragments[j]
                                calc_checksum = blackBox.calculate_checksum(payload_frag)

                                message = blackBox(3, flags=4, fragmentSeq=seq_num, payload=payload_frag,
                                                   timestamp=message_id,checksum=calc_checksum)
                                sendMSG(sock, message, ip, port)
                                window_manager.sender_window.next_seq_num = (seq_num + 1) % (MAX_SEQ_NUM + 1)

                    # Wait for ACKs for the current window
                    while True:
                        with window_manager.window_lock:
                            if all(packet.acknowledged for packet in window_manager.sender_window.packets.values()):
                                break
                        time.sleep(0.1)

                # After sending the completion confirmation
                confirm_msg = blackBox(2, flags=5)
                sendMSG(sock, confirm_msg, ip, port, storeMessage=False)

                # Reset sender window
                sender_window = None
                with window_manager.window_lock:
                    window_manager.sender_window = None

        except Exception as e:
            print(f"Error in send thread: {e}")
            continue
