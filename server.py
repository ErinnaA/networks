import sys
import os
import socket
import select
import threading

# Constants
ENCODING = "utf-8"
RECV_BUF = 4096

# Global state
clients = {}          # sock -> {"username": str, "addr": (ip, port)}
groups = {}           # group_name -> set of sockets

def broadcast(message, exclude_sock=None):
    """Send message to all connected clients except exclude_sock."""
    for sock in list(clients.keys()):
        if sock is not exclude_sock:
            try:
                sock.sendall(message.encode(ENCODING))
            except Exception:
                # Handle broken connection
                handle_disconnect(sock)

def send_to_user(target_username, message):
    """Unicast to a single user."""
    for sock, info in list(clients.items()):
        if info["username"] == target_username:
            try:
                sock.sendall(message.encode(ENCODING))
            except Exception:
                handle_disconnect(sock)
            break

def send_to_group(group_name, message, exclude_sock=None):
    """Multicast to users in a named group."""
    members = groups.get(group_name, set())
    for sock in list(members):
        if sock is exclude_sock:
            continue
        try:
            sock.sendall(message.encode(ENCODING))
        except Exception:
            handle_disconnect(sock)

def remove_from_groups(sock):
    for gname, members in groups.items():
        if sock in members:
            members.remove(sock)

def handle_disconnect(sock):
    """Clean up when a client disconnects unexpectedly."""
    if sock not in clients:
        return
    username = clients[sock]["username"]
    del clients[sock]
    remove_from_groups(sock)
    try:
        sock.close()
    except Exception:
        pass
    leave_msg = f"[{username}] has left\n"
    broadcast(leave_msg, exclude_sock=None)

def handle_client(sock):
    """Per-client receive loop (could alternatively use select in main thread)."""
    while True:
        try:
            data = sock.recv(RECV_BUF)
        except Exception:
            handle_disconnect(sock)
            break

        if not data:
            # Connection closed
            handle_disconnect(sock)
            break

        text = data.decode(ENCODING).strip()
        username = clients[sock]["username"]

        # Command parsing (you will define your own commands, e.g. /quit, /broadcast, /msg, /join, /leave, /files, /get)
        if text.startswith("/"):
            # Example command handling skeleton
            parts = text.split()
            cmd = parts[0].lower()

            if cmd == "/quit":
                # graceful leave
                handle_disconnect(sock)
                break

            elif cmd == "/broadcast":
                # /broadcast message...
                msg_body = " ".join(parts[1:])
                out = f"{username} (broadcast): {msg_body}\n"
                broadcast(out, exclude_sock=sock)

            elif cmd == "/msg" and len(parts) >= 3:
                # /msg target_username message...
                target = parts[1]
                msg_body = " ".join(parts[2:])
                out = f"{username} -> {target}: {msg_body}\n"
                send_to_user(target, out)

            elif cmd == "/join" and len(parts) == 2:
                group_name = parts[1]
                groups.setdefault(group_name, set()).add(sock)
                sock.sendall(f"Joined group {group_name}\n".encode(ENCODING))

            elif cmd == "/leave" and len(parts) == 2:
                group_name = parts[1]
                if group_name in groups and sock in groups[group_name]:
                    groups[group_name].remove(sock)
                    sock.sendall(f"Left group {group_name}\n".encode(ENCODING))

            elif cmd == "/gmsg" and len(parts) >= 3:
                # /gmsg group_name message...
                group_name = parts[1]
                msg_body = " ".join(parts[2:])
                out = f"{username} [{group_name}]: {msg_body}\n"
                send_to_group(group_name, out, exclude_sock=sock)

            elif cmd == "/files":
                # TODO: implement listing files in SharedFiles and sending count
                # Use SERVER_SHARED_FILES env variable or default
                pass

            elif cmd == "/get" and len(parts) >= 3:
                # /get tcp filename
                # /get udp filename
                # TODO: implement file transfer (TCP or UDP)
                pass

            else:
                sock.sendall(b"Unknown or malformed command\n")

        else:
            # Plain text message; you may choose a default mode (e.g., broadcast)
            out = f"{username}: {text}\n"
            broadcast(out, exclude_sock=sock)

def main():
    if len(sys.argv) != 2:
        print("Usage: python server.py [port]")
        sys.exit(1)

    port = int(sys.argv[1])

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("", port))
    server_sock.listen(5)

    print(f"Server listening on port {port}")

    try:
        while True:
            client_sock, addr = server_sock.accept()
            print(f"New connection from {addr[0]}:{addr[1]}")  # requirement: print IP and port

            # Receive initial username from client
            try:
                username_data = client_sock.recv(RECV_BUF)
            except Exception:
                client_sock.close()
                continue

            if not username_data:
                client_sock.close()
                continue

            username = username_data.decode(ENCODING).strip()
            clients[client_sock] = {"username": username, "addr": addr}

            # Send welcome message over socket
            welcome = f"Welcome {username}! You are connected to the server.\n"
            client_sock.sendall(welcome.encode(ENCODING))

            # Inform others
            join_msg = f"[{username}] has joined\n"
            broadcast(join_msg, exclude_sock=client_sock)

            # Start per-client thread
            t = threading.Thread(target=handle_client, args=(client_sock,), daemon=True)
            t.start()

    except KeyboardInterrupt:
        print("Server shutting down...")
    finally:
        for sock in list(clients.keys()):
            try:
                sock.close()
            except Exception:
                pass
        server_sock.close()

if __name__ == "__main__":
    main()
