import socket
from threading import Lock

import time
from typing import Set, Dict

import controlThread
from window_manager import manager, sendMSG, ReceiverWindow, lastMessageCorrupted,window_manager, handle_nak

SIZE = 8
bigMessageBuffer = []
processedFile = ''
fileLen = 0
textBuffer = [None]
receiver_lock = Lock()
file_transfer_state = {}
receiver_window = None
fragmented_messages = {}


class FileTransferState:
    def __init__(self, filename: str):
        self.filename = f"received_files/{filename}"
        self.file = None
        self.file_size: int = 0
        self.fragment_count: int = 0
        self.received_fragments: Set[int] = set()
        self.fragments_data: Dict[int, bytes] = {}
        self.missing_fragments: Set[int] = set()
        self.last_request_time: Dict[int, float] = {}
        self.request_attempts: Dict[int, int] = {}
        self.MAX_RETRIES = 3
        self.REQUEST_TIMEOUT = 5.0  # seconds

    def initialize_file(self, size: int, count: int):
        self.file_size = size
        self.fragment_count = count
        self.file = open(self.filename, 'wb')
        self.missing_fragments = set(range(count))

    def can_request_fragment(self, fragment_num: int, current_time: float) -> bool:
        if fragment_num not in self.last_request_time:
            return True

        if (current_time - self.last_request_time[fragment_num] >= self.REQUEST_TIMEOUT and
                self.request_attempts.get(fragment_num, 0) < self.MAX_RETRIES):
            return True

        return False

    def record_fragment_request(self, fragment_num: int, current_time: float):
        self.last_request_time[fragment_num] = current_time
        self.request_attempts[fragment_num] = self.request_attempts.get(fragment_num, 0) + 1

    def process_fragment(self, fragment_num: int, data: bytes) -> bool:
        if fragment_num in self.missing_fragments:
            self.fragments_data[fragment_num] = data
            self.received_fragments.add(fragment_num)
            self.missing_fragments.remove(fragment_num)
            return True
        return False

    def is_complete(self) -> bool:
        return len(self.missing_fragments) == 0

    def write_file(self):
        if not self.is_complete():
            return False

        # Sort fragments and write them in order
        for i in range(self.fragment_count):
            self.file.write(self.fragments_data[i])
        self.file.close()
        return True
def handle_file_transfer(parsedMessage, sock, ip, responsePort, file_transfer_state: FileTransferState = None):
    checksum = manager.calculate_checksum(parsedMessage['payload'])
    current_time = time.time()

    if parsedMessage['flags'] == 1:  # Filename
        if checksum == int.from_bytes(parsedMessage['checksum'], byteorder='big'):
            filename = parsedMessage['payload'].decode('utf-8')
            file_transfer_state = FileTransferState(filename)
            print(f"Receiving file: {filename}")
            ack_message = manager(5, flags=1, fragmentSeq=parsedMessage['fragmentSeq'],
                                  timestamp=parsedMessage["timeStamp"])
            sendMSG(sock, ack_message, ip, responsePort, storeMessage=False)
            return file_transfer_state

    elif parsedMessage['flags'] == 2:  # File size
        if checksum == int.from_bytes(parsedMessage['checksum'], byteorder='big'):
            file_size = int(parsedMessage['payload'].decode('utf-8'))
            print(f"File size: {file_size}")
            ack_message = manager(5, flags=1, fragmentSeq=parsedMessage['fragmentSeq'],
                                  timestamp=parsedMessage["timeStamp"])
            sendMSG(sock, ack_message, ip, responsePort, storeMessage=False)
            if file_transfer_state:
                file_transfer_state.file_size = file_size

    elif parsedMessage['flags'] == 3:  # Fragment count
        if checksum == int.from_bytes(parsedMessage['checksum'], byteorder='big'):
            fragment_count = int(parsedMessage['payload'].decode('utf-8'))
            print(f"Expected fragments: {fragment_count}")
            if file_transfer_state:
                file_transfer_state.initialize_file(file_transfer_state.file_size, fragment_count)
            ack_message = manager(5, flags=1, fragmentSeq=parsedMessage['fragmentSeq'],
                                  timestamp=parsedMessage["timeStamp"])
            sendMSG(sock, ack_message, ip, responsePort, storeMessage=False)

    elif parsedMessage['flags'] == 4:  # File fragment
        if checksum == int.from_bytes(parsedMessage['checksum'], byteorder='big'):
            fragment_num = parsedMessage['fragmentSeq']

            if file_transfer_state and file_transfer_state.process_fragment(fragment_num, parsedMessage['payload']):
                print(f"Received fragment {fragment_num}")
                ack_message = manager(5, flags=1, fragmentSeq=fragment_num,
                                      timestamp=parsedMessage["timeStamp"])
                sendMSG(sock, ack_message, ip, responsePort, storeMessage=False)

                # Check for missing fragments
                if len(file_transfer_state.missing_fragments) > 0:
                    for missing_fragment in list(file_transfer_state.missing_fragments):
                        if file_transfer_state.can_request_fragment(missing_fragment, current_time):
                            print(f"Requesting missing fragment {missing_fragment}")
                            request_message = manager(4, flags=6, fragmentSeq=missing_fragment,
                                                      timestamp=parsedMessage["timeStamp"])
                            sendMSG(sock, request_message, ip, responsePort, storeMessage=False)
                            file_transfer_state.record_fragment_request(missing_fragment, current_time)

                # Check if file is complete
                if file_transfer_state.is_complete():
                    if file_transfer_state.write_file():
                        print("File transfer complete")
                    else:
                        print("Error writing file")

                progress = ((file_transfer_state.fragment_count - len(file_transfer_state.missing_fragments)) /
                            file_transfer_state.fragment_count * 100)
                print(f"File transfer progress: {progress:.2f}%")
        else:
            print(f"Checksum mismatch for fragment {parsedMessage['fragmentSeq']}")
            nak_message = manager(5, flags=2, fragmentSeq=parsedMessage['fragmentSeq'],
                                  timestamp=parsedMessage["timeStamp"])
            sendMSG(sock, nak_message, ip, responsePort, storeMessage=False)

    return file_transfer_state

