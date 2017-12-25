import itertools
import json
import multiprocessing
import sys

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

    compose_file = Option(name='compose-file', default='docker-compose.yml')

    configuration_label = 'fabricio.configuration'

    digests_label = 'fabricio.digests'

    get_update_command = 'docker stack deploy {options} {name}'.format

    def __init__(self, *args, **kwargs):
        super(Stack, self).__init__(*args, **kwargs)
        self._updated = multiprocessing.Event()

    @property
    def current_settings_tag(self):
        return 'fabricio-current-stack:{0}'.format(self.name)

    @property
    def backup_settings_tag(self):
        return 'fabricio-backup-stack:{0}'.format(self.name)

    def read_configuration(self):
        return open(self.compose_file, 'rb').read()

    def upload_configuration(self, configuration):
        fab.put(six.BytesIO(configuration), self.compose_file)

    def update(self, tag=None, registry=None, account=None, force=False):
        if not self.is_manager():
            return None

        self.reset_update_status()

        configuration = self.read_configuration()
        new_settings = b64encode(configuration).decode()

        with fab.cd(self.temp_dir):
            self.upload_configuration(configuration)

            result = self._update(new_settings, force=force)

            if self._updated.is_set():
                image = self.image[registry:tag:account]
                self.save_new_settings(new_settings, image)

            return result is None or result

    @utils.once_per_command(block=True)
    def _update(self, new_settings, force=False, set_update_status=True):
        if not force:
            settings, digests = self.current_settings
            digests = digests and json.loads(b64decode(digests).decode())
            if settings == new_settings and digests is not None:
                new_digests = self._get_digests(digests)
                if digests == new_digests:
                    return False

        options = utils.Options(self.options)
        fabricio.run(self.get_update_command(options=options, name=self.name))

        if set_update_status:
            self._updated.set()

        return True

    def revert(self):
        if not self.is_manager():
            return
        self.reset_update_status()
        self._revert()
        if self._updated.is_set():
            self.rotate_sentinel_images(rollback=True)

    @utils.once_per_command(block=True)
    def _revert(self):
        settings, digests = self.backup_settings
        if not settings:
            raise ServiceError('service backup not found')

        with fab.cd(self.temp_dir):
            configuration = b64decode(settings)
            self.upload_configuration(configuration)

            self._update(settings, force=True, set_update_status=False)

            digests = digests and b64decode(digests).decode()
            digests = digests and json.loads(digests)
            if digests:
                self._revert_images(digests)

        # set updated status if everything was OK
        self._updated.set()

    def _revert_images(self, digests):
        images = self.__get_images()
        for service, image in images.items():
            digest = digests[image]
            command = 'docker service update --image {digest} {service}'
            command = command.format(digest=digest, service=service)
            fabricio.run(command)

    @utils.once_per_command(block=True)
    def reset_update_status(self):
        self._updated.clear()

    @property
    def current_settings(self):
        return self._get_settings(Image(self.current_settings_tag))

    @property
    def backup_settings(self):
        return self._get_settings(Image(self.backup_settings_tag))

    def _get_settings(self, image):
        try:
            labels = image.info.get('Config', {}).get('Labels', {})
            return (
                labels.get(self.configuration_label),
                labels.get(self.digests_label),
            )
        except ImageNotFoundError:
            return None, None

    def rotate_sentinel_images(self, rollback=False):
        backup_tag = self.backup_settings_tag
        current_tag = self.current_settings_tag
        if rollback:
            backup_tag, current_tag = current_tag, backup_tag
        with contextlib.suppress(utils.host_errors):
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

        labels = [(self.configuration_label, settings)]
        with contextlib.suppress(utils.host_errors):
            digests = self._get_digests(self.images)
            bucket = json.dumps(digests, sort_keys=True)
            bucket = b64encode(bucket.encode()).decode()
            labels.append((self.digests_label, bucket))

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
        except utils.host_errors as error:
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
