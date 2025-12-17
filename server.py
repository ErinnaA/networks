import sys
import os
import socket
import select
import threading

# Constants
ENCODING = "utf-8"
RECV_BUF = 4096
HEADER_SIZE = 8  # Fixed 8-byte length header for file protocol

# Global state
clients = {}  # sock -> {"username": str, "addr": (ip, port)}
groups = {}  # group_name -> set of sockets
file_transfers = {}  # sock -> transfer_state dict


def pack_header(size):
    """Pack file size into 8-byte fixed header."""
    return f"{size:08d}".encode(ENCODING)


def unpack_header(header):
    """Unpack file size from 8-byte header."""
    return int(header.decode(ENCODING))


def tcp_file_transfer(client_sock, filename):
    """Handle TCP file download over existing connection."""
    shared_dir = os.environ.get("SERVER_SHARED_FILES", "SharedFiles")
    filepath = os.path.join(shared_dir, filename)

    if not os.path.exists(filepath):
        client_sock.sendall(b"FILE_NOT_FOUND\n")
        return

    try:
        filesize = os.path.getsize(filepath)
        client_sock.sendall(b"TCP_FILE_START\n")
        client_sock.sendall(pack_header(filesize))

        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(RECV_BUF)
                if not chunk:
                    break
                client_sock.sendall(chunk)

        client_sock.sendall(b"TCP_FILE_END\n")
        print(f"TCP sent {filename} ({filesize} bytes) to {clients[client_sock]['username']}")
    except Exception as e:
        client_sock.sendall(f"TCP_ERROR: {e}\n".encode(ENCODING))


def udp_file_transfer(client_addr, filename):
    """Handle UDP file download - new UDP socket."""
    shared_dir = os.environ.get("SERVER_SHARED_FILES", "SharedFiles")
    filepath = os.path.join(shared_dir, filename)

    if not os.path.exists(filepath):
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.sendto(b"FILE_NOT_FOUND", client_addr)
        udp_sock.close()
        return

    try:
        filesize = os.path.getsize(filepath)
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.settimeout(10.0)

        udp_sock.sendto(b"UDP_FILE_START", client_addr)
        udp_sock.sendto(pack_header(filesize), client_addr)

        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(RECV_BUF)
                if not chunk:
                    break
                udp_sock.sendto(chunk, client_addr)

        udp_sock.sendto(b"UDP_FILE_END", client_addr)
        print(f"UDP sent {filename} ({filesize} bytes) to {client_addr}")
        udp_sock.close()
    except Exception as e:
        print(f"UDP transfer error: {e}")


def handle_file_command(sock, parts):
    """Handle /get tcp|udp filename command."""
    if len(parts) != 3:
        sock.sendall(b"Usage: /get tcp filename or /get udp filename\n")
        return

    proto, filename = parts[1].lower(), parts[2]
    username = clients[sock]["username"]

    if proto == "tcp":
        tcp_file_transfer(sock, filename)
    elif proto == "udp":
        # Send UDP port back to client (use same TCP port for simplicity)
        sock.sendall(f"UDP_DOWNLOAD {filename} {sock.getpeername()[1]}\n".encode(ENCODING))
    else:
        sock.sendall(b"Protocol must be tcp or udp\n")


def send_files_list(sock):
    """Handle /files command."""
    shared_dir = os.environ.get("SERVER_SHARED_FILES", "SharedFiles")

    if not os.path.exists(shared_dir):
        sock.sendall(b"No SharedFiles folder found\n")
        return

    try:
        files = [f for f in os.listdir(shared_dir) if os.path.isfile(os.path.join(shared_dir, f))]
        count = len(files)
        response = f"SUCCESS {count} files:\n"
        for f in files:
            size = os.path.getsize(os.path.join(shared_dir, f))
            response += f"  {f} ({size} bytes)\n"
        sock.sendall(response.encode(ENCODING))
    except Exception as e:
        sock.sendall(f"Error: {e}\n".encode(ENCODING))


def broadcast(message, exclude_sock=None):
    for tsock in list(clients.keys()):
        if tsock is exclude_sock:
            continue
        try:
            tsock.sendall(message.encode(ENCODING))
        except:
            handle_disconnect(tsock)


def handle_disconnect(sock):
    if sock not in clients:
        return
    username = clients[sock]["username"]
    del clients[sock]

    # Cleanup groups
    for group_name in list(groups):
        groups[group_name].discard(sock)

    try:
        sock.close()
    except:
        pass

    print(f"Client {username} disconnected")
    leave_msg = f"[{username}] has left\n"
    broadcast(leave_msg)


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
                    # New client
                    try:
                        client_sock, addr = server_sock.accept()
                        client_sock.setblocking(False)
                        print(f"New connection from {addr[0]}:{addr[1]}")

                        username_data = client_sock.recv(RECV_BUF)
                        if not username_data:
                            client_sock.close()
                            continue

                        username = username_data.decode(ENCODING).strip()
                        clients[client_sock] = {"username": username, "addr": addr}

                        welcome = f"Welcome {username}!\n"
                        client_sock.sendall(welcome.encode(ENCODING))

                        join_msg = f"[{username}] has joined\n"
                        broadcast(join_msg, client_sock)

                        read_socks.append(client_sock)
                    except:
                        continue
                else:
                    # Client data
                    try:
                        data = sock.recv(RECV_BUF)
                        if not data:
                            handle_disconnect(sock)
                            read_socks.remove(sock)
                            continue

                        text = data.decode(ENCODING).strip()
                        username = clients[sock]["username"]

                        if text.startswith("/"):
                            parts = text.split(maxsplit=2)
                            cmd = parts[0].lower()

                            if cmd == "/quit":
                                handle_disconnect(sock)
                                read_socks.remove(sock)
                            elif cmd == "/files":
                                send_files_list(sock)
                            elif cmd == "/get":
                                handle_file_command(sock, parts)
                            elif cmd == "/broadcast" and len(parts) > 1:
                                msg = " ".join(parts[1:])
                                broadcast(f"{username} (broadcast): {msg}\n", sock)
                            else:
                                sock.sendall(b"Unknown command\n")
                        else:
                            broadcast(f"{username}: {text}\n", sock)
                    except:
                        handle_disconnect(sock)
                        if sock in read_socks:
                            read_socks.remove(sock)

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        for sock in list(clients):
            handle_disconnect(sock)
        server_sock.close()


if __name__ == "__main__":
    main()
