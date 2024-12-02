import unittest
from unittest import mock

from interpreter.core.computer.files.files import Files


class TestFiles(unittest.TestCase):
    def setUp(self):
        self.files = Files(mock.Mock())

    @mock.patch("interpreter.core.computer.files.files.aifs")
    def test_search(self, mock_aifs):
        # Arrange
        mock_args = ["foo", "bar"]
        mock_kwargs = {"foo": "bar"}

        # Act
        self.files.search(mock_args, mock_kwargs)

        # Assert
        mock_aifs.search.assert_called_once_with(mock_args, mock_kwargs)

    def test_edit_original_text_in_filedata(self):
        # Arrange
        mock_open = mock.mock_open(read_data="foobar")
        mock_write = mock_open.return_value.write

        # Act
        with mock.patch("interpreter.core.computer.files.files.open", mock_open):
            self.files.edit("example/filepath/file", "foobar", "foobarbaz")

        # Assert
        mock_open.assert_any_call("example/filepath/file", "r")
        mock_open.assert_any_call("example/filepath/file", "w")
        mock_write.assert_called_once_with("foobarbaz")

    def test_edit_original_text_not_in_filedata(self):
        # Arrange
        mock_open = mock.mock_open(read_data="foobar")

        # Act
        with self.assertRaises(ValueError) as context_manager:
            with mock.patch("interpreter.core.computer.files.files.open", mock_open):
                self.files.edit("example/filepath/file", "barbaz", "foobarbaz")

        # Assert
        mock_open.assert_any_call("example/filepath/file", "r")
        self.assertEqual(
            str(context_manager.exception),
            "Original text not found. Did you mean one of these? foobar",
        )