def handle_text_message(parsedMessage, sock, ip, responsePort, receiver_window, addr):
    seq_num = parsedMessage['fragmentSeq']
    message_id = parsedMessage["timeStamp"]

    # Create test message with same parameters but without checksum
    test_message = manager(
        msgType=parsedMessage['msgType'],
        flags=parsedMessage['flags'],
        payload=parsedMessage['payload'],
        fragmentSeq=parsedMessage['fragmentSeq'],
        timestamp=parsedMessage["timeStamp"]
    )

    # Compare checksums
    received_checksum = int.from_bytes(parsedMessage['checksum'], byteorder='big')
    wait_checksum = test_message.checksum

    print(f"Received checksum: {received_checksum}")
    print(f"Calculated checksum: {wait_checksum}")

    # Non-fragmented message
    if parsedMessage['flags'] == 1:
        if receiver_window.is_in_window(seq_num):
            if wait_checksum == received_checksum:
                # Send ack for verif. message
                print(f"Message verified. Sending ACK for packet {seq_num}")
                ack_message = manager(5, flags=1, fragmentSeq=seq_num, timestamp=message_id)
                sendMSG(sock, ack_message, ip, responsePort, storeMessage=False)
                print(f"{addr} Sent a message: {parsedMessage['payload'].decode('utf-8')}")

                # Update receiver window with received packet
                receiver_window.receive_packet(seq_num, parsedMessage['payload'])
            else:
                print(f"Checksum mismatch for packet {seq_num}, sending NAK")
                nak_message = manager(5, flags=2, fragmentSeq=seq_num, timestamp=message_id)
                sendMSG(sock, nak_message, ip, responsePort, storeMessage=False)

    # Start of fragmented message
    elif parsedMessage['flags'] == 2:
        fragmented_messages[message_id] = {
            "buffer": [None] * parsedMessage["fragmentSeq"],
            "expected_fragments": parsedMessage["fragmentSeq"],
            "received_fragments": set()  # Track successfully received fragments
        }
        print(f"Started receiving fragmented message with {parsedMessage['fragmentSeq']} fragments")

    # Fragment of message
    elif parsedMessage['flags'] == 4:
        if message_id not in fragmented_messages:
            print(f"Received fragment for unknown message ID {message_id}")
            return

        message_info = fragmented_messages[message_id]
        extracted_j = int.from_bytes(parsedMessage['payload'][:4], byteorder='big')
        original_payload = parsedMessage['payload'][4:]

        if wait_checksum == received_checksum:
            if extracted_j < len(message_info["buffer"]):
                # Check if this fragment was already received correctly
                if extracted_j not in message_info["received_fragments"]:
                    message_info["buffer"][extracted_j] = original_payload.decode('utf-8')
                    message_info["received_fragments"].add(extracted_j)
                    print(f"Fragment {extracted_j} received and verified")

                # Send ack
                ack_message = manager(5, flags=1, fragmentSeq=seq_num, timestamp=message_id)
                sendMSG(sock, ack_message, ip, responsePort, storeMessage=False)

                # Check if message is complete sended
                if len(message_info["received_fragments"]) == message_info["expected_fragments"]:
                    complete_message = ''.join(message_info["buffer"])
                    print(f"{addr} Sent a complete fragmented message: {complete_message}")
                    del fragmented_messages[message_id]
            else:
                print(f"Fragment index {extracted_j} out of range")
        else:
            print(f"Checksum mismatch for fragment {extracted_j}, sending NAK")
            nak_message = manager(5, flags=2, fragmentSeq=seq_num, timestamp=message_id)
            sendMSG(sock, nak_message, ip, responsePort, storeMessage=False)

