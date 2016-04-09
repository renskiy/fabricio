import unittest

from fabricio.docker.apps.python.django import Django
from fabricio.docker.containers import DockerContainer


class Api(Django, DockerContainer):
    pass


class TestCase(unittest.TestCase):

    def test(self):
        Api()
