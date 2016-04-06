from fabricio.docker.container import Container

__all__ = [
    'DockerContainer',
]


class DockerContainer(Container):

    COMMAND_RUN = 'docker run {options} {image} {cmd}'

    COMMAND_EXECUTE = 'docker exec --tty {name} {cmd}'

    COMMAND_START = 'docker start {name}'

    COMMAND_STOP = 'docker stop --time {timeout} {name}'

    COMMAND_DELETE = 'docker rm {name}'

    COMMAND_RENAME = 'docker rename {name} {new_name}'

    COMMAND_INFO = 'docker inspect --type container --format {template} {name}'

    COMMAND_SIGNAL = 'docker kill --signal {signal} {name}'

    def __init__(self, *args, **kwargs):
        super(DockerContainer, self).__init__(*args, **kwargs)
        self.options['name'] = self.name
        self.options['detach'] = not self.temporary
        self.options.setdefault('rm', self.temporary)
        self.options.setdefault('tty', self.temporary)
        self.options.setdefault('user', self.user)
        self.options.setdefault('publish', self.ports)
        self.options.setdefault('env', self.env)
        self.options.setdefault('volume', self.volumes)
        self.options.setdefault('link', self.links)
        self.options.setdefault('add-host', self.hosts)
        self.options.setdefault('net', self.network)
        self.options.setdefault('restart', self.restart_policy)
        self.options.setdefault('stop-signal', self.stop_signal)
