import json
import weakref

from cached_property import cached_property
from fabric import api as fab


class Image(object):

    COMMAND_INFO = 'docker inspect --type image {image}'
    COMMAND_DELETE = 'docker rmi {image}'
    COMMAND_FORCE_DELETE = 'docker rmi --force {image}'

    def __init__(self, name, tag=None, container=None):
        forced_tag = tag
        self.name, _, tag = str(name).partition(':')
        self.tag = forced_tag or tag or 'latest'
        self.container = container and weakref.proxy(container)

    def __str__(self):
        return '{name}:{tag}'.format(name=self.name, tag=self.tag)

    def __getitem__(self, tag):
        return type(self)(name=self.name, tag=tag)

    @property
    def info(self):
        image = self.container and self.container.info['Image'] or self
        info = fab.sudo(self.COMMAND_INFO.format(image=image)).stdout
        return json.loads(info)[0]

    @cached_property
    def id(self):
        return self.info['Id']

    def delete(self, force=False, force_container_delete=False):
        image = self.id
        if self.container:
            self.container.delete(force=force_container_delete)
        command = force and self.COMMAND_FORCE_DELETE or self.COMMAND_DELETE
        fab.sudo(command.format(image=image))
