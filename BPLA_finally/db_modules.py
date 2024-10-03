from abc import ABC, abstractmethod
import logging
import sqlite3


class Drone:
    """Модель домена дрона"""
    tbl_drones_cols = [
        "id",
        "serial_number",
        "model",
        "manufacturer",
        "max_altitude",
        "max_speed",
        "max_flight_time",
        "max_flight_dist",
        "payload",
        "battery_capacity",
        "n_rotors",
        "purchase_date",
        "year"]
    tbl_status_mgn = [
        "id",
        "status_mgn"]

    def __init__(self, id, serial_number=None,
                       max_altitude=None,
                       max_speed=None,
                       max_flight_time=None,
                       max_flight_dist=None,
                       payload=None,
                       model=None,
                       manufacturer=None,
                       battery_capacity=None,
                       n_rotors=None,
                       purchase_date=None,
                       year=None
                 ):
        self.id = id
        self.serial_number = serial_number
        self.model = model
        self.manufacturer = manufacturer
        self.max_altitude = max_altitude
        self.max_speed = max_speed
        self.max_flight_time = max_flight_time
        self.max_flight_dist = max_flight_dist
        self.payload = payload
        self.battery_capacity = battery_capacity
        self.n_rotors = n_rotors
        self.purchase_date = purchase_date
        self.year = year

    def __str__(self):
        return (
                f"ID: {self.id},"
                f"Серийный номер: {self.serial_number}, "
                f"Модель: {self.model}, "
                f"Производитель: {self.manufacturer}, "
                f"Кол-во моторов: {self.n_rotors}"
                )

    def __hash__(self):
        return hash((self.serial_number, self.model))

    def __eq__(self, other):
        if isinstance(other, Drone):
            return (self.serial_number == other.serial_number and
                    self.model == other.model)
        return False


class IDroneMapper(ABC):
    """Интерфейс преобразователя данных между моделью и БД."""
    def __init__(self, conn):
        self.conn = conn

    @abstractmethod
    def add_drone(self, drone: Drone):
        pass

    @abstractmethod
    def get_drone(self, drone: Drone):
        pass


class SQLiteDroneMapper(IDroneMapper):
    """Преобразователь данных между моделью и БД SQLite"""

    def get_new_drone_id(self):
        query_builder = QueryBuilder()
        query = query_builder.select_last_drone_id()
        cursor = self.conn.cursor()
        cursor.execute(query)
        self.conn.commit()
        id = cursor.fetchone()[0] + 1
        return id

    def add_drone(self, drone: Drone):
        """Метод для добавления данных в БД."""
        query_builder = QueryBuilder()
        query = query_builder.insert_into("tbl_drones", Drone.tbl_drones_cols).values(
                    drone.id,
                            drone.serial_number,
                            drone.model,
                            drone.manufacturer,
                            drone.max_altitude,
                            drone.max_speed,
                            drone.max_flight_time,
                            drone.max_flight_dist,
                            drone.payload,
                            drone.battery_capacity,
                            drone.n_rotors,
                            drone.purchase_date,
                            drone.year
                        ).build()
        cursor = self.conn.cursor()
        try:
            cursor.execute(query, query_builder.get_params())
        except sqlite3.IntegrityError as error:
            logging.error(f"Ошибка при добавлении дрона в БД. {error}")
        self.conn.commit()
        drone.id = cursor.lastrowid

    def get_drone(self, drone_id: int):
        """Метод для извлечения данных дрона из БД."""
        query_builder = QueryBuilder()
        query = query_builder.select("tbl_drones", "id", ",".join(Drone.tbl_drones_cols)).where(
                                  "id=?", (drone_id,)).build()
        cursor = self.conn.cursor()
        cursor.execute(query, query_builder.get_params())
        return cursor.fetchone()

    def get_drone_status_mgn(self, drone_id: int):
        """Метод извлечения состояния управления дрона (lock или release)"""
        query_builder = QueryBuilder()
        query = query_builder.select("tbl_drones_mgn", 'id', 'status_mgn').where(
                                     "id=?", (drone_id,)).build()
        cursor = self.conn.cursor()
        cursor.execute(query, query_builder.get_params())
        return cursor.fetchone()[0]

    def update_drone(self, drone_id: int, **kwargs):
        """Метод для изменения данных в БД."""
        query_builder = QueryBuilder()
        query = query_builder.update("tbl_drones", **kwargs).where(
                                  "id=?", (drone_id,)).build()
        cursor = self.conn.cursor()
        cursor.execute(query, query_builder.get_params())
        self.conn.commit()

    def update_drone_status_mgn(self, drone_id: int, status: str):
        """Метод для изменения статуса управления дроном (lock или release)"""
        status_dict = dict(zip(Drone.tbl_status_mgn, (drone_id, status)))
        query_builder = QueryBuilder()
        query = query_builder.update("tbl_drones_mgn", **status_dict).where(
                                     "id=?", (drone_id,)).build()
        cursor = self.conn.cursor()
        cursor.execute(query, query_builder.get_params())
        self.conn.commit()

    def remove_drone(self, drone_id: int):
        """Метод для удаления данных из БД."""
        query_builder = QueryBuilder()
        query = query_builder.delete("tbl_drones").where(
                                  "id=?", (drone_id,)).build()
        cursor = self.conn.cursor()
        cursor.execute(query, query_builder.get_params())
        self.conn.commit()

    def get_drones(self, order_by: str):
        """Метод для извлечения данных всех дронов из БД."""
        query_builder = QueryBuilder()
        query = query_builder.select("tbl_drones", order_by, ",".join(Drone.tbl_drones_cols)).build()
        cursor = self.conn.cursor()
        cursor.execute(query, query_builder.get_params())
        return cursor.fetchall()