def receivePacket(ip: str, listenPort: int, responsePort: int):
    global processedFile, fileLen, textBuffer, file_transfer_state, receiver_window, sender_window
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', listenPort))

    with window_manager.window_lock:
        receiver_window = ReceiverWindow(8)  # Same window size as sender

    print(f"Listening on port {listenPort}...")

    while True:
        try:
            data, addr = sock.recvfrom(1500)
            message = manager.fromMessageBytes(data)
            parsedMessage = message.parse()

            if receiver_window is None:
                with receiver_lock:
                    receiver_window = ReceiverWindow(8)

            if lastMessageCorrupted:
                print(f"Message corrupted, requesting resend")
                nak_message = manager(5, flags=2, timestamp=parsedMessage["timeStamp"])
                sendMSG(sock, nak_message, ip, responsePort, storeMessage=False)
                continue

            # control messages
            if parsedMessage['msgType'] == 1:
                # Handle control messages
                with controlThread.connection_lock:
                    if parsedMessage['flags'] == 2:
                        controlThread.hasConnectionToPeer = True
                        response = manager(1, flags=3)
                        sendMSG(sock, response, ip, responsePort)
                        print(f"A peer has connected: {addr}")
                        receiver_window = ReceiverWindow(8)
                    elif parsedMessage['flags'] == 3:
                        controlThread.hasConnectionToPeer = True
                    elif parsedMessage['flags'] == 4:
                        response = manager(1, flags=5) # response to keep alive
                        sendMSG(sock, response, ip, responsePort)
                    elif parsedMessage['flags'] == 5:
                        controlThread.expectingResponse = False
                    elif parsedMessage['flags'] == 8:
                        response = manager(1, flags=9)
                        sendMSG(sock, response, ip, responsePort)
                        controlThread.hasConnectionToPeer = False
                        controlThread.expectingResponse = False
                        controlThread.ConnectionManuallyInterrupted = True
                        print("peer has cut their connection")
                    elif parsedMessage['flags'] == 9:
                        controlThread.hasConnectionToPeer = False
                        controlThread.expectingResponse = False
                        controlThread.ConnectionManuallyInterrupted = True

            # receivePacket
            elif parsedMessage['msgType'] in [2, 3]:
                handle_text_message(parsedMessage, sock, ip, responsePort, receiver_window, addr)

            #file transfer
            elif parsedMessage['msgType'] == 4:
                file_transfer_state = handle_file_transfer(parsedMessage, sock, ip, responsePort, file_transfer_state)

            elif parsedMessage['msgType'] == 5 and parsedMessage['flags'] == 1:
                with window_manager.window_lock:
                    print(f"Received ACK for packet {parsedMessage['fragmentSeq']}")

                    if (window_manager.sender_window is not None and
                        parsedMessage['fragmentSeq'] in window_manager.sender_window.packets):
                        sender_window = window_manager.sender_window
                        seq_num = parsedMessage['fragmentSeq']
                        sender_window.packets[seq_num].acknowledged = True
                        sender_window.remove_packet(seq_num)
            elif parsedMessage['msgType'] == 5 and parsedMessage['flags'] == 2:
                print(f"Received NAK for packet {parsedMessage['fragmentSeq']}")
                handle_nak(parsedMessage, parsedMessage['fragmentSeq'], sock, ip, responsePort)

            else:
                print(f"Unknown message type: {parsedMessage['msgType']}")



        except Exception as e:
            print(f"Error in receive thread: {e}")
            continue