import shutil
import unittest

from archive.classic_interpreter.core.computer.terminal.languages.php import Php


class TestPhp(unittest.TestCase):
    def setUp(self):
        if shutil.which("php") is None:
            raise unittest.SkipTest("php not installed")

        self.php = Php()

    def tearDown(self):
        self.php.terminate()

    def test_run(self):
        for chunk in self.php.run("\n<?\necho 'Hello World';\n?>\n"):
            if chunk["format"] == "active_line" or chunk["content"] == "\n":
                pass
            elif chunk["format"] == "output":
                self.assertEqual("Hello World\n", chunk["content"])
            else:
                self.fail("Wrong chunk format")

    def test_run_hang(self):
        for chunk in self.php.run("\n<?\necho World';\n?>\n"):
            if chunk["format"] == "active_line" or chunk["content"] == "\n":
                pass
            elif "error" in chunk:
                self.assertEqual(
                    "Maximum retries reached. Code is hang.", chunk["content"]
                )
            elif chunk["format"] == "output":
                self.assertEqual(
                    'Parse error: syntax error, unexpected string content ";", '
                    'expecting "," or ";" in Standard input code on line 3\n',
                    chunk["content"],
                )
            else:
                self.fail("Wrong chunk format")


if __name__ == "__main__":
    testing = TestPhp()
    testing.setUp()
    testing.test_run()
    testing.tearDown()
    testing.setUp()
    testing.test_run_hang()
    testing.tearDown()
