import sys
import os
import socket
import threading

ENCODING = "utf-8"
RECV_BUF = 4096
FIXED_MSG_SIZE = 1024


def recv_loop(sock, username):
    """Receive loop handling both control messages and TCP file downloads."""
    os.makedirs(username, exist_ok=True)

    # TCP file download state
    tcp_filename = None
    tcp_remaining = 0
    tcp_file = None

    while True:
        try:
            # Always recv RECV_BUF for consistency
            data = sock.recv(RECV_BUF)
            if not data:
                break

            # If in TCP file download mode, treat as raw bytes
            if tcp_file is not None and tcp_remaining > 0:
                to_write = min(len(data), tcp_remaining)
                tcp_file.write(data[:to_write])
                tcp_remaining -= to_write
                if tcp_remaining <= 0:
                    tcp_file.close()
                    tcp_file = None
                    print(f"\nDownloaded {tcp_filename} via TCP (complete)")
                else:
                    # Still more bytes to read
                    pass
                continue

            # Normal control message mode
            try:
                text = data.decode(ENCODING).rstrip()
            except UnicodeDecodeError:
                # Shouldn't happen in control mode
                continue

            # Handle TCP file header: "TCP_FILE filename size"
            if text.startswith("TCP_FILE "):
                parts = text.split()
                if len(parts) >= 3:
                    tcp_filename = parts[1]
                    tcp_remaining = int(parts[2])
                    filepath = os.path.join(username, tcp_filename)
                    tcp_file = open(filepath, "wb")
                    print(f"\nStarting TCP download: {tcp_filename} ({tcp_remaining} bytes)")
                continue

            # Handle UDP info: "UDP_INFO filename port"
            if text.startswith("UDP_INFO "):
                parts = text.split()
                if len(parts) >= 3:
                    filename = parts[1]
                    udp_port = int(parts[2])
                    host = sock.getpeername()[0]
                    threading.Thread(
                        target=download_udp_file,
                        args=(host, udp_port, filename, username),
                        daemon=True,
                    ).start()
                continue

            # Normal control text
            print(text)
        except:
            break

    # Clean up
    if tcp_file is not None:
        tcp_file.close()
    sock.close()
    os._exit(0)


def download_udp_file(host, port, filename, username):
    """UDP file download (simple, no retransmissions)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(10)
    os.makedirs(username, exist_ok=True)
    filepath = os.path.join(username, filename)

    try:
        # Send request: "REQ filename username"
        req = f"REQ {filename} {username}"
        sock.sendto(req.encode(ENCODING), (host, port))

        # Receive filesize
        data, _ = sock.recvfrom(RECV_BUF)
        filesize = int(data.decode(ENCODING))
        if filesize == 0:
            print(f"\nUDP download failed: file {filename} not found")
            return

        with open(filepath, "wb") as f:
            bytes_recvd = 0
            while bytes_recvd < filesize:
                chunk, _ = sock.recvfrom(RECV_BUF)
                if not chunk:
                    break
                f.write(chunk)
                bytes_recvd += len(chunk)

        print(f"\nDownloaded {filename} ({filesize} bytes) via UDP")
    except:
        print("\nUDP download failed")
    finally:
        sock.close()


def main():
    if len(sys.argv) != 4:
        print("Usage: python client.py [username] [hostname] [port]")
        sys.exit(1)

    username, hostname, port = sys.argv[1], sys.argv[2], int(sys.argv[3])

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((hostname, port))
    sock.sendall(username.encode(ENCODING))

    # Print commands
    print("Commands:")
    print("  /quit")
    print("  /files")
    print("  /get tcp filename")
    print("  /get udp filename")
    print("  /broadcast message")
    print("  /msg target message")
    print("  /join groupname")
    print("  /leave groupname")
    print("  /gmsg groupname message")
    print()

    # Background thread to receive all server messages
    recv_thread = threading.Thread(
        target=recv_loop, args=(sock, username), daemon=True
    )
    recv_thread.start()

    while True:
        try:
            msg = input()
            stripped = msg.strip()
            if stripped.lower() == "quit" or stripped.lower() == "/quit":
                sock.sendall("/quit".ljust(FIXED_MSG_SIZE).encode(ENCODING))
                break

            # All commands sent as fixed-size messages
            sock.sendall(msg.ljust(FIXED_MSG_SIZE).encode(ENCODING))
        except:
            break

    sock.close()


if __name__ == "__main__":
    main()
