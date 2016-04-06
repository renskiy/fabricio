import six

from fabric import api as fab


class Container(object):

    image = NotImplemented

    cmd = ''

    user = None

    ports = []

    env = []

    volumes = []

    links = []

    hosts = []

    network = None

    restart_policy = None

    stop_signal = None
    
    class Commands:

        RUN = NotImplemented
    
        EXECUTE = NotImplemented
    
        START = NotImplemented
    
        STOP = NotImplemented
    
        DELETE = NotImplemented
    
        RENAME = NotImplemented
    
        INFO = NotImplemented
    
        SIGNAL = NotImplemented

    FALLBACK_CONTAINER_NAME_SUFFIX = '_fallback'

    def __init__(self, name=None, temporary=False, options=None):
        self.name = name
        self.temporary = temporary
        if temporary:
            self.ports = []
            self.restart_policy = None
        self.options = options or {}

    @property
    def _options(self):
        for option, value in self.options.items():
            if value is None:
                continue
            if isinstance(value, bool):
                if value is True:
                    yield self.make_option(option)
            elif isinstance(value, six.string_types):
                yield self.make_option(option, value)
            else:
                for single_value in value:
                    yield self.make_option(option, single_value)

    @staticmethod
    def make_option(option, value=None):
        option = '--' + option
        if value is not None:
            # TODO escape value
            option += ' ' + value
        return option

    def make_options(self):
        return ' '.join(self._options)

    def fork(self, name=None, temporary=False, options=None):
        forked = type(self)(name=name, temporary=temporary, options=options)
        for option, value in self.options.items():
            forked.options.setdefault(option, value)
        return forked

    def _run(self, cmd=None):
        return fab.sudo(self.Commands.RUN.format(
            image=self.image,
            name=self.name,
            cmd=self.cmd if cmd is None else cmd,
            options=self.make_options(),
        ))

    def run(self):
        self._run()

    def execute(self, cmd):
        if self.temporary:
            return self._run(cmd)
        return fab.sudo(self.Commands.EXECUTE.format(
            name=self.name,
            cmd=cmd,
        ))

    def start(self):
        fab.sudo(self.Commands.START.format(
            name=self.name,
        ))

    def stop(self, timeout=10):
        fab.sudo(self.Commands.STOP.format(
            name=self.name,
            timeout=timeout,
        ))

    def delete(self):
        fab.sudo(self.Commands.DELETE.format(
            name=self.name,
        ))

    def rename(self, new_name):
        fab.sudo(self.Commands.RENAME.format(
            name=self.name,
            new_name=new_name,
        ))
        self.name = new_name

    def info(self, template='""'):
        # TODO template should be empty string by default
        return fab.sudo(self.Commands.INFO.format(
            name=self.name,
            template=template,
        ))

    def signal(self, signal):
        fab.sudo(self.Commands.SIGNAL.format(
            name=self.name,
            signal=signal,
        ))

    def upgrade(self):
        new_container = self.fork(
            name=self.name,
        )
        self.rename(self.name + self.FALLBACK_CONTAINER_NAME_SUFFIX)
        self.stop()
        new_container.run()

    def fallback(self):
        fallback_container = self.fork(
            name=self.name + self.FALLBACK_CONTAINER_NAME_SUFFIX,
        )
        self.stop()
        self.delete()
        fallback_container.rename(self.name)
        fallback_container.start()

from .docker import *
