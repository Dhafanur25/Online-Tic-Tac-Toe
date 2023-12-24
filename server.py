# Import library yang diperlukan dari Flask dan Flask-SocketIO
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room
import time

# Inisialisasi aplikasi Flask dan Flask-SocketIO
app = Flask(__name__, template_folder='templates')
socketio = SocketIO(app)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Variabel dictionary untuk menyimpan room_id, list players, dan list board
gamerooms = {}

# Fungsi untuk merender halaman homeRoom
@app.route('/')
def index():
    return render_template('homeRoom.html')

# Fungsi untuk merender halaman gameRoom berdasarkan ID ruangan
@app.route('/gameRoom/<int:room_id>')
def game_room(room_id):
    return render_template('gameRoom.html', room_id=room_id)

# Fungsi untuk handle ketika user tutup tab atau pencet dashboard
@socketio.on('tab_close')
def handle_disconnect():
    url = request.referrer
    url_parts = url.split('?')
    room_id = url_parts[0].split('/')[-1]
    player_symbol = url_parts[1]

    handle_pop({'room_id': room_id, 'player': player_symbol})
    print(f'Player disconnect from {url}')

# Fungsi untuk handle user gabung ke gameRoom
@socketio.on('join_room')
def handle_join_room(data):
    room_id = data.get('room_id')

    # Jika isi players pada gameroom dengan id... 0 maka player baru join di set 'X'
    # Jika sudah ada satu orang 'X' maka player baru join di set 'O'
    # Jika sudah ada satu orang 'O' maka player baru join di set 'X' dan list players di reverse
    current_players = gamerooms.get(room_id, {}).get('players', [])
    player_symbol = 'X' if not current_players else 'O' if 'X' in current_players else 'X'
    
    join_room(room_id)
    gamerooms[room_id]['players'].append(player_symbol)
    if current_players and current_players[0] == 'O':
        current_players.reverse()
    emit('room_joined', {'status': 'Joined room successfully', 'room_id': room_id, 'player_symbol': player_symbol})

# Fungsi untuk mengambil room_id yang belum penuh atau membuat room_id baru jika tidak ada
@app.route('/fetchRoomId', methods=['GET'])
def fetch_room_id():
    existing_room_id = find_not_full_game_room()

    if existing_room_id is not None:
        room_id = existing_room_id
        print(f"Pairing players in existing room: {room_id}")
    else:
        # jika tidak ada existing room yang kosong, maka buat baru
        room_id = len(gamerooms) + 1
        gamerooms[room_id] = {'players': [], 'board': [['', '', ''], ['', '', ''], ['', '', '']]}
        print(f"Created game room with room_id: {room_id}")
    return jsonify({'room_id': room_id})

# Fungsi utama untuk handle jika board di pencet user
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
    # Cek apakah di room tersebut ada 2 players
    if (len(gamerooms[room_id]['players']) == 2):
        # Mengisi index dari cell yang di pencet dengan nama player yang pencet
        gamerooms[room_id]['board'][cell_index // 3][cell_index % 3] = current_player_name 
        # Cek apakah move itu membuat suatu kemenangan
        winner = check_winner(room_id)

        if winner: # Handle jika menang
            announce_winner(room_id, winner)
        elif is_board_full(room_id): # Handle jika board sudah penuh
            announce_draw(room_id)
        else:
            # Jika game masih berjalan maka list players di reverse
            switch_turn(room_id)
        
        print("Current Rooms:", gamerooms, len(gamerooms[room_id]['players']))
        # Update board untuk semua players di room id itu
        socketio.emit('update_board', {'room_id': room_id, 'board': gamerooms[room_id]['board']})

# Fungsi untuk handle ketika player keluar game akan dihapus dari dict
@socketio.on('pop_player')
def handle_pop(data, on_complete=None):
    room_id = int(data.get('room_id'))
    player = data.get('player')
    
    if room_id in gamerooms:
        if player in gamerooms[room_id]['players']:
            gamerooms[room_id]['players'].remove(player)

    # Jika player pada suatu room bernilai 0 maka board di clear supaya room bisa di pakai kembali
    if (len(gamerooms[room_id]['players']) == 0): 
        reset_room(room_id)

    check(data)
    print("Current Rooms:", gamerooms)
    emit('acknowledgment',callback=None)

# Fungsi untuk reset list boardnya pada suatu room
@socketio.on('board_clear')
def board_clear(data):
    room_id = int(data.get('room_id'))
    gamerooms[room_id]['board'] = [['', '', ''], ['', '', ''], ['', '', '']];
    emit('update_board',{'room_id': room_id, 'board': gamerooms[room_id]['board']})

# Fungsi untuk Cek jumlah players pada suatu gameroom
@socketio.on('check')   
def check(data):
    room_id = int(data.get('room_id'))
    socketio.emit('check_player', {'player_count': len(gamerooms[room_id]['players']), 'room_id':room_id })
    print("Current Rooms:", gamerooms, len(gamerooms[room_id]['players']))

# Fungsi untuk cek apakah ada yang menang
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

# Fungsi mendapatkan player pertama di suatu room
def get_current_player(room_id):
    room = gamerooms.get(room_id)
    if room is not None and room['players']:
        return room['players'][0]
    print(f"Error: Unable to get current player for room {room_id}")
    return None

# Fungsi untuk reverse list players
def switch_turn(room_id):
    room = gamerooms[room_id]
    room['players'].reverse()
    socketio.emit('update_turn', {'next_player': room['players'][0], 'room_id':room_id })

# Fungsi untuk reset players dan board pada suatu room_id
def reset_room(room_id):
    gamerooms[room_id] = {'players': [], 'board': [['', '', ''], ['', '', ''], ['', '', '']]}

# Fungsi untuk handle cell yang sudah diisi tidak boleh diubah isinya
def is_valid_move(room_id, cell_index):
    return gamerooms[room_id]['board'][cell_index // 3][cell_index % 3] == ''

# Fungsi untuk cek apakah list board sudah penuh semua
def is_board_full(room_id):
    return all(cell != '' for row in gamerooms[room_id]['board'] for cell in row)

# Fungsi untuk umumkan pemenang ke semua client pada room_id
def announce_winner(room_id, winner):
    socketio.emit('announce', {'status': 'Winner announced', 'winner': winner, 'room_id':room_id})

# Fungsi untuk umumkan draw ke semua client pada room_id
def announce_draw(room_id):
    socketio.emit('announce', {'status': 'Draw announced', 'room_id':room_id})

# Fungsi untuk mencari room_id yang belum penuh
def find_not_full_game_room():
    for room_id, room_data in gamerooms.items():
        if len(room_data['players']) < 2:
            return room_id
    return None

# Jalankan server Flask-SocketIO pada alamat dan port tertentu
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=1234, debug=True)
