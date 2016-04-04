from enum import Enum
from fabric import api as fab

try:
    str = unicode
except NameError:
    pass


class BaseContainer(object):

    image = NotImplemented

    cmd = ''

    name = None

    detach = True

    ports = []

    env = []

    volumes = []

    links = []

    hosts = []

    network = None

    restart_policy = None

    stop_signal = None

    class Command(Enum):

        RUN = NotImplemented

        START = NotImplemented

        STOP = NotImplemented

        DELETE = NotImplemented

        SIGNAL = NotImplemented

        RENAME = NotImplemented

        INFO = NotImplemented

    def __init__(self, *image_and_cmd, **options):
        assert len(image_and_cmd) <= 2
        image_and_cmd = image_and_cmd or (self.image, self.cmd)
        self.image = image_and_cmd[0]
        self.cmd = ''.join(image_and_cmd[1:])
        self._options = {
            option.replace('_', '-'): value
            for option, value in options.items()
        }

    @staticmethod
    def make_option(option, value=None):
        option = '--' + option
        if value is not None:
            # TODO escape value
            option += ' ' + value
        return option

    @property
    def options(self):
        for option, value in self._options.items():
            if value is None:
                continue
            if isinstance(value, bool):
                if value is True:
                    yield self.make_option(option)
            elif isinstance(value, (str, bytes)):
                yield self.make_option(option, value)
            else:
                for single_value in value:
                    yield self.make_option(option, single_value)

    def run(self):
        fab.sudo(self.Command.RUN.format(
            image=self.image,
            name=self.name,
            cmd=self.cmd,
            options=' '.join(self.options),
        ))

    def start(self):
        fab.sudo(self.Command.START.format(
            name=self.name,
        ))

    def stop(self, timeout=10):
        fab.sudo(self.Command.STOP.format(
            name=self.name,
            timeout=timeout,
        ))

    def delete(self):
        fab.sudo(self.Command.DELETE.format(
            name=self.name,
        ))

    def signal(self, signal):
        fab.sudo(self.Command.SIGNAL.format(
            name=self.name,
            signal=signal,
        ))

    def rename(self, new_name):
        fab.sudo(self.Command.RENAME.format(
            name=self.name,
            new_name=new_name,
        ))
        self.name = new_name

    def info(self, template='""'):
        # TODO template should be empty string by default
        return fab.sudo(self.Command.INFO.format(
            name=self.name,
            template=template,
        ))


class BaseTemporaryContainer(BaseContainer):

    detach = False
