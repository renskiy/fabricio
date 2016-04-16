import warnings

from fabric import api as fab

from fabricio import Options


class Container(object):

    image = None

    cmd = ''

    COMMAND_INFO = NotImplemented
    COMMAND_DELETE = NotImplemented
    COMMAND_FORCE_DELETE = NotImplemented
    COMMAND_DELETE_IMAGE = 'docker rmi {image}'
    COMMAND_RUN = NotImplemented
    COMMAND_EXECUTE = NotImplemented
    COMMAND_START = NotImplemented
    COMMAND_STOP = NotImplemented
    COMMAND_RESTART = NotImplemented
    COMMAND_RENAME = NotImplemented
    COMMAND_SIGNAL = NotImplemented

    def __init__(
        self,
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
        self.name = name
        if temporary:
            if ports or restart_policy:
                warnings.warn('Provided ports and/or restart_policy were '
                              'ignored because of temporary flag was set')
            self.ports = []
            self.restart_policy = None
        else:
            self.restart_policy = restart_policy
            self.ports = ports or []
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
    def id(self):
        return self.info('{{.Id}}').stdout

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

    def info(self, template='""'):
        # TODO template should be empty string by default
        return fab.sudo(self.COMMAND_INFO.format(
            name=self.name,
            template=template,
        ))

    def delete(self, force=False, delete_image=False):
        image_id = delete_image and self.image_id
        command = self.COMMAND_FORCE_DELETE if force else self.COMMAND_DELETE
        fab.sudo(command.format(
            name=self.name,
        ))
        if delete_image:
            fab.sudo(self.COMMAND_DELETE_IMAGE.format(
                image=image_id,
            ))

    def _run(self, cmd=None):
        return fab.sudo(self.COMMAND_RUN.format(
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
        return fab.sudo(self.COMMAND_EXECUTE.format(
            name=self.name,
            cmd=cmd,
        ))

    def start(self):
        fab.sudo(self.COMMAND_START.format(
            name=self.name,
        ))

    def stop(self, timeout=10):
        fab.sudo(self.COMMAND_STOP.format(
            name=self.name,
            timeout=timeout,
        ))

    def restart(self, timeout=10):
        fab.sudo(self.COMMAND_RESTART.format(
            name=self.name,
            timeout=timeout,
        ))

    def rename(self, new_name):
        fab.sudo(self.COMMAND_RENAME.format(
            name=self.name,
            new_name=new_name,
        ))
        self.name = new_name

    def signal(self, signal):
        fab.sudo(self.COMMAND_SIGNAL.format(
            name=self.name,
            signal=signal,
        ))

    def upgrade(self, force=False):
        new_container = self.fork(name=self.name)
        if not force and new_container.image.id == self.image_id:
            fab.puts('No image change detected. Upgrade skipped.')
            return
        obsolete_container = self.get_fallback_container()
        obsolete_container.delete(delete_image=True)
        self.rename(obsolete_container.name)
        self.stop()
        new_container.run()

    def fallback(self):
        # TODO delete failed image
        fallback_container = self.get_fallback_container()
        self.delete(force=True)
        fallback_container.start()
        fallback_container.rename(self.name)

    @property
    def fallback_container_name(self):
        if not self.name:
            raise ValueError  # TODO error message
        return self.name + '_fallback'

    def get_fallback_container(self):
        return self.fork(name=self.fallback_container_name)

###############

from .docker import DockerContainer
