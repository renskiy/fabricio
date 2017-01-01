import functools
import json
import warnings

import six

from docker import utils as docker_utils, auth as docker_auth

import fabricio

from fabricio import utils

from .registry import Registry


class ImageNotFoundError(RuntimeError):
    pass


class Image(object):

    name = None

    tag = None

    registry = None

    use_digest = False

    def __new__(cls, name=None, tag=None, registry=None):
        if isinstance(name, Image):
            return name[registry:tag]
        return super(Image, cls).__new__(cls)

    def __init__(self, name=None, tag=None, registry=None):
        if isinstance(name, six.string_types):
            _registry, _name, _tag = self.parse_image_name(name)
            self.name = _name
            self.tag = tag or _tag or 'latest'  # TODO 'latest' is unnecessary
            self.registry = Registry(registry or _registry)
            self.use_digest = tag is None and '@' in name
        self.field_names = {}  # descriptor's cache
        self.service = None

    def __str__(self):
        if self.service is not None:
            image_id = getattr(self.service, 'image_id', None)
            if image_id:
                return image_id
        return self.__repr__()

    def __repr__(self):
        if not self.name:
            raise ValueError('image name is not set or empty')
        tag_separator = '@' if self.use_digest else ':'
        registry = self.registry and '{0}/'.format(self.registry) or ''
        tag = self.tag and '{0}{1}'.format(tag_separator, self.tag) or ''
        return '{registry}{name}{tag}'.format(
            registry=registry,
            name=self.name,
            tag=tag,
        )

    def __get__(self, service, owner_cls):
        if service is None:
            return self
        field_name = self.get_field_name(owner_cls)
        image = service.__dict__.get(field_name)
        if image is None:
            image = service.__dict__[field_name] = self[:]

        # this causes circular reference between container and image, but it
        # isn't an issue due to a temporary nature of Fabric runtime
        image.service = service

        return image

    def __set__(self, service, image):
        field_name = self.get_field_name(type(service))
        service.__dict__[field_name] = self.__class__(image)

    def __getitem__(self, item):
        if isinstance(item, slice):
            registry, tag = item.start, item.stop
        else:
            registry, tag = None, item
        registry = registry or self.registry
        if self.use_digest and tag is None:
            name = '{name}@{digest}'.format(name=self.name, digest=self.tag)
        else:
            tag, name = tag or self.tag, self.name
        return self.__class__(name=name, tag=tag, registry=registry)

    def get_field_name(self, owner_cls):
        field_name = self.field_names.get(owner_cls)
        if field_name is None:
            for attr in dir(owner_cls):
                if getattr(owner_cls, attr) is self:
                    if field_name is not None:
                        raise ValueError(
                            'Same instance of Image used for more than one '
                            'attribute of class {cls}'.format(
                                cls=owner_cls.__name__,
                            )
                        )
                    self.field_names[owner_cls] = field_name = attr
        return field_name

    @staticmethod
    def parse_image_name(image):
        repository, tag = docker_utils.parse_repository_tag(image)
        registry, name = docker_auth.resolve_repository_name(repository)
        if registry == docker_auth.INDEX_NAME:
            registry = None
        return registry, name, tag

    @property
    def digest(self):
        if not self.use_digest:
            for repo_digest in self.info.get('RepoDigests', ()):
                return repo_digest
            raise RuntimeError('image has no digest')
        return repr(self)

    @utils.default_property
    def info(self):
        command = 'docker inspect --type image {image}'
        info = fabricio.run(
            command.format(image=self),
            abort_exception=ImageNotFoundError,
        )
        return json.loads(info)[0]

    def get_delete_callback(self, force=False):
        command = 'docker rmi {force}{image}'
        force = force and '--force ' or ''
        return functools.partial(
            fabricio.run,
            command.format(image=self, force=force),
            ignore_errors=True,
        )

    def delete(self, force=False, ignore_errors=True, deferred=False):
        delete_callback = self.get_delete_callback(force=force)
        if deferred:
            warnings.warn(
                'deferred argument is deprecated and will be removed in v0.4, '
                'use get_delete_callback() instead',
                category=RuntimeWarning, stacklevel=2,
            )
            return delete_callback
        return delete_callback(ignore_errors=ignore_errors)

    @classmethod
    def make_container_options(
        cls,
        temporary=None,
        name=None,
        options=(),
    ):
        override_options = {}
        if temporary:
            override_options['restart'] = None
        return utils.Options(
            options,
            name=name,
            rm=temporary,
            tty=temporary,
            interactive=temporary,
            detach=temporary is not None and not temporary,
            **override_options
        )

    def run(
        self,
        command=None,
        cmd=None,  # deprecated
        name=None,
        temporary=True,
        options=(),
        quiet=True,
        **kwargs  # deprecated
    ):
        if kwargs:
            warnings.warn(
                'Container options must be provided in `options` arg, '
                'kwargs behavior will be removed in v0.4',
                category=RuntimeWarning, stacklevel=2,
            )
            options = dict(options, **kwargs)
        if cmd:
            warnings.warn(
                "'cmd' argument deprecated and will be removed in v0.4, "
                "use 'command' instead",
                category=RuntimeWarning, stacklevel=2,
            )
        run_command = 'docker run {options} {image} {command}'
        return fabricio.run(
            run_command.format(
                image=self,
                command=command or cmd or '',
                options=self.make_container_options(
                    temporary=temporary,
                    name=name,
                    options=options,
                ),
            ),
            quiet=quiet,
        )

    def create(self, command=None, name=None, options=()):
        run_command = 'docker create {options} {image}{command}'
        return fabricio.run(
            run_command.format(
                image=self,
                command=command and ' {0}'.format(command) or '',
                options=self.make_container_options(name=name, options=options),
            ),
        )

    def pull(self):
        return fabricio.run(
            'docker pull {image}'.format(image=self),
            quiet=False,
        )
