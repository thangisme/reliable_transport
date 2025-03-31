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
    connection_active = False
    sender_address = True

    try:
        while True:
            try:
                # Receive packet
                pkt, address = s.recvfrom(1472)

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
                    if not connection_active:
                        connection_active = True
                        sender_address = address
                        print(f"Connection activated with sender {sender_address}", file=sys.stderr)
                        
                        # Send ACK for START
                        ack_packet = create_ack(1)

                        s.sendto(ack_packet, address)
                        print_debug(f"Sent ACK for START to {sender_address}")

                    else:
                        print_debug(f"Ignored START from {address} while in connection with {sender_address}")
                elif pkt_header.type == 1:  # End
                    print(
                        f"Received END packet with seq_num {pkt_header.seq_num}",
                        file=sys.stderr,
                    )
                    # Send ACK for END
                    ack_packet = create_ack(pkt_header.seq_num + 1)

                    s.sendto(ack_packet, address)
                    print("Sent ACK for END, terminating conneciton", file=sys.stderr)

                    connection_active = False
                    sender_address = None
                    break
                elif pkt_header.type == 2:  # DATA
                    msg = pkt[16 : 16 + pkt_header.length]
                    print(
                        f"Received DATA packet {pkt_header.seq_num}, size: {pkt_header.length}, expecting {expected_seq_num}",
                        file=sys.stderr,
                     )

                    if pkt_header.seq_num == expected_seq_num:
                        # In-order packet, process it
                        sys.stdout.buffer.write(msg)
                        sys.stdout.flush()  # Ensure data is written immediately

                        expected_seq_num += 1

                        ack_packet = create_ack(expected_seq_num)

                        s.sendto(ack_packet, sender_address)
                        print(
                            f"Processed packets up to {expected_seq_num - 1}, sent ACK {expected_seq_num}",
                            file=sys.stderr,
                        )
                    else:
                        print(f"Discarded packet {pkt_header.seq_num}", file=sys.stderr)
                        ack_packet = create_ack(expected_seq_num)

                        s.sendto(ack_packet, sender_address)
                        print(
                            f"Resent ACK {expected_seq_num} due to unexpected packet {pkt_header.seq_num}",
                            file=sys.stderr,
                        )

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
