import sys
import os
import socket
import select
import time
from collections import defaultdict

# ===== Constants =====
ENCODING = "utf-8"
RECV_BUF = 4096
FIXED_MSG_SIZE = 1024
TCP_FILE_DELAY = 0.1
UDP_PACING_DELAY = 0.001

clients = {}
name_to_sock = {}
groups = defaultdict(set)

UDP_PORT = 13000


# ===== Utility functions =====

def send_fixed(sock, message: str):
    """Send a fixed-length control message."""
    if message is None:
        message = ""
    data = message.encode(ENCODING)
    if len(data) > FIXED_MSG_SIZE:
        data = data[:FIXED_MSG_SIZE]
    else:
        data = data.ljust(FIXED_MSG_SIZE, b" ")
    sock.sendall(data)


def broadcast(message: str, exclude_sock=None):
    """Broadcast control message to all clients except exclude_sock."""
    for sock in list(clients.keys()):
        if sock is exclude_sock:
            continue
        try:
            send_fixed(sock, message)
        except Exception as e:
            print(f"Broadcast error: {e}")
            handle_disconnect(sock)


def unicast(username: str, message: str):
    """Send message to a single user if connected."""
    sock = name_to_sock.get(username)
    if sock is not None and sock in clients:
        try:
            send_fixed(sock, message)
        except Exception as e:
            print(f"Unicast error to {username}: {e}")
            handle_disconnect(sock)


def groupcast(group: str, message: str, exclude_sock=None):
    """Send message to all members of a group except optional exclude."""
    for sock in list(groups.get(group, set())):
        if sock is exclude_sock:
            continue
        if sock not in clients:
            continue
        try:
            send_fixed(sock, message)
        except Exception as e:
            print(f"Groupcast error: {e}")
            handle_disconnect(sock)


def handle_disconnect(sock):
    """Clean up disconnected client."""
    info = clients.pop(sock, None)
    if not info:
        try:
            sock.close()
        except:
            pass
        return

    username = info["username"]
    name_to_sock.pop(username, None)

    for g in list(groups.keys()):
        if sock in groups[g]:
            groups[g].discard(sock)
            if not groups[g]:
                del groups[g]

    try:
        sock.close()
    except:
        pass

    print(f"Client {username} disconnected")
    broadcast(f"{username} has left")


# ===== File functions =====

def send_files_list(sock):
    """Handle /files command."""
    shared_dir = os.environ.get("SERVER_SHARED_FILES", "SharedFiles")

    if not os.path.exists(shared_dir):
        send_fixed(sock, "No SharedFiles folder found")
        return

    files = [f for f in os.listdir(shared_dir)
             if os.path.isfile(os.path.join(shared_dir, f))]
    count = len(files)

    send_fixed(sock, f"FILES_START {count}")

    for fname in files:
        try:
            size = os.path.getsize(os.path.join(shared_dir, fname))
            send_fixed(sock, f"FILE_ENTRY {fname} {size}")
        except Exception as e:
            print(f"Error getting file info for {fname}: {e}")
            continue

    send_fixed(sock, "FILES_END")


def tcp_file_transfer(sock, filename):
    """TCP file download."""
    shared_dir = os.environ.get("SERVER_SHARED_FILES", "SharedFiles")
    filepath = os.path.join(shared_dir, filename)

    if not os.path.exists(filepath):
        send_fixed(sock, "FILE_NOT_FOUND")
        return

    filesize = os.path.getsize(filepath)

    header = f"TCP_FILE {filename} {filesize}"
    send_fixed(sock, header)

    time.sleep(TCP_FILE_DELAY)

    sock.setblocking(True)

    try:
        with open(filepath, "rb") as f:
            sent = 0
            while sent < filesize:
                chunk = f.read(RECV_BUF)
                if not chunk:
                    break
                sock.sendall(chunk)
                sent += len(chunk)
    except Exception as e:
        print(f"Error during TCP file transfer: {e}")
    finally:
        sock.setblocking(False)


def handle_file_command(sock, parts):
    """Handle /get tcp|udp [filename]."""
    if len(parts) != 3:
        send_fixed(sock, "Usage: /get tcp|udp [filename]")
        return

    proto = parts[1].lower()
    filename = parts[2]

    if proto == "tcp":
        tcp_file_transfer(sock, filename)
    elif proto == "udp":
        info = f"UDP_INFO {filename} {UDP_PORT}"
        send_fixed(sock, info)
    else:
        send_fixed(sock, "Unknown protocol (use tcp or udp)")


# ===== Command handling =====

