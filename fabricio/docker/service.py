import ctypes
import functools
import itertools
import json
import multiprocessing
import re
import shlex
import sys

from base64 import b64encode, b64decode

import contextlib2 as contextlib
import dpath
import six

from cached_property import cached_property
from fabric import colors, api as fab
from fabric.exceptions import CommandTimeout, NetworkError
from frozendict import frozendict
from six.moves import map, shlex_quote

import fabricio

from fabricio import utils

from .base import BaseService, Option, Attribute
from .container import Container, ContainerNotFoundError

host_errors = (RuntimeError, NetworkError, CommandTimeout)


def get_option_value(string, option):
    """
    get option value from string with nested options
    such as "source=from,destination=to"
    """
    for part in re.split(r'(?<!\\),', string):
        if not part.startswith(option + '='):
            continue
        value = shlex.split(part.split('=', 1)[-1])
        # removing \x00 necessary for Python 2.6
        return value and value[0].replace('\x00', '') or None


class ServiceError(RuntimeError):
    pass


class ServiceNotFoundError(ServiceError):
    pass


class RemovableOption(Option):

    path = NotImplemented

    force_add = False

    force_rm = False

    def cast_rm(self, value):
        return value

    def __init__(self, func=None, path=None, force_add=None, force_rm=None, **kwargs):  # noqa
        super(RemovableOption, self).__init__(func=func, **kwargs)
        self.path = path or self.path
        self.force_add = force_add if force_add is not None else self.force_add
        self.force_rm = force_rm if force_rm is not None else self.force_rm

    def get_values_to_add(self, service, attr):
        new_values = self.get_new_values(service, attr)
        new_values = utils.OrderedSet(new_values)

        if not self.force_add:
            current_values = self.get_current_values(service.info)
            new_values -= current_values

        return list(new_values) or None

    def get_values_to_remove(self, service, attr):
        current_values = self.get_current_values(service.info)
        current_values = utils.OrderedSet(current_values)

        if not self.force_rm:
            new_values = self.get_new_values(service, attr)
            new_values = map(self.cast_rm, new_values)
            current_values -= new_values

        return list(current_values) or None

    def get_current_values(self, service_info):
        if '*' in self.path:
            return dpath.util.values(service_info, self.path)
        try:
            return dpath.util.get(service_info, self.path)
        except KeyError:
            return []

    @staticmethod
    def get_new_values(service, attr):
        values = getattr(service, attr)
        if callable(values):
            values = values(service)
        if values is None:
            return []
        if isinstance(values, six.string_types):
            return [values]
        return values


class LabelOption(RemovableOption):

    def cast_rm(self, value):
        # 'ENV=value' => 'ENV'
        return value.split('=', 1)[0]


class EnvOption(LabelOption):

    path = '/Spec/TaskTemplate/ContainerSpec/Env/*'

    def get_current_values(self, service_info):
        values = super(EnvOption, self).get_current_values(service_info)
        return map(lambda value: value.split('=', 1)[0], values)


class PublishOption(RemovableOption):

    path = '/Spec/EndpointSpec/Ports/*/TargetPort'

    force_add = True

    def get_current_values(self, service_info):
        values = super(PublishOption, self).get_current_values(service_info)
        return map(six.text_type, values)

    def cast_rm(self, value, from_current=False):
        # 'source:target/protocol' => 'target'
        return six.text_type(value).rsplit('/', 1)[0].rsplit(':', 1)[-1]


class MountOption(RemovableOption):

    path = '/Spec/TaskTemplate/ContainerSpec/Mounts/*/Target'

    force_add = True

    def cast_rm(self, value):
        # 'type=volume,destination=/path' => '/path'
        destination = get_option_value(value, 'destination')
        destination = destination or get_option_value(value, 'target')
        return destination or get_option_value(value, 'dst')


class HostOption(RemovableOption):

    path = '/Spec/TaskTemplate/ContainerSpec/Hosts/*'

    def get_current_values(self, *args, **kwargs):
        values = super(HostOption, self).get_current_values(*args, **kwargs)
        # 'ip host' => 'host:ip'
        return map(lambda value: ':'.join(value.split(' ', 1)[::-1]), values)


class PlacementPrefOption(RemovableOption):

    path = '/Spec/TaskTemplate/Placement/Preferences/*'

    force_add = True

    force_rm = True

    def get_current_values(self, *args, **kwargs):
        values = super(PlacementPrefOption, self).get_current_values(*args, **kwargs)  # noqa
        for value in values:
            yield ','.join(
                u'{strategy}={descriptor}'.format(
                    strategy=strategy.lower(),
                    descriptor=shlex_quote(descriptor[strategy + 'Descriptor'])
                )
                for strategy, descriptor in value.items()
            )


