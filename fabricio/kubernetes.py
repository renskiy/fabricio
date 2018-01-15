from fabric import api as fab
from six.moves import shlex_quote, filter, reduce, map

import fabricio

from fabricio import docker, utils


class Configuration(docker.Stack):

    get_update_command = 'kubectl apply {options}'.format

    @property
    def current_settings_tag(self):
        return 'fabricio-current-kubernetes:{0}'.format(self.name)

    @property
    def backup_settings_tag(self):
        return 'fabricio-backup-kubernetes:{0}'.format(self.name)

    @docker.Option(name='filename')
    def config(self):
        raise docker.ServiceError("must provide 'config' or 'filename' option")

    def _is_manager(self):
        return fabricio.run(
            'kubectl config current-context',
            ignore_errors=True,
        ).succeeded

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
                filename=shlex_quote(self.config),
            )
        )

        result = dict()
        for line in filter(None, fabricio.run(command).splitlines()):
            kind, image_spec = line.split(None, 1)
            name, image = image_spec.rsplit(None, 1)
            result.setdefault(kind, dict())[name] = image

        return result

    def destroy(self, **options):
        """
        any passed argument will be forwarded to 'kubectl delete' as option
        """
        super(Configuration, self).destroy(**options)

    @fabricio.once_per_task(block=True)
    def _destroy(self, **options):
        configuration, _ = self.current_settings

        if not configuration:
            raise docker.ServiceError('current configuration not found')

        with fab.cd(self.temp_dir):
            self.upload_configuration(configuration)

            options = utils.Options(options)
            options.setdefault('filename', self.config)
            fabricio.run('kubectl delete {options}'.format(options=options))
