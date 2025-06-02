from flask import Flask, render_template, request, redirect, url_for, session, Response
from uuid import uuid4  # Для генерации уникальных ID
from flask_socketio import SocketIO, join_room, leave_room
from datetime import timedelta
import time, configparser
import utils
from entities import Player
from database import db_get_rating, db_check_table_existance

app = Flask(__name__)
app_version = '0.2.4'
app.secret_key = "secret_key_123"  # Для работы с сессиями (если понадобится)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1) # Время жизни постоянной сессии (например, 1 дней)
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*")  # Разрешить все источники
db_check_table_existance() # проверяем, существует ли таблица, если нет, то создаём

DEBUG = False


# начальная инициализация глобальных переменных
def first_init():
    global players,players_count,players_start_time,revealed_players_count,global_current_player,game_start_time,game_time,extra_time_restriction
    global current_position,current_round,time_of_battles,global_rate,global_ratings,player_who_win,countdown_time,global_status,round_rate
    global GAME_STARTED,ROOM_NAME,ENDGAME,WINNER_WAS_CHOSEN

    config = configparser.ConfigParser(allow_no_value=True)
    config.read("config.ini")
    players = {} # Словарь для хранения игроков (ключ - user_id)
    players_count = 0
    players_start_time = int(config.get("settings", "players_start_time")) # получение из конфига стартового времени всех игроков
    # запрет на добавление количества секунд в начале следующего хода игрока, если он сходил быстрее данного времени (сек)
    extra_time_restriction = int(config.get("settings", "extra_time_restriction"))
    revealed_players_count = 0 # количество раскрывшихся игроков
    round_rate = int(config.get("settings", "round_rate"))
    global_current_player = None
    game_start_time = None # время старта игры
    game_time = 0 # общее время игры
    current_position = 0
    current_round = 0 # Текущий раунд
    time_of_battles = 0
    global_rate = float(config.get("settings", "global_rate")) # % переноса остатка времени после паса или раскрытия (0.2 = 20%)
    global_ratings = db_get_rating() # получаем глобальный рейтинг игроков из базы данных
    player_who_win = ' '
    countdown_time = None
    global_status = "Ожидание игроков" # 0 - выбор игроков
    GAME_STARTED = False # игра стартовала
    ROOM_NAME = "Главная комната" # Фиксированное название комнаты
    ENDGAME = False
    WINNER_WAS_CHOSEN = False

########################################################################################
first_init() # вызов функции начальной инициализации глобальных переменных
#######################################################################################
        
# проверка логина и позиции на ошибки
def check_login_errors(players, username, position, GAME_STARTED):
    if len(username) < 3:
            error_str = f'{username} username is too short'
            print(f'{username} username is too short')
            return True, error_str
    elif not username.isalnum():
        error_str = f'{username} only letters and numbers is allowed'
        print(f'{username} only letters and numbers is allowed')
        return True, error_str
    
    for player in players:
        if username == players.get(player).username:
            error_str = f'{username} username already exists'
            print(f'{username} username already exists')
            return True, error_str
        elif int(position) == players.get(player).position:
            error_str = f'{position} position already exists'
            print(f'{position} position already exists')
            return True, error_str
    
    if GAME_STARTED: 
        error_str = "Can't enter, game already started"
        print(f'{username} try to join, but game already started')
        return True, error_str
        
    return False, None

# проверка легитимности игры (минимум 3 чел, 10 мин общее время ходов игроков, 30 минут общее время игры)
def check_game_legitimacy(players, game_time):
    players_total_time = 0
    for user_id in players:
        players_total_time += players[user_id].game_time
    if len(players) > 2 and players_total_time > 60 and game_time > 1800:
        print(f'game legitimacy check was approved: pc:{len(players)}, ptt:{players_total_time}, gt:{game_time} statistics recorded')
        return True
    print(f'game legitimacy check was denied: pc:{len(players)}, ptt:{players_total_time}, gt:{game_time} statistics not recorded')
    return False

# проверка на легитимность победителя(должны все игроки проголосовать за одного)
def check_winner_legitimacy(players, winner_name):
    count = 0
    for user_id in players:
        if players[user_id].choosed_winner == winner_name:
            count += 1
    if count == len(players):
        return True
    return False

# получаем текущего игрока с помощью глобальной позиции
def get_player_by_position(players, position):
    for player in players:
        print(f'p_position {players.get(player).position} p_name {players.get(player).username} glo_pos {position}')
        if players.get(player).position == position:
            print(f'следущий ход {players.get(player).username}')
            return players.get(player) # возвращаем игрока
        else:
            print('player not found')

# получаем количество игроков            
def get_players_count(players):
    return len(players)

