import collections
import json
import re
import sys

import dpath
import six

from cached_property import cached_property
from fabric import colors
from frozendict import frozendict

import fabricio

from fabricio import utils

from .base import BaseService, Option, Attribute
from .container import Container, ContainerNotFoundError


class ServiceNotFoundError(RuntimeError):
    pass


class ServiceCannotBeRevertedError(RuntimeError):
    pass


class RemovableOption(Option):

    path = None

    value_type = six.text_type

    def __init__(self, func=None, path=None, **kwargs):
        super(RemovableOption, self).__init__(func=func, **kwargs)
        self.path = path or self.path

    def get_current_values(self, service_info):
        if '*' in self.path:
            return dpath.util.values(service_info, self.path)
        try:
            return dpath.util.get(service_info, self.path)
        except KeyError:
            return []

    def get_values_to_remove(self, service_info, new_values):
        current_values = self.get_current_values(service_info)
        if not current_values:
            return None
        new_values = self.normalize_new_values(new_values)
        return list(set(map(str, current_values)).difference(new_values))

    def normalize_new_values(self, new_values):
        if new_values is None:
            return []
        if isinstance(new_values, six.string_types):
            return [self.value_type(new_values)]
        return map(self.value_type, new_values)


class Label(RemovableOption):

    class value_type(utils.Item):

        def get_comparison_value(self):
            # fetch label key
            return self.split('=', 1)[0]


class Env(Label):

    path = '/Spec/TaskTemplate/ContainerSpec/Env/*'

    def get_current_values(self, *args, **kwargs):
        values = super(Env, self).get_current_values(*args, **kwargs)
        return map(
            self.value_type.get_comparison_value,
            map(self.value_type, values),
        )


class Port(RemovableOption):

    path = '/Spec/EndpointSpec/Ports/*/TargetPort'

    class value_type(utils.Item):

        def get_comparison_value(self):
            # fetch target port
            return self.rsplit('/', 1)[0].rsplit(':', 1)[-1]


class Mount(RemovableOption):

    path = '/Spec/TaskTemplate/ContainerSpec/Mounts/*/Target'

    class value_type(utils.Item):

        comparison_value_re = re.compile(
            'destination=(?P<quote>[\'"]?)(?P<dst>.*?)(?P=quote)(?:,|$)',
            flags=re.UNICODE,
        )

        def get_comparison_value(self):
            # fetch target path
            match = self.comparison_value_re.search(self)
            return match and match.group('dst')


