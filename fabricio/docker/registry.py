class Registry(str):

    def __init__(self, *args, **kwargs):
        super(Registry, self).__init__(*args, **kwargs)
        self.host, _, port = self.partition(':')
        self.port = port and int(port)
