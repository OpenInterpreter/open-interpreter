import unittest
from interpreter.core.computer.terminal.languages.shell import Shell

class TestShell(unittest.TestCase):
    def setUp(self):
        self.shell = Shell()

    def tearDown(self):
        self.shell.terminate()

    def test_run(self):
        for chunk in self.shell.run("echo 'Hello World'"):
            if chunk["format"] == "active_line" or chunk["content"] == "\n":
                pass
            elif chunk["format"] == "output":
                self.assertEqual('Hello World\n', chunk["content"])
            else:
                self.fail('Wrong chunk format')

    def test_run_hang(self):
        for chunk in self.shell.run("echo World'"):
            if chunk["format"] == "active_line" or chunk["content"] == "\n":
                pass
            elif "error" in chunk:
                self.assertEqual("Maximum retries reached. Code is hang.", chunk["content"])
            elif chunk["format"] == "output":
                self.assertIn('unmatched', chunk["content"])
            else:
                self.fail('Wrong chunk format')

if __name__ == "__main__":
    testing = TestShell()
    testing.setUp()
    testing.test_run()
    testing.tearDown()
    testing.setUp()
    testing.test_run_hang()
    testing.tearDown()
