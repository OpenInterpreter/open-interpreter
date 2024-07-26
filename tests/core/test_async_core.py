import os
from unittest import TestCase, mock

from interpreter.core.async_core import Server, AsyncInterpreter


class TestServerConstruction(TestCase):
    def test_host_and_port_from_env_1(self):
        fake_host = "fake_host"
        fake_port = 1234

        with mock.patch.dict(os.environ, {"HOST": fake_host, "PORT": str(fake_port)}):
            s = Server(AsyncInterpreter())
            self.assertEqual(s.host, fake_host)
            self.assertEqual(s.port, fake_port)

    def test_host_and_port_from_env_2(self):
        fake_host = "some-other-fake-host"
        fake_port = 4321

        with mock.patch.dict(os.environ, {"HOST": fake_host, "PORT": str(fake_port)}):
            s = Server(AsyncInterpreter())
            self.assertEqual(s.host, fake_host)
            self.assertEqual(s.port, fake_port)
