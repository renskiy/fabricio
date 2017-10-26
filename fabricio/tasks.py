import contextlib
import functools
import os
import sys
import types

from fabric import api as fab, colors, state
from fabric.contrib import console
from fabric.main import is_task_object

import fabricio

from fabricio import docker, utils
from fabricio.misc import dangling_images_delete_command


def _uncrawl(task, _cache={}):
    if not _cache:
        def _fill_cache(mapping=state.commands, keys=[]):
            for key, value in mapping.items():
                _keys = keys + [key]
                if isinstance(value, dict):
                    _fill_cache(value, _keys)
                else:
                    _cache[value] = '.'.join(_keys)
        _fill_cache()
    return _cache.get(task)


def execute(*args, **kwargs):
    try:
        task, args = args[0], args[1:]
    except IndexError:
        raise TypeError('must provide task to execute')
    default_name = '{command}.{task_name}({id})'.format(
        command=fab.env.command,
        task_name=getattr(task, 'name', task.__name__),
        id=id(task),
    )
    with utils.patch(task, 'name', _uncrawl(task) or default_name):
        return fab.execute(task, *args, **kwargs)


def skip_unknown_host(func):
    @functools.wraps(func)
    def _task(*args, **kwargs):
        if fab.env.get('host_string', False):
            return func(*args, **kwargs)
        fabricio.log(
            "'{func}' execution was skipped due to no host provided "
            "(command: {command})".format(
                func=func.__name__,
                command=fab.env.command,
            )
        )
    _task.wrapped = func  # compatibility with 'fab --display <task>' option
    return _task


class Tasks(object):

    @property
    def __name__(self):
        return self

    __class__ = types.ModuleType

    def __new__(cls, *args, **kwargs):
        self = super(Tasks, cls).__new__(cls)
        for attr in dir(cls):
            attr_value = getattr(cls, attr)
            if is_task_object(attr_value):
                task_decorator = fab.task(
                    default=attr_value.is_default,
                    name=attr_value.name,
                    aliases=attr_value.aliases,
                    task_class=attr_value.__class__,
                )
                bounded_task = functools.partial(attr_value.wrapped, self)
                task = task_decorator(functools.wraps(attr_value)(bounded_task))
                for wrapped_attr in [
                    'parallel',
                    'serial',
                    'pool_size',
                    'hosts',
                    'roles',
                ]:
                    if hasattr(attr_value.wrapped, wrapped_attr):
                        setattr(
                            task.wrapped,
                            wrapped_attr,
                            getattr(attr_value.wrapped, wrapped_attr),
                        )
                setattr(self, attr, task)
        return self

    def __init__(self, roles=(), hosts=(), create_default_roles=True):
        if create_default_roles:
            for role in roles:
                fab.env.roledefs.setdefault(role, [])
        for task in self:
            if not hasattr(task, 'roles'):
                task.roles = roles
            if not hasattr(task, 'hosts'):
                task.hosts = hosts

    def __iter__(self):
        for name, attr_value in vars(self).items():
            if is_task_object(attr_value):
                yield attr_value


class Infrastructure(Tasks):

    def __new__(cls, *args, **kwargs):
        if len(args) > 1:
            raise ValueError('only 1 positional argument allowed')
        if not args:
            return lambda callback: cls(callback, **kwargs)
        return super(Infrastructure, cls).__new__(cls, *args, **kwargs)

    def __init__(
        self,
        callback=None,
        color=colors.yellow,
        name=None,
        *args, **kwargs
    ):
        super(Infrastructure, self).__init__(*args, **kwargs)
        # We need to be sure that `default()` will be at first place
        # every time when vars(self) is being invoked.
        # See Fabric's `extract_tasks()`
        self.__dict__ = utils.OrderedDict(
            (('default', self.default), ),
            **self.__dict__
        )
        self.callback = callback
        self.color = color
        self.name = name = name or callback.__name__
        name = color(name)
        self.default.__doc__ = self.default.__doc__.format(name=name)
        self.confirm.__doc__ = self.confirm.__doc__.format(name=name)

    @fab.task(default=True, name='confirm')
    def default(self, *args, **kwargs):
        """
        select {name} infrastructure to run task(s) on
        """
        if not console.confirm(
            'Are you sure you want to select {name} '
            'infrastructure to run task(s) on?'.format(
                name=self.color(self.name),
            ),
            default=False,
        ):
            fab.abort('Aborted')
        self.confirm(*args, **kwargs)

    @fab.task
    def confirm(self, *args, **kwargs):
        """
        automatically confirm {name} infrastructure selection
        """
        fab.env.infrastructure = self.name
        self.callback(*args, **kwargs)

