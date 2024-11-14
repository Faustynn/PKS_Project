import configparser
import struct

class Config:
    def __init__(self, config_file):
        self.config = configparser.ConfigParser()
        self.config.read(config_file)

        self.DEBUG = self.config.getboolean('SPECIAL', 'DEBUG')
        self.SAVE_DIR = self.config.get('SPECIAL', 'SAVE_DIR')

        self.MAX_UDP_SIZE = self.config.getint('HEADER', 'MAX_UDP_SIZE')
        self.HEADER_FORMAT = self.config.get('HEADER', 'HEADER_FORMAT')
        self.HEADER_SIZE = struct.calcsize(self.HEADER_FORMAT)

        self.WINDOW_SIZE = self.config.getint('HEADER', 'WINDOW_SIZE')
        self.TIMEOUT = self.config.getint('HEADER', 'TIMEOUT_WINDOW')

        self.load_constants()

    def load_constants(self):
        self.FLAGS_KEEP_ALIVE = self.config.getint('FLAGS', 'KEEP_ALIVE')
        self.FLAGS_ACK = self.config.getint('FLAGS', 'ACK')
        self.FLAGS_NACK = self.config.getint('FLAGS', 'NACK')
        self.FLAGS_SYN = self.config.getint('FLAGS', 'SYN')
        self.FLAGS_SYN_ACK = self.config.getint('FLAGS', 'SYN_ACK')
        self.FLAGS_FIN = self.config.getint('FLAGS', 'FIN')
        self.FLAGS_RST = self.config.getint('FLAGS', 'RST')
        self.ERROR = self.config.getint('FLAGS', 'ERROR')


        self.STATE_OUT_DISCONNECTED = self.config.getint('STATES', 'STATE_OUT_DISCONNECTED')
        self.STATE_OUT_SYN_SENT = self.config.getint('STATES', 'STATE_OUT_SYN_SENT')
        self.STATE_OUT_ESTABLISHED = self.config.getint('STATES', 'STATE_OUT_ESTABLISHED')

        self.STATE_IN_LISTEN = self.config.getint('STATES', 'STATE_IN_LISTEN')
        self.STATE_IN_SYN_RECEIVED = self.config.getint('STATES', 'STATE_IN_SYN_RECEIVED')
        self.STATE_IN_ESTABLISHED = self.config.getint('STATES', 'STATE_IN_ESTABLISHED')


        self.TIMEOUT_HANDSHAKE = self.config.getint('TIMEOUTS', 'TIMEOUT_HANDSHAKE')
        self.KEEP_ALIVE_WAIT = self.config.getint('TIMEOUTS', 'KEEP_ALIVE_WAIT')
        self.KEEP_ALIVE_INTERVAL = self.config.getint('TIMEOUTS', 'KEEP_ALIVE_INTERVAL')