# получаем время битв в конце игры после выбора победителя
def get_time_of_battles(players, game_time):
    players_total_time = 0
    for user_id in players:
        players_total_time += players[user_id].game_time
    return game_time - players_total_time

# получаем победителя и увеличиваем у всех игроков количество сыгранных игр
def get_winner_and_increase_games_count(players, player_who_win):
    for user_id in players:
        if players[user_id].username == player_who_win:
            players[user_id].increase_games_count(True)
        else:
            players[user_id].increase_games_count(False)

# Отправляем команду на перезагрузку всем клиентам
def force_reload_for_all():   
    socketio.emit('force_reload', room=ROOM_NAME)
    
# проверка готовности всех игроков
def all_players_ready(players):
    temp_count = 0
    for player in players:
        if players.get(player).ready:
            temp_count += 1
    if len(players) == temp_count:
        return True
    else:
        return False

def host_readiness(players):
    for player in players:
        if players.get(player).ready and players.get(player).position == 1:
            return True
    return False

# передача жетона первого игрока следущему игроку (новый раунд)
def first_player_change(players):
    print(f"СМЕНА ПОЗИЦИЙ ИГРОКОВ:")
    for player in players:
        if players.get(player).position == 1:
            players.get(player).change_position(pos=len(players))
            print(f'позиция {players.get(player).username} теперь {players.get(player).position}')
        else:
            new_pos = players.get(player).position - 1
            players.get(player).change_position(pos=new_pos)
            print(f'позиция {players.get(player).username} теперь {players.get(player).position}')

# Сброс статуса игроков на "Ожидание"
def player_status_reset(players):
    print(f"Сброс статуса игроков на 'Oжидание'")
    for player in players:
        players.get(player).status = "Ожидание"

# Сброс готовности игроков
def players_not_ready(players):
    print(f"Сброс готовности игроков")
    for player in players:
        players.get(player).get_ready(False)

# обновляем общее время игры
def update_game_time(game_start_time):
    return int(time.time() - game_start_time) 

# обновляем статистику игроков (рейтинги итд)
def update_statistics(players):
    for user_id in players:
        players[user_id].update_statistics()

# В обработчике подключения
@socketio.on('connect')
def handle_connect():
    join_room(ROOM_NAME)  # Присоединяем клиента к комнате
    # передаём звуки через web-socket, обход ограницчений браузеров на воспроизведение звуков
    socketio.emit('roundstart-1', {'url': '/static/sounds/roundstart-1.mp3'}) 
    socketio.emit('roundstart-2', {'url': '/static/sounds/roundstart-2.mp3'})
    socketio.emit('roundstart-3', {'url': '/static/sounds/roundstart-3.mp3'})
    socketio.emit('roundstart-4', {'url': '/static/sounds/roundstart-4.mp3'})
    socketio.emit('the_last_sec', {'url': '/static/sounds/the_last_sec.mp3'})
    socketio.emit('time_is_up', {'url': '/static/sounds/time_is_up.mp3'})
    
    print(f'Новое подключение: {request.sid}')

# Главная страница
@app.route('/')
def index():
    global players

    # Генерируем уникальный ID для пользователя, если его нет в сессии
    if 'user_id' not in session:
        session['user_id'] = str(uuid4())
    else: # проверяем есть ли игрок уже в списке игроков, если есть сразу перенаправляем его в комнату
        user_id = session.get('user_id') # получаем сессию игрока т.е. кто нажал на кнопку
        if user_id in players:
            print("user already in session")
            return redirect(url_for('room'))
        
    return render_template('index.html', 
                        app_version=app_version,
                        global_ratings=global_ratings)

@app.route('/winner', methods=['POST'])
def winner():
    global WINNER_WAS_CHOSEN, players, player_who_win, time_of_battles, game_time
    player_username = request.form.get('player')  # Получаем значение из формы
    # Теперь вы можете использовать player_username для дальнейшей обработки
    user_id = session.get('user_id') # получаем сессию игрока т.е. кто нажал на кнопку
    # проверяем есть ли id игрока в списке игроков
    if user_id in players:
        players[user_id].choose_winner(player_username)
        print(f'игрок {players[user_id].username} выбрал победителем игрока {player_username}')
    
    # проверка выбора победителя путём голосования всех игроков
    WINNER_WAS_CHOSEN = check_winner_legitimacy(players, player_username)
    if WINNER_WAS_CHOSEN:
        player_who_win = player_username
        time_of_battles = get_time_of_battles(players, game_time)

        if check_game_legitimacy(players, game_time) or DEBUG: # проверяем легитимность игры
            print('recording winner and increase players game count')
            get_winner_and_increase_games_count(players, player_who_win) # обновляем статистику игроков в базе данных
            update_statistics(players) # обновляем статистику игроков в сущностях (рейтинги итд)

        players = dict(sorted(players.items(), key=lambda item: item[1].rating, reverse=True)) # сортировка игроков по убыванию рейтинга

        force_reload_for_all() # Отправляем команду на перезагрузку всем клиентам 
    return redirect(url_for('room'))

