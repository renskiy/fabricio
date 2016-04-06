import unittest

from fabricio.docker.app.django import Django
from fabricio.docker.container import DockerContainer


class Api(Django, DockerContainer):
    pass


class TestCase(unittest.TestCase):

    def test(self):
        Api()