def process_message(sock, text):
    """Handle a command or normal chat message from a client."""
    if sock not in clients:
        return True

    username = clients[sock]["username"]

    if text.startswith("/"):
        parts = text.split(maxsplit=2)
        cmd = parts[0].lower()

        if cmd == "/quit":
            handle_disconnect(sock)
            return True

        elif cmd == "/files":
            send_files_list(sock)

        elif cmd == "/get":
            handle_file_command(sock, parts)

        elif cmd == "/broadcast" and len(parts) > 1:
            msg = parts[1] if len(parts) == 2 else parts[1] + " " + parts[2]
            broadcast(f"{username} (broadcast): {msg}", exclude_sock=sock)

        elif cmd == "/msg" and len(parts) >= 3:
            target = parts[1]
            msg = parts[2]
            if target not in name_to_sock:
                send_fixed(sock, f"User {target} not found")
            else:
                unicast(target, f"{username} (private): {msg}")
                send_fixed(sock, f"Private to {target}: {msg}")

        elif cmd == "/join" and len(parts) >= 2:
            group = parts[1]
            groups[group].add(sock)
            send_fixed(sock, f"Joined group {group}")

        elif cmd == "/leave" and len(parts) >= 2:
            group = parts[1]
            if group in groups and sock in groups[group]:
                groups[group].discard(sock)
                send_fixed(sock, f"Left group {group}")
            else:
                send_fixed(sock, f"Not a member of group {group}")

        elif cmd == "/gmsg" and len(parts) >= 3:
            group = parts[1]
            msg = parts[2]
            if group not in groups or sock not in groups[group]:
                send_fixed(sock, f"Not in group {group}")
            else:
                groupcast(group, f"{username} (group {group}): {msg}",
                          exclude_sock=sock)

        else:
            send_fixed(sock, "Unknown command")

    else:
        broadcast(f"{username}: {text}", exclude_sock=sock)

    return False


# ===== Main =====

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

    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.bind(("", UDP_PORT))
    udp_sock.setblocking(False)

    print(f"Server listening on TCP port {port}, UDP port {UDP_PORT}")
    read_socks = [server_sock, udp_sock]

    try:
        while True:
            ready_read, _, ready_except = select.select(
                read_socks, [], read_socks, 1.0
            )

            for sock in ready_except:
                if sock in clients:
                    handle_disconnect(sock)
                if sock in read_socks:
                    read_socks.remove(sock)

            for sock in ready_read:
                if sock is server_sock:
                    try:
                        client_sock, addr = server_sock.accept()
                        client_sock.setblocking(False)
                        print(f"New connection from {addr[0]}:{addr[1]}")

                        data = client_sock.recv(RECV_BUF)
                        username = data.decode(ENCODING).strip()

                        clients[client_sock] = {"username": username,
                                                "addr": addr}
                        name_to_sock[username] = client_sock

                        welcome = f"Welcome {username}!"
                        send_fixed(client_sock, welcome)
                        broadcast(f"{username} has joined",
                                  exclude_sock=client_sock)

                        read_socks.append(client_sock)
                    except Exception as e:
                        print(f"Error accepting connection: {e}")
                        continue

                elif sock is udp_sock:
                    try:
                        data, addr = udp_sock.recvfrom(RECV_BUF)
                        try:
                            text = data.decode(ENCODING).strip()
                        except:
                            continue

                        parts = text.split(maxsplit=2)
                        if len(parts) >= 3 and parts[0] == "REQ":
                            filename = parts[1]
                            username = parts[2]
                            shared_dir = os.environ.get(
                                "SERVER_SHARED_FILES", "SharedFiles"
                            )
                            filepath = os.path.join(shared_dir, filename)
                            if not os.path.exists(filepath):
                                udp_sock.sendto(b"0", addr)
                                continue

                            filesize = os.path.getsize(filepath)
                            udp_sock.sendto(
                                str(filesize).encode(ENCODING), addr
                            )

                            time.sleep(0.01)

                            with open(filepath, "rb") as f:
                                while True:
                                    chunk = f.read(1400)
                                    if not chunk:
                                        break
                                    udp_sock.sendto(chunk, addr)
                                    time.sleep(UDP_PACING_DELAY)
                    except Exception as e:
                        print(f"UDP error: {e}")
                        continue

                else:
                    try:
                        data = sock.recv(FIXED_MSG_SIZE)
                        if not data:
                            handle_disconnect(sock)
                            if sock in read_socks:
                                read_socks.remove(sock)
                            continue

                        try:
                            text = data.decode(ENCODING).rstrip()
                        except:
                            continue

                        socket_closed = process_message(sock, text)
                        if socket_closed and sock in read_socks:
                            read_socks.remove(sock)

                    except Exception:
                        handle_disconnect(sock)
                        if sock in read_socks:
                            read_socks.remove(sock)

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        for sock in list(clients.keys()):
            handle_disconnect(sock)
        server_sock.close()
        udp_sock.close()


if __name__ == "__main__":
    main()
