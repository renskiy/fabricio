import warnings

from fabric import api as fab

from fabricio import Options


class Container(object):

    image = None

    cmd = ''

    class Commands:
        RUN = NotImplemented
        EXECUTE = NotImplemented
        START = NotImplemented
        STOP = NotImplemented
        RESTART = NotImplemented
        DELETE = NotImplemented
        FORCE_DELETE = NotImplemented
        RENAME = NotImplemented
        INFO = NotImplemented
        SIGNAL = NotImplemented

    def __init__(
        self,
        image=None,
        name=None,
        cmd=None,
        temporary=False,
        user=None,
        ports=None,
        env=None,
        volumes=None,
        links=None,
        hosts=None,
        network=None,
        restart_policy=None,
        stop_signal=None,
        options=None,
    ):
        if temporary:
            if ports or restart_policy:
                warnings.warn('Provided ports and/or restart_policy were '
                              'ignored because of temporary flag was set')
            self.ports = []
            self.restart_policy = None
        else:
            self.restart_policy = restart_policy
            self.ports = ports or []
        self.image = image or self.image
        self.name = name or self.random_name
        self.cmd = self.cmd if cmd is None else cmd
        self.temporary = temporary
        self.user = user
        self.env = env or []
        self.volumes = volumes or []
        self.links = links or []
        self.hosts = hosts or []
        self.network = network
        self.stop_signal = stop_signal
        self.additional_options = options or {}

    @property
    def options(self):
        return Options(self.additional_options)

    @property
    def image_id(self):
        raise NotImplementedError

    @property
    def random_name(self):
        raise NotImplementedError

    def fork(
        self,
        image=None,
        name=None,
        cmd=None,
        temporary=False,
        options=None,
    ):
        return type(self)(
            image=image or self.image,
            name=name,
            cmd=self.cmd if cmd is None else cmd,
            temporary=temporary,
            options=dict(self.options, **options or {}),
        )

    def _run(self, cmd=None):
        return fab.sudo(self.Commands.RUN.format(
            image=self.image,
            name=self.name,
            cmd=self.cmd if cmd is None else cmd,
            options=self.options,
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

    def restart(self, timeout=10):
        fab.sudo(self.Commands.RESTART.format(
            name=self.name,
            timeout=timeout,
        ))

    def delete(self, force=False):
        command = self.Commands.FORCE_DELETE if force else self.Commands.DELETE
        fab.sudo(command.format(
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

    def upgrade(self, force=False):
        # TODO upgrade only if necessary
        # TODO delete obsolete image
        # TODO implement force=True
        new_container = self.fork(name=self.name)
        self.rename(self.fallback_container_name)
        self.stop()
        new_container.run()

    def fallback(self):
        # TODO delete failed image
        fallback_container = self.fallback_container
        self.delete(force=True)
        fallback_container.start()
        fallback_container.rename(self.name)

    @property
    def fallback_container_name(self):
        if not self.name:
            raise ValueError  # TODO error message
        return self.name + '_fallback'

    @property
    def fallback_container(self):
        return self.fork(name=self.fallback_container_name)

from .docker import DockerContainer
from .kubernetes import KubernetesContainer
