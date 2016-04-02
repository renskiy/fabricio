class BaseContainer(object):

    def __init__(self, *image_and_cmd, **options):
        assert 1 <= len(image_and_cmd) <= 2
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
            elif isinstance(value, basestring):
                yield self.make_option(option, value)
            else:
                for single_value in value:
                    yield self.make_option(option, single_value)


class Container(BaseContainer):

    image = NotImplemented

    cmd = ''

    name = None

    publish = []

    env = []

    volume = []

    link = []

    add_host = []

    net = None

    restart = None

    stop_signal = None

    def __init__(self, *image_and_cmd, **options):
        image_and_cmd = image_and_cmd or (self.image, self.cmd)
        options.setdefault('detach', True)
        options.setdefault('name', self.name)
        options.setdefault('publish', self.publish)
        options.setdefault('env', self.env)
        options.setdefault('volume', self.volume)
        options.setdefault('link', self.link)
        options.setdefault('add_host', self.add_host)
        options.setdefault('net', self.net)
        options.setdefault('restart', self.restart)
        options.setdefault('stop_signal', self.stop_signal)
        super(Container, self).__init__(*image_and_cmd, **options)


class TemporaryContainer(Container):

    def __init__(self, *image_and_cmd, **options):
        options.setdefault('detach', False)
        options.setdefault('rm', True)
        options.setdefault('tty', True)
        options.setdefault('interactive', True)
        super(TemporaryContainer, self).__init__(*image_and_cmd, **options)
