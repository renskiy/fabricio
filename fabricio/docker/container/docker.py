from fabricio import Options
from fabricio.docker.container import Container


class DockerContainer(Container):

    COMMAND_INFO = 'docker inspect --type container --format {template} {name}'
    COMMAND_DELETE = 'docker rm {name}'
    COMMAND_FORCE_DELETE = 'docker rm --force {name}'
    COMMAND_RUN = 'docker run {options} {image} {cmd}'
    COMMAND_EXECUTE = 'docker exec --tty {name} {cmd}'
    COMMAND_START = 'docker start {name}'
    COMMAND_STOP = 'docker stop --time {timeout} {name}'
    COMMAND_RESTART = 'docker restart --time {timeout} {name}'
    COMMAND_RENAME = 'docker rename {name} {new_name}'
    COMMAND_SIGNAL = 'docker kill --signal {signal} {name}'

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
        return Options(super(DockerContainer, self).options, **options)

    @property
    def image_id(self):
        return self.info('{{.Image}}').stdout