@app.route('/login', methods=['POST'])
def login():
        # Получаем данные из формы
    username = request.form.get('username')
    position = request.form.get('position')

        #проверяем есть ли этот ник и позиция в словаре
    check_bool, error_str = check_login_errors(players, username, position, GAME_STARTED)
    if check_bool: 
        return render_template('error.html', error=error_str) # Передаем ошибку на страницу ошибок
    
    user_id = session['user_id'] # Получаем user_id из сессии 
    players[user_id] = Player(user_id,username,position,players_start_time,global_rate) # Создаем или обновляем игрока
    players[user_id].update_statistics()
    print(f'{username} addeded to list')
    force_reload_for_all() # Отправляем команду на перезагрузку всем клиентам   
    return redirect(url_for('room')) # Перенаправляем в комнату

@app.route('/room')
def room():
    global game_time, ENDGAME, players

    # Проверяем, авторизован ли пользователь
    user_id = session.get('user_id')
    if not user_id or user_id not in players:
        return redirect(url_for('index'))
    
    # проверка, если активный игрок перезагрузит страницу, тогда обновим время игрока т.к. таймер стартует заново
    if players[user_id].active:
        players[user_id].update_timer()

    # обновляем общее время игры
    if game_start_time and not ENDGAME:
        game_time = update_game_time(game_start_time)

    # Передаем всех игроков в шаблон
    return render_template('room.html', 
                         players=players.values(),
                         current_player=players[user_id],
                         room_name=ROOM_NAME,
                         global_status=global_status,
                         global_current_player=global_current_player,
                         current_round=current_round,
                         game_time=game_time,
                         ENDGAME=ENDGAME,
                         WINNER_WAS_CHOSEN=WINNER_WAS_CHOSEN,
                         player_who_win=player_who_win,
                         time_of_battles=time_of_battles)

@app.route('/start_game')
def start_game():  
    global global_status,current_position,global_current_player,players_count,players,revealed_players_count,current_round,game_start_time,GAME_STARTED

    if global_status == "Ожидание игроков":
        user_id = session.get('user_id') # получаем сессию игрока т.е. кто нажал на кнопку
        if user_id in players:
            if players[user_id].ready == False: # если игрок не готов
                players[user_id].get_ready(True) # поменять параметр игрока на готов

        # проверка на готовность игрока на позиции 1 (хоста), запуск начала первого раунда
        if host_readiness(players):
            if current_round == 0: # в начале первого раунда сохраняем время начала игры
                GAME_STARTED = True
                game_start_time = int(time.time())

            current_position += 1 # текущая позиция первого игрока
            current_round += 1 # увеличиваем текущий раунд
            global_current_player = get_player_by_position(players, current_position) # определяем текущего игрока
            global_status = "Ход Игроков" # меняем глобальный статус игры
            players_count = get_players_count(players) # определяем количество игроков
            
            # изменяем внутренние параметры игрока
            global_current_player.change_status("Активный")
            global_current_player.set_active(True) # текущий активный игрок
            global_current_player.start_turn_timer() # записываем время начала хода
            print('clicked start game')
            
            # Перенаправляем в комнату
            force_reload_for_all() # Отправляем команду на перезагрузку всем клиентам
            return redirect(url_for('room'))
        else:
            return redirect(url_for('room'))
    else:
        return redirect(url_for('room'))

@app.route('/passed')
def passed():
    global global_status, current_position, global_current_player, players_count, players, revealed_players_count, current_round
    
    user_id = session.get('user_id') # получаем сессию игрока т.е. кто нажал на кнопку
    if user_id in players:
        if players[user_id].active: # если это активный игрок
            print(f'Active player clicked "pass" button: {players.get(user_id).username}')
            
            if global_current_player.status == "Раскрылся":
                pass
            else:
                # изменение статуса игрока на неактивного
                global_current_player.change_status("Ожидание")
                global_current_player.set_active(False) # текущий активный игрок
                global_current_player.get_turn_time() # запись в личное время игрока за все ходы
                global_current_player.end_turn_timer(current_round,round_rate,extra_time_restriction) # подсчёт времени на следущий ход

            # алгоритм передачи хода при нажатии кнопки пасс
            for i in range(players_count):
                # ход передаётся следущему игроку, т.е. после игрока на позиции 1 ходит игрок на позиции 2
                if current_position >= players_count: # если текущая позиция равна максимальной (кол-ву игроков), то сбрасывается до 1
                    current_position = current_position - (players_count - 1)
                else:
                    current_position += 1

                global_current_player = get_player_by_position(players, current_position) # определяем текущего игрока

                # проверяем раскрылся ли игрок, если да, то передаём ход следущему нераскрывшемуся игроку
                if global_current_player.status == "Раскрылся":
                    print(f'{global_current_player.username} {global_current_player.status} переход к следущей позиции')
                else:
                    break
            
            # изменяем внутренние параметры игрока
            global_current_player.change_status("Активный")
            global_current_player.set_active(True) # текущий активный игрок
            global_current_player.start_turn_timer() # записываем время начала хода

            force_reload_for_all() # Отправляем команду на перезагрузку всем клиентам
            return redirect(url_for('room'))

    print(f"произошло нажатие кнопки пасс неактивным игроком {players[user_id].username}")
    return redirect(url_for('room'))

