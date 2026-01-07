Instant Messenger - Networks Assignment Part 1


OVERVIEW
My program implements a TCP-based instant messenger with UDP/TCP file download using
only the standard socket library. It supports multiple clients, broadcast/unicast/group
messaging, and file sharing from the server's SharedFiles folder.

USAGE INSTRUCTIONS
------------------
1. Create SharedFiles folder next to server.py with test files:
   mkdir SharedFiles
   echo "test" > SharedFiles/test.txt

2. Set up a terminal for the server called Terminal 1:
   Use the following command to set up the server
   python server.py [port]
   e.g. python server.py 12000

3. Set up a terminal per client, using the following command:
   python client.py [username] [hostname] [port]
   e.g. python client.py Alice 127.0.0.1 12000
        python client.py Bob 127.0.0.1 12000

4. Client Commands:
   Once connected, you may message an unlimited amount of times by entering input at the flashing cursor.
   You may also want to use commands to control who your messages go to:
   - Plain text: broadcasts the message to all connected clients (except to the sender)
   - /quit: exit the chatting application
   - /broadcast [message]: broadcasts the message to all chatters
   - /msg [user] [message]: private message to the inputted user
   - /files: lists the contents of SharedFiles (count + sizes, from server)
   - /get tcp [filename]: TCP download to [user]/[filename]
   - /get udp [filename]: UDP download to [user]/[filename]
   - /join [groupname]: join a named group or creates a group if it doesn't exist
   - /leave [groupname]: leave a named group
   - /gmsg [groupname] [message]: send a message to all members of a group (excluding the sender)

REQUIREMENTS MET
--------------------
1) CONNECTION FUNCTIONS:
   - Server prints IP and port of client on connect
   - Welcome message sent over socket on connect
   - Multiple clients supported via select()
   - "[user] has joined/left" broadcast to others when others connect
   - Graceful (/quit) and unexpected disconnect handled
   - Server survives client disconnects

2) MESSAGING FUNCTIONS:
   - Multiple messages supported
   - /broadcast [message] - sends to all other clients
   - /msg [user] [message] - unicast to specific client
   - /join [groupname], /leave [groupname] - group management
   - /gmsg [groupname] [message] - multicast to group members

3) FILE DOWNLOADING:
   - /files
     - Lists all files in the server's SharedFiles folder
     - Uses multi-message protocol to handle any number of files
     - Displays file count and each file's size in bytes
     - All information sent from server over network (not hardcoded)
   - /get tcp filename
     - Server sends header `TCP_FILE filename size` over TCP connection
     - Client downloads exactly that many bytes
     - Prints: `Downloaded filename (X bytes) via TCP - COMPLETE`
   - /get udp filename
     - Server sends `UDP_INFO filename udp_port` over TCP
     - Client uses UDP to request and download file
     - Prints completion status and detects packet loss
   - Files saved to per-user folder named after username
   - All sizes and counts sent over network, not hardcoded

4) DOCUMENTATION: This file


