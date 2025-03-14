###############################################################################
# receiver.py
###############################################################################

import sys
import socket

from util import *


def receiver(receiver_port, window_size):
    """Listen on socket and print received message to sys.stdout"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", receiver_port))
    print(
        f"Receiver bound to port {receiver_port}, window size: {window_size}",
        file=sys.stderr,
    )

    s.settimeout(30)

    # Initialize
    expected_seq_num = 1  # First data packet should have seq_num=1
    received_data = {}  # Buffer for out-of-order packets
    connection_active = False
    sender_address = None

    try:
        while True:
            try:
                # Receive packet
                pkt, address = s.recvfrom(2048)
                sender_address = address

                # Extract header
                pkt_header = PacketHeader(pkt[:16])

                # Verify checksum
                original_checksum = pkt_header.checksum
                pkt_header.checksum = 0

                # Reconstruct packet for checksum verification
                if pkt_header.length > 0:
                    msg = pkt[16 : 16 + pkt_header.length]
                    computed_checksum = compute_checksum(bytes(pkt_header) + msg)
                else:
                    # FOr control packets with no data
                    computed_checksum = compute_checksum(bytes(pkt_header))

                # Check if checksum is valid
                if original_checksum != computed_checksum:
                    print(
                        f"Checksum error in packet {pkt_header.seq_num}, ignoring",
                        file=sys.stderr,
                    )
                    continue

                # Handle packet based ob type
                if pkt_header.type == 0:  # START
                    print("Received START packet", file=sys.stderr)

                    # Set the expected sequence number for the first data packet
                    expected_seq_num = 1
                    connection_active = True

                    # Send ACK for START
                    ack_header = PacketHeader(type=3, seq_num=1, length=0)
                    ack_packet = bytes(ack_header)
                    checksum = compute_checksum(ack_packet)
                    ack_header.checksum = checksum
                    ack_packet = bytes(ack_header)

                    s.sendto(ack_packet, address)
                    print("Sent ACK for START", file=sys.stderr)
                elif pkt_header.type == 1:  # End
                    print(
                        f"Received END packet with seq_num {pkt_header.seq_num}",
                        file=sys.stderr,
                    )
                    # Send ACK for END
                    ack_header = PacketHeader(
                        type=3, seq_num=pkt_header.seq_num + 1, length=0
                    )
                    ack_packet = bytes(ack_header)
                    checksum = compute_checksum(ack_packet)
                    ack_header.checksum = checksum
                    ack_packet = bytes(ack_header)

                    s.sendto(ack_packet, address)
                    print("Sent ACK for END, terminating conneciton", file=sys.stderr)

                    connection_active = False
                    break
                elif pkt_header.type == 2:  # DATA
                    msg = pkt[16 : 16 + pkt_header.length]
                    print(
                        f"Received DATA packet {pkt_header.seq_num}, size: {pkt_header.length}",
                        file=sys.stderr,
                    )

                    # Check if packet is duplicated (already processed)
                    if pkt_header.seq_num < expected_seq_num:
                        print(f"Duplicate DATA packet {pkt_header.seq_num} ignored", file=sys.stderr)
                    elif pkt_header.seq_num == expected_seq_num:
                        sys.stdout.buffer.write(msg)
                        sys.stdout.flush()
                        expected_seq_num += 1
                        # Processs any buffered next packets in order
                        while expected_seq_num in received_data:
                            sys.stdout.buffer.write(received_data[expected_seq_num])
                            sys.stdout.flush()
                            del received_data[expected_seq_num]
                            expected_seq_num += 1
                    else:
                        # For out-of-order, only buffer if not already
                        if pkt_header.seq_num not in received_data:
                            received_data[pkt_header.seq_num] = msg

                    ack_header = PacketHeader(type=3, seq_num=pkt_header.seq_num, length=0)
                    ack_packet = bytes(ack_header)
                    checksum = compute_checksum(ack_packet)
                    ack_header.checksum = checksum
                    ack_packet = bytes(ack_header)
                    s.sendto(ack_packet, address)
                    print(f"Sent indiviual ACK for packet {pkt_header.seq_num}", file=sys.stderr)

            except socket.timeout:
                if not connection_active:
                    print(
                        "Socket timeout while waiting for initial conneciton",
                        file=sys.stderr,
                    )
                    break
                print(
                    "Socket timeout - no packet received for 30 seconds",
                    file=sys.stderr,
                )
    except KeyboardInterrupt:
        print("Receiver interrupted by user", file=sys.stderr)
    finally:
        s.close()
        print("Receiver socket closed", file=sys.stderr)


def main():
    """Parse command-line argument and call receiver function"""
    if len(sys.argv) != 3:
        sys.exit("Usage: python receiver.py [Receiver Port] [Window Size]")
    receiver_port = int(sys.argv[1])
    window_size = int(sys.argv[2])
    receiver(receiver_port, window_size)


if __name__ == "__main__":
    main()
