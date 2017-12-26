import collections
import functools
import json

import mock
import six

from fabric import api as fab

import fabricio

from fabricio import docker, utils, kubernetes
from fabricio.docker import stack as stack_module
from tests import SucceededResult, args_parser, FabricioTestCase, FailedResult


def as_ordereddict(result):
    return collections.OrderedDict(sorted(result.items()))


class StackTestCase(FabricioTestCase):

    def setUp(self):
        kubernetes.open = mock.MagicMock()
        self.cd = mock.patch.object(fab, 'cd')
        self.cd.start()

    def tearDown(self):
        kubernetes.open = open
        self.cd.stop()

    @mock.patch.object(fabricio, 'log')
    @mock.patch.object(stack_module, 'dict', new=collections.OrderedDict)
    @mock.patch.object(kubernetes, 'dict', new=collections.OrderedDict)
    @mock.patch.object(kubernetes, 'set', new=utils.OrderedSet)
    @mock.patch.object(json, 'loads', new=functools.partial(json.loads, object_hook=as_ordereddict))
    @mock.patch.object(fab, 'put')
    def test_update(self, put, *args):
        cases = dict(
            worker=dict(
                init_kwargs=dict(),
                update_kwargs={},
                side_effect=[
                    FailedResult(),  # manager status
                ],
                expected_command_args=[
                    {'args': ['kubectl', 'config', 'current-context']},
                ],
                expected_result=None,
                all_hosts=['host1', 'host2'],
            ),
            no_changes=dict(
                init_kwargs=dict(),
                update_kwargs={},
                side_effect=[
                    SucceededResult(),  # manager status
                    SucceededResult(json.dumps([{'Config': {
                        'Labels': {
                            'fabricio.configuration': 'azhzLnltbA==',  # k8s.yml
                            'fabricio.digests': 'e30=',  # {}
                        },
                    }}])),  # image info
                ],
                expected_command_args=[
                    {'args': ['kubectl', 'config', 'current-context']},
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-current-kubernetes:k8s']},
                ],
                expected_result=False,
                expected_compose_file='k8s.yml',
                should_upload_compose_file=True,
            ),
            forced=dict(
                init_kwargs=dict(),
                update_kwargs=dict(force=True),
                side_effect=[
                    SucceededResult(),  # manager status
                    SucceededResult(),  # configuration deploy
                    fabricio.Error(),  # update sentinel images
                    SucceededResult(),  # configuration images
                    SucceededResult(),  # build new sentinel image
                ],
                expected_command_args=[
                    {'args': ['kubectl', 'config', 'current-context']},
                    {'args': ['kubectl', 'apply', '--filename=k8s.yml']},
                    {'args': ['docker', 'rmi', 'fabricio-backup-kubernetes:k8s;', 'docker', 'tag', 'fabricio-current-kubernetes:k8s', 'fabricio-backup-kubernetes:k8s;', 'docker', 'rmi', 'fabricio-current-kubernetes:k8s']},
                    {'args': ['kubectl', 'get', '--output', 'go-template', '--filename', 'k8s.yml', '--template', r'{{define "images"}}{{$kind := .kind}}{{$name := .metadata.name}}{{with .spec.template.spec.containers}}{{range .}}{{$kind}}/{{$name}} {{.name}} {{.image}}{{"\n"}}{{end}}{{end}}{{end}}{{if eq .kind "List"}}{{range .items}}{{template "images" .}}{{end}}{{else}}{{template "images" .}}{{end}}']},
                    {'args': ['echo', 'FROM scratch\nLABEL fabricio.configuration=azhzLnltbA== fabricio.digests=e30=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-kubernetes:k8s', '-']},
                ],
                expected_result=True,
                expected_compose_file='k8s.yml',
                should_upload_compose_file=True,
            ),
            created=dict(
                init_kwargs=dict(),
                update_kwargs=dict(),
                side_effect=[
                    SucceededResult(),  # manager status
                    docker.ImageNotFoundError(),  # image info
                    SucceededResult(),  # configuration deploy
                    SucceededResult(),  # update sentinel images
                    SucceededResult(),  # configuration images
                    SucceededResult(),  # build new sentinel image
                ],
                expected_command_args=[
                    {'args': ['kubectl', 'config', 'current-context']},
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-current-kubernetes:k8s']},
                    {'args': ['kubectl', 'apply', '--filename=k8s.yml']},
                    {'args': ['docker', 'rmi', 'fabricio-backup-kubernetes:k8s;', 'docker', 'tag', 'fabricio-current-kubernetes:k8s', 'fabricio-backup-kubernetes:k8s;', 'docker', 'rmi', 'fabricio-current-kubernetes:k8s']},
                    {'args': ['kubectl', 'get', '--output', 'go-template', '--filename', 'k8s.yml', '--template', r'{{define "images"}}{{$kind := .kind}}{{$name := .metadata.name}}{{with .spec.template.spec.containers}}{{range .}}{{$kind}}/{{$name}} {{.name}} {{.image}}{{"\n"}}{{end}}{{end}}{{end}}{{if eq .kind "List"}}{{range .items}}{{template "images" .}}{{end}}{{else}}{{template "images" .}}{{end}}']},
                    {'args': ['echo', 'FROM scratch\nLABEL fabricio.configuration=azhzLnltbA== fabricio.digests=e30=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-kubernetes:k8s', '-']},
                ],
                expected_result=True,
                expected_compose_file='k8s.yml',
                should_upload_compose_file=True,
            ),
            created_skip_sentinels_errors=dict(
                init_kwargs=dict(),
                update_kwargs=dict(),
                side_effect=[
                    SucceededResult(),  # manager status
                    docker.ImageNotFoundError(),  # image info
                    SucceededResult(),  # configuration deploy
                    fabricio.Error(),  # update sentinel images
                    fabricio.Error(),  # configuration images
                    fabricio.Error(),  # build new sentinel image
                ],
                expected_command_args=[
                    {'args': ['kubectl', 'config', 'current-context']},
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-current-kubernetes:k8s']},
                    {'args': ['kubectl', 'apply', '--filename=k8s.yml']},
                    {'args': ['docker', 'rmi', 'fabricio-backup-kubernetes:k8s;', 'docker', 'tag', 'fabricio-current-kubernetes:k8s', 'fabricio-backup-kubernetes:k8s;', 'docker', 'rmi', 'fabricio-current-kubernetes:k8s']},
                    {'args': ['kubectl', 'get', '--output', 'go-template', '--filename', 'k8s.yml', '--template', r'{{define "images"}}{{$kind := .kind}}{{$name := .metadata.name}}{{with .spec.template.spec.containers}}{{range .}}{{$kind}}/{{$name}} {{.name}} {{.image}}{{"\n"}}{{end}}{{end}}{{end}}{{if eq .kind "List"}}{{range .items}}{{template "images" .}}{{end}}{{else}}{{template "images" .}}{{end}}']},
                    {'args': ['echo', 'FROM scratch\nLABEL fabricio.configuration=azhzLnltbA==\n', '|', 'docker', 'build', '--tag', 'fabricio-current-kubernetes:k8s', '-']},
                ],
                expected_result=True,
                expected_compose_file='k8s.yml',
                should_upload_compose_file=True,
            ),
            created_with_custom_image=dict(
                init_kwargs=dict(image='image:tag'),
                update_kwargs=dict(),
                side_effect=[
                    SucceededResult(),  # manager status
                    docker.ImageNotFoundError(),  # image info
                    SucceededResult(),  # configuration deploy
                    SucceededResult(),  # update sentinel images
                    SucceededResult(),  # configuration images
                    SucceededResult(),  # build new sentinel image
                ],
                expected_command_args=[
                    {'args': ['kubectl', 'config', 'current-context']},
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-current-kubernetes:k8s']},
                    {'args': ['kubectl', 'apply', '--filename=k8s.yml']},
                    {'args': ['docker', 'rmi', 'fabricio-backup-kubernetes:k8s;', 'docker', 'tag', 'fabricio-current-kubernetes:k8s', 'fabricio-backup-kubernetes:k8s;', 'docker', 'rmi', 'fabricio-current-kubernetes:k8s']},
                    {'args': ['kubectl', 'get', '--output', 'go-template', '--filename', 'k8s.yml', '--template', r'{{define "images"}}{{$kind := .kind}}{{$name := .metadata.name}}{{with .spec.template.spec.containers}}{{range .}}{{$kind}}/{{$name}} {{.name}} {{.image}}{{"\n"}}{{end}}{{end}}{{end}}{{if eq .kind "List"}}{{range .items}}{{template "images" .}}{{end}}{{else}}{{template "images" .}}{{end}}']},
                    {'args': ['echo', 'FROM image:tag\nLABEL fabricio.configuration=azhzLnltbA== fabricio.digests=e30=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-kubernetes:k8s', '-']},
                ],
                expected_result=True,
                expected_compose_file_name='k8s.yml',
                should_upload_compose_file=True,
            ),
            created_with_custom_image_update_params=dict(
                init_kwargs=dict(image='image:tag'),
                update_kwargs=dict(tag='new-tag', registry='registry', account='account'),
                side_effect=[
                    SucceededResult(),  # manager status
                    docker.ImageNotFoundError(),  # image info
                    SucceededResult(),  # configuration deploy
                    SucceededResult(),  # update sentinel images
                    SucceededResult(),  # configuration images
                    SucceededResult(),  # build new sentinel image
                ],
                expected_command_args=[
                    {'args': ['kubectl', 'config', 'current-context']},
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-current-kubernetes:k8s']},
                    {'args': ['kubectl', 'apply', '--filename=k8s.yml']},
                    {'args': ['docker', 'rmi', 'fabricio-backup-kubernetes:k8s;', 'docker', 'tag', 'fabricio-current-kubernetes:k8s', 'fabricio-backup-kubernetes:k8s;', 'docker', 'rmi', 'fabricio-current-kubernetes:k8s']},
                    {'args': ['kubectl', 'get', '--output', 'go-template', '--filename', 'k8s.yml', '--template', r'{{define "images"}}{{$kind := .kind}}{{$name := .metadata.name}}{{with .spec.template.spec.containers}}{{range .}}{{$kind}}/{{$name}} {{.name}} {{.image}}{{"\n"}}{{end}}{{end}}{{end}}{{if eq .kind "List"}}{{range .items}}{{template "images" .}}{{end}}{{else}}{{template "images" .}}{{end}}']},
                    {'args': ['echo', 'FROM registry/account/image:new-tag\nLABEL fabricio.configuration=azhzLnltbA== fabricio.digests=e30=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-kubernetes:k8s', '-']},
                ],
                expected_result=True,
                expected_compose_file_name='k8s.yml',
                should_upload_compose_file=True,
            ),
            created_from_empty_image_with_custom_image_update_params=dict(
                init_kwargs=dict(),
                update_kwargs=dict(tag='registry/account/image:tag'),
                side_effect=[
                    SucceededResult(),  # manager status
                    docker.ImageNotFoundError(),  # image info
                    SucceededResult(),  # configuration deploy
                    SucceededResult(),  # update sentinel images
                    SucceededResult(),  # configuration images
                    SucceededResult(),  # build new sentinel image
                ],
                expected_command_args=[
                    {'args': ['kubectl', 'config', 'current-context']},
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-current-kubernetes:k8s']},
                    {'args': ['kubectl', 'apply', '--filename=k8s.yml']},
                    {'args': ['docker', 'rmi', 'fabricio-backup-kubernetes:k8s;', 'docker', 'tag', 'fabricio-current-kubernetes:k8s', 'fabricio-backup-kubernetes:k8s;', 'docker', 'rmi', 'fabricio-current-kubernetes:k8s']},
                    {'args': ['kubectl', 'get', '--output', 'go-template', '--filename', 'k8s.yml', '--template', r'{{define "images"}}{{$kind := .kind}}{{$name := .metadata.name}}{{with .spec.template.spec.containers}}{{range .}}{{$kind}}/{{$name}} {{.name}} {{.image}}{{"\n"}}{{end}}{{end}}{{end}}{{if eq .kind "List"}}{{range .items}}{{template "images" .}}{{end}}{{else}}{{template "images" .}}{{end}}']},
                    {'args': ['echo', 'FROM registry/account/image:tag\nLABEL fabricio.configuration=azhzLnltbA== fabricio.digests=e30=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-kubernetes:k8s', '-']},
                ],
                expected_result=True,
                expected_compose_file_name='k8s.yml',
                should_upload_compose_file=True,
            ),
            updated_configuration_changed=dict(
                init_kwargs=dict(),
                update_kwargs=dict(),
                side_effect=[
                    SucceededResult(),  # manager status
                    SucceededResult(json.dumps([{'Config': {
                        'Labels': {
                            'fabricio.configuration': 'b2xkLWNvbXBvc2UueW1s',
                            'fabricio.digests': 'eyJpbWFnZTp0YWciOiAiZGlnZXN0In0=',
                        },
                    }}])),  # image info
                    SucceededResult(),  # configuration deploy
                    SucceededResult(),  # update sentinel images
                    SucceededResult('kind name image:tag'),  # configuration images
                    SucceededResult(), SucceededResult(), SucceededResult(),  # image pull
                    SucceededResult('digest'),  # images digests
                    SucceededResult(),  # build new sentinel image
                ],
                expected_command_args=[
                    {'args': ['kubectl', 'config', 'current-context']},
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-current-kubernetes:k8s']},
                    {'args': ['kubectl', 'apply', '--filename=k8s.yml']},
                    {'args': ['docker', 'rmi', 'fabricio-backup-kubernetes:k8s;', 'docker', 'tag', 'fabricio-current-kubernetes:k8s', 'fabricio-backup-kubernetes:k8s;', 'docker', 'rmi', 'fabricio-current-kubernetes:k8s']},
                    {'args': ['kubectl', 'get', '--output', 'go-template', '--filename', 'k8s.yml', '--template', r'{{define "images"}}{{$kind := .kind}}{{$name := .metadata.name}}{{with .spec.template.spec.containers}}{{range .}}{{$kind}}/{{$name}} {{.name}} {{.image}}{{"\n"}}{{end}}{{end}}{{end}}{{if eq .kind "List"}}{{range .items}}{{template "images" .}}{{end}}{{else}}{{template "images" .}}{{end}}']},
                    {'args': ['docker', 'tag', 'image:tag', 'fabricio-temp-image:image', '&&', 'docker', 'rmi', 'image:tag']}, {'args': ['docker', 'pull', 'image:tag']}, {'args': ['docker', 'rmi', 'fabricio-temp-image:image']},
                    {'args': ['docker', 'inspect', '--type', 'image', '--format', '{{index .RepoDigests 0}}', 'image:tag']},
                    {'args': ['echo', 'FROM scratch\nLABEL fabricio.configuration=azhzLnltbA== fabricio.digests=eyJpbWFnZTp0YWciOiAiZGlnZXN0In0=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-kubernetes:k8s', '-']},
                ],
                expected_result=True,
                expected_compose_file='k8s.yml',
                should_upload_compose_file=True,
            ),
            updated_image_changed=dict(
                init_kwargs=dict(),
                update_kwargs=dict(),
                side_effect=[
                    SucceededResult(),  # manager status
                    SucceededResult(json.dumps([{'Config': {
                        'Labels': {
                            'fabricio.configuration': 'azhzLnltbA==',
                            'fabricio.digests': 'eyJpbWFnZTp0YWciOiAiZGlnZXN0In0=',
                        },
                    }}])),  # image info
                    SucceededResult(), SucceededResult(), SucceededResult(),  # image pull
                    SucceededResult('new-digest'),  # images digests
                    SucceededResult(),  # configuration deploy
                    SucceededResult(),  # update sentinel images
                    SucceededResult('kind name image:tag'),  # configuration images
                    SucceededResult(), SucceededResult(), SucceededResult(),  # image pull
                    SucceededResult('new-digest'),  # images digests
                    SucceededResult(),  # build new sentinel image
                ],
                expected_command_args=[
                    {'args': ['kubectl', 'config', 'current-context']},
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-current-kubernetes:k8s']},
                    {'args': ['docker', 'tag', 'image:tag', 'fabricio-temp-image:image', '&&', 'docker', 'rmi', 'image:tag']}, {'args': ['docker', 'pull', 'image:tag']}, {'args': ['docker', 'rmi', 'fabricio-temp-image:image']},
                    {'args': ['docker', 'inspect', '--type', 'image', '--format', '{{index .RepoDigests 0}}', 'image:tag']},
                    {'args': ['kubectl', 'apply', '--filename=k8s.yml']},
                    {'args': ['docker', 'rmi', 'fabricio-backup-kubernetes:k8s;', 'docker', 'tag', 'fabricio-current-kubernetes:k8s', 'fabricio-backup-kubernetes:k8s;', 'docker', 'rmi', 'fabricio-current-kubernetes:k8s']},
                    {'args': ['kubectl', 'get', '--output', 'go-template', '--filename', 'k8s.yml', '--template', r'{{define "images"}}{{$kind := .kind}}{{$name := .metadata.name}}{{with .spec.template.spec.containers}}{{range .}}{{$kind}}/{{$name}} {{.name}} {{.image}}{{"\n"}}{{end}}{{end}}{{end}}{{if eq .kind "List"}}{{range .items}}{{template "images" .}}{{end}}{{else}}{{template "images" .}}{{end}}']},
                    {'args': ['docker', 'tag', 'image:tag', 'fabricio-temp-image:image', '&&', 'docker', 'rmi', 'image:tag']}, {'args': ['docker', 'pull', 'image:tag']}, {'args': ['docker', 'rmi', 'fabricio-temp-image:image']},
                    {'args': ['docker', 'inspect', '--type', 'image', '--format', '{{index .RepoDigests 0}}', 'image:tag']},
                    {'args': ['echo', 'FROM scratch\nLABEL fabricio.configuration=azhzLnltbA== fabricio.digests=eyJpbWFnZTp0YWciOiAibmV3LWRpZ2VzdCJ9\n', '|', 'docker', 'build', '--tag', 'fabricio-current-kubernetes:k8s', '-']},
                ],
                expected_result=True,
                expected_compose_file='k8s.yml',
                should_upload_compose_file=True,
            ),
            updated_images_changed=dict(
                init_kwargs=dict(),
                update_kwargs=dict(),
                side_effect=[
                    SucceededResult(),  # manager status
                    SucceededResult(json.dumps([{'Config': {
                        'Labels': {
                            'fabricio.configuration': 'azhzLnltbA==',
                            'fabricio.digests': 'eyJpbWFnZTE6dGFnIjogImRpZ2VzdDEiLCAiaW1hZ2UyOnRhZyI6ICJkaWdlc3QyIn0=',
                        },
                    }}])),  # image info
                    SucceededResult(), SucceededResult(), SucceededResult(),  # image1 pull
                    SucceededResult(), SucceededResult(), SucceededResult(),  # image2 pull
                    SucceededResult('new-digest1\nnew-digest2\n'),  # images digests
                    SucceededResult(),  # configuration deploy
                    SucceededResult(),  # update sentinel images
                    SucceededResult('kind1 image1 image1:tag\nkind2 image2 image2:tag\n'),  # configuration images
                    SucceededResult(), SucceededResult(), SucceededResult(),  # image1 pull
                    SucceededResult(), SucceededResult(), SucceededResult(),  # image2 pull
                    SucceededResult('new-digest1\nnew-digest2\n'),  # images digests
                    SucceededResult(),  # build new sentinel image
                ],
                expected_command_args=[
                    {'args': ['kubectl', 'config', 'current-context']},
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-current-kubernetes:k8s']},
                    {'args': ['docker', 'tag', 'image1:tag', 'fabricio-temp-image:image1', '&&', 'docker', 'rmi', 'image1:tag']}, {'args': ['docker', 'pull', 'image1:tag']}, {'args': ['docker', 'rmi', 'fabricio-temp-image:image1']},
                    {'args': ['docker', 'tag', 'image2:tag', 'fabricio-temp-image:image2', '&&', 'docker', 'rmi', 'image2:tag']}, {'args': ['docker', 'pull', 'image2:tag']}, {'args': ['docker', 'rmi', 'fabricio-temp-image:image2']},
                    {'args': ['docker', 'inspect', '--type', 'image', '--format', '{{index .RepoDigests 0}}', 'image1:tag', 'image2:tag']},
                    {'args': ['kubectl', 'apply', '--filename=k8s.yml']},
                    {'args': ['docker', 'rmi', 'fabricio-backup-kubernetes:k8s;', 'docker', 'tag', 'fabricio-current-kubernetes:k8s', 'fabricio-backup-kubernetes:k8s;', 'docker', 'rmi', 'fabricio-current-kubernetes:k8s']},
                    {'args': ['kubectl', 'get', '--output', 'go-template', '--filename', 'k8s.yml', '--template', r'{{define "images"}}{{$kind := .kind}}{{$name := .metadata.name}}{{with .spec.template.spec.containers}}{{range .}}{{$kind}}/{{$name}} {{.name}} {{.image}}{{"\n"}}{{end}}{{end}}{{end}}{{if eq .kind "List"}}{{range .items}}{{template "images" .}}{{end}}{{else}}{{template "images" .}}{{end}}']},
                    {'args': ['docker', 'tag', 'image1:tag', 'fabricio-temp-image:image1', '&&', 'docker', 'rmi', 'image1:tag']}, {'args': ['docker', 'pull', 'image1:tag']}, {'args': ['docker', 'rmi', 'fabricio-temp-image:image1']},
                    {'args': ['docker', 'tag', 'image2:tag', 'fabricio-temp-image:image2', '&&', 'docker', 'rmi', 'image2:tag']}, {'args': ['docker', 'pull', 'image2:tag']}, {'args': ['docker', 'rmi', 'fabricio-temp-image:image2']},
                    {'args': ['docker', 'inspect', '--type', 'image', '--format', '{{index .RepoDigests 0}}', 'image1:tag', 'image2:tag']},
                    {'args': ['echo', 'FROM scratch\nLABEL fabricio.configuration=azhzLnltbA== fabricio.digests=eyJpbWFnZTE6dGFnIjogIm5ldy1kaWdlc3QxIiwgImltYWdlMjp0YWciOiAibmV3LWRpZ2VzdDIifQ==\n', '|', 'docker', 'build', '--tag', 'fabricio-current-kubernetes:k8s', '-']},
                ],
                expected_result=True,
                expected_compose_file='k8s.yml',
                should_upload_compose_file=True,
            ),
        )
        for case, data in cases.items():
            with self.subTest(case):
                fab.env.command = '{0}__{1}'.format(self, case)
                with mock.patch.dict(fab.env, dict(all_hosts=data.get('all_hosts', ['host']))):
                    kubernetes.open.return_value = six.BytesIO(b'k8s.yml')
                    kubernetes.open.reset_mock()
                    put.reset_mock()
                    configuration = kubernetes.Configuration(
                        name='k8s',
                        options={'filename': 'k8s.yml'},
                        **data.get('init_kwargs', {})
                    )
                    side_effect = self.command_checker(
                        args_parsers=args_parser,
                        expected_args_set=data.get('expected_command_args', []),
                        side_effects=data.get('side_effect', []),
                    )
                    with mock.patch.object(fabricio, 'run', side_effect=side_effect):
                        with mock.patch('six.BytesIO') as filename:
                            result = configuration.update(**data.get('update_kwargs', {}))
                    self.assertEqual(data['expected_result'], result)
                    expected_compose_file_name = data.get('expected_compose_file_name')
                    if expected_compose_file_name:
                        kubernetes.open.assert_called_once_with(expected_compose_file_name, 'rb')
                    if data.get('should_upload_compose_file', False):
                        put.assert_called_once()
                        filename.assert_called_once_with(b'k8s.yml')
                    else:
                        put.assert_not_called()

    @mock.patch.object(stack_module, 'dict', new=collections.OrderedDict)
    @mock.patch.object(kubernetes, 'dict', new=collections.OrderedDict)
    @mock.patch.object(fab, 'put')
    def test_revert(self, put, *args):
        cases = dict(
            worker=dict(
                init_kwargs=dict(),
                side_effect=[
                    FailedResult(),  # manager status
                ],
                expected_command_args=[
                    {'args': ['kubectl', 'config', 'current-context']},
                ],
                all_hosts=['host1', 'host2'],
            ),
            reverted=dict(
                init_kwargs=dict(),
                side_effect=[
                    SucceededResult(),  # manager status
                    SucceededResult(json.dumps([{'Config': {
                        'Labels': {
                            'fabricio.configuration': 'b2xkLWNvbXBvc2UueW1s',
                        },
                    }}])),  # image info
                    SucceededResult(),  # configuration deploy
                    SucceededResult(),  # update sentinel images
                ],
                expected_command_args=[
                    {'args': ['kubectl', 'config', 'current-context']},
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-backup-kubernetes:k8s']},
                    {'args': ['kubectl', 'apply', '--filename=fabricio.kubernetes.k8s.yml']},
                    {'args': ['docker', 'rmi', 'fabricio-current-kubernetes:k8s;', 'docker', 'tag', 'fabricio-backup-kubernetes:k8s', 'fabricio-current-kubernetes:k8s;', 'docker', 'rmi', 'fabricio-backup-kubernetes:k8s']},
                ],
                expected_compose_file=b'old-compose.yml',
            ),
            reverted_with_pod_update=dict(
                init_kwargs=dict(),
                side_effect=[
                    SucceededResult(),  # manager status
                    SucceededResult(json.dumps([{'Config': {
                        'Labels': {
                            'fabricio.configuration': 'Y29tcG9zZS55bWw=',  # compose.yml
                            'fabricio.digests': 'eyJpbWFnZTp0YWciOiAiZGlnZXN0In0=',  # {"image:tag": "digest"}
                        },
                    }}])),  # image info
                    SucceededResult(),  # configuration deploy
                    SucceededResult('kind name image:tag\n'),  # configuration services
                    SucceededResult(),  # pod update
                    SucceededResult(),  # update sentinel images
                ],
                expected_command_args=[
                    {'args': ['kubectl', 'config', 'current-context']},
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-backup-kubernetes:k8s']},
                    {'args': ['kubectl', 'apply', '--filename=fabricio.kubernetes.k8s.yml']},
                    {'args': ['kubectl', 'get', '--output', 'go-template', '--filename', 'fabricio.kubernetes.k8s.yml', '--template', r'{{define "images"}}{{$kind := .kind}}{{$name := .metadata.name}}{{with .spec.template.spec.containers}}{{range .}}{{$kind}}/{{$name}} {{.name}} {{.image}}{{"\n"}}{{end}}{{end}}{{end}}{{if eq .kind "List"}}{{range .items}}{{template "images" .}}{{end}}{{else}}{{template "images" .}}{{end}}']},
                    {'args': ['kubectl', 'set', 'image', 'kind', 'name=digest']},
                    {'args': ['docker', 'rmi', 'fabricio-current-kubernetes:k8s;', 'docker', 'tag', 'fabricio-backup-kubernetes:k8s', 'fabricio-current-kubernetes:k8s;', 'docker', 'rmi', 'fabricio-backup-kubernetes:k8s']},
                ],
                expected_compose_file=b'compose.yml',
            ),
            reverted_with_pods_update=dict(
                init_kwargs=dict(),
                side_effect=[
                    SucceededResult(),  # manager status
                    SucceededResult(json.dumps([{'Config': {
                        'Labels': {
                            'fabricio.configuration': 'Y29tcG9zZS55bWw=',  # compose.yml
                            'fabricio.digests': 'eyJpbWFnZTE6dGFnIjogImRpZ2VzdDEiLCAiaW1hZ2UyOnRhZyI6ICJkaWdlc3QyIn0=',  # {"image1:tag": "digest1", "image2:tag": "digest2"}
                        },
                    }}])),  # image info
                    SucceededResult(),  # configuration deploy
                    SucceededResult('kind1 name1 image1:tag\nkind2 name2 image2:tag'),  # configuration services
                    SucceededResult(),  # pod update
                    SucceededResult(),  # pod update
                    SucceededResult(),  # update sentinel images
                ],
                expected_command_args=[
                    {'args': ['kubectl', 'config', 'current-context']},
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-backup-kubernetes:k8s']},
                    {'args': ['kubectl', 'apply', '--filename=fabricio.kubernetes.k8s.yml']},
                    {'args': ['kubectl', 'get', '--output', 'go-template', '--filename', 'fabricio.kubernetes.k8s.yml', '--template', r'{{define "images"}}{{$kind := .kind}}{{$name := .metadata.name}}{{with .spec.template.spec.containers}}{{range .}}{{$kind}}/{{$name}} {{.name}} {{.image}}{{"\n"}}{{end}}{{end}}{{end}}{{if eq .kind "List"}}{{range .items}}{{template "images" .}}{{end}}{{else}}{{template "images" .}}{{end}}']},
                    {'args': ['kubectl', 'set', 'image', 'kind1', 'name1=digest1']},
                    {'args': ['kubectl', 'set', 'image', 'kind2', 'name2=digest2']},
                    {'args': ['docker', 'rmi', 'fabricio-current-kubernetes:k8s;', 'docker', 'tag', 'fabricio-backup-kubernetes:k8s', 'fabricio-current-kubernetes:k8s;', 'docker', 'rmi', 'fabricio-backup-kubernetes:k8s']},
                ],
                expected_compose_file=b'compose.yml',
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                fab.env.command = '{0}__{1}'.format(self, case)
                put.reset_mock()
                with mock.patch.dict(fab.env, dict(all_hosts=data.get('all_hosts', ['host']))):
                    configuration = kubernetes.Configuration(
                        name='k8s',
                        options={'filename': 'k8s.yml'},
                        **data.get('init_kwargs', {})
                    )
                    side_effects = data.get('side_effect', [])
                    side_effect = self.command_checker(
                        args_parsers=args_parser,
                        expected_args_set=data.get('expected_command_args', []),
                        side_effects=side_effects,
                    )
                    with mock.patch.object(fabricio, 'run', side_effect=side_effect) as run:
                        with mock.patch('six.BytesIO') as compose_file:
                            configuration.revert()
                    self.assertEqual(run.call_count, len(side_effects))
                    expected_compose_file = data.get('expected_compose_file')
                    if expected_compose_file:
                        put.assert_called_once()
                        compose_file.assert_called_once_with(expected_compose_file)
                    else:
                        put.assert_not_called()

    def test_revert_raises_error_when_backup_not_found(self):
        side_effect = self.command_checker(
            args_parsers=args_parser,
            expected_args_set=[
                {'args': ['kubectl', 'config', 'current-context']},
                {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-backup-kubernetes:k8s']},
            ],
            side_effects=[
                SucceededResult(),  # manager status
                docker.ImageNotFoundError(),  # image info
            ],
        )
        with mock.patch.object(fabricio, 'run', side_effect=side_effect):
            configuration = kubernetes.Configuration(name='k8s')
            with self.assertRaises(docker.ServiceError):
                configuration.revert()

    @mock.patch.object(kubernetes.Configuration, 'is_manager', return_value=True)
    @mock.patch.object(kubernetes.Configuration, '_revert')
    def test_revert_does_not_rollback_sentinels_on_error(self, *args):
        with mock.patch.object(kubernetes.Configuration, 'rotate_sentinel_images') as rotate_sentinel_images:
            configuration = kubernetes.Configuration(name='k8s')
            configuration.revert()
            rotate_sentinel_images.assert_not_called()
