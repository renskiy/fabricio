import itertools
import json
import sys
import warnings

from base64 import b64encode, b64decode

import contextlib2 as contextlib
import six

from fabric import colors, api as fab
from six.moves import map, shlex_quote, filter, zip_longest

import fabricio

from fabricio import utils

from .base import ManagedService, Option, Attribute, ServiceError
from .image import Image, ImageNotFoundError


class Stack(ManagedService):

    image_id = None

    info = None

    temp_dir = Attribute(default='/tmp')

    config = Option(name='compose-file', default='docker-compose.yml')

    @property
    def compose_file(self):  # pragma: no cover
        warnings.warn(
            "'compose_file' option is deprecated and will be removed in v0.6, "
            "use 'config' or 'compose-file' instead", DeprecationWarning,
        )
        return self.config

    configuration_label = 'fabricio.configuration'

    digests_label = 'fabricio.digests'

    get_update_command = 'docker stack deploy {options} {name}'.format

    def __init__(self, *args, **kwargs):
        options = kwargs.setdefault('options', {})
        if 'compose_file' in options:  # pragma: no cover
            warnings.warn(
                "'compose_file' option is deprecated and will be removed"
                " in v0.6, use 'config' or 'compose-file' instead",
                RuntimeWarning, stacklevel=2,
            )
            options.setdefault('config', options['compose_file'])

        super(Stack, self).__init__(*args, **kwargs)

    @property
    def current_settings_tag(self):
        return 'fabricio-current-stack:{0}'.format(self.name)

    @property
    def backup_settings_tag(self):
        return 'fabricio-backup-stack:{0}'.format(self.name)

    def upload_configuration(self, configuration):
        fab.put(six.BytesIO(configuration), self.config)

    def update(self, tag=None, registry=None, account=None, force=False):
        if not self.is_manager():
            return None

        configuration = open(self.config, 'rb').read()
        with fab.cd(self.temp_dir):
            self.upload_configuration(configuration)
            updated = self._update(configuration, force=force)

            if updated:
                self.save_new_settings(
                    configuration=configuration,
                    image=self.image[registry:tag:account],
                )

        return updated

    @fabricio.once_per_task(block=True)
    def _update(self, new_configuration, force=False):
        if not force:
            configuration, digests = self.current_settings
            if configuration == new_configuration and digests is not None:
                new_digests = self._get_digests(digests)
                if digests == new_digests:
                    return False

        options = utils.Options(self.options)
        command = self.get_update_command(options=options, name=self.name)
        fabricio.run(command)

        return True

    def revert(self):
        if not self.is_manager():
            return
        with fab.cd(self.temp_dir):
            self._revert()
        if self._revert.has_result():
            self.rotate_sentinel_images(rollback=True)

    @fabricio.once_per_task(block=True)
    def _revert(self):
        configuration, digests = self.backup_settings

        if configuration is None:
            raise ServiceError('backup configuration not found')

        self.upload_configuration(configuration)

        self._update(configuration, force=True)

        if digests:
            self._revert_images(digests)

    def _revert_images(self, digests):
        images = self.__get_images()
        for service, image in images.items():
            digest = digests[image]
            command = 'docker service update --image {digest} {service}'
            command = command.format(digest=digest, service=service)
            fabricio.run(command)

    @property
    def current_settings(self):
        return self._get_settings(Image(self.current_settings_tag))

    @property
    def backup_settings(self):
        return self._get_settings(Image(self.backup_settings_tag))

    def _get_settings(self, image):
        try:
            labels = image.info.get('Config', {}).get('Labels', {})
            configuration = labels.get(self.configuration_label)
            configuration = configuration and b64decode(configuration)
            digests = labels.get(self.digests_label)
            digests = digests and json.loads(b64decode(digests).decode())
            return configuration, digests
        except ImageNotFoundError:
            return None, None

    def rotate_sentinel_images(self, rollback=False):
        backup_tag = self.backup_settings_tag
        current_tag = self.current_settings_tag
        if rollback:
            backup_tag, current_tag = current_tag, backup_tag

        backup_images = [backup_tag]
        with contextlib.suppress(ImageNotFoundError):
            backup_images.append(Image(backup_tag).info['Parent'])

        with contextlib.suppress(fabricio.host_errors):
            # TODO make separate call for each docker command
            fabricio.run(
                (
                    'docker rmi {backup_images}'
                    '; docker tag {current_tag} {backup_tag}'
                    '; docker rmi {current_tag}'
                ).format(
                    backup_images=' '.join(backup_images),
                    current_tag=current_tag,
                    backup_tag=backup_tag,
                ),
            )

    def save_new_settings(self, configuration, image):
        self.rotate_sentinel_images()

        labels = [(self.configuration_label, b64encode(configuration).decode())]
        with contextlib.suppress(fabricio.host_errors):
            digests = self._get_digests(self.images)
            digests_bucket = json.dumps(digests, sort_keys=True)
            digests_bucket = b64encode(digests_bucket.encode()).decode()
            labels.append((self.digests_label, digests_bucket))

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
        except fabricio.host_errors as error:
            fabricio.log(
                'WARNING: {error}'.format(error=error),
                output=sys.stderr,
                color=colors.red,
            )

    @property
    def images(self):
        images = self.__get_images()
        return list(set(images.values()))

    def __get_images(self):
        command = 'docker stack services --format "{{.Name}} {{.Image}}" %s'
        command %= self.name
        lines = filter(None, fabricio.run(command).splitlines())
        return dict(map(lambda line: line.rsplit(None, 1), lines))

    @staticmethod
    def _get_digests(images):
        if not images:
            return {}

        for image in images:
            Image(image).pull(use_cache=True, ignore_errors=True)

        command = (
            'docker inspect --type image --format "{{index .RepoDigests 0}}" %s'
        ) % ' '.join(images)
        digests = fabricio.run(command, ignore_errors=True, use_cache=True)

        return dict(zip_longest(images, filter(None, digests.splitlines())))

    def get_backup_version(self):
        return self.fork(image=self.backup_settings_tag)

    def destroy(self, **options):
        """
        any passed argument will be forwarded to 'docker stack rm' as option
        """
        if self.is_manager():
            self._destroy(**options)
            if self._destroy.has_result():
                self.remove_sentinel_images()

    def remove_sentinel_images(self):
        images = [self.current_settings_tag, self.backup_settings_tag]
        with contextlib.suppress(ImageNotFoundError):
            images.append(Image(self.current_settings_tag).info['Parent'])
            images.append(Image(self.backup_settings_tag).info['Parent'])
        fabricio.run(
            'docker rmi {images}'.format(images=' '.join(images)),
            ignore_errors=True,
        )

    @fabricio.once_per_task(block=True)
    def _destroy(self, **options):
        fabricio.run('docker stack rm {options} {name}'.format(
            options=utils.Options(options),
            name=self.name,
        ))
