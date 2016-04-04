from . import BaseContainer, BaseTemporaryContainer


class Container(BaseContainer):

    class Command(BaseContainer.Command):

        RUN = 'docker run {options} {image} {cmd}'

        START = 'docker start {name}'

        STOP = 'docker stop --time {timeout} {name}'

        DELETE = 'docker rm {name}'

        SIGNAL = 'docker kill --signal {signal} {name}'

        RENAME = 'docker rename {name} {new_name}'

        INFO = 'docker inspect --type container --format {template} {name}'

    def __init__(self, *image_and_cmd, **options):
        options.setdefault('detach', self.detach)
        options.setdefault('name', self.name)
        options.setdefault('publish', self.ports)
        options.setdefault('env', self.env)
        options.setdefault('volume', self.volumes)
        options.setdefault('link', self.links)
        options.setdefault('add_host', self.hosts)
        options.setdefault('net', self.network)
        options.setdefault('restart', self.restart_policy)
        options.setdefault('stop_signal', self.stop_signal)
        super(Container, self).__init__(*image_and_cmd, **options)


class TemporaryContainer(BaseTemporaryContainer):

    def __init__(self, *image_and_cmd, **options):
        options.setdefault('rm', True)
        options.setdefault('tty', True)
        super(TemporaryContainer, self).__init__(*image_and_cmd, **options)
