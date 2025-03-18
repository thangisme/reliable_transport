import socket
import sys

from util import *


def receiver(receiver_port, window_size):
    """Listen on socket and print received message to sys.stdout"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", receiver_port))
    print_debug(f"Receiver bound to port {receiver_port}, window size: {window_size}")

    s.settimeout(30)

    # Initialize
    expected_seq_num = 1  # First data packet should have seq_num=1
    received_data = {}  # Buffer for out-of-order packets
    connection_active = False

    try:
        while True:
            try:
                # Receive packet
                pkt, address = s.recvfrom(2048)

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
                    print_debug(
                        f"Checksum error in packet {pkt_header.seq_num}, ignoring",
                    )
                    continue

                # Handle packet based ob type
                if pkt_header.type == 0:  # START
                    print_debug("Received START packet")

                    # Set the expected sequence number for the first data packet
                    expected_seq_num = 1
                    connection_active = True

                    # Send ACK for START
                    ack_packet = create_ack(1)

                    s.sendto(ack_packet, address)
                    print_debug("Sent ACK for START")
                elif pkt_header.type == 1:  # End
                    print_debug(
                        f"Received END packet with seq_num {pkt_header.seq_num}",
                    )
                    # Send ACK for END
                    ack_packet = create_ack(pkt_header.seq_num + 1)

                    s.sendto(ack_packet, address)
                    print_debug("Sent ACK for END, terminating conneciton")

                    connection_active = False
                    break
                elif pkt_header.type == 2:  # DATA
                    msg = pkt[16 : 16 + pkt_header.length]
                    print_debug(
                        f"Received DATA packet {pkt_header.seq_num}, size: {pkt_header.length}",
                    )

                    # Check if packet is duplicated (already processed)
                    if pkt_header.seq_num < expected_seq_num:
                        print_debug(
                            f"Duplicate DATA packet {pkt_header.seq_num} ignored",
                        )
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
                    elif pkt_header.seq_num >= expected_seq_num + window_size:
                        print_debug(
                            f"Dropped packet {pkt_header.seq_num} outside window"
                        )
                        continue
                    else:
                        # For out-of-order, only buffer if not already
                        if pkt_header.seq_num not in received_data:
                            received_data[pkt_header.seq_num] = msg

                    ack_packet = create_ack(pkt_header.seq_num)
                    s.sendto(ack_packet, address)
                    print_debug(f"Sent indiviual ACK for packet {pkt_header.seq_num}")

            except socket.timeout:
                if not connection_active:
                    print_debug("Socket timeout while waiting for initial conneciton")
                    break
                print_debug("Socket timeout - no packet received for 30 seconds")
    except KeyboardInterrupt:
        print_debug("Receiver interrupted by user")
    finally:
        s.close()
        print_debug("Receiver socket closed")


def main():
    """Parse command-line argument and call receiver function"""
    if len(sys.argv) != 3:
        sys.exit("Usage: python receiver.py [Receiver Port] [Window Size]")
    receiver_port = int(sys.argv[1])
    window_size = int(sys.argv[2])
    receiver(receiver_port, window_size)


if __name__ == "__main__":
    main()
