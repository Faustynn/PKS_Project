import struct
import zlib

def create_header(config, seq_num, ack_num, service_type, data_type, timer):
    checksum = 0
    header_length = config.HEADER_SIZE
    combined_service_data = (service_type << 4) | (data_type & 0x0F)

    header = struct.pack(
        config.HEADER_FORMAT,
        seq_num,
        ack_num,
        header_length,
        combined_service_data,
        checksum,
        timer
    )
    checksum = calculate_checksum(header)

    header = struct.pack(
        config.HEADER_FORMAT,
        seq_num,
        ack_num,
        header_length,
        combined_service_data,
        checksum,
        timer
    )

    return header

def calculate_checksum(data):
    return zlib.crc32(data) & 0xFFFF
