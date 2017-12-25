import collections
import functools
import os
import sys
import types
import warnings

import contextlib2 as contextlib

from fabric import api as fab, colors, state
from fabric.contrib import console
from fabric.main import is_task_object
from fabric.tasks import WrappedCallableTask, get_task_details

import fabricio

from fabricio import docker, utils
from fabricio.misc import dangling_images_delete_command

fab.env.setdefault('infrastructure', None)


# add to Fabric's WrappedCallableTask additional method to get
# benefits from using super() inside method-based tasks
WrappedCallableTask.__get__ = lambda self, instance, owner: (
    self.__class__(
        self.wrapped.__get__(instance, owner),
        aliases=self.aliases,
        default=self.is_default,
        name=self.name,
    )
)


def _uncrawl(task, _cache={}):  # pragma: no cover
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


def execute(*args, **kwargs):  # pragma: no cover
    warnings.warn(
        'fabricio.execute() is deprecated in favour of fabric.api.execute()',
        DeprecationWarning,
    )
    warnings.warn(
        'fabricio.execute() is deprecated and will be removed in v0.6, '
        'use fabric.api.execute() instead',
        RuntimeWarning, stacklevel=2,
    )
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


class SshTunnel(object):

    bind_address = '127.0.0.1'

    host = 'localhost'

    def __new__(cls, mapping):
        if mapping is None:
            return None
        return super(SshTunnel, cls).__new__(cls)

    def __init__(self, mapping):
        mapping = str(mapping)
        parts = mapping.split(':', 3)
        if len(parts) == 4:
            self.bind_address, port, self.host, host_port = parts
        elif len(parts) == 3:
            port, self.host, host_port = parts
        elif len(parts) == 2:
            port, host_port = parts
        else:
            port = host_port = parts[0]
        self.port = int(port)
        self.host_port = int(host_port)


class Tasks(object):

    @property
    def __name__(self):
        return self

    __class__ = types.ModuleType

    def __new__(cls, *args, **kwargs):
        self = super(Tasks, cls).__new__(cls)
        for attr in dir(cls):
            obj = getattr(self, attr, None)
            if is_task_object(obj):
                setattr(self, attr, obj)
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
        for obj in vars(self).values():
            if is_task_object(obj):
                yield obj


class Infrastructure(Tasks):

    def __new__(cls, *args, **kwargs):
        if len(args) > 1:
            raise ValueError('only 1 positional argument allowed')
        if not args:
            return lambda callback: cls(callback, **kwargs)
        return super(Infrastructure, cls).__new__(cls)

    def __init__(
        self,
        callback=None,
        color=colors.yellow,
        name=None,
        *args, **kwargs
    ):
        super(Infrastructure, self).__init__(*args, **kwargs)

        default = self.default
        confirm = self.confirm

        # We need to be sure that `default()` will be at first place
        # every time when vars(self) is being invoked.
        # This is necessary to exclude `default` from the list of task
        # because of it's already there as default task.
        # See `fabric.main.extract_tasks()` for details
        self.__dict__ = collections.OrderedDict(
            [('default', default)],
            **self.__dict__
        )

        self.callback = callback
        self.color = color
        self.name = name = name or callback.__name__
        name = color(name)
        doc = callback.__doc__ or ''
        default.__doc__ = default.__doc__.format(name=name)
        confirm.__doc__ = confirm.__doc__.format(name=name)
        default.__details__ = functools.partial(self._details, doc, default)
        confirm.__details__ = functools.partial(self._details, doc, confirm)

    def _details(self, doc, method):
        doc = (method.__doc__ or '') + doc
        with utils.patch(self.callback, '__doc__', doc):
            return get_task_details(self.callback)

    @fab.task(
        default=True,
        # mock another task name to exclude this task from the tasks list
        name='confirm',
    )
    @fab.serial
    def default(self, *args, **kwargs):
        """
        select {name} infrastructure to run task(s) on
        """
        with utils.patch(fab.env, 'parallel', False):
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
    @fab.serial
    def confirm(self, *args, **kwargs):
        """
        automatically confirm {name} infrastructure selection
        """
        fab.env.infrastructure = self.name
        self.callback(*args, **kwargs)


