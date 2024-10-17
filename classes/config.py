import configparser
import struct

class Config:
    def __init__(self, config_file):
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
        self.DEBUG = self.config.getboolean('MODE', 'DEBUG')
        self.MAX_UDP_SIZE = self.config.getint('HEADER', 'MAX_UDP_SIZE')
        self.HEADER_FORMAT = self.config.get('HEADER', 'HEADER_FORMAT')
        self.HEADER_SIZE = struct.calcsize(self.HEADER_FORMAT)
        self.load_constants()

    def load_constants(self):
        self.DATA_TYPE_TEXT = self.config.getint('DATA_TYPE', 'DATA_TYPE_TEXT')
        self.DATA_TYPE_IMAGE = self.config.getint('DATA_TYPE', 'DATA_TYPE_IMAGE')
        self.DATA_TYPE_VIDEO = self.config.getint('DATA_TYPE', 'DATA_TYPE_VIDEO')
        self.DATA_TYPE_KEEP_ALIVE = self.config.getint('DATA_TYPE', 'DATA_TYPE_KEEP_ALIVE')

        
        self.TYPE_OF_SERVICE_DATA = self.config.getint('TYPE_OF_SERVICE', 'TYPE_OF_SERVICE_DATA')
        self.TYPE_OF_SERVICE_KEEP_ALIVE = self.config.getint('TYPE_OF_SERVICE', 'TYPE_OF_SERVICE_KEEP_ALIVE')
        self.TYPE_OF_SERVICE_FIN = self.config.getint('TYPE_OF_SERVICE', 'TYPE_OF_SERVICE_FIN')
        self.TYPE_OF_SERVICE_ACK = self.config.getint('TYPE_OF_SERVICE', 'TYPE_OF_SERVICE_ACK')
        self.TYPE_OF_SERVICE_SYN = self.config.getint('TYPE_OF_SERVICE', 'TYPE_OF_SERVICE_HANDSHAKE')
        self.TYPE_OF_SERVICE_SYN_ACK = 4


        self.STATE_OUT_DISCONNECTED = self.config.getint('STATES', 'STATE_OUT_DISCONNECTED')
        self.STATE_OUT_SYN_SENT = self.config.getint('STATES', 'STATE_OUT_SYN_SENT')
        self.STATE_OUT_ESTABLISHED = self.config.getint('STATES', 'STATE_OUT_ESTABLISHED')

        self.STATE_IN_LISTEN = self.config.getint('STATES', 'STATE_IN_LISTEN')
        self.STATE_IN_SYN_RECEIVED = self.config.getint('STATES', 'STATE_IN_SYN_RECEIVED')
        self.STATE_IN_ESTABLISHED = self.config.getint('STATES', 'STATE_IN_ESTABLISHED')


        self.TIMEOUT_HANDSHAKE = self.config.getint('TIMEOUTS', 'TIMEOUT_HANDSHAKE')
        self.TIMEOUT_KEEP_ALIVE = self.config.getint('TIMEOUTS', 'TIMEOUT_KEEP_ALIVE')
        self.KEEP_ALIVE_INTERVAL = self.config.getint('TIMEOUTS', 'KEEP_ALIVE_INTERVAL')