infrastructure = Infrastructure


class DockerTasks(Tasks):

    def __init__(
        self,
        service=None,
        registry=None,
        account=None,
        ssh_tunnel_port=None,
        migrate_commands=False,
        backup_commands=False,
        pull_command=False,
        update_command=False,
        revert_command=False,
        **kwargs
    ):
        super(DockerTasks, self).__init__(**kwargs)
        self.service = service
        self.registry = registry
        self.account = account
        self.ssh_tunnel_port = ssh_tunnel_port
        # if there is at least one task to run then assume it is command mode,
        # there is no other way to find this out
        command_mode = bool(fab.env.tasks)
        self.backup.use_task_objects = command_mode or backup_commands
        self.restore.use_task_objects = command_mode or backup_commands
        self.migrate.use_task_objects = command_mode or migrate_commands
        self.migrate_back.use_task_objects = command_mode or migrate_commands
        self.revert.use_task_objects = command_mode or revert_command
        self.pull.use_task_objects = command_mode or pull_command
        self.update.use_task_objects = command_mode or update_command
        self.prepare.use_task_objects = command_mode or registry is not None
        self.push.use_task_objects = command_mode or registry is not None

    def _set_registry(self, registry):
        self.__dict__['registry'] = docker.Registry(registry)

    def _get_registry(self):
        return self.__dict__.get('registry')

    registry = property(_get_registry, _set_registry)

    @property
    def host_registry(self):
        return docker.Registry(
            'localhost:{port}'.format(port=self.ssh_tunnel_port)
            if self.ssh_tunnel_port else
            self.registry
        )

    @property
    def image(self):
        return self.service.image

    @fab.task
    @skip_unknown_host
    def revert(self):
        """
        revert service container(s) to a previous version
        """
        self.service.revert()

    @fab.task
    @skip_unknown_host
    def migrate(self, tag=None):
        """
        apply new migrations
        """
        self.service.migrate(
            tag=tag,
            registry=self.host_registry,
            account=self.account,
        )

    @fab.task(name='migrate-back')
    @skip_unknown_host
    def migrate_back(self):
        """
        remove previously applied migrations if any
        """
        self.service.migrate_back()

    @fab.task
    @skip_unknown_host
    def backup(self):
        """
        backup service data
        """
        self.service.backup()

    @fab.task
    @skip_unknown_host
    def restore(self, backup_name=None):
        """
        restore service data
        """
        self.service.restore(backup_name=backup_name)

    @fab.task
    @fab.hosts()
    @fab.roles()
    def rollback(self, migrate_back=True):
        """
        rollback service to a previous version (migrate-back -> revert)
        """
        if utils.strtobool(migrate_back):
            execute(self.migrate_back)
        execute(self.revert)

    @fab.task
    @fab.hosts()
    @fab.roles()
    def prepare(self, tag=None):
        """
        download Docker image from the original registry
        """
        if self.registry is None and self.account is None:
            return
        fabricio.local(
            'docker pull {image}'.format(image=self.image[tag]),
            quiet=False,
            use_cache=True,
        )
        self.delete_dangling_images()

    @staticmethod
    def delete_dangling_images():
        fabricio.local(dangling_images_delete_command(), ignore_errors=True)

    def push_image(self, tag=None):
        image = self.image[self.registry:tag:self.account]
        fabricio.local(
            'docker push {image}'.format(image=image),
            quiet=False,
            use_cache=True,
        )

    @fab.task
    @fab.hosts()
    @fab.roles()
    def push(self, tag=None):
        """
        push downloaded Docker image to the registry
        """
        if self.registry is None and self.account is None:
            return
        tag_with_registry = str(self.image[self.registry:tag:self.account])
        fabricio.local(
            'docker tag {image} {tag}'.format(
                image=self.image[tag],
                tag=tag_with_registry,
            ),
            use_cache=True,
        )
        self.push_image(tag=tag)
        fabricio.local(
            'docker rmi {tag}'.format(tag=tag_with_registry),
            use_cache=True,
        )

    def pull_image(self, tag=None):
        self.service.pull_image(
            tag=tag,
            registry=self.host_registry,
            account=self.account,
        )

    @contextlib.contextmanager
    def remote_tunnel(self):
        if self.ssh_tunnel_port:
            if self.registry:
                local_port = self.registry.port
                local_host = self.registry.host
            elif self.image.registry:
                local_port = self.image.registry.port
                local_host = self.image.registry.host
            else:
                raise ValueError(
                    'Either local host or local port for SSH tunnel '
                    'can not be obtained'
                )
            with contextlib.closing(open(os.devnull, 'w')) as output:
                with utils.patch(sys, 'stdout', output):
                    # forward sys.stdout to os.devnull to prevent
                    # printing debug messages by fab.remote_tunnel

                    with fab.remote_tunnel(
                        remote_port=self.host_registry.port,
                        local_port=local_port,
                        local_host=local_host,
                    ):
                        yield
        else:
            yield

    @fab.task
    @skip_unknown_host
    def pull(self, tag=None):
        """
        pull Docker image from the registry
        """
        with self.remote_tunnel():
            self.pull_image(tag=tag)

    @fab.task
    @skip_unknown_host
    def update(self, tag=None, force=False):
        """
        update service to a new version
        """
        updated = self.service.update(
            tag=tag,
            registry=self.host_registry,
            account=self.account,
            force=utils.strtobool(force),
        )
        if not updated:
            fabricio.log('No changes detected, update skipped.')

    @fab.task
    @fab.hosts()
    @fab.roles()
    def upgrade(
        self,
        tag=None,
        force=False,
        backup=False,
        migrate=True,
    ):
        """
        upgrade service to a new version (backup -> pull -> migrate -> update)
        """
        if utils.strtobool(backup):
            execute(self.backup)
        execute(self.pull, tag=tag)
        if utils.strtobool(migrate):
            execute(self.migrate, tag=tag)
        execute(self.update, tag=tag, force=force)

    @fab.task(default=True)
    @fab.hosts()
    @fab.roles()
    def deploy(
        self,
        tag=None,
        force=False,
        backup=False,
        migrate=True,
    ):
        """
        full service deploy (prepare -> push -> upgrade)
        """
        execute(self.prepare, tag=tag)
        execute(self.push, tag=tag)
        execute(
            self.upgrade,
            tag=tag,
            force=force,
            backup=backup,
            migrate=migrate,
        )


class ImageBuildDockerTasks(DockerTasks):

    def __init__(self, service=None, build_path='.', **kwargs):
        super(ImageBuildDockerTasks, self).__init__(service, **kwargs)
        self.build_path = build_path
        self.prepare.use_task_objects = True
        self.push.use_task_objects = True

    @fab.task
    @fab.hosts()
    @fab.roles()
    def prepare(self, tag=None, **kwargs):
        """
        build Docker image (see 'docker build --help' for available options)
        """
        # default options
        kwargs.setdefault('pull', True)
        kwargs.setdefault('force-rm', True)

        for key, value in kwargs.items():
            try:
                kwargs[key] = utils.strtobool(value)
            except ValueError:
                pass

        options = utils.Options(
            tag=self.image[self.registry:tag:self.account],
            **kwargs
        )
        fabricio.local(
            'docker build {options} {build_path}'.format(
                build_path=self.build_path,
                options=options,
            ),
            quiet=False,
            use_cache=True,
        )
        self.delete_dangling_images()

    @fab.task
    @fab.hosts()
    @fab.roles()
    def push(self, tag=None):
        """
        push built Docker image to the registry
        """
        self.push_image(tag=tag)
