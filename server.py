import sys
import os
import socket
import select

# Constants
ENCODING = "utf-8"
RECV_BUF = 4096
FIXED_MSG_SIZE = 1024  # Fixed size per hint #5

clients = {}  # sock -> {"username": str, "addr": (ip, port)}


def send_fixed(sock, message):
    """Send fixed-size message (hint #5)."""
    data = (message + " " * (FIXED_MSG_SIZE - len(message))).encode(ENCODING)
    data = data[:FIXED_MSG_SIZE]
    sock.sendall(data)


def broadcast(message, exclude_sock=None):
    """Broadcast to all except sender."""
    for sock in list(clients.keys()):
        if sock is exclude_sock:
            continue
        try:
            send_fixed(sock, message)
        except:
            handle_disconnect(sock)


def handle_disconnect(sock):
    """Clean up disconnected client."""
    if sock in clients:
        username = clients[sock]["username"]
        del clients[sock]
        try:
            sock.close()
        except:
            pass
        print(f"Client {username} disconnected")
        broadcast(f"[{username}] has left")


def send_files_list(sock):
    """Handle /files command."""
    shared_dir = os.environ.get("SERVER_SHARED_FILES", "SharedFiles")

    if not os.path.exists(shared_dir):
        send_fixed(sock, "No SharedFiles folder found")
        return

    files = [f for f in os.listdir(shared_dir)
             if os.path.isfile(os.path.join(shared_dir, f))]
    count = len(files)
    response = f"SUCCESS {count} files:\n"
    for f in files:
        size = os.path.getsize(os.path.join(shared_dir, f))
        response += f"  {f} ({size} bytes)\n"
    send_fixed(sock, response)


def tcp_file_transfer(sock, filename):
    """TCP file download."""
    shared_dir = os.environ.get("SERVER_SHARED_FILES", "SharedFiles")
    filepath = os.path.join(shared_dir, filename)

    if not os.path.exists(filepath):
        send_fixed(sock, "FILE_NOT_FOUND")
        return

    filesize = os.path.getsize(filepath)
    send_fixed(sock, "TCP_FILE_START")
    send_fixed(sock, str(filesize))

    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(RECV_BUF)
            if not chunk:
                break
            sock.sendall(chunk)

    send_fixed(sock, "TCP_FILE_END")


def handle_file_command(sock, parts):
    """Handle /get tcp|udp filename."""
    if len(parts) != 3:
        send_fixed(sock, "Usage: /get tcp filename")
        return

    proto, filename = parts[1].lower(), parts[2]
    if proto == "tcp":
        tcp_file_transfer(sock, filename)
    else:
        send_fixed(sock, f"UDP_DOWNLOAD {filename}")


def process_message(sock, text):
    """Handle client message."""
    username = clients[sock]["username"]

    if text.startswith("/"):
        parts = text.split(maxsplit=2)
        cmd = parts[0].lower()

        if cmd == "/quit":
            handle_disconnect(sock)
        elif cmd == "/files":
            send_files_list(sock)
        elif cmd == "/get":
            handle_file_command(sock, parts)
        elif cmd == "/broadcast" and len(parts) > 1:
            msg = " ".join(parts[1:])
            broadcast(f"{username} (broadcast): {msg}")
        else:
            send_fixed(sock, "Unknown command")
    else:
        broadcast(f"{username}: {text}")


def main():
    if len(sys.argv) != 2:
        print("Usage: python server.py [port]")
        sys.exit(1)

    port = int(sys.argv[1])
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("", port))
    server_sock.listen(5)
    server_sock.setblocking(False)

    print(f"Server listening on port {port}")
    read_socks = [server_sock]

    try:
        while True:
            ready_read, _, ready_except = select.select(read_socks, [], read_socks, 1.0)

            for sock in ready_except:
                handle_disconnect(sock)
                if sock in read_socks:
                    read_socks.remove(sock)

            for sock in ready_read:
                if sock is server_sock:
                    # New connection
                    try:
                        client_sock, addr = server_sock.accept()
                        client_sock.setblocking(False)
                        print(f"New connection from {addr[0]}:{addr[1]}")

                        data = client_sock.recv(RECV_BUF)
                        username = data.decode(ENCODING).strip()
                        clients[client_sock] = {"username": username, "addr": addr}

                        welcome = f"Welcome {username}!"
                        client_sock.sendall(welcome.encode(ENCODING))
                        broadcast(f"[{username}] has joined", client_sock)

                        read_socks.append(client_sock)
                    except:
                        continue
                else:
                    # Client data
                    try:
                        data = sock.recv(FIXED_MSG_SIZE)
                        if not data:
                            handle_disconnect(sock)
                            if sock in read_socks:
                                read_socks.remove(sock)
                            continue

                        text = data.decode(ENCODING).rstrip()
                        process_message(sock, text)
                    except:
                        handle_disconnect(sock)
                        if sock in read_socks:
                            read_socks.remove(sock)

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        for sock in list(clients.keys()):
            handle_disconnect(sock)
        server_sock.close()


if __name__ == "__main__":
    main()