@app.route('/revealed')
def revealed(): #TODO
    global global_status, current_position, global_current_player, players_count, players, revealed_players_count, current_round

    user_id = session.get('user_id') # получаем сессию игрока т.е. кто нажал на кнопку
    if user_id in players:
        if players[user_id].active: # если это активный игрок
            print(f'Active player clicked "reveal" button: {players.get(user_id).username}')

            # изменение статуса игрока на раскрывшегося
            global_current_player.change_status("Раскрылся")
            global_current_player.set_active(False) # текущий активный игрок
            global_current_player.get_turn_time() # запись в личное время игрока за все ходы
            global_current_player.end_turn_timer(current_round,round_rate,extra_time_restriction) # подсчёт времени на следущий ход
            revealed_players_count += 1 # счётчик раскрывшихся игроков

            if revealed_players_count == players_count:
                print('Все игроки раскрылись!')
                global_status = "Ожидание игроков"
                global_current_player = None
                current_position = 0 # сбрасываем текущую позицию
                revealed_players_count = 0 # сбрасываем количество раскрывшихся игроков
                first_player_change(players) # смена позиций игроков после окончания раунда
                players_not_ready(players) # Сброс готовности игроков перед началом второго раунда
                player_status_reset(players) # Смена статуса на "Ожидание"
            else:
                # алгоритм передачи хода при нажатии кнопки
                for i in range(players_count):
                    # ход передаётся следущему игроку, т.е. после игрока на позиции 1 ходит игрок на позиции 2
                    if current_position >= players_count: # если текущая позиция равна максимальной (кол-ву игроков), то сбрасывается до 1
                        current_position = current_position - (players_count - 1)
                    else:
                        current_position += 1

                    global_current_player = get_player_by_position(players, current_position) # определяем текущего игрока

                    # проверяем раскрылся ли игрок, если да, то передаём ход следущему нераскрывшемуся игроку
                    if global_current_player.status == "Раскрылся":
                        print(f'{global_current_player.username} {global_current_player.status} переход к следущей позиции')
                    else:
                        # изменяем внутренние параметры игрока
                        global_current_player.change_status("Активный")
                        global_current_player.set_active(True) # текущий активный игрок
                        global_current_player.start_turn_timer() # записываем время начала хода
                        break
            
                

            force_reload_for_all() # Отправляем команду на перезагрузку всем клиентам
            return redirect(url_for('room'))
        
    return redirect(url_for('room'))


@app.route('/logout')
def logout():
    # Удаляем игрока при выходе
    user_id = session.get('user_id')
    if user_id in players:
        del players[user_id]
        session.pop('user_id', None)
        force_reload_for_all() # Отправляем команду на перезагрузку всем клиентам
    return redirect(url_for('index'))

@app.route('/endgame') # после нажатия кнопки конец игры
def endgame():
    global ENDGAME, game_time
    user_id = session.get('user_id') # получаем сессию игрока т.е. кто нажал на кнопку
    if user_id in players:
        if players[user_id].position == 1: # если это хост
            ENDGAME = True
            game_time = update_game_time(game_start_time) # обновляем общее время игры
            force_reload_for_all() # Отправляем команду на перезагрузку всем клиентам
    return redirect(url_for('room'))

@app.route('/restart')
def restart():
    global players
    user_id = session.get('user_id') # получаем сессию игрока т.е. кто нажал на кнопку
    if user_id in players:
        if players[user_id].position == 1: # если это хост
            players = {}
            session.clear()
            first_init()
            force_reload_for_all() # Отправляем команду на перезагрузку всем клиентам
            return redirect(url_for('index'))
    return redirect(url_for('room'))
            

if __name__ == '__main__':
    socketio.run(app, host=utils.get_internal_ip(), port=5000, debug=True) # utils.get_internal_ip()