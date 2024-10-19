import unittest
from unittest import mock
from interpreter.core.computer.computer import Computer

class TestComputer(unittest.TestCase):
    def setUp(self):
        self.computer = Computer(mock.Mock())

    def test_get_all_computer_tools_list(self):
        # Act
        tools_list = self.computer._get_all_computer_tools_list()

        # Assert
        self.assertEqual(len(tools_list), 15)

    def test_get_all_computer_tools_signature_and_description(self):
        # Act
        tools_description = self.computer._get_all_computer_tools_signature_and_description()

        # Assert
        self.assertGreater(len(tools_description), 64)

if __name__ == "__main__":
    testing = TestComputer()
    testing.setUp()
    testing.test_get_all_computer_tools_signature_and_description()