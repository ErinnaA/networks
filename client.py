import sys
import os
import socket
import threading

ENCODING = "utf-8"
RECV_BUF = 4096
FIXED_MSG_SIZE = 1024


def recv_loop(sock, username):
    """Receive loop."""
    os.makedirs(username, exist_ok=True)
    file_mode = False
    filename = ""
    filesize = 0
    f = None

    while True:
        try:
            data = sock.recv(FIXED_MSG_SIZE)
            if not data:
                break

            text = data.decode(ENCODING).rstrip()

            if file_mode:
                if text == "TCP_FILE_START":
                    file_mode = True
                    continue
                elif text == "TCP_FILE_END":
                    print(f"\nDownloaded {filename} ({filesize} bytes)")
                    file_mode = False
                    f.close()
                    continue
                elif "TCP_FILE" not in text:
                    # File data
                    f.write(data)
                    continue

            print(text, end="")

            # Handle file responses
            if text.startswith("SUCCESS"):
                print("\n")
            elif text == "TCP_FILE_START":
                file_mode = True
            elif text.startswith(str(0).zfill(8)) or text[0].isdigit():
                filesize = int(text)
                filename = "downloaded_file"  # Set from command context
                f = open(os.path.join(username, filename), 'wb')
            elif text.startswith("UDP_DOWNLOAD"):
                parts = text.split()
                udp_filename = parts[1]
                # Start UDP download in thread
                threading.Thread(target=lambda: download_udp_file(sock.getpeername()[0],
                                                                  int(parts[2]),
                                                                  udp_filename, username),
                                 daemon=True).start()

        except:
            break

    sock.close()
    os._exit(0)


def download_udp_file(host, port, filename, username):
    """UDP file download."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(10)
    os.makedirs(username, exist_ok=True)
    filepath = os.path.join(username, filename)

    try:
        data, _ = sock.recvfrom(RECV_BUF)
        filesize = int(data.decode(ENCODING))

        with open(filepath, 'wb') as f:
            bytes_recvd = 0
            while bytes_recvd < filesize:
                chunk, _ = sock.recvfrom(RECV_BUF)
                f.write(chunk)
                bytes_recvd += len(chunk)

        print(f"\nDownloaded {filename} ({filesize} bytes) via UDP")
    except:
        print("UDP download failed")
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

    print("Connected. Commands: /quit /files /get tcp file /get udp file\n")

    recv_thread = threading.Thread(target=recv_loop, args=(sock, username), daemon=True)
    recv_thread.start()

    while True:
        try:
            msg = input()
            if msg.strip().lower() == "quit":
                sock.sendall(b"/quit")
                break
            sock.sendall(msg.ljust(FIXED_MSG_SIZE).encode(ENCODING))
        except:
            break

    sock.close()


if __name__ == "__main__":
    main()
