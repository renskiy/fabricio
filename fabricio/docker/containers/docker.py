from fabricio import Options
from fabricio.docker.containers import Container


class DockerContainer(Container):

    class Commands(Container.Commands):
        RUN = 'docker run {options} {image} {cmd}'
        EXECUTE = 'docker exec --tty {name} {cmd}'
        START = 'docker start {name}'
        STOP = 'docker stop --time {timeout} {name}'
        RESTART = 'docker restart --time {timeout} {name}'
        DELETE = 'docker rm {name}'
        FORCE_DELETE = 'docker rm --force {name}'
        RENAME = 'docker rename {name} {new_name}'
        INFO = 'docker inspect --type container --format {template} {name}'
        SIGNAL = 'docker kill --signal {signal} {name}'

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

    @property
    def random_name(self):
        return None
