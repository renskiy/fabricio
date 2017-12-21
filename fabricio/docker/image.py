import json
import warnings

import docker.auth
import docker.utils
import six

from functools import partial

import fabricio

from fabricio import utils

from .registry import Registry


class ImageError(RuntimeError):
    pass


class ImageNotFoundError(ImageError):
    pass


class Image(object):

    name = None

    tag = None

    registry = None

    use_digest = False

    @property
    def temp_tag(self):
        return 'fabricio-temp-image:' + self.name.rsplit('/')[-1]

    def __new__(cls, name=None, tag=None, registry=None):
        if isinstance(name, Image):
            return name[registry:tag]
        return super(Image, cls).__new__(cls)

    def __init__(self, name=None, tag=None, registry=None):
        if name is not None and not isinstance(name, Image):
            _registry, _name, _tag = self.parse_image_name(name)
            self.name = _name
            self.tag = tag or _tag or 'latest'  # TODO 'latest' is unnecessary
            self.registry = Registry(registry or _registry)
            self.use_digest = not tag and '@' in name
        self.field_names = {}  # descriptor's cache
        self.service = None

    def __str__(self):
        if self.service is not None:
            image_id = getattr(self.service, 'image_id', None)
            if image_id:
                return image_id
        return super(Image, self).__str__()

    def __repr__(self):
        if not self.name:
            raise ImageError('image name is not set or empty')
        tag_separator = '@' if self.use_digest else ':'
        registry = self.registry and '{0}/'.format(self.registry) or ''
        tag = self.tag and '{0}{1}'.format(tag_separator, self.tag) or ''
        return '{registry}{name}{tag}'.format(
            registry=registry,
            name=self.name,
            tag=tag,
        )

    def __bool__(self):
        try:
            return bool(repr(self))
        except ImageError:
            return False

    def __nonzero__(self):
        return self.__bool__()

    def __get__(self, service, owner_cls):
        if service is None:
            return self
        field_name = self.get_field_name(owner_cls)
        if field_name not in service.__dict__:
            image = service.__dict__[field_name] = self[:]
            image.service = service
        return service.__dict__[field_name]

    def __set__(self, service, image):
        field_name = self.get_field_name(type(service))
        image = self.__class__(image)
        image.service = service
        service.__dict__[field_name] = image

    def __getitem__(self, item):
        if isinstance(item, slice):
            registry, tag, account = item.start, item.stop, item.step
        else:
            registry, tag, account = None, item, None

        use_digest = self.use_digest

        # tag can override image registry, name and/or digest
        _registry, _name, _tag = self.parse_image_name(tag)
        if not _tag:
            if _registry:
                _tag = 'latest'
            else:
                _tag, _name = _name, None
        if _tag:
            use_digest = _name and tag and '@' in tag

        registry = _registry or registry or self.registry
        name = _name or account and self.name and '{account}/{name}'.format(
            account=account,
            name=self.name.split('/')[-1],
        ) or self.name
        tag = _tag or tag or self.tag

        if use_digest:
            name = '{name}@{digest}'.format(name=name, digest=tag)
            tag = None

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
        if not image:
            return None, None, None
        repository, tag = docker.utils.parse_repository_tag(image)
        registry, name = docker.auth.resolve_repository_name(repository)
        if registry == docker.auth.INDEX_NAME:
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
        return partial(
            fabricio.run,
            command.format(image=self, force=force),
            ignore_errors=True,
        )

    def delete(self, force=False, ignore_errors=True):
        delete_callback = self.get_delete_callback(force=force)
        return delete_callback(ignore_errors=ignore_errors)

    @classmethod
    def make_container_options(
        cls,
        temporary=None,
        name=None,
        options=(),
    ):
        return utils.Options(
            options,
            name=name,
            rm=temporary,
            tty=temporary,
            interactive=temporary,
            detach=temporary is not None and not temporary,
        )

    def run(
        self,
        command=None,
        name=None,
        temporary=True,
        options=(),
        quiet=True,
    ):
        run_command = 'docker run {options} {image} {command}'
        return fabricio.run(
            run_command.format(
                image=self,
                command=command or '',
                options=self.make_container_options(
                    temporary=temporary,
                    name=name,
                    options=options,
                ),
            ),
            quiet=quiet,
        )

    def create(self, command=None, name=None, options=()):  # pragma: no cover
        warnings.warn('Image.create() is deprecated', DeprecationWarning)
        warnings.warn(
            'Image.create() is deprecated',
            RuntimeWarning, stacklevel=2,
        )
        run_command = 'docker create {options} {image} {command}'.rstrip()
        return fabricio.run(
            run_command.format(
                image=self,
                command=command or '',
                options=self.make_container_options(name=name, options=options),
            ),
        )

    def pull(self, local=False, use_cache=False, ignore_errors=False):
        run = fabricio.local if local else fabricio.run
        run = partial(run, use_cache=use_cache, ignore_errors=ignore_errors)
        run_ignore_errors = partial(run, ignore_errors=True)

        image = six.text_type(self)

        run_ignore_errors(
            'docker tag {image} {tag} '
            '&& docker rmi {image}'.format(image=image, tag=self.temp_tag)
        )
        pull_result = run('docker pull ' + image, quiet=False)
        if pull_result.succeeded:
            run_ignore_errors('docker rmi {tag}'.format(tag=self.temp_tag))

    def build(self, local=False, build_path='.', options=None, use_cache=False):
        if local:
            run = fabricio.local
            run_capture_output = partial(run, capture=True)
        else:
            run = run_capture_output = fabricio.run
        run = partial(run, use_cache=use_cache)
        run_capture_output = partial(run_capture_output, use_cache=use_cache)
        run_ignore_errors = partial(run, ignore_errors=True)

        image = six.text_type(self)
        options = options or utils.Options()
        options['tag'] = image

        # default options
        options.setdefault('pull', 1)
        options.setdefault('force-rm', 1)

        with utils.patch(fabricio, 'run', run_capture_output):
            try:
                old_parent_id = self.info['Parent']
            except ImageNotFoundError:
                old_parent_id = ''

        run_ignore_errors(
            'docker tag {image} {tag} '
            '&& docker rmi {image}'.format(image=image, tag=self.temp_tag)
        )
        run(
            'docker build {options} {build_path}'.format(
                options=options,
                build_path=build_path,
            ),
            quiet=False,
        )
        run_ignore_errors('docker rmi {tag} {old_parent}'.format(
            tag=self.temp_tag,
            old_parent=old_parent_id,
        ))
