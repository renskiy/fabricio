import six

from cached_property import cached_property
from fabric import api as fab
from six.moves import shlex_quote, urllib_parse, filter, reduce, map

import fabricio

from fabricio import docker, utils


class Configuration(docker.Stack):

    compose_file = None

    get_update_command = 'kubectl apply {options}'.format

    @property
    def current_settings_tag(self):
        return 'fabricio-current-kubernetes:{0}'.format(self.name)

    @property
    def backup_settings_tag(self):
        return 'fabricio-backup-kubernetes:{0}'.format(self.name)

    @docker.Option
    def filename(self):
        raise docker.ServiceError('must provide filename with configuration')

    @cached_property
    def _options(self):
        options = self._get_available_options()
        options.pop('compose_file', None)
        return options

    def is_manager(self):
        return fabricio.run(
            'kubectl config current-context',
            ignore_errors=True,
            use_cache=True,
        ).succeeded

    def read_configuration(self):
        return open(self.filename, 'rb').read()

    def upload_configuration(self, configuration):
        if not urllib_parse.urlparse(self.filename).scheme:
            # upload 'filename' if it is not URL
            fab.put(six.BytesIO(configuration), self.filename)

    def _revert(self):
        filename = 'fabricio.kubernetes.{name}.yml'.format(name=self.name)
        with utils.patch(self, 'filename', filename):
            super(Configuration, self)._revert()

    def _revert_images(self, digests):
        spec = self.__get_images_spec()
        for kind, images in spec.items():
            image_updates = ' '.join(
                '{0}={1}'.format(name, digests[image])
                for name, image in images.items()
            )
            command = 'kubectl set image {kind} {images}'
            command = command.format(kind=kind, images=image_updates)
            fabricio.run(command)

    @property
    def images(self):
        spec = self.__get_images_spec()
        return list(reduce(set.union, map(dict.values, spec.values()), set()))

    def __get_images_spec(self):
        template = (  # noqa
            '{{define "images"}}'
                '{{$kind := .kind}}'
                '{{$name := .metadata.name}}'
                '{{with .spec.template.spec.containers}}'
                    '{{range .}}'
                        r'{{$kind}}/{{$name}} {{.name}} {{.image}}{{"\n"}}'
                    '{{end}}'
                '{{end}}'
            '{{end}}'
            '{{if eq .kind "List"}}'
                '{{range .items}}{{template "images" .}}{{end}}'
            '{{else}}'
                '{{template "images" .}}'
            '{{end}}'
        )
        command = (
            'kubectl get'
            ' --output go-template'
            ' --filename {filename}'
            ' --template {template}'
            ''.format(
                template=shlex_quote(template),
                filename=shlex_quote(self.filename),
            )
        )

        result = dict()
        for line in filter(None, fabricio.run(command).splitlines()):
            kind, image_spec = line.split(None, 1)
            name, image = image_spec.rsplit(None, 1)
            result.setdefault(kind, dict())[name] = image

        return result