class DBFactory(ABC):
    """Интерфейс фабрики для работы с базами данных."""
    @abstractmethod
    def connect(self, path_to_db: str):
        pass


class SQLiteDBFactory(DBFactory):
    """Реализация фабрики для подключения к SQLite"""
    def connect(self, path_to_db: str):
        logging.info('Работаем с БД SQLite')
        try:
            # Подключение к базе данных
            conn = sqlite3.connect(path_to_db)
            logging.info(f"Подключение к БД установлено")
            return conn
        except sqlite3.Error as e:
            # Обработка ошибки подключения
            logging.warning(f"Ошибка подключения: {e}")
            return None


class PostgreSQLDBFactory(DBFactory):
    """Реализация фабрики для подключения к PostgreSQL"""
    def connect(self, path_to_db: str):
        logging.info('Работаем с БД PostgreSQL')
        logging.info(f"Подключение к БД установлено")
        return True


class IDroneRepository(ABC):
    """Интерфейс доступа к данным БД"""
    def __init__(self, conn):
        self.mapper = SQLiteDroneMapper(conn)

    @abstractmethod
    def add_drone(self, drone: Drone):
        pass

    @abstractmethod
    def remove_drone(self, drone_id: int):
        pass

    @abstractmethod
    def get_drone(self, drone_id: int):
        pass

    @abstractmethod
    def get_drones(self, order_by: str):
        pass

    @abstractmethod
    def update_drone(self, drone_id: int, **kwargs):
        pass


class SQLiteIDroneRepository(IDroneRepository):
    """Реализация доступа к данным БД."""

    def get_drone_id(self):
        return self.mapper.get_new_drone_id()

    def add_drone(self, drone: Drone):
        """Добавление дрона."""
        self.mapper.add_drone(drone)

    def remove_drone(self, drone_id: int):
        """Удаление дрона."""
        logging.info(f'Удаляем дрон с ID: {drone_id}.')
        self.mapper.remove_drone(drone_id)

    def get_drone(self, drone_id: int):
        """Извлечение данных дрона."""
        drone_values = self.mapper.get_drone(drone_id)
        if drone_values:
            drone_dict = dict(zip(Drone.tbl_drones_cols, drone_values))
            return Drone(**drone_dict)
        logging.warning(f'В таблице tbl_drones нет дрона с id = {drone_id}')
        return None

    def get_drone_status_mgn(self, drone_id: int):
        """Извлечение статуса управления дроном (lock или release)"""
        value = self.mapper.get_drone_status_mgn(drone_id)
        if value:
            return value
        logging.warning(f'В таблице tbl_drones_mgn нет данных о статусе управления дроном c id = {drone_id}')

    def get_drones(self, order_by: str):
        """Извлечение данных всех дронов."""
        drones = []
        list_drones_values = self.mapper.get_drones(order_by)
        for drone_values in list_drones_values:
            drone_dict = dict(zip(Drone.tbl_drones_cols, drone_values))
            drone_dict_del_id = drone_dict.copy()
            drone_dict_del_id.pop('id')
            drones.append(Drone(**drone_dict_del_id))
        return drones

    def get_drones_with_id(self, order_by: str):
        """Извлечение данных всех дронов."""
        drones = []
        list_drones_values = self.mapper.get_drones(order_by)
        for drone_values in list_drones_values:
            drone_dict = dict(zip(Drone.tbl_drones_cols, drone_values))
            drones.append(Drone(**drone_dict))
        return drones

    def update_drone(self, drone_id: int, **kwargs):
        """Изменение данных дрона"""
        logging.info(f"Обновляем данные дрона c ID = {drone_id}")
        self.mapper.update_drone(drone_id, **kwargs)

    def update_drone_status_mgn(self, drone_id: int, status: str):
        """Изменение данных состояния упарвления дроном (lock или release)"""
        logging.info(f"Обновляем состояние управления дрона c ID = {drone_id}")
        self.mapper.update_drone_status_mgn(drone_id, status)


