import struct
import zlib

 # Format !IIHHHHI (20)
def create_header(config, seq_num, ack_num, flags, window,checksum, reserved):
    checksum = 0
    offset = config.HEADER_SIZE
    reserved = 0

    header = struct.pack(
        config.HEADER_FORMAT,
        seq_num,
        ack_num,
        offset,
        flags,
        window,
        checksum,
        reserved,
    )
    checksum = calculate_checksum(header)

    header = struct.pack(
        config.HEADER_FORMAT,
        seq_num,
        ack_num,
        offset,
        flags,
        window,
        checksum,
        reserved,
    )
    return header


# Checksum calculation throw crc32
def calculate_checksum(data):
    return zlib.crc32(data) & 0xFFFF
