import binascii
import sys

from scapy.all import Packet
from scapy.all import IntField

class PacketHeader(Packet):
    name = "PacketHeader"
    fields_desc = [
        IntField("type", 0), # 0: START; 1: END; 2: DATA; 3: ACK
        IntField("seq_num", 0),
        IntField("length", 0),
        IntField("checksum", 0),
    ]

def compute_checksum(pkt):
    return binascii.crc32(bytes(pkt)) & 0xffffffff

def build_packet(header, data=b""):
    header.checksum = 0
    pkt_bytes = bytes(header) + data
    header.checksum = compute_checksum(pkt_bytes)
    return bytes(header) + data

def create_ack(seq_num, ack_type=3):
    ack_header = PacketHeader(type=ack_type, seq_num=seq_num, length=0, checksum=0)
    return build_packet(ack_header)

def print_debug(msg):
    print(msg, file=sys.stderr)