infrastructure = Infrastructure


class DockerTasks(Tasks):

    _warnings_stacklevel = 2

    def __init__(
        self,
        service=None,
        registry=None,
        host_registry=None,
        account=None,
        ssh_tunnel_port=None,  # deprecated
        ssh_tunnel=None,
        migrate_commands=False,
        backup_commands=False,
        pull_command=False,
        update_command=False,
        revert_command=False,
        **kwargs
    ):
        super(DockerTasks, self).__init__(**kwargs)

        # We need to be sure that `deploy()` will be at first place
        # every time when vars(self) is being invoked.
        # This is necessary to exclude `deploy` from the list of task
        # because of it's already there as default task.
        # See `fabric.main.extract_tasks()` for details
        self.deploy.is_default = True  # force is_default property
        self.__dict__ = collections.OrderedDict(
            [('deploy', self.deploy)],
            **self.__dict__
        )

        self.service = service
        self.registry = registry
        self.host_registry = host_registry or registry
        self.account = account
        self.ssh_tunnel = ssh_tunnel

        if ssh_tunnel_port:
            warnings.warn(
                'ssh_tunnel_port is deprecated and will be removed in v0.6, '
                'use ssh_tunnel instead',
                RuntimeWarning, stacklevel=self._warnings_stacklevel,
            )
            registry = self.registry or self.image and self.image.registry
            assert registry, 'must provide registry if using ssh_tunnel_port'
            self.host_registry = 'localhost:%d' % ssh_tunnel_port
            self.ssh_tunnel = '{port}:{host}:{host_port}'.format(
                port=ssh_tunnel_port,
                host=registry.host,
                host_port=registry.port,
            )

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
        if command_mode:
            # set original name for `deploy` method to allow explicit invocation
            self.deploy.name = 'deploy'

        # enable following commands only in custom registry mode
        custom_mode = bool(registry or account)
        self.prepare.use_task_objects = command_mode or custom_mode
        self.push.use_task_objects = command_mode or custom_mode
        self.upgrade.use_task_objects = command_mode or custom_mode

    def _set_registry(self, registry):
        self.__dict__['registry'] = docker.Registry(registry)

    def _get_registry(self):
        return self.__dict__.get('registry')

    registry = property(_get_registry, _set_registry)

    def _set_host_registry(self, host_registry):
        self.__dict__['host_registry'] = docker.Registry(host_registry)

    def _get_host_registry(self):
        return self.__dict__.get('host_registry')

    host_registry = property(_get_host_registry, _set_host_registry)

    def _set_ssh_tunnel(self, ssh_tunnel):
        self.__dict__['ssh_tunnel'] = SshTunnel(ssh_tunnel)

    def _get_ssh_tunnel(self):
        return self.__dict__.get('ssh_tunnel')

    ssh_tunnel = property(_get_ssh_tunnel, _set_ssh_tunnel)

    @property
    def image(self):
        return self.service.image

    @fab.task
    @skip_unknown_host
    def revert(self):
        """
        revert service container(s) to a previous version
        """
        with self.remote_tunnel():
            self.service.revert()

    @fab.task
    @skip_unknown_host
    def migrate(self, tag=None):
        """
        apply new migrations
        """
        with self.remote_tunnel():
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
        with self.remote_tunnel():
            self.service.migrate_back()

    @fab.task
    @skip_unknown_host
    def backup(self):
        """
        backup service data
        """
        with self.remote_tunnel():
            self.service.backup()

    @fab.task
    @skip_unknown_host
    def restore(self, backup_name=None):
        """
        restore service data
        """
        with self.remote_tunnel():
            self.service.restore(backup_name=backup_name)

    @fab.task
    def rollback(self, migrate_back=True):
        """
        rollback service to a previous version (migrate-back -> revert)
        """
        if utils.strtobool(migrate_back):
            self.migrate_back()
        self.revert()

    @fab.hosts()
    @fab.roles()
    @fab.task
    def prepare(self, tag=None):
        """
        download Docker image from the original registry
        """
        if self.registry is None and self.account is None:
            return
        image = self.image[tag]  # type: docker.Image
        if image:
            image.pull(local=True, use_cache=True)

    def delete_dangling_images(self):  # pragma: no cover
        warnings.warn(
            'delete_dangling_images() is deprecated and will be removed in v0.6',  # noqa
            DeprecationWarning,
        )
        warnings.warn(
            'delete_dangling_images() is deprecated and will be removed in v0.6',  # noqa
            RuntimeWarning, stacklevel=self._warnings_stacklevel,
        )
        fabricio.local(dangling_images_delete_command(), ignore_errors=True)

    def push_image(self, tag=None):
        image = self.image[self.registry:tag:self.account]
        fabricio.local(
            'docker push {image}'.format(image=image),
            quiet=False,
            use_cache=True,
        )

    @fab.hosts()
    @fab.roles()
    @fab.task
    def push(self, tag=None):
        """
        push downloaded Docker image to intermediate registry
        """
        if self.registry is None and self.account is None:
            return
        image = self.image[tag]
        if not image:
            return
        proxy_tag = image[self.registry:tag:self.account]
        fabricio.local(
            'docker tag {image} {tag}'.format(
                image=image,
                tag=proxy_tag,
            ),
            use_cache=True,
        )
        self.push_image(tag=tag)
        fabricio.local(
            'docker rmi {tag}'.format(tag=proxy_tag),
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
        with contextlib.ExitStack() as stack:
            if self.ssh_tunnel:
                output = stack.enter_context(contextlib.closing(open(os.devnull, 'w')))  # noqa
                # forward sys.stdout to os.devnull to prevent
                # printing debug messages by fab.remote_tunnel
                stack.enter_context(utils.patch(sys, 'stdout', output))
                stack.enter_context(fab.remote_tunnel(
                    remote_bind_address=self.ssh_tunnel.bind_address,
                    remote_port=self.ssh_tunnel.port,
                    local_host=self.ssh_tunnel.host,
                    local_port=self.ssh_tunnel.host_port,
                ))
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
        with self.remote_tunnel():
            updated = self.service.update(
                tag=tag,
                registry=self.host_registry,
                account=self.account,
                force=utils.strtobool(force),
            )
        if updated is False:
            fabricio.log('No changes detected, update skipped.')

    @fab.task
    def upgrade(self, tag=None, force=False, backup=False, migrate=True):
        """
        upgrade service to a new version (backup -> pull -> migrate -> update)
        """
        if utils.strtobool(backup):
            self.backup()
        self.pull(tag=tag)
        if utils.strtobool(migrate):
            self.migrate(tag=tag)
        self.update(tag=tag, force=force)

    @fab.hosts()
    @fab.roles()
    @fab.task(
        default=True,
        # mock another task name to exclude this task from the tasks list
        name='rollback',
    )
    def deploy(self, tag=None, force=False, backup=False, migrate=True):
        """
        full service deploy (prepare -> push -> upgrade)
        """
        self.prepare(tag=tag)
        self.push(tag=tag)
        fab.execute(
            self.upgrade,
            tag=tag,
            force=force,
            backup=backup,
            migrate=migrate,
        )


class ImageBuildDockerTasks(DockerTasks):

    _warnings_stacklevel = 3

    def __init__(self, service=None, build_path='.', **kwargs):
        super(ImageBuildDockerTasks, self).__init__(service, **kwargs)
        self.build_path = build_path
        self.prepare.use_task_objects = True
        self.push.use_task_objects = True
        self.upgrade.use_task_objects = True

    @fab.hosts()
    @fab.roles()
    @fab.task
    def prepare(self, tag=None, **kwargs):
        """
        build Docker image (see 'docker build --help' for available options)
        """
        for key, value in kwargs.items():
            with contextlib.suppress(ValueError):
                kwargs[key] = utils.strtobool(value)
        options = utils.Options(kwargs)
        image = self.image[self.registry:tag:self.account]  # type: docker.Image
        image.build(
            local=True,
            build_path=self.build_path,
            options=options,
            use_cache=True,
        )

    @fab.hosts()
    @fab.roles()
    @fab.task
    def push(self, tag=None):
        """
        push built Docker image to the registry
        """
        self.push_image(tag=tag)
