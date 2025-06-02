import time
from database import *

# Класс для игрока
class Player:
    def __init__(self, user_id, username, position, players_start_time, global_rate):
        self.user_id = user_id
        self.username = username
        self.position = int(position)
        self.uid = int(position)
        self.game_time = 0 # личное время всех ходов игрока
        self.ready = False
        self.rate = global_rate
        self.status = "Ожидание" # Ожидание Активный Раскрылся
        self.STARTER_TIME = players_start_time # начальное время (с которого всё начинается в 1 раунде)
        self.timer = self.STARTER_TIME
        self.turn_started_time = None
        self.turn_ended_time = None
        self.active = False
        self.choosed_winner = ' ' # Игрок выбрал победителя
        self.statistics = []
        self.wins = 0 # количество побед
        self.total_games = 0 # общее количество игр
        self.rating = 0 # процент побед игрока
        
    def get_ready(self, bool=True): # Параметр готовности игрока True False
        self.ready = bool

    def update_statistics(self): # получаем статистику по игроку из базы (игры, победы, рейтинг)
        self.statistics = db_get_or_create_player(self.username, self.total_games, self.wins, self.rating)
        self.total_games, self.wins, self.rating = self.statistics[0][1],self.statistics[0][2],self.statistics[0][3]

    def change_status(self, string): 
        self.status = string

    def change_position(self, pos):
        self.position = pos
    
    def choose_winner(self, winner_name):
        self.choosed_winner = winner_name

    def increase_games_count(self, winner=False):
        db_increase_games_count(self.username, winner)

    def set_active(self, bool): #True False изменить игкрока на активного или нет, т.е. который сейчас ходит
        self.active = bool

    def start_turn_timer(self): # сохранение времени переменной начала хода
        self.turn_started_time = time.time()

    def end_turn_timer(self, round=0, round_rate=3, extra_time_restriction=5): # подсчёт остатка времени таймера после хода
        time_for_turn = int(time.time() - self.turn_started_time) # время хода игрока
        print(f'{self.username}: совершил ход за {time_for_turn}')

        # считаем остаток хода для добавления на следующий ход и умножаем на модификатор self.rate (condfig.ini)
        self.turn_ended_time = (self.timer - int(time.time() - self.turn_started_time)) * self.rate

        # проверка если остаток хода меньше 0 или ход совершён слишком быстро, то не добавляем время
        if self.turn_ended_time <= 0 or time_for_turn < extra_time_restriction:
            print(f'{self.username}: слишком быстрый ход({time_for_turn}c), дополнительное время не добавлено ')
            self.turn_ended_time = 0

        print(f'добавленное время = {self.turn_ended_time}')
        print(self.STARTER_TIME,round * round_rate,int(self.turn_ended_time))
        self.timer = self.STARTER_TIME + (round * round_rate) + int(self.turn_ended_time)
        print(f'self.timer = {self.timer}')

    def get_turn_time(self):
        self.game_time += int(time.time() - self.turn_started_time)
        print(f'общее время всех ходов игрока {self.username}: {self.game_time}')

    # обновление таймера на случай, если активный игрок перезагрузит страницу
    def update_timer(self):
        print(f"Обновление таймера {self.username}: Было:{self.timer} прошло: {int(time.time() - self.turn_started_time)} осталось: {self.timer - int(time.time() - self.turn_started_time)}")
        self.timer = self.timer - int(time.time() - self.turn_started_time)
        self.start_turn_timer()