import ctypes
import functools
import hashlib
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
from six.moves import map, shlex_quote, range, filter, zip_longest

import fabricio

from fabricio import utils

from .base import BaseService, Option, Attribute
from .image import Image, ImageNotFoundError

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


class StackError(ServiceError):
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
            new_values = (
                value
                for values in new_values
                for value in (
                    values if isinstance(values, (list, tuple)) else [values]
                )
            )
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

    def cast_rm(self, value, from_current=False):
        # 'source:target/protocol' => int('target')
        target_port = six.text_type(value).rsplit('/', 1)[0].rsplit(':', 1)[-1]
        if '-' not in target_port:
            return int(target_port)
        port_start, port_end = map(int, target_port.split('-', 1))
        return list(range(port_start, port_end + 1))


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


class _Base(BaseService):

    def __init__(self, *args, **kwargs):
        super(_Base, self).__init__(*args, **kwargs)
        self.manager_found = multiprocessing.Event()
        self.is_manager_call_count = multiprocessing.Value(ctypes.c_int, 0)
        self.pull_errors = multiprocessing.Manager().dict()

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
                        msg = 'Service manager with pulled image was not found'
                        raise ServiceError(msg)
                    self.manager_found.clear()
                    self.is_manager_call_count.value = 0

    def pull_image(self, *args, **kwargs):
        try:
            if self.image:
                return super(_Base, self).pull_image(*args, **kwargs)
        except host_errors as error:
            self.pull_errors[fab.env.host] = True
            fabricio.log(
                'WARNING: {error}'.format(error=error),
                output=sys.stderr,
                color=colors.red,
            )

    def migrate(self, *args, **kwargs):
        if self.is_manager():
            super(_Base, self).migrate(*args, **kwargs)

    def migrate_back(self):
        if self.is_manager():
            super(_Base, self).migrate_back()

    def backup(self):
        if self.is_manager():
            super(_Base, self).backup()

    def restore(self, backup_name=None):
        if self.is_manager():
            super(_Base, self).restore(backup_name=backup_name)


class Service(_Base):

    options_label_name = 'fabricio.service.options'

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
            labels = service_info.get('Spec', {}).get('Labels', {})
            current_options = labels.pop(self.options_label_name, None)
            new_options = self._encode_options(dict(
                self.options,
                image=image,
                args=self.cmd,
            ))

            if force or current_options != new_options:
                label_with_new_options = {
                    self.options_label_name: new_options,
                }
                self._update_labels(label_with_new_options)

                if service_info:
                    options = utils.Options(self.update_options, image=image)
                    self._update_service(options)
                else:
                    self._create_service(image)

                return True
        return False

    def update(self, tag=None, registry=None, account=None, force=False):
        if not self.is_manager():
            return False
        result = self._update(self.image[registry:tag:account], force=force)
        return result is None or result

    @utils.once_per_command
    def _revert(self):
        command = 'docker service rollback {service}'.format(service=self)
        fabricio.run(command)

    def revert(self):
        if self.is_manager():
            self._revert()

    @utils.default_property
    def info(self):
        command = 'docker service inspect {service}'
        info = fabricio.run(
            command.format(service=self),
            abort_exception=ServiceNotFoundError,
        )
        return json.loads(info)[0]

    @staticmethod
    def _encode_options(options):
        bucket = json.dumps(options, sort_keys=True, default=six.text_type)
        return hashlib.md5(bucket.encode()).hexdigest()

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


