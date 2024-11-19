import socket
import random
import time
from collections import deque
import threading

WINDOW_SIZE = 10
TIMEOUT = 5000  # milliseconds
SEQ_NUM_BITS = 16  # Using 8 bits for sequence numbers
MAX_SEQ_NUM = 2 ** SEQ_NUM_BITS - 1
lastTimestamp = 0
lastMessageCorrupted = False
storedMessages = deque(maxlen=256)


class Packet:
    def __init__(self, sequence_number, payload, send_time=None):
        self.sequence_number = sequence_number
        self.payload = payload
        self.send_time = send_time
        self.acknowledged = False

class SenderWindow:
    def __init__(self, size):
        self.size = size
        self.base = 0
        self.next_seq_num = 0
        self.packets = {}  # Dict to store packets in window

    def is_full(self):
        return len(self.packets) >= self.size

    def can_send(self, seq_num):
        return (seq_num >= self.base and
                seq_num < self.base + self.size and
                len(self.packets) < self.size)

    def add_packet(self, packet):
        if self.can_send(packet.sequence_number):
            self.packets[packet.sequence_number] = packet
            return True
        return False

    def remove_packet(self, seq_num):
        if seq_num in self.packets:
            del self.packets[seq_num]
            # Update base to the next unacknowledged packet
            while self.base not in self.packets and self.base != self.next_seq_num:
                self.base = (self.base + 1) % (MAX_SEQ_NUM + 1)

class ReceiverWindow:
    def __init__(self, size):
        self.size = size
        self.base = 0
        self.received_buffer = {}

    def is_in_window(self, seq_num):
        if self.base <= seq_num < self.base + self.size:
            return True
        # Handle wrap-around
        if self.base + self.size > MAX_SEQ_NUM:
            if seq_num >= self.base or seq_num < (self.base + self.size) % (MAX_SEQ_NUM + 1):
                return True
        return False

    def receive_packet(self, seq_num, payload):
        if self.is_in_window(seq_num):
            self.received_buffer[seq_num] = payload
            # Try to advance window
            while self.base in self.received_buffer:
                del self.received_buffer[self.base]
                self.base = (self.base + 1) % (MAX_SEQ_NUM + 1)
            return True
        return False

def hashMSG(bytes):
    crc = 0xFFFF
    polynomial = 0x1021

    for byte in bytes:
        crc ^= byte << 8
        for i in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ polynomial
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


class blackBox:
    def __init__(self, msgType: int, flags: int = 0, payload=[], fragmentSeq: int = 0, timestamp=None,
                     checksum=None):
        global lastTimestamp

        infoList = []
        infoList.append((msgType << 4) | flags)
        # Изменяем способ хранения fragmentSeq для поддержки 16 бит
        infoList.append((fragmentSeq >> 8) & 0xFF)  # Старший байт
        infoList.append(fragmentSeq & 0xFF)  # Младший байт
        if timestamp is None:
            infoList.append((lastTimestamp + 1) % 256)
            self.timestamp = (lastTimestamp + 1) % 256
            lastTimestamp = (lastTimestamp + 1) % 256
        else:
            self.timestamp = timestamp % 256
            infoList.append(self.timestamp)

        for b in payload:
            if not (0 <= b < 256):
                print(f"Invalid byte value: {b}")
            infoList.append(b if 0 <= b < 256 else 0)

        if checksum is not None:
            self.checksum = checksum
        else:
            payload_bytes = bytes(infoList[4:])
            self.checksum = hashMSG(payload_bytes)

        self.bytes = bytes(infoList)
        self.bytes = (self.bytes[:1] + self.checksum.to_bytes(2, byteorder='big') + self.bytes[1:])

    def parse(self):
        global lastMessageCorrupted
        message = {
                'msgType': (self.bytes[0] >> 4),
                'flags': self.bytes[0] & 15,
                'checksum': self.bytes[1:3],
                # Изменяем парсинг fragmentSeq для поддержки 16 бит
                'fragmentSeq': (self.bytes[3] << 8) | self.bytes[4],  # Объединяем два байта
                'timeStamp': int.from_bytes(self.bytes[5:6], byteorder='big'),
                'payload': self.bytes[6:]
        }

        payload_checksum = hashMSG(message['payload'])
        received_checksum = int.from_bytes(message['checksum'], byteorder='big')

        if payload_checksum != received_checksum:
            lastMessageCorrupted = True
            print(f"Checksum mismatch: expected {received_checksum}, got {payload_checksum}")

        return message

    @classmethod
    def calculate_checksum(cls, param):
        return hashMSG(param)
    @classmethod
    def fromMessageBytes(cls, messageBytes):
        obj = cls.__new__(cls)
        obj.bytes = messageBytes

        # Extract checksum for all packet without checksum
        obj.checksum = int.from_bytes(obj.bytes[1:3], byteorder='big')
        return obj


def getIpAddress():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ipAddress = s.getsockname()[0]
    finally:
        s.close()
    return ipAddress

def sendMSG(sock, message: blackBox, ip, port, storeMessage=True, sendBadMessage=False):
    if storeMessage:
        storedMessages.append(message)
    bytesToSend = message.bytes
    if sendBadMessage:
        byteData = bytearray(message.bytes)
        byteData[random.randint(6, len(byteData) - 1)] = random.randint(0, 255)
        bytesToSend = bytes(byteData)

    sock.sendto(bytesToSend, (ip, port))

def findStoredMessage(timestamp):
    for message in storedMessages:
        if message.timestamp == timestamp:
            return message
    return None

class WindowManager:
    def __init__(self):
        self.sender_window = None
        self.receiver_window = None
        self.window_lock = threading.Lock()
window_manager = WindowManager()

def handle_nak(parsedMessage, fragmentSeq, sock, ip, port):
    print(f"Processing NAK for sequence number {fragmentSeq}")

    if window_manager.sender_window and fragmentSeq in window_manager.sender_window.packets:
        packet = window_manager.sender_window.packets[fragmentSeq]
        message = blackBox.fromMessageBytes(packet.payload)

        print(f"Resending packet {fragmentSeq}")
        sendMSG(sock, message, ip, port, sendBadMessage=False)
        packet.send_time = time.time()

        packet.acknowledged = False
    else:
        print(f"Packet {fragmentSeq} not found in window")

def calculate_checksum(msg):
    return hashMSG(msg)