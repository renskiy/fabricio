import json
import weakref

from cached_property import cached_property
from fabric import api as fab


class Image(object):

    COMMAND_INFO = 'docker inspect --type image {image}'
    COMMAND_DELETE = 'docker rmi {image}'
    COMMAND_FORCE_DELETE = 'docker rmi --force {image}'

    def __init__(self, name=None, tag=None, container=None):
        forced_tag = tag
        self.name, _, tag = name and str(name).partition(':') or [None] * 3
        self.tag = forced_tag or tag or 'latest'
        self.container = container and weakref.proxy(container)

    def __str__(self):
        if not self.name:
            raise ValueError('Can\'t stringify image without name')
        return '{name}:{tag}'.format(name=self.name, tag=self.tag)

    def __repr__(self):
        return '<Image {__str__}>'.format(__str__=self.__str__())

    def __getitem__(self, tag):
        return type(self)(name=self.name, tag=tag)

    @property
    def info(self):
        image = self.container.info.get('Image') if self.container else self
        if image:
            info = fab.sudo(self.COMMAND_INFO.format(image=image))
            if info.succeeded:
                return json.loads(str(info))[0]
        return {}

    @cached_property
    def id(self):
        return self.info.get('Id')

    def delete(self, force=False, force_container_delete=False, ignore_delete_error=False):
        image = self.id
        if image:
            if self.container:
                self.container.delete(force=force_container_delete)
            command = force and self.COMMAND_FORCE_DELETE or self.COMMAND_DELETE
            with fab.settings(warn_only=ignore_delete_error):
                fab.sudo(command.format(image=image))
