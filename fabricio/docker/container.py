import json
import warnings

from fabric import api as fab

from fabricio import Options
from fabricio.docker import Image


class Container(object):

    image = None

    cmd = ''

    COMMAND_INFO = 'docker inspect --type container {container}'
    COMMAND_DELETE = 'docker rm {container}'
    COMMAND_FORCE_DELETE = 'docker rm --force {container}'
    COMMAND_RUN = 'docker run {options} {image} {cmd}'
    COMMAND_EXECUTE = 'docker exec --tty {container} {cmd}'
    COMMAND_START = 'docker start {container}'
    COMMAND_STOP = 'docker stop --time {timeout} {container}'
    COMMAND_RESTART = 'docker restart --time {timeout} {container}'
    COMMAND_RENAME = 'docker rename {container} {new_name}'
    COMMAND_SIGNAL = 'docker kill --signal {signal} {container}'

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
        self.image = Image(image or self.image, container=self)
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
        options = {
            'name': self.name,
            'detach': not self.temporary,
            'rm': self.temporary,
            'tty': self.temporary,
            'publish': self.ports,
            'restart': self.restart_policy,
            'user': self.user,
            'env': self.env,
            'volume': self.volumes,
            'link': self.links,
            'add-host': self.hosts,
            'net': self.network,
            'stop-signal': self.stop_signal,
        }
        return Options(self.additional_options, **options)

    def fork(
        self,
        image=None,
        name=None,
        cmd=None,
        temporary=False,
        options=None,
    ):
        return type(self)(
            image=image,
            container=name,
            cmd=self.cmd if cmd is None else cmd,
            temporary=temporary,
            options=dict(self.options, **options or {}),
        )

    @property
    def info(self):
        info = fab.sudo(self.COMMAND_INFO.format(container=self.name)).stdout
        return json.loads(info)[0]

    def delete(self, force=False, delete_image=False):
        if delete_image:
            self.image.delete(force_container_delete=force)
        else:
            command = force and self.COMMAND_FORCE_DELETE or self.COMMAND_DELETE
            fab.sudo(command.format(container=self.name))

    def _run(self, cmd=None):
        return fab.sudo(self.COMMAND_RUN.format(
            image=self.image,
            cmd=self.cmd if cmd is None else cmd,
            options=self.options,
        ))

    def run(self):
        self._run()

    def execute(self, cmd):
        if self.temporary:
            return self._run(cmd)
        return fab.sudo(self.COMMAND_EXECUTE.format(
            container=self.name,
            cmd=cmd,
        ))

    def start(self):
        fab.sudo(self.COMMAND_START.format(container=self.name))

    def stop(self, timeout=10):
        fab.sudo(self.COMMAND_STOP.format(
            container=self.name,
            timeout=timeout,
        ))

    def restart(self, timeout=10):
        fab.sudo(self.COMMAND_RESTART.format(
            container=self.name,
            timeout=timeout,
        ))

    def rename(self, new_name):
        fab.sudo(self.COMMAND_RENAME.format(
            container=self.name,
            new_name=new_name,
        ))
        self.name = new_name

    def signal(self, signal):
        fab.sudo(self.COMMAND_SIGNAL.format(
            container=self.name,
            signal=signal,
        ))

    def update(self, force=False, tag=None):
        tag = tag or self.image.tag
        if not force and self.image[tag].id == self.image.id:
            # TODO make special log method
            fab.puts('No image change detected. Upgrade skipped.')
            return
        old_backup_container = self.get_backup_container()
        old_backup_container.delete(delete_image=True)
        new_container = self.fork(name=self.name)
        self.rename(self.backup_container_name)
        self.stop()
        new_container.run()

    def revert(self):
        # TODO delete failed image
        backup_container = self.get_backup_container()
        self.delete(force=True)
        backup_container.start()
        backup_container.rename(self.name)

    @property
    def backup_container_name(self):
        if not self.name:
            raise ValueError  # TODO error message
        return self.name + '_fallback'

    def get_backup_container(self):
        return self.fork(name=self.backup_container_name)