class Stack(_Base):

    temp_dir = Attribute(default='/tmp')

    compose_file = Option(name='compose-file', default='docker-compose.yml')

    image_id = None

    info = None

    def __init__(self, *args, **kwargs):
        super(Stack, self).__init__(*args, **kwargs)
        self.stack_updated = multiprocessing.Event()

    @property
    def compose_label(self):
        return 'fabricio.stack.compose.{0}'.format(self.name)

    @property
    def images_info_label(self):
        return 'fabricio.stack.images.{0}'.format(self.name)

    @property
    def current_settings_tag(self):
        return 'fabricio-current-stack:{0}'.format(self.name)

    @property
    def backup_settings_tag(self):
        return 'fabricio-backup-stack:{0}'.format(self.name)

    @property
    def actual_compose_file(self):
        return self.options.get('compose-file')

    def update(self, tag=None, registry=None, account=None, force=False):
        if not self.is_manager():
            return False
        self.reset_stack_updated_status()
        compose_file = open(self.actual_compose_file, 'rb').read()
        new_settings = b64encode(compose_file).decode()
        result = self._update(compose_file, new_settings, force=force)
        if self.stack_updated.is_set():
            image = self.image[registry:tag:account]
            self.save_new_settings(new_settings, image)
        return result is None or result

    @utils.once_per_command(block=True)
    def _update(self, compose_file, new_settings, force=False):
        if not force:
            settings, digests = self.current_settings
            digests = digests and json.loads(b64decode(digests).decode())
            if settings == new_settings and digests is not None:
                new_digests = self._get_digests(digests)
                if digests == new_digests:
                    return False
        with fab.cd(self.temp_dir):
            fab.put(six.BytesIO(compose_file), self.actual_compose_file)
            fabricio.run('docker stack deploy {options} {name}'.format(
                options=utils.Options(self.options),
                name=self.name,
            ))
        self.stack_updated.set()
        return True

    def revert(self):
        if not self.is_manager():
            return False
        self.reset_stack_updated_status()
        self._revert()
        if self.stack_updated.is_set():
            self.rotate_sentinel_images(rollback=True)

    @utils.once_per_command(block=True)
    def _revert(self):
        backup_settings, backup_digests = self.backup_settings
        if not backup_settings:
            raise StackError('stack backup settings not found')
        compose_file = b64decode(backup_settings)
        self._update(compose_file, backup_settings, force=True)

        # update stack services with image digests from backup
        backup_digests = backup_digests and b64decode(backup_digests).decode()
        backup_digests = backup_digests and json.loads(backup_digests)
        if backup_digests:
            images = self._get_services_images()
            for service, image in images.items():
                digest = backup_digests[image]
                command = 'docker service update --image {digest} {service}'
                command = command.format(digest=digest, service=service)
                fabricio.run(command)

    @utils.once_per_command(block=True)
    def reset_stack_updated_status(self):
        self.stack_updated.clear()

    @property
    def current_settings(self):
        return self._get_settings(Image(self.current_settings_tag))

    @property
    def backup_settings(self):
        return self._get_settings(Image(self.backup_settings_tag))

    def _get_settings(self, image):
        with contextlib.suppress(ImageNotFoundError):
            image_labels = image.info.get('Config', {}).get('Labels', {})
            return (
                image_labels.get(self.compose_label),
                image_labels.get(self.images_info_label),
            )
        return None, None

    def rotate_sentinel_images(self, rollback=False):
        backup_tag = self.backup_settings_tag
        current_tag = self.current_settings_tag
        if rollback:
            backup_tag, current_tag = current_tag, backup_tag
        with contextlib.suppress(host_errors):
            fabricio.run(
                (
                    'docker rmi {backup_tag}'
                    '; docker tag {current_tag} {backup_tag}'
                    '; docker rmi {current_tag}'
                ).format(
                    backup_tag=backup_tag,
                    current_tag=current_tag,
                ),
            )

    def save_new_settings(self, settings, image):
        self.rotate_sentinel_images()

        labels = [(self.compose_label, settings)]
        with contextlib.suppress(host_errors):
            images = self.get_images()
            images and labels.append((self.images_info_label, images))

        dockerfile = (
            'FROM {image}\n'
            'LABEL {labels}\n'
        ).format(
            image=image or 'scratch',
            labels=' '.join(itertools.starmap('{0}={1}'.format, labels)),
        )
        build_command = 'echo {dockerfile} | docker build --tag {tag} -'.format(
            dockerfile=shlex_quote(dockerfile),
            tag=self.current_settings_tag,
        )
        try:
            fabricio.run(build_command)
        except host_errors as error:
            fabricio.log(
                'WARNING: {error}'.format(error=error),
                output=sys.stderr,
                color=colors.red,
            )

    def get_images(self):
        images = self._get_services_images()
        digests = self._get_digests(set(images.values()))
        bucket = json.dumps(digests, sort_keys=True)
        return b64encode(bucket.encode()).decode()

    def _get_services_images(self):
        command = "docker stack services --format '{{.Name}} {{.Image}}' %s"
        command %= self.name
        lines = filter(None, fabricio.run(command).splitlines())
        return dict(map(lambda line: line.rsplit(None, 1), lines))

    @staticmethod
    def _get_digests(images):
        images = list(images)
        if not images:
            return {}
        for image in images:
            fabricio.run(
                'docker pull %s' % image,
                ignore_errors=True,
                quiet=False,
                use_cache=True,
            )
        command = (
            "docker inspect --type image --format '{{index .RepoDigests 0}}' %s"
        ) % ' '.join(images)
        digests = fabricio.run(command, ignore_errors=True, use_cache=True)
        return dict(zip_longest(images, filter(None, digests.splitlines())))

    def get_backup_version(self):
        return self.fork(image=self.backup_settings_tag)
