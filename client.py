import sys
import os
import socket
import threading

ENCODING = "utf-8"
RECV_BUF = 4096
HEADER_SIZE = 8


def recv_loop(sock):
    while True:
        try:
            data = sock.recv(RECV_BUF)
            if not data:
                print("\nServer disconnected.")
                break
            print(data.decode(ENCODING), end="")
        except:
            break
    os._exit(0)


def download_tcp_file(sock, filename, username):
    """Download file over TCP."""
    os.makedirs(username, exist_ok=True)
    filepath = os.path.join(username, filename)

    with open(filepath, 'wb') as f:
        # Wait for file start
        start_msg = sock.recv(RECV_BUF).decode(ENCODING).strip()
        if "FILE_NOT_FOUND" in start_msg or "ERROR" in start_msg:
            print(start_msg)
            return

        # Read header
        header = sock.recv(HEADER_SIZE)
        filesize = int(header.decode(ENCODING))

        bytes_received = 0
        while bytes_received < filesize:
            chunk = sock.recv(min(RECV_BUF, filesize - bytes_received))
            if not chunk:
                break
            f.write(chunk)
            bytes_received += len(chunk)

        end_msg = sock.recv(RECV_BUF).decode(ENCODING).strip()
        print(f"\nDownloaded {filename} ({filesize} bytes) via TCP")

    print(f"Saved to {filepath}")


def download_udp_file(hostname, port, filename, username):
    """Download file over UDP."""
    os.makedirs(username, exist_ok=True)
    filepath = os.path.join(username, filename)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(15.0)

    try:
        # Wait for file start
        start_msg, _ = sock.recvfrom(RECV_BUF)
        if b"FILE_NOT_FOUND" in start_msg:
            print("File not found")
            return

        # Read header
        header, _ = sock.recvfrom(HEADER_SIZE)
        filesize = int(header.decode(ENCODING))

        with open(filepath, 'wb') as f:
            bytes_received = 0
            while bytes_received < filesize:
                chunk, _ = sock.recvfrom(min(RECV_BUF, filesize - bytes_received))
                f.write(chunk)
                bytes_received += len(chunk)

            end_msg, _ = sock.recvfrom(RECV_BUF)
            print(f"\nDownloaded {filename} ({filesize} bytes) via UDP")
            print(f"Saved to {filepath}")

    except socket.timeout:
        print("UDP download timeout")
    finally:
        sock.close()


def main():
    if len(sys.argv) != 4:
        print("Usage: python client.py [username] [hostname] [port]")
        sys.exit(1)

    username, hostname, port = sys.argv[1], sys.argv[2], int(sys.argv[3])

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((hostname, port))
        sock.sendall(username.encode(ENCODING))

        print("Connected. Commands:")
        print("  /quit, /files, /get tcp filename, /get udp filename\n")

        recv_thread = threading.Thread(target=recv_loop, args=(sock,), daemon=True)
        recv_thread.start()

        while True:
            try:
                msg = input()
                if msg.strip().lower() == "quit":
                    sock.sendall(b"/quit")
                    break

                full_msg = msg + "\n"
                sock.sendall(full_msg.encode(ENCODING))

                # Check for UDP download instruction from server
                if msg.startswith("/get udp"):
                    # Server will respond with "UDP_DOWNLOAD filename port"
                    pass  # Handled by recv_loop parsing below

            except EOFError:
                break

    except Exception as e:
        print(f"Error: {e}")
    finally:
        sock.close()
        os._exit(0)


if __name__ == "__main__":
    main()
