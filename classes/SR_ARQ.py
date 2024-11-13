import time

class SR_Window:
    def __init__(self, window_size, timeout):
        self.window_size = window_size
        self.timeout = timeout
        self.window = {}
        self.base = 0
        self.next_seq_num = 0