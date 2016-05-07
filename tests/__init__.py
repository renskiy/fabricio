class AttributeString(str):

    def __new__(cls, *args, **kwargs):
        kwargs.pop('succeeded', None)
        return super(AttributeString, cls).__new__(cls, *args, **kwargs)

    def __init__(self, *args, **kwargs):
        self.succeeded = kwargs.pop('succeeded', True)
        super(AttributeString, self).__init__(*args, **kwargs)
