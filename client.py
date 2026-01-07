import sys
import os
import socket
import threading
import time

ENCODING = "utf-8"
RECV_BUF = 4096
FIXED_MSG_SIZE = 1024


def recv_loop(sock, username):
    """Receive loop handling both control messages and TCP file downloads."""
    os.makedirs(username, exist_ok=True)

    tcp_filename = None
    tcp_remaining = 0
    tcp_file = None
    tcp_filesize = 0

    files_list_active = False
    files_count = 0
    files_received = 0

    buffer = b""

    while True:
        try:
            if tcp_file is not None and tcp_remaining > 0:
                data = sock.recv(min(tcp_remaining, 65536))
            else:
                data = sock.recv(RECV_BUF)

            if not data:
                break

            if tcp_file is not None and tcp_remaining > 0:
                tcp_file.write(data)
                tcp_remaining -= len(data)
                if tcp_remaining <= 0:
                    tcp_file.close()
                    tcp_file = None
                    actual_size = os.path.getsize(os.path.join(username, tcp_filename))
                    if actual_size == tcp_filesize:
                        print(f"\nDownloaded {tcp_filename} ({tcp_filesize} bytes) via TCP - COMPLETE")
                    else:
                        print(f"\nTCP download incomplete: {actual_size}/{tcp_filesize} bytes")
                continue

            buffer += data

            while len(buffer) >= FIXED_MSG_SIZE:
                message_data = buffer[:FIXED_MSG_SIZE]
                buffer = buffer[FIXED_MSG_SIZE:]

                try:
                    text = message_data.decode(ENCODING).rstrip()
                except UnicodeDecodeError:
                    continue

                if text.startswith("TCP_FILE "):
                    parts = text.split()
                    if len(parts) >= 3:
                        tcp_filename = parts[1]
                        tcp_filesize = int(parts[2])
                        tcp_remaining = tcp_filesize
                        filepath = os.path.join(username, tcp_filename)
                        tcp_file = open(filepath, "wb")
                        print(f"\nStarting TCP download: {tcp_filename} ({tcp_filesize} bytes)")
                    continue

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

                if text.startswith("FILES_START "):
                    parts = text.split()
                    if len(parts) >= 2:
                        files_count = int(parts[1])
                        files_list_active = True
                        files_received = 0
                        print(f"\nSharedFiles contains {files_count} file(s):")
                    continue

                if text.startswith("FILE_ENTRY ") and files_list_active:
                    parts = text.split(maxsplit=2)
                    if len(parts) >= 3:
                        fname = parts[1]
                        fsize = parts[2]
                        print(f"  {fname} ({fsize} bytes)")
                        files_received += 1
                    continue

                if text.startswith("FILES_END") and files_list_active:
                    files_list_active = False
                    print(f"Total: {files_received} file(s) listed")
                    continue

                if text:
                    print(text)

        except Exception as e:
            print(f"\nConnection error: {e}")
            break

    if tcp_file is not None:
        tcp_file.close()
    sock.close()
    os._exit(0)


def download_udp_file(host, port, filename, username):
    """UDP file download with timeout and buffer handling."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)

    os.makedirs(username, exist_ok=True)
    filepath = os.path.join(username, filename)

    try:
        req = f"REQ {filename} {username}"
        sock.sendto(req.encode(ENCODING), (host, port))

        data, _ = sock.recvfrom(RECV_BUF)
        filesize = int(data.decode(ENCODING))
        if filesize == 0:
            print(f"\nUDP download failed: file {filename} not found")
            return

        with open(filepath, "wb") as f:
            bytes_recvd = 0
            consecutive_timeouts = 0

            while bytes_recvd < filesize:
                try:
                    chunk, _ = sock.recvfrom(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    bytes_recvd += len(chunk)
                    consecutive_timeouts = 0
                except socket.timeout:
                    consecutive_timeouts += 1
                    if consecutive_timeouts > 10:
                        break
                    continue

        if bytes_recvd >= filesize:
            print(f"\nDownloaded {filename} ({filesize} bytes) via UDP - COMPLETE")
        else:
            print(f"\nUDP download incomplete: {bytes_recvd}/{filesize} bytes - PACKET LOSS DETECTED")
    except Exception as e:
        print(f"\nUDP download failed: {e}")
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

    print("Commands:")
    print("  /quit")
    print("  /files")
    print("  /get tcp [filename]")
    print("  /get udp [filename]")
    print("  /broadcast [message]")
    print("  /msg [user] [message]")
    print("  /join [groupname]")
    print("  /leave [groupname]")
    print("  /gmsg [groupname] [message]")
    print()

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
                time.sleep(0.2)
                break

            sock.sendall(msg.ljust(FIXED_MSG_SIZE).encode(ENCODING))
        except:
            break

    sock.close()


if __name__ == "__main__":
    main()
