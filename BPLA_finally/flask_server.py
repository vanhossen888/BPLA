import asyncio
import datetime
import jwt
import logging
import numpy as np
import time
from db_modules import Drone, DBConnectionManager, SQLiteDBFactory, SQLiteIDroneRepository
from flask import Flask, request, redirect, url_for, render_template, flash, session, jsonify
from flask_socketio import SocketIO, emit
from functools import wraps

# Логирование для вывода информации и ошибок
logging.basicConfig(
    handlers=[
        logging.FileHandler(filename='server.log', encoding='utf-8', mode='a+')
    ],
    format='%(asctime)s - %(levelname)s - %(funcName)s: %(message)s',
    level=logging.DEBUG)

app = Flask(__name__)
socketio = SocketIO(app)
factory = SQLiteDBFactory()


def log_execution_time(func):
    """Декоратор для логирования времени выполнения функции"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        result = await func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        logging.info(
            f'Функция {func.__name__} выполнена за {execution_time:.4f} секунд.'
        )
        return result

    return wrapper


def get_secret_key():
    """Функция для получения SECRET_KEY из базы данных"""
    try:
        with DBConnectionManager(factory, path_to_db='prod.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key FROM tbl_secret")
            logging.warning('Получен SECRET_KEY!')
            return cursor.fetchone()[0]
    except Exception as e:
        logging.error(f'SECRET_KEY не получен! Проверьте БД! {str(e)}')


# Установка SECRET_KEY в приложении.
app.secret_key = get_secret_key()


def generate_token(username):
    """Создаем JWT-токен для указанного имени пользователя, со сроком годности 60 мин."""
    payload = {
        'username': username,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=60)
    }
    token = jwt.encode(payload, app.secret_key, algorithm='HS256')
    logging.info(f'Сгенерирован токен для пользователя: {username}.')
    return token


def verify_token(token):
    """Проверяем действительность токена."""
    try:
        payload = jwt.decode(token, app.secret_key, algorithms=['HS256'])
        return payload['username']
    except jwt.ExpiredSignatureError:
        logging.error('Токен истек')
        return None  # Токен истек
    except jwt.InvalidTokenError as e:
        logging.error(f'Невалидный токен: {str(e)}')
        return None  # Невалидный токен


def check_session_token(token):
    if not token:
        logging.warning(
            'Токен отсутствует, перенаправление на страницу логаута')
        return redirect(
            url_for('logout'))  # Перенаправление на страницу логаута
    username = verify_token(token)
    if not username:
        logging.warning(
            'Недействительный токен, перенаправление на страницу логаута')
        return redirect(
            url_for('logout'))  # Перенаправление на страницу логаута
    return username  # Вернуть имя пользователя, если токен действителен


@socketio.on('get_drone_status')
@log_execution_time
async def get_drone_status(data):
    """Асинхронная функция для получения статуса дронов."""
    drone_id = data['drone_id']
    try:
        status_mgn = await asyncio.to_thread(get_drone_status_mgn, drone_id)
        emit('drone_status_response', {
            'drone_id': drone_id,
            'status': status_mgn
        })
    except Exception as e:
        logging.error(
            f'Ошибка получения статуса дрона ID: {drone_id}. {str(e)}')
        emit('error', {'message': str(e)})


async def get_drone_status_mgn(drone_id: int):
    """Функция для получения статуса управления дроном (lock или release)"""
    try:
        with DBConnectionManager(factory, path_to_db='prod.db') as conn:
            drone_repository = SQLiteIDroneRepository(conn)
            status_mgn = await asyncio.to_thread(
                drone_repository.get_drone_status_mgn, drone_id)
            logging.info(
                f'Получен статус управления дроном ID: {drone_id} - {status_mgn}.'
            )
            return status_mgn
    except Exception as e:
        logging.error(
            f'Не получен статус управления дроном ID: {drone_id}! {str(e)}')


async def set_drone_status_mgn(drone_id, status: str):
    """Асинхронная функция для изменения текущего статуса управления дроном (lock)"""
    try:
        with DBConnectionManager(factory, path_to_db='prod.db') as conn:
            drone_repository = SQLiteIDroneRepository(conn)
            await asyncio.to_thread(drone_repository.update_drone_status_mgn,
                                    drone_id, status)
            logging.warning(
                f'Изменен статус управления дроном ID: {drone_id} - LOCK')
            await asyncio.to_thread(conn.commit)
    except Exception as e:
        logging.error(
            f'Не изменен статус управления дроном ID: {drone_id}! {str(e)}')


async def check_drone_status_mgn(drone_id):
    status_mgn = await get_drone_status_mgn(drone_id)
    if status_mgn == 'release':
        return status_mgn


@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
async def login():
    if request.method == 'POST':
        login = request.form['login']
        password = request.form['password']
        with DBConnectionManager(factory, path_to_db='prod.db') as conn:
            cursor = conn.cursor()
            await asyncio.to_thread(
                cursor.execute,
                "SELECT * FROM tbl_users WHERE login = ? AND password = ?",
                (login, password))
            user = await asyncio.to_thread(cursor.fetchone)
            if user:
                session['token'] = generate_token(login)
                response = redirect(url_for('list_drones'))
                logging.warning(f'Пользователь {login} авторизован в системе!')
                return response
            else:
                flash('Неправильный логин или пароль', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('token', None)
    logging.warning(f'Пользователь вышел из системы!')
    return redirect(url_for('login'))


@app.route('/drones', methods=['GET'])
@log_execution_time
async def list_drones():
    token = session.get('token')
    result = check_session_token(token)

    if isinstance(result, str):
        with DBConnectionManager(factory, path_to_db='prod.db') as conn:
            drone_repository = SQLiteIDroneRepository(conn)
            drones = await asyncio.to_thread(
                drone_repository.get_drones_with_id, order_by='id')
            return render_template('list_drones.html', drones=drones)
    return result


@app.route('/drones/add', methods=['GET', 'POST'])
@log_execution_time
async def add_drone():
    token = session.get('token')
    result = check_session_token(token)

    if isinstance(result, str):
        with DBConnectionManager(factory, path_to_db='prod.db') as conn:
            drone_repository = SQLiteIDroneRepository(conn)
            if request.method == 'POST':
                try:
                    drone_id = {
                        'id':
                        await asyncio.to_thread(drone_repository.get_drone_id)
                    }
                    drone_data_without_id = {
                        key: request.form[key]
                        for key in request.form
                    }
                    drone_data = {**drone_id, **drone_data_without_id}
                    drone = Drone(**drone_data)
                    await asyncio.to_thread(drone_repository.add_drone, drone)
                    logging.info(f'В систему добавлен дрон с ID: {drone_id}')
                    return redirect(url_for('list_drones'))
                except Exception as e:
                    logging.error(
                        f'Произошла ошибка при добавлении дрона: {str(e)}')
            return render_template('add_drone.html')
    return result


@app.route('/drones/update/<int:drone_id>', methods=['GET', 'POST'])
@log_execution_time
async def update_drone(drone_id):
    token = session.get('token')
    result = check_session_token(token)

    if isinstance(result, str):
        with DBConnectionManager(factory, path_to_db='prod.db') as conn:
            drone_repository = SQLiteIDroneRepository(conn)
            try:
                if request.method == 'POST':
                    drone_data = {
                        key: request.form[key]
                        for key in request.form
                    }
                    drone_repository.update_drone(drone_id, **drone_data)
                    logging.warning(
                        f'В системе обновлен дрон с ID: {drone_id}')
                    return redirect(url_for('list_drones'))

                drone = drone_repository.get_drone(drone_id)
                return render_template('update.html', drone=drone)
            except Exception as e:
                logging.error(
                    f'Произошла ошибка при обновлении дрона: {str(e)}')

    return result


@app.route('/drones/delete/<int:drone_id>', methods=['POST'])
@log_execution_time
async def delete_drone(drone_id):
    token = session.get('token')
    result = check_session_token(token)

    if isinstance(result, str):
        with DBConnectionManager(factory, path_to_db='prod.db') as conn:
            drone_repository = SQLiteIDroneRepository(conn)
            drone_repository.remove_drone(drone_id)
            logging.warning(f'Из системы удален дрон с ID: {drone_id}')
            return redirect(url_for('list_drones'))

    return result


@app.route('/drones/control/<int:drone_id>', methods=['POST'])
async def control_drone(drone_id):
    token = session.get('token')
    result = check_session_token(token)

    if await check_drone_status_mgn(drone_id) == 'release':
        await set_drone_status_mgn(drone_id, 'lock')

        if isinstance(result, str):
            return render_template('control_drone.html',
                                   token=token,
                                   drone_id=drone_id)
        return result
    else:
        return jsonify({
            "error":
            f'Доступ к управлению заблокирован! Дроном ID: {drone_id} управляет другой оператор.'
        }), 403


@app.route('/drones/release/<int:drone_id>', methods=['GET', 'POST'])
async def drone_release(drone_id):
    """Функция для выхода из формы управления дроном"""
    await set_drone_status_mgn(drone_id, 'release')
    return redirect(url_for('list_drones', drone_id=drone_id))


# Задаем начальные параметры
center_latitude = np.random.uniform(-90, 90)  # Широта центра
center_longitude = np.random.uniform(-180, 180)  # Долгота центра
battery_level = 100.0  # Начальный уровень заряда
log_data = []  # Хранение логов
telemetry_data = {}  # Переменная для хранения данных телеметрии


def generate_telemetry():
    """Генератор случайной телеметрии."""
    global battery_level, log_data, telemetry_data

    # Генерация случайного радиуса в пределах 1000 метров
    radius = 1000  # Радиус в метрах
    distance = np.random.uniform(-radius, radius)

    # Преобразование расстояния в координаты
    delta_latitude = distance / 111320  # 1 градус широты ~ 111.32 км
    delta_longitude = distance / (111320 * np.cos(np.radians(center_latitude))
                                  )  # Корректируем по широте

    # Генерация новых координат
    current_latitude = center_latitude + delta_latitude * np.random.choice(
        [-1, 1])
    current_longitude = center_longitude + delta_longitude * np.random.choice(
        [-1, 1])

    # Генерация других параметров
    speed = np.random.uniform(0, 5.56)  # Скорость до 20 км/ч (5.56 м/с)
    direction = np.random.randint(0, 361)  # Направление
    altitude = np.random.uniform(0, 500)  # Высота до 500 метров
    flight_time = np.random.randint(0, 3601)  # Время полета (в секундах)

    # Уменьшаем уровень заряда со временем
    battery_level -= (speed * flight_time / 3600) * (
        100 / 20)  # Пропорционально скорости и времени
    battery_level = max(battery_level,
                        0)  # Уровень заряда не может быть меньше 0%

    telemetry_data["telemetry"] = (
        f"Координаты: ({current_latitude:.6f}, {current_longitude:.6f})\n"
        f"Скорость: {speed:.2f} м/с\n"
        f"Направление: {direction}°\n"
        f"Высота: {altitude:.2f} м\n"
        f"Время полета: {flight_time} с\n"
        f"Уровень заряда: {battery_level:.2f} %")

    log_message = f"{time.strftime('%H:%M:%S')} - Телеметрия обновлена: {telemetry_data['telemetry']}"
    log_data.append(log_message)


@socketio.on('request_telemetry')
async def handle_request_telemetry():
    """Обработчик для запроса телеметрии."""
    generate_telemetry()
    emit('telemetry_update', {
        "telemetry": telemetry_data["telemetry"],
        "log": "\n".join(log_data)
    })


if __name__ == '__main__':
    socketio.run(app, debug=True, host='127.0.0.1')
