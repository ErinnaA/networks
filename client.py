import sys
import os
import socket
import threading

ENCODING = "utf-8"
RECV_BUF = 4096

def recv_loop(sock):
    """Continuously receive messages from server and print them."""
    while True:
        try:
            data = sock.recv(RECV_BUF)
        except Exception:
            print("Connection error. Exiting receive loop.")
            break

        if not data:
            print("Server closed the connection.")
            break

        text = data.decode(ENCODING)
        print(text, end="")  # server already includes newline

    # If receive loop exits, terminate process
    os._exit(0)

def send_loop(sock, username):
    """Read user input and send to server."""
    while True:
        try:
            user_input = input()
        except EOFError:
            user_input = "/quit"

        if not user_input:
            continue

        # Client-side command handling if needed, otherwise send raw
        if user_input.strip().lower() == "/quit":
            try:
                sock.sendall(b"/quit")
            except Exception:
                pass
            break

        try:
            sock.sendall(user_input.encode(ENCODING))
        except Exception:
            print("Failed to send data. Closing.")
            break

    try:
        sock.close()
    except Exception:
        pass
    os._exit(0)

def main():
    if len(sys.argv) != 4:
        print("Usage: python client.py [username] [hostname] [port]")
        sys.exit(1)

    username = sys.argv[1]
    hostname = sys.argv[2]
    port = int(sys.argv[3])

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((hostname, port))
    except Exception as e:
        print(f"Could not connect to {hostname}:{port} - {e}")
        sys.exit(1)

    # Send username first so server can use it
    sock.sendall(username.encode(ENCODING))

    # Start a thread to receive messages from server
    t = threading.Thread(target=recv_loop, args=(sock,), daemon=True)
    t.start()

    print("Connected. Type messages or commands.")
    print("Example commands:")
    print("  /broadcast hello everyone")
    print("  /msg Alice hi")
    print("  /join group1")
    print("  /gmsg group1 hello group")
    print("  /files")
    print("  /get tcp filename")
    print("  /get udp filename")
    print("  /quit")

    # Main thread handles user input
    send_loop(sock, username)

if __name__ == "__main__":
    main()
