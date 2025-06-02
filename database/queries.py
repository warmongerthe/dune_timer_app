from database import Database

db = Database('data/players.db') # манипулирование базой данных

# проверяем, существует ли таблица, если нет, то создаём
def db_check_table_existance(): 
    with db.get_cursor() as cursor:
        cursor.execute("""CREATE TABLE IF NOT EXISTS players (
                        username TEXT NOT NULL UNIQUE,
                        total_games INTEGER,
                        wins INTEGER,
                        rating INTEGER
                    );""")

# получаем имя игрока (уникальное в бд), если его ещё нет, то записываем в бд
def db_get_or_create_player(username, total_games, wins, rating):   
    with db.get_cursor() as cursor: # проверяем есть ли игрок в базе, если нет, то добавляем
        cursor.execute("INSERT INTO players (username, total_games, wins, rating) SELECT ?,?,?,? "
        "WHERE NOT EXISTS (SELECT username FROM players WHERE username = ?);", (username, total_games, wins, rating, username))
            # обновляем рейтинг побед
        cursor.execute("UPDATE players SET rating = (wins * 100) / total_games WHERE username = ? AND total_games > 0;",(username,))
        cursor.execute("SELECT * FROM players WHERE username = ?", (username,)) # получаем таблицу игрока
        return cursor.fetchall()
    
# получаем рейтинг игроков из базы данных
def db_get_rating(limit=100):
    with db.get_cursor() as cursor:
        cursor.execute("SELECT * FROM players WHERE total_games > 0 ORDER BY rating DESC LIMIT ?", (limit,))
        return cursor.fetchall()

# увеличиваем количество игр и побед (если победитель True) 
def db_increase_games_count(username, winner=False): # увеличиваем количество игр и побед в конце игры
    with db.get_cursor() as cursor:
        cursor.execute("UPDATE players SET total_games = total_games + 1 WHERE username = ?;", (username,))
        if winner:
            cursor.execute("UPDATE players SET wins = wins + 1 WHERE username = ?;", (username,))

