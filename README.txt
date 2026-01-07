Instant Messenger - Networks Assignment Part 1
=============================================

OVERVIEW
--------
This implements a TCP-based instant messenger with UDP/TCP file download using only the
standard socket library. Supports multiple clients, broadcast/unicast/group messaging,
and file sharing from server's SharedFiles folder.

REQUIREMENTS MET
----------------
1) CONNECTION FUNCTIONS (8 marks):
   - Server prints client IP:port on connect
   - Welcome message sent over socket (not hardcoded)
   - Multiple clients supported via select()
   - "[username] has joined/left" broadcast to others
   - Graceful (/quit) and unexpected disconnect handled
   - Server survives client disconnects

2) MESSAGING FUNCTIONS (15 marks):
   - Multiple messages supported
   - /broadcast - sends to all other clients
   - /msg target msg - unicast to specific client
   - /join groupname, /leave groupname - group management
   - /gmsg group msg - multicast to group members

3) FILE DOWNLOADING (20 marks):
   - /files
     - Lists all files in the server's SharedFiles folder
     - Includes a SUCCESS message with the number of files and each file's size in bytes,
       all sent from the server over the connection socket (not hardcoded on the client).
   - /get tcp filename
     - Server sends a header `TCP_FILE filename size` over the TCP connection.
     - Client uses this size (from the network) to download exactly that many bytes and
       prints: `Downloaded filename (X bytes) via TCP`.
   - /get udp filename
     - Server sends `UDP_INFO filename udp_port` over TCP.
     - Client opens a UDP socket, sends a `REQ filename username` message, receives the file size
       first, then receives chunks until that many bytes are written, and prints:
       `Downloaded filename (X bytes) via UDP`.
   - Files are saved in a per-user folder on the client side named after the username.
   - All displayed sizes and counts come from values sent over the network, not hardcoded.

4) DOCUMENTATION (7 marks): This file

USAGE INSTRUCTIONS
------------------
1. Create SharedFiles folder next to server.py with test files:
   mkdir SharedFiles
   echo "test" > SharedFiles/test.txt

2. Terminal 1 (Server):
   python server.py 12000

3. Terminal 2+ (Clients):
   python client.py Alice 127.0.0.1 12000
   python client.py Bob 127.0.0.1 12000

4. Client Commands:
   - Plain text: broadcasts to all connected clients (except sender)
   - /quit: graceful exit
   - /broadcast hello: broadcast message
   - /msg Bob hi: private message to Bob
   - /files: list SharedFiles (count + sizes, from server)
   - /get tcp test.txt: TCP download to username/test.txt
   - /get udp test.txt: UDP download to username/test.txt
   - /join groupname: join a named group
   - /leave groupname: leave a named group
   - /gmsg groupname message: send to all members of a group (excluding sender)

   The client provides a continuous input prompt (using standard input) so multiple
   clients can type and send messages concurrently over their own connections.

IMPLEMENTATION NOTES
--------------------
- Single-threaded server using select.select() to handle multiple TCP clients plus
  one UDP socket.
- All TCP sockets (except during TCP file transfer) are non-blocking, with robust
  error/disconnect handling.
- TCP file transfers:
  - Server sends a control header `TCP_FILE filename size` as a fixed-length message.
  - After the header, the server temporarily switches the client socket to blocking
    mode to stream the file bytes reliably, then restores non-blocking mode when finished.
  - Client enters a "download mode" when it sees the TCP_FILE header, reads exactly
    size bytes, writes them to <username>/filename, and then returns to normal message
    handling.
- UDP file transfers:
  - Server listens on a single UDP port (13000) for file requests.
  - Protocol: client sends `REQ filename username`, server replies with the file size
    as text, then sends the file as a sequence of UDP datagrams.
  - To avoid flooding and packet loss, the server:
    - Uses smaller UDP chunks (around 1400 bytes) instead of full RECV_BUF.
    - Adds a short delay between packets to pace transmission.
  - Client increases its UDP receive buffer and loops until it has received the
    announced number of bytes (or times out), then prints the size received.
- All file sizes shown on the client (both /files listing and downloads) are values
  computed by the server and sent over the network; nothing is hardcoded client-side.
- clients = {sock: {"username": str, "addr": tuple}} dictionary for tracking connected users.
- name_to_sock = {username: sock} for quick unicast lookups.
- groups = {groupname: set(sockets)} for multicast group messaging.
- Files saved to <username>/ on the client side automatically.
- SERVER_SHARED_FILES environment variable optionally overrides the default SharedFiles
  directory.

TESTED ON
---------
- Python 3.13+ on Windows (per assignment requirements).
- Works with multiple simultaneous clients connected to the same server, each with its
  own input prompt and independent message stream.

KNOWN LIMITATIONS
-----------------
- UDP file transfer is still best-effort: basic pacing and buffering are implemented,
  but there is no retransmission, sequencing, or advanced reliability logic, so very
  large files over a real network may still be less reliable than TCP.
- No file upload (download only, as specified in the assignment).
- Simple command parsing (no quoting or complex argument parsing).
- Terminal UI is minimal: messages from other users may interleave with what the user
  is typing, which is standard behaviour for simple console chat clients.
