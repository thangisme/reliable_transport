###############################################################################
# sender.py
###############################################################################

import sys
import socket
import time
from util import *


def sender(receiver_ip, receiver_port, window_size):
    """Open socket and send message from sys.stdin"""
    # Create UDP socket (SOCK_DGRAM) with IPv4 address family (AF_INET)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Read the message from stdin
    message = sys.stdin.buffer.read()
    print(f"Read {len(message)} bytes from stdin...")

    # --- Conection establishment (START phase) ---
    # Create a START packet with type=0, seq_num=0
    seq_num = 0  # Starting sequence number

    # Create the header
    start_header = PacketHeader(type=0, seq_num=seq_num, length=0)

    # Create the packet(header only, no data)
    start_packet = bytes(start_header)

    # Calculate checksum and update header
    checksum = compute_checksum(start_packet)
    start_header.checksum = checksum
    start_packet = bytes(start_header)

    # Send the START packet
    s.sendto(start_packet, (receiver_ip, receiver_port))
    print(f"Send START packet")

    # Wait for acknowledgment (ACK) from receiver
    s.settimeout(0.5)
    start_acked = False

    # Keep trying until we got ACK for out START
    while not start_acked:
        try:
            # Try to receive an ACK
            data, addr = s.recvfrom(1472)  # Max UDP payload size

            # Parse the received packet
            header = PacketHeader(data)

            # Check if it's an ACK for our START
            if (
                header.type == 3 and header.seq_num == 1
            ):  # ACK with seq_num=1 means START was received
                print("Connection established!")
                start_acked = True
                seq_num = 1  # Next packet will be seq_num=1

        except socket.timeout:
            # If tiemout occurs, resend the START packet
            print("Timeout waiting for START ACK, resending ...")
            s.sendto(start_packet, (receiver_ip, receiver_port))

    # --- Data transfer phase ---
    # Split the message into chunks that fit in packets
    # Maximum UDP payload is 1472 bytes, subtract header sieze (16 bytes)
    MAX_DATA_SIZE = 1472 - 16
    chunks = []
    for i in range(0, len(message), MAX_DATA_SIZE):
        chunks.append(message[i : i + MAX_DATA_SIZE])

    print(f"Message split into {len(chunks)} chunks")

    # Set up sliding iwndow parameters
    base = 1  # First unacknowledged packet
    next_seq_num = 1  # Next packet to send

    # Buffer for storing sent packets (for potential retransmission)
    buffer = {}

    # Set socket to non-blocking for parallel sending/receiving
    s.setblocking(False)

    # Initialize timer variables
    timer_active = False
    timer_start = 0
    timeout_duration = 0.5

    # Continue until all packets are acknowledged
    while base <= len(chunks):
        # Send new packets that fit within the window
        while next_seq_num < base + window_size and next_seq_num <= len(chunks):
            # Get the chunk to send
            chunk_index = next_seq_num - 1  # adjusted for 1-indexded sequence
            data = chunks[chunk_index]

            # Create DATA packet header
            header = PacketHeader(type=2, seq_num=next_seq_num, length=len(data))

            # Combine header and data
            packet = bytes(header) + data

            # Calculate and update checksum
            checksum = compute_checksum(packet)
            header.checksum = checksum
            packet = bytes(header) + data

            # Store packet in buffer for potential retransmission
            buffer[next_seq_num] = packet

            # Send the packet
            s.sendto(packet, (receiver_ip, receiver_port))
            print(f"Sent DATA packet {next_seq_num}")

            # Start timer if this is the first packet in the window
            if not timer_active:
                timer_start = time.time()
                timer_active = True

            # Move to next packet
            next_seq_num += 1

        # Try to receive ACKS (non-blocking)
        try:
            data, addr = s.recvfrom(1472)

            # Parse header
            header = PacketHeader(data)

            # Check if it's an ACK
            if header.type == 3:
                print(f"Received ACK {header.seq_num}")

                # Move the window if this ACK is for a packet we haven't acknowledged yet
                if header.seq_num > base:
                    # Update base (fist unacknowledged packet)
                    base = header.seq_num

                    # If all sent packets are acknowledged, stop the timer
                    if base == next_seq_num:
                        timer_active = False
                    else:
                        # Otherwise restart the timer for the next unacknowledged packet
                        timer_start = time.time()

        except BlockingIOError:
            # No data available to receive, this is expected with non-blocking socket
            pass

        if timer_active and (time.time() - timer_start > timeout_duration):
            print("Timeout occured, resending unacknowledges packets")

            # Resend all unacknowledged packets in the window
            for seq in range(base, next_seq_num):
                if seq in buffer:
                    s.sendto(buffer[seq], (receiver_ip, receiver_port))
                    print(f"Resent DATA packet {seq}")

            # Reset timer
            timer_start = time.time()

    # --- Connection termination (END phase)
    # Create END packet (type=1)
    end_header = PacketHeader(type=1, seq_num=next_seq_num, length=0)
    end_packet = bytes(end_header)

    # Calculate and update checksum
    checksum = compute_checksum(end_packet)
    end_header.checksum = checksum
    end_packet = bytes(end_header)

    # Switch back to blocking socket with timeout
    s.setblocking(True)
    s.settimeout(0.5)

    # Send END packet
    s.sendto(end_packet, (receiver_ip, receiver_port))
    print(f"Sent END packet with seq_num {next_seq_num}")

    # Wait for ACK for END packet or timeout after 500ms
    end_time = time.time()
    end_acked = False

    while not end_acked and time.time() - end_time < 0.5:
        try:
            data, addr = s.recvfrom(1472)
            header = PacketHeader(data)

            # Check if it's an ACK for our END packet
            if header.type == 3 and header.seq_num == next_seq_num + 1:
                print("Received ACK for End packet, connection terminatited")
                end_acked = True
                break
        except socket.timeout:
            # Resend END packet
            print("Timeout waiting for END ACK, resending ...")
            s.sendto(end_packet, (receiver_ip, receiver_port))

    s.close()


def main():
    """Parse command-line arguments and call sender function"""
    if len(sys.argv) != 4:
        sys.exit(
            "Usage: python sender.py [Receiver IP] [Receiver Port] [Window Size] < [message]"
        )
    receiver_ip = sys.argv[1]
    receiver_port = int(sys.argv[2])
    window_size = int(sys.argv[3])
    sender(receiver_ip, receiver_port, window_size)


if __name__ == "__main__":
    main()
