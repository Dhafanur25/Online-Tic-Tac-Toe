# Tic-Tac-Toe Web Application

This web application implements Tic-Tac-Toe with RPC, multiple game rooms, and a dashboard. It uses flash-socketio and needs to be on the same IPv4 address and port 1234.

## How to Run:

1. Make sure all devices are on the same Wi-Fi network.
2. Run `ipconfig` in the terminal.
3. Take note of the IPv4 address.
4. Update the address in the socket for `gameRoom.html` and `homeRoom.html` with your IPv4 address.

## Note:

1. Make sure to have downloaded flask socket-io using
   ```bash
   pip install Flask Flask-SocketIO
   
2. If it's not working try changing the port to a higher value.

