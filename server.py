from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room
import time

app = Flask(__name__, template_folder='templates')
socketio = SocketIO(app)
app.config['TEMPLATES_AUTO_RELOAD'] = True

waitlist = []
gamerooms = {}

#func for render
@app.route('/')
def index():
    return render_template('homeRoom.html')

@app.route('/gameRoom/<int:room_id>')
def game_room(room_id):
    return render_template('gameRoom.html', room_id=room_id)

#func for connect disconnect
@socketio.on('tab_close')
def handle_disconnect():
    url = request.referrer
    url_parts = url.split('?')
    room_id = url_parts[0].split('/')[-1]
    player_symbol = url_parts[1]
    handle_pop({'room_id': room_id, 'player': player_symbol})
    print(f'Player closed tab from {url}')

@socketio.on('join_room')
def handle_join_room(data):
    room_id = data.get('room_id')

    current_players = gamerooms.get(room_id, {}).get('players', [])
    player_symbol = 'X' if not current_players else 'O' if 'X' in current_players else 'X'
    
    join_room(room_id)
    gamerooms[room_id]['players'].append(player_symbol)
    if current_players and current_players[0] == 'O':
        current_players.reverse()
    emit('room_joined', {'status': 'Joined room successfully', 'room_id': room_id, 'player_symbol': player_symbol})

@app.route('/fetchRoomId', methods=['GET'])
def fetch_room_id():
    existing_room_id = find_not_full_game_room()

    if existing_room_id is not None:
        room_id = existing_room_id
        print(f"Pairing players in existing room: {room_id}")
    else:
        # If no existing room found, create a new one
        room_id = len(gamerooms) + 1
        gamerooms[room_id] = {'players': [], 'board': [['', '', ''], ['', '', ''], ['', '', '']]}
        print(f"Created game room with room_id: {room_id}")
    return jsonify({'room_id': room_id})

#Main func
@socketio.on('make_move')
def make_move(data):
    room_id = int(data.get('room_id'))
    cell_index = int(data.get('cell_index'))
    current_player_name = data.get('current_player')
    
    if room_id is None:
        emit('move_not_made', {'status': 'Invalid request. Missing room_id.'})
        return
    if cell_index is None:
        emit('move_not_made', {'status': 'Invalid request. Missing cell_index.'})
        return
    if current_player_name is None:
        emit('move_not_made', {'status': 'Invalid request. Missing current_player_name.'})
        return
    if not is_valid_move(room_id, cell_index):
        emit('invalid_move', {'status': 'Invalid move. Cell is already occupied or out of bounds.'})
        return
    if (len(gamerooms[room_id]['players']) == 2):
        gamerooms[room_id]['board'][cell_index // 3][cell_index % 3] = current_player_name
        winner = check_winner(room_id)

        if winner:
            announce_winner(room_id, winner)
        elif is_board_full(room_id):
            announce_draw(room_id)
        else:
            switch_turn(room_id)
        
        print("Current Rooms:", gamerooms, len(gamerooms[room_id]['players']))
        socketio.emit('update_board', {'room_id': room_id, 'board': gamerooms[room_id]['board']})

@socketio.on('pop_player')
def handle_pop(data, on_complete=None):
    room_id = int(data.get('room_id'))
    player = data.get('player')
    
    if room_id in gamerooms:
        if player in gamerooms[room_id]['players']:
            gamerooms[room_id]['players'].remove(player)

    if (len(gamerooms[room_id]['players']) == 0):
        reset_room(room_id)

    check(data)
    print("Current Rooms:", gamerooms)
    emit('acknowledgment',callback=None)

# Additional func
@socketio.on('board_clear')
def board_clear(data):
    room_id = int(data.get('room_id'))
    gamerooms[room_id]['board'] = [['', '', ''], ['', '', ''], ['', '', '']];
    emit('update_board',{'room_id': room_id, 'board': gamerooms[room_id]['board']})

@socketio.on('check')   
def check(data):
    room_id = int(data.get('room_id'))
    socketio.emit('check_player', {'player_count': len(gamerooms[room_id]['players']), 'room_id':room_id })
    print("Current Rooms:", gamerooms, len(gamerooms[room_id]['players']))

def check_winner(room_id):
    room = gamerooms[room_id]
    board = room['board']
    for i in range(3):
        if board[i][0] == board[i][1] == board[i][2] and board[i][0] != '':
            winner = board[i][0]  # Check rows
            announce_winner(room_id, winner)
            return
        if board[0][i] == board[1][i] == board[2][i] and board[0][i] != '':
            winner = board[0][i]  # Check columns
            announce_winner(room_id, winner)
            return

    if board[0][0] == board[1][1] == board[2][2] and board[0][0] != '':
        winner = board[0][0]  # Check diagonal
        announce_winner(room_id, winner)
        return
    if board[0][2] == board[1][1] == board[2][0] and board[0][2] != '':
        winner = board[0][2]  # Check anti-diagonal
        announce_winner(room_id, winner)
        return

    if is_board_full(room_id):
        announce_draw(room_id)

def get_current_player(room_id):
    room = gamerooms.get(room_id)
    if room is not None and room['players']:
        return room['players'][0]
    print(f"Error: Unable to get current player for room {room_id}")
    return None

def switch_turn(room_id):
    room = gamerooms[room_id]
    room['players'].reverse()
    socketio.emit('update_turn', {'next_player': room['players'][0], 'room_id':room_id })

def reset_room(room_id):
    gamerooms[room_id] = {'players': [], 'board': [['', '', ''], ['', '', ''], ['', '', '']]}

def is_valid_move(room_id, cell_index):
    return gamerooms[room_id]['board'][cell_index // 3][cell_index % 3] == ''

def is_board_full(room_id):
    return all(cell != '' for row in gamerooms[room_id]['board'] for cell in row)

def announce_winner(room_id, winner):
    socketio.emit('announce', {'status': 'Winner announced', 'winner': winner, 'room_id':room_id})

def announce_draw(room_id):
    socketio.emit('announce', {'status': 'Draw announced', 'room_id':room_id})

def find_not_full_game_room():
    for room_id, room_data in gamerooms.items():
        if len(room_data['players']) < 2:
            return room_id
    return None

#run the server that can be access with the same ipv4 and port 1234
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=1234, debug=True)