class QueryBuilder:
    """Конструктор SQL-запросов SELECT, INSERT, UPDATE, DELETE"""
    def __init__(self):
        """Инициализация словаря для хранения частей запроса и списка параметров"""
        self.__query_parts = {}
        self.__params = []

    def select_last_drone_id(self):
        query = 'SELECT id FROM tbl_drones ORDER BY id DESC LIMIT 1'
        return query

    def insert_into(self, table: str, columns: list):
        """Метод для создания части запроса для добавления данных в БД - INSERT INTO.
        Пример: "INSERT INTO tbl_users (id, name) VALUES (?, ?)" """
        cols = ','.join(columns)  # ["id", "name"] -> "id,name"
        question_marks = ','.join(['?'] * len(columns))  # ["?"] * 3 = ["?", "?", "?"]
        self.__query_parts["INSERT INTO"] = f"INSERT INTO {table} ({cols}) VALUES ({question_marks})"
        return self

    def select(self, table: str, order_by, columns="*"):
        """Метод для создания части запроса на выборку данных из БД - SELECT."""
        self.__query_parts["SELECT"] = f"SELECT {columns}"
        self.__query_parts["FROM"] = f"FROM {table}"
        self.__query_parts["ORDER BY"] = f"ORDER BY {order_by}"
        return self

    def delete(self, table: str):
        """Метод для создания части запроса на удаление данных из БД - DELETE."""
        self.__query_parts["DELETE"] = f"DELETE FROM {table} "
        return self

    def update(self, table: str, **kwargs):
        """Метод для создания части запроса на изменение данных в БД - UPDATE."""
        set_clause = ', '.join(f'{key}=?' for key in kwargs.keys())
        self.__query_parts["UPDATE"] = f"UPDATE {table} SET {set_clause} "
        self.__params = list(kwargs.values())
        return self

    def values(self, *columns: list):
        """Метод для добавления значений для части запроса INSERT INTO."""
        self.__params.extend(columns)
        return self

    def get_params(self):
        """Метод для получения списка параметров для добавления к частям запросов."""
        return self.__params

    def where(self, condition: str, params=None):
        """Метод для создания фильтра выборки данных из БД - WHERE."""
        self.__query_parts["WHERE"] = f"WHERE {condition}"
        if params:
            self.__params.append(params[0])
        return self

    def build(self):
        """Метод для окончательной сборки SQL-запроса."""
        query = ""
        if "INSERT INTO" in self.__query_parts:
            query = self.__query_parts["INSERT INTO"]
        if "SELECT" in self.__query_parts:
            query = f'{self.__query_parts["SELECT"]} {self.__query_parts["FROM"]} '
        if "DELETE" in self.__query_parts:
            query = f'{self.__query_parts["DELETE"]} '
        if "UPDATE" in self.__query_parts:
            query = f'{self.__query_parts["UPDATE"]} '
        if "WHERE" in self.__query_parts:
            query += f'{self.__query_parts["WHERE"]} '
        if "ORDER BY" in self.__query_parts:
            query += self.__query_parts["ORDER BY"]
        return query


class DBConnectionManager:
    """Менеджер для управления соединениями с БД"""
    def __init__(self, db_factory, path_to_db):
        self.__db_factory = db_factory
        self.__path_to_db = path_to_db
        self.__connection = None

    def __enter__(self):
        self.__connection = self.__db_factory.connect(self.__path_to_db)
        return self.__connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.__connection:
            self.__connection.close()
            logging.info("Соединение с БД закрыто.")
