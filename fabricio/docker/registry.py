class Registry(str):

    def __new__(cls, value=None, *args, **kwargs):
        if value is None:
            return None
        return super(Registry, cls).__new__(cls, value, *args, **kwargs)

    def __init__(self, *args, **kwargs):
        super(Registry, self).__init__(*args, **kwargs)
        self.host, _, port = self.partition(':')
        self.port = port and int(port)
