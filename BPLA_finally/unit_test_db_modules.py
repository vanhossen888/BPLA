import sqlite3
import unittest
from db_modules import Drone, SQLiteDroneMapper
from unittest.mock import MagicMock, patch


class TestDrone(unittest.TestCase):
    def test_str_method(self):
        drone = Drone(id=1, serial_number="SN123", model="ModelX", manufacturer="ManufacturerY", n_rotors=4)
        self.assertEqual(str(drone), "ID: 1,Серийный номер: SN123, Модель: ModelX, Производитель: ManufacturerY, Кол-во моторов: 4")

    def test_equality(self):
        drone1 = Drone(id=1, serial_number="SN123", model="ModelX")
        drone2 = Drone(id=2, serial_number="SN123", model="ModelX")
        drone3 = Drone(id=3, serial_number="SN456", model="ModelY")
        self.assertTrue(drone1 == drone2)
        self.assertFalse(drone1 == drone3)

    def test_hash(self):
        drone1 = Drone(id=1, serial_number="SN123", model="ModelX")
        drone2 = Drone(id=2, serial_number="SN123", model="ModelX")
        drone3 = Drone(id=3, serial_number="SN456", model="ModelY")
        self.assertEqual(hash(drone1), hash(drone2))
        self.assertNotEqual(hash(drone1), hash(drone3))


class TestSQLiteDroneMapper(unittest.TestCase):
    def setUp(self):
        # Создаем мок соединения SQLite
        self.mock_conn = MagicMock(spec=sqlite3.Connection)
        self.mapper = SQLiteDroneMapper(self.mock_conn)

    def test_get_new_drone_id(self):
        # Настраиваем mock для возврата последнего ID
        self.mock_conn.cursor.return_value.fetchone.return_value = (5,)
        new_id = self.mapper.get_new_drone_id()
        self.assertEqual(new_id, 6)

    def test_add_drone(self):
        drone = Drone(id=1, serial_number="SN123", model="ModelX", manufacturer="ManufacturerY", n_rotors=4)
        # Настраиваем mock для выполнения запроса
        self.mock_conn.cursor.return_value.lastrowid = 1  # Эмулируем id последней вставленной записи
        self.mapper.add_drone(drone)
        # Проверяем, что метод execute был вызван
        self.mock_conn.cursor.return_value.execute.assert_called_once()
        self.assertEqual(drone.id, 1)  # Проверяем, что id дрона установлен правильно

    def test_get_drone(self):
        drone_id = 1
        mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (
        1, "SN123", "ModelX", "ManufacturerY", 100, 20, 30, 40, 5, 5000, 4, "2023-01-01", 2023)
        result = self.mapper.get_drone(drone_id)
        # Проверка, что метод execute был вызван
        mock_cursor.execute.assert_called_once()
        # Проверка, что результат соответствует ожидаемому
        self.assertEqual(result,
                         (1, "SN123", "ModelX", "ManufacturerY", 100, 20, 30, 40, 5, 5000, 4, "2023-01-01", 2023))

    def test_update_drone(self):
        drone_id = 1
        updates = {'model': 'ModelY', 'max_speed': 25}
        mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value = mock_cursor
        self.mapper.update_drone(drone_id, **updates)
        mock_cursor.execute.assert_called_once()

    def test_remove_drone(self):
        drone_id = 1
        mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value = mock_cursor
        self.mapper.remove_drone(drone_id)
        mock_cursor.execute.assert_called_once()


if __name__ == '__main__':
    unittest.main()