class Service(BaseService):

    current_options_label_name = '_current_options'
    backup_options_label_name = '_backup_options'

    ignore_worker_errors = Attribute(default=True)

    command = Attribute()
    args = Attribute()

    labels = Label(name='label', path='/Spec/Labels')
    container_labels = Label(
        name='container-label',
        path='/Spec/TaskTemplate/ContainerSpec/Labels',
        safe=False,
    )
    constraints = RemovableOption(
        name='constraint',
        path='/Spec/TaskTemplate/Placement/Constraints/*',
        safe=False,
    )
    replicas = Option(default=1, safe=False)
    mounts = Mount(name='mount', safe=False)
    network = Option()
    restart_condition = Option(name='restart-condition', safe=False)
    stop_timeout = Option(name='stop-grace-period', default='10s', safe=False)
    env = Env()
    ports = Port(name='publish', safe=False)
    user = Option()

    @utils.default_property
    def image_id(self):
        return self.info['Spec']['TaskTemplate']['ContainerSpec']['Image']

    def get_backup_version(self):
        label_name = self.backup_options_label_name
        backup_options = json.loads(self.info['Spec']['Labels'][label_name])
        backup_service = self.fork(image=backup_options['image'])
        backup_service.image_id = None
        return backup_service

    @cached_property
    def _update_options(self):
        options = {}
        for cls in type(self).__mro__[::-1]:
            for attr, option in vars(cls).items():
                if isinstance(option, Option):
                    def add_values(service, attr=attr):
                        return getattr(service, attr)
                    name = option.name or attr
                    if isinstance(option, RemovableOption):
                        rm_values = self._RmValuesGetter
                        options[name + '-rm'] = rm_values(option, attr)
                        options[name + '-add'] = add_values
                    else:
                        options[name] = add_values
        return options

    @property
    def update_options(self):
        return frozendict(
            (
                (option, callback(self))
                for option, callback in self._update_options.items()
            ),
            args=self.args,
            network=None,  # network can't be updated
            **self._additional_options
        )

    def _update_service(self, options):
        fabricio.run('docker service update {options} {service}'.format(
            options=options,
            service=self,
        ))

    def _create_service(self, image):
        command = 'docker service create {options} {image} {command} {args}'
        fabricio.run(command.format(
            options=utils.Options(self.options, name=self),
            image=image,
            command=(
                '"{0}"'.format((self.command or '').replace('"', '\\"'))
                if self.command or self.args else
                ''
            ),
            args=self.args or '',
        ))

    @utils.once_per_command
    def _update(self, image, force=False):
        try:
            service_info = self.info
        except ServiceNotFoundError:
            service_info = {}

        with utils.patch(self, 'info', service_info, force_delete=True):
            labels = service_info.get('Spec', {}).get('Labels', {})
            current_options = labels.pop(self.current_options_label_name, '{}')
            labels.pop(self.backup_options_label_name, None)

            update_options = dict(self.update_options, image=image)

            if force or self._service_need_update(
                options_old=json.loads(current_options),
                options_new=update_options,
            ):
                new_labels = {self.current_options_label_name: json.dumps(
                    update_options,
                    default=six.text_type
                )}
                if service_info:
                    new_labels[self.backup_options_label_name] = current_options
                self._update_labels(**new_labels)

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
            current.rename(self.revert_sentinel_name)
            current.rename(self.backup_sentinel_name)
        except RuntimeError:
            pass

    def update(self, tag=None, registry=None, force=False):
        image = self.image[registry:tag]
        with utils.patch(image, 'info', image.info, force_delete=True):
            try:
                self._update_sentinels(image)
            except RuntimeError as error:
                fabricio.log(
                    'WARNING: {error}'.format(error=error),
                    output=sys.stderr,
                    color=colors.red,
                )
            if not self.is_manager():
                return False
            result = self._update(image.digest, force=force)
            return result or result is None

    def _service_need_update(self, options_old, options_new):
        useless_options_new = 0
        for option, new_value in options_new.items():
            if not (
                self._rm_values_getter(option) is None
                and option in options_old
            ):
                if new_value:
                    return True
                else:
                    useless_options_new += 1
                    continue
            old_value = options_old[option]
            if isinstance(new_value, six.string_types):
                new_value = [new_value]
            if isinstance(old_value, six.string_types):
                old_value = [old_value]
            if (
                isinstance(new_value, collections.Iterable)
                or isinstance(old_value, collections.Iterable)
            ):
                try:
                    if set(new_value) != set(old_value):
                        return True
                    else:
                        continue
                except TypeError:
                    pass
            if bool(new_value) != bool(old_value):
                return True
            if (new_value or old_value) and new_value != old_value:
                return True
        useless_options_old = sum(
            self._rm_values_getter(option) is not None
            for option, value in options_old.items()
        )
        len_options_old = len(options_old) - useless_options_old
        len_options_new = len(options_new) - useless_options_new
        return len_options_old != len_options_new

    def _rm_values_getter(self, option):
        option_getter = self._update_options.get(option)
        if isinstance(option_getter, self._RmValuesGetter):
            return option_getter

    def _options_revert_patch(self, backup_options):
        service = utils.AttrDict(backup_options, info=self.info)
        result = utils.Options(
            (option, value)
            for option, value in backup_options.items()
            if self._rm_values_getter(option) is None
        )
        for option in self._update_options:
            if option.endswith('-add'):
                rm_option = option[:-4] + '-rm'
                rm_option_getter = self._rm_values_getter(rm_option)

                if rm_option_getter is not None:
                    service.setdefault(option)
                    rm_option_value = rm_option_getter(service, attr=option)
                    if rm_option_value:
                        result[rm_option] = rm_option_value
        return result

    @utils.once_per_command
    def _revert(self):
        with utils.patch(self, 'info', self.info, force_delete=True):
            try:
                labels = self.info['Spec']['Labels']
                backup_options = labels[self.backup_options_label_name]
            except KeyError:
                raise ServiceCannotBeRevertedError
            decoded_backup_options = json.loads(backup_options)
            label_add = decoded_backup_options.get('label-add') or []
            if not isinstance(label_add, list):
                label_add = [label_add]
            label_add.append('{label}={value}'.format(
                label=self.current_options_label_name,
                value=backup_options.replace('"', '\\"'),
            ))
            decoded_backup_options['label-add'] = label_add
            update_options = self._options_revert_patch(decoded_backup_options)
            self._update_service(utils.Options(update_options))

    def revert(self):
        self._revert_sentinels()
        if self.is_manager():
            self._revert()

    def pull_image(self, tag=None, registry=None):
        try:
            return super(Service, self).pull_image(tag=tag, registry=registry)
        except RuntimeError:
            if not self.ignore_worker_errors or self.is_manager():
                raise

    def migrate(self, tag=None, registry=None):
        if self.is_manager():
            super(Service, self).migrate(tag=tag, registry=registry)

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

    @staticmethod
    def is_manager():
        return fabricio.run(
            "docker info 2>&1 | grep 'Is Manager:'",
            use_cache=True,
        ).endswith('true')

    def _update_labels(self, **labels):
        service_labels = self.labels
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
            service_labels.append("{label}={value}".format(
                label=label,
                value=value.replace('"', '\\"'),
            ))
        self.labels = service_labels

    class _RmValuesGetter(object):

        def __init__(self, option, attr):
            # type: (RemovableOption, str) -> None
            self.option = option
            self.attr = attr

        def __call__(self, service, attr=None):
            return self.option.get_values_to_remove(
                service_info=service.info,
                new_values=getattr(service, attr or self.attr),
            )
