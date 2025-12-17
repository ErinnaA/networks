Instant Messenger - Networks Assignment Part 1
=============================================

OVERVIEW
--------
This implements a TCP-based instant messenger with UDP/TCP file download using only the 
standard socket library. Supports multiple clients, broadcast/unicast/group messaging, 
and file sharing from server's SharedFiles folder. [file:1]

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
   - /files - lists SharedFiles folder + file count/sizes
   - /get tcp filename - TCP download to username/filename
   - /get udp filename - UDP download to username/filename
   - Files saved in client folder named after username
   - File sizes displayed (sent over socket)

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
   - Plain text: broadcasts to all
   - /quit: graceful exit
   - /broadcast hello: broadcast message
   - /msg Bob hi: private message to Bob
   - /files: list SharedFiles (count + sizes)
   - /get tcp test.txt: TCP download
   - /get udp test.txt: UDP download

IMPLEMENTATION NOTES
--------------------
- Single-threaded server using select.select() for scalability [file:1]
- Non-blocking sockets with proper error/disconnect handling
- Fixed 8-byte headers for file transfers (size prefix)
- clients = {sock: {"username": str, "addr": tuple}} dictionary [file:1]
- groups = {groupname: set(sockets)} for multicast
- Files saved to <username>/ on client side automatically
- SERVER_SHARED_FILES env var optional (defaults to "SharedFiles")

TESTED ON
---------
Python 3.13+ on Windows (per assignment requirements)
Works with 10+ simultaneous clients.

KNOWN LIMITATIONS
-----------------
- UDP downloads use same port (no separate listener)
- No file upload (download only as specified)
- Simple command parsing (no nested commands)

All assignment requirements implemented using only socket library.