class Service(BaseService):

    current_options_label_name = '_current_options'

    use_image_sentinels = Attribute(default=False)

    command = Attribute()
    args = Attribute()
    mode = Attribute()

    env = EnvOption(safe=True)
    label = LabelOption(path='/Spec/Labels')
    container_label = LabelOption(
        name='container-label',
        path='/Spec/TaskTemplate/ContainerSpec/Labels',
        safe_name='label',
    )
    publish = PublishOption()
    constraint = RemovableOption(
        path='/Spec/TaskTemplate/Placement/Constraints/*',
    )
    replicas = Option()
    mount = MountOption(safe=True)
    network = RemovableOption(
        path='/Spec/TaskTemplate/Networks/*/Target',
        force_add=True,
        force_rm=True,
        safe=True,
    )
    restart_condition = Option(name='restart-condition')
    stop_grace_period = Option(name='stop-grace-period')
    user = Option(safe=True)
    host = HostOption(safe_name='add-host')
    secret = RemovableOption(
        path='/Spec/TaskTemplate/ContainerSpec/Secrets/*/SecretName',
        force_add=True,
        force_rm=True,
    )
    config = RemovableOption(
        path='/Spec/TaskTemplate/ContainerSpec/Configs/*/ConfigName',
        force_add=True,
        force_rm=True,
    )
    group = RemovableOption(
        path='/Spec/TaskTemplate/ContainerSpec/Groups/*',
        safe_name='group-add',
    )
    placement_pref = PlacementPrefOption(name='placement-pref')
    dns = RemovableOption(
        path='/Spec/TaskTemplate/ContainerSpec/DNSConfig/Nameservers/*',
        safe=True,
    )
    dns_option = RemovableOption(
        path='/Spec/TaskTemplate/ContainerSpec/DNSConfig/Options/*',
        name='dns-option',
        safe=True,
    )
    dns_search = RemovableOption(
        path='/Spec/TaskTemplate/ContainerSpec/DNSConfig/Search/*',
        name='dns-search',
        safe=True,
    )

    def __init__(self, *args, **kwargs):
        super(Service, self).__init__(*args, **kwargs)
        self.manager_found = multiprocessing.Event()
        self.is_manager_call_count = multiprocessing.Value(ctypes.c_int, 0)
        self.pull_errors = multiprocessing.Manager().dict()

    @property
    def cmd(self):
        return ' '.join([self.command or '', self.args or '']).strip()

    @utils.default_property
    def image_id(self):
        return self.info['Spec']['TaskTemplate']['ContainerSpec']['Image']

    def get_backup_version(self):
        current_info = self.info
        if 'PreviousSpec' not in current_info:
            raise ServiceError('service backup not found')
        previous_spec = current_info['PreviousSpec']
        backup_version = self.fork()
        backup_version.info = dict(self.info, Spec=previous_spec)
        return backup_version

    @cached_property
    def _update_options(self):
        options = {}
        for attr, option in self._options.items():
            name = option.name or attr
            if isinstance(option, RemovableOption):
                options[name + '-rm'] = functools.partial(
                    option.get_values_to_remove,
                    attr=attr,
                )
                options[name + '-add'] = functools.partial(
                    option.get_values_to_add,
                    attr=attr,
                )
            else:
                options[name] = getattr(self, attr)
        return options

    @property
    def update_options(self):
        options = itertools.chain(
            (
                (option, value)
                for option, value in self._update_options.items()
            ),
            self._other_options.items(),
        )
        evaluated_options = (
            (option, value(self) if callable(value) else value)
            for option, value in options
        )
        return frozendict(
            (
                (option, value)
                for option, value in evaluated_options
                if value is not None
            ),
            args=self.cmd,
        )

    def _update_service(self, options):
        fabricio.run('docker service update {options} {service}'.format(
            options=options,
            service=self,
        ))

    def _create_service(self, image):
        command = 'docker service create {options} {image} {cmd}'
        fabricio.run(command.format(
            options=utils.Options(self.options, name=self, mode=self.mode),
            image=image,
            cmd=self.cmd,
        ))

    @utils.once_per_command
    def _update(self, image, force=False):
        image = image.digest
        try:
            service_info = self.info
        except ServiceNotFoundError:
            service_info = {}

        with utils.patch(self, 'info', service_info, force_delete=True):
            new_options = dict(self.options, image=image, args=self.cmd)

            labels = service_info.get('Spec', {}).get('Labels', {})
            current_options = labels.pop(self.current_options_label_name, '')

            if force or self._decode_options(current_options) != new_options:
                label_with_new_options = {
                    self.current_options_label_name:
                    self._encode_options(new_options),
                }
                self._update_labels(label_with_new_options)

                if service_info:
                    options = utils.Options(self.update_options, image=image)
                    self._update_service(options)
                else:
                    self._create_service(image)

                return True
        return False

    @staticmethod
    def _delete_obsolete_images(repository):
        images = 'docker images --no-trunc --quiet {0}'.format(repository)
        fabricio.run(
            'docker rmi $({images})'.format(images=images),
            ignore_errors=True,
        )

    @property
    def current_sentinel_name(self):
        return '{service}_current'.format(service=self)

    @property
    def backup_sentinel_name(self):
        return '{service}_backup'.format(service=self)

    @property
    def revert_sentinel_name(self):
        return '{service}_revert'.format(service=self)

    def _update_sentinels(self, image):
        current = Container(name=self.current_sentinel_name)
        backup = Container(name=self.backup_sentinel_name)
        revert = Container(name=self.revert_sentinel_name)
        try:
            if current.image_id == image.info['Id']:
                return
            try:
                backup.delete()
            except RuntimeError:
                pass
            current.rename(self.backup_sentinel_name)
        except ContainerNotFoundError:
            pass
        try:
            revert.delete(delete_dangling_volumes=False)
        except RuntimeError:
            pass
        image.create(name=self.current_sentinel_name)

        image.tag = None
        self._delete_obsolete_images(repository=image)

    def _revert_sentinels(self):
        current = Container(name=self.current_sentinel_name)
        try:
            # raises RuntimeError if revert sentinel already exists
            # preventing double revert
            current.rename(self.revert_sentinel_name)

            # ignore RuntimeError if backup sentinel exists - usual case,
            # preferring backup sentinels over revert,
            # _update_sentinels() always tries to remove revert sentinel if any
            current.rename(self.backup_sentinel_name)
        except RuntimeError:
            pass

    def update(self, tag=None, registry=None, account=None, force=False):
        image = self.image[registry:tag:account]
        is_manager = self.is_manager()
        with contextlib.ExitStack() as stack:
            if self.use_image_sentinels:
                try:
                    context = utils.patch(image, 'info', image.info, force_delete=True)  # noqa
                    stack.enter_context(context)
                    self._update_sentinels(image)
                except host_errors as error:
                    fabricio.log(
                        'WARNING: {error}'.format(error=error),
                        output=sys.stderr,
                        color=colors.red,
                    )
            if not is_manager:
                return False
            result = self._update(image, force=force)
            return result or result is None

    @utils.once_per_command
    def _revert(self):
        command = 'docker service rollback {service}'.format(service=self)
        fabricio.run(command)

    def revert(self):
        is_manager = self.is_manager()
        if self.use_image_sentinels:
            self._revert_sentinels()
        if is_manager:
            self._revert()

    def pull_image(self, *args, **kwargs):
        try:
            return super(Service, self).pull_image(*args, **kwargs)
        except host_errors as error:
            self.pull_errors[fab.env.host] = True
            fabricio.log(
                'WARNING: {error}'.format(error=error),
                output=sys.stderr,
                color=colors.red,
            )

    def migrate(self, *args, **kwargs):
        if self.is_manager():
            super(Service, self).migrate(*args, **kwargs)

    def migrate_back(self):
        if self.is_manager():
            super(Service, self).migrate_back()

    def backup(self):
        if self.is_manager():
            super(Service, self).backup()

    def restore(self, backup_name=None):
        if self.is_manager():
            super(Service, self).restore(backup_name=backup_name)

    @utils.default_property
    def info(self):
        command = 'docker service inspect {service}'
        info = fabricio.run(
            command.format(service=self),
            abort_exception=ServiceNotFoundError,
        )
        return json.loads(info)[0]

    def is_manager(self):
        try:
            if self.pull_errors.get(fab.env.host, False):
                return False
            is_manager = fabricio.run(
                "docker info 2>&1 | grep 'Is Manager:'",
                use_cache=True,
            ).endswith('true')
            if is_manager:
                self.manager_found.set()
            return is_manager
        except host_errors as error:
            fabricio.log(
                'WARNING: {error}'.format(error=error),
                output=sys.stderr,
                color=colors.red,
            )
            return False
        finally:
            with self.is_manager_call_count.get_lock():
                self.is_manager_call_count.value += 1
                if self.is_manager_call_count.value >= len(fab.env.all_hosts):
                    if not self.manager_found.is_set():
                        msg = 'Swarm manager with pulled image was not found'
                        raise ServiceError(msg)
                    self.manager_found.clear()
                    self.is_manager_call_count.value = 0

    @staticmethod
    def _encode_options(options):
        options = utils.OrderedDict(sorted(options.items()))
        options_string = json.dumps(options, default=six.text_type).encode()
        return b64encode(options_string).decode()

    @staticmethod
    def _decode_options(encoded_options):
        try:
            return json.loads(encoded_options or '{}')
        except ValueError:
            pass
        return json.loads(b64decode(encoded_options).decode() or '{}')

    def _update_labels(self, labels):
        service_labels = self.label
        if not service_labels:
            service_labels = []
        elif isinstance(service_labels, six.string_types):
            service_labels = [service_labels]
        else:
            try:
                service_labels = list(service_labels)
            except TypeError:
                service_labels = [six.text_type(service_labels)]
        for label, value in labels.items():
            service_labels.append("{0}={1}".format(label, value))
        self.label = service_labels
