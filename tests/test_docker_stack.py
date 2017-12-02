import functools
import json

import mock
import six

from fabric import api as fab

import fabricio

from fabricio import docker, utils
from fabricio.docker import service
from tests import SucceededResult, args_parser, FabricioTestCase, \
    docker_inspect_args_parser


def as_ordereddict(result):
    return utils.OrderedDict(sorted(result.items()))


class ContainerTestCase(FabricioTestCase):

    def setUp(self):
        service.open = mock.MagicMock()
        self.cd = mock.patch.object(fab, 'cd')
        self.cd.start()

    def tearDown(self):
        service.open = open
        self.cd.stop()

    @mock.patch.object(fabricio, 'log')
    @mock.patch.object(service, 'dict', new=utils.OrderedDict)
    @mock.patch.object(service, 'set', new=utils.OrderedSet)
    @mock.patch.object(json, 'loads', new=functools.partial(json.loads, object_hook=as_ordereddict))
    @mock.patch.object(fab, 'put')
    def test_update(self, put, *args):
        cases = dict(
            worker=dict(
                init_kwargs=dict(name='stack'),
                update_kwargs={},
                side_effect=[
                    SucceededResult('  Is Manager: false'),  # manager status
                ],
                args_parser=[
                    args_parser,
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                ],
                expected_result=False,
                all_hosts=['host1', 'host2'],
            ),
            no_changes=dict(
                init_kwargs=dict(name='stack'),
                update_kwargs={},
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult(json.dumps([{'Config': {
                        'Labels': {
                            'fabricio.stack.compose.stack': 'Y29tcG9zZS55bWw=',
                            'fabricio.stack.images.stack': 'e30=',
                        },
                    }}])),  # image info
                ],
                args_parser=[
                    args_parser,
                    docker_inspect_args_parser,
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'fabricio-current-stack:stack',
                    },
                ],
                expected_result=False,
                expected_compose_file='docker-compose.yml',
            ),
            forced=dict(
                init_kwargs=dict(name='stack'),
                update_kwargs=dict(force=True),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult(),  # stack deploy
                    RuntimeError(),  # update sentinel images
                    SucceededResult(),  # stack images
                    SucceededResult(),  # build new sentinel image
                ],
                args_parser=[
                    args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {
                        'args': ['docker', 'stack', 'deploy', '--compose-file=docker-compose.yml', 'stack'],
                    },
                    {
                        'args': ['docker', 'rmi', 'fabricio-backup-stack:stack;', 'docker', 'tag', 'fabricio-current-stack:stack', 'fabricio-backup-stack:stack;', 'docker', 'rmi', 'fabricio-current-stack:stack'],
                    },
                    {
                        'args': ['docker', 'stack', 'services', '--format', '{{.Name}} {{.Image}}', 'stack'],
                    },
                    {
                        'args': ['echo', 'FROM scratch\nLABEL fabricio.stack.compose.stack=Y29tcG9zZS55bWw= fabricio.stack.images.stack=e30=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                ],
                expected_result=True,
                expected_compose_file='docker-compose.yml',
                should_upload_compose_file=True,
            ),
            created=dict(
                init_kwargs=dict(name='stack'),
                update_kwargs=dict(),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    docker.ImageNotFoundError(),  # image info
                    SucceededResult(),  # stack deploy
                    SucceededResult(),  # update sentinel images
                    SucceededResult(),  # stack images
                    SucceededResult(),  # build new sentinel image
                ],
                args_parser=[
                    args_parser,
                    docker_inspect_args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'fabricio-current-stack:stack',
                    },
                    {
                        'args': ['docker', 'stack', 'deploy', '--compose-file=docker-compose.yml', 'stack'],
                    },
                    {
                        'args': ['docker', 'rmi', 'fabricio-backup-stack:stack;', 'docker', 'tag', 'fabricio-current-stack:stack', 'fabricio-backup-stack:stack;', 'docker', 'rmi', 'fabricio-current-stack:stack'],
                    },
                    {
                        'args': ['docker', 'stack', 'services', '--format', '{{.Name}} {{.Image}}', 'stack'],
                    },
                    {
                        'args': ['echo', 'FROM scratch\nLABEL fabricio.stack.compose.stack=Y29tcG9zZS55bWw= fabricio.stack.images.stack=e30=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                ],
                expected_result=True,
                expected_compose_file='docker-compose.yml',
                should_upload_compose_file=True,
            ),
            created_skip_sentinels_errors=dict(
                init_kwargs=dict(name='stack'),
                update_kwargs=dict(),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    docker.ImageNotFoundError(),  # image info
                    SucceededResult(),  # stack deploy
                    RuntimeError(),  # update sentinel images
                    RuntimeError(),  # stack images
                    RuntimeError(),  # build new sentinel image
                ],
                args_parser=[
                    args_parser,
                    docker_inspect_args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'fabricio-current-stack:stack',
                    },
                    {
                        'args': ['docker', 'stack', 'deploy', '--compose-file=docker-compose.yml', 'stack'],
                    },
                    {
                        'args': ['docker', 'rmi', 'fabricio-backup-stack:stack;', 'docker', 'tag', 'fabricio-current-stack:stack', 'fabricio-backup-stack:stack;', 'docker', 'rmi', 'fabricio-current-stack:stack'],
                    },
                    {
                        'args': ['docker', 'stack', 'services', '--format', '{{.Name}} {{.Image}}', 'stack'],
                    },
                    {
                        'args': ['echo', 'FROM scratch\nLABEL fabricio.stack.compose.stack=Y29tcG9zZS55bWw=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                ],
                expected_result=True,
                expected_compose_file='docker-compose.yml',
                should_upload_compose_file=True,
            ),
            created_with_custom_compose=dict(
                init_kwargs=dict(name='stack', options=dict(compose_file='compose.yml')),
                update_kwargs=dict(),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    docker.ImageNotFoundError(),  # image info
                    SucceededResult(),  # stack deploy
                    SucceededResult(),  # update sentinel images
                    SucceededResult(),  # stack images
                    SucceededResult(),  # build new sentinel image
                ],
                args_parser=[
                    args_parser,
                    docker_inspect_args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'fabricio-current-stack:stack',
                    },
                    {
                        'args': ['docker', 'stack', 'deploy', '--compose-file=compose.yml', 'stack'],
                    },
                    {
                        'args': ['docker', 'rmi', 'fabricio-backup-stack:stack;', 'docker', 'tag', 'fabricio-current-stack:stack', 'fabricio-backup-stack:stack;', 'docker', 'rmi', 'fabricio-current-stack:stack'],
                    },
                    {
                        'args': ['docker', 'stack', 'services', '--format', '{{.Name}} {{.Image}}', 'stack'],
                    },
                    {
                        'args': ['echo', 'FROM scratch\nLABEL fabricio.stack.compose.stack=Y29tcG9zZS55bWw= fabricio.stack.images.stack=e30=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                ],
                expected_result=True,
                expected_compose_file='compose.yml',
                should_upload_compose_file=True,
            ),
            created_with_custom_compose2=dict(
                init_kwargs=dict(name='stack', options={'compose-file': 'compose.yml'}),
                update_kwargs=dict(),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    docker.ImageNotFoundError(),  # image info
                    SucceededResult(),  # stack deploy
                    SucceededResult(),  # update sentinel images
                    SucceededResult(),  # stack images
                    SucceededResult(),  # build new sentinel image
                ],
                args_parser=[
                    args_parser,
                    docker_inspect_args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'fabricio-current-stack:stack',
                    },
                    {
                        'args': ['docker', 'stack', 'deploy', '--compose-file=compose.yml', 'stack'],
                    },
                    {
                        'args': ['docker', 'rmi', 'fabricio-backup-stack:stack;', 'docker', 'tag', 'fabricio-current-stack:stack', 'fabricio-backup-stack:stack;', 'docker', 'rmi', 'fabricio-current-stack:stack'],
                    },
                    {
                        'args': ['docker', 'stack', 'services', '--format', '{{.Name}} {{.Image}}', 'stack'],
                    },
                    {
                        'args': ['echo', 'FROM scratch\nLABEL fabricio.stack.compose.stack=Y29tcG9zZS55bWw= fabricio.stack.images.stack=e30=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                ],
                expected_result=True,
                expected_compose_file='compose.yml',
                should_upload_compose_file=True,
            ),
            created_with_custom_image=dict(
                init_kwargs=dict(name='stack', image='image:tag'),
                update_kwargs=dict(),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    docker.ImageNotFoundError(),  # image info
                    SucceededResult(),  # stack deploy
                    SucceededResult(),  # update sentinel images
                    SucceededResult(),  # stack images
                    SucceededResult(),  # build new sentinel image
                ],
                args_parser=[
                    args_parser,
                    docker_inspect_args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'fabricio-current-stack:stack',
                    },
                    {
                        'args': ['docker', 'stack', 'deploy', '--compose-file=docker-compose.yml', 'stack'],
                    },
                    {
                        'args': ['docker', 'rmi', 'fabricio-backup-stack:stack;', 'docker', 'tag', 'fabricio-current-stack:stack', 'fabricio-backup-stack:stack;', 'docker', 'rmi', 'fabricio-current-stack:stack'],
                    },
                    {
                        'args': ['docker', 'stack', 'services', '--format', '{{.Name}} {{.Image}}', 'stack'],
                    },
                    {
                        'args': ['echo', 'FROM image:tag\nLABEL fabricio.stack.compose.stack=Y29tcG9zZS55bWw= fabricio.stack.images.stack=e30=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                ],
                expected_result=True,
                expected_compose_file_name='docker-compose.yml',
                should_upload_compose_file=True,
            ),
            created_with_custom_image_update_params=dict(
                init_kwargs=dict(name='stack', image='image:tag'),
                update_kwargs=dict(tag='new-tag', registry='registry', account='account'),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    docker.ImageNotFoundError(),  # image info
                    SucceededResult(),  # stack deploy
                    SucceededResult(),  # update sentinel images
                    SucceededResult(),  # stack images
                    SucceededResult(),  # build new sentinel image
                ],
                args_parser=[
                    args_parser,
                    docker_inspect_args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'fabricio-current-stack:stack',
                    },
                    {
                        'args': ['docker', 'stack', 'deploy', '--compose-file=docker-compose.yml', 'stack'],
                    },
                    {
                        'args': ['docker', 'rmi', 'fabricio-backup-stack:stack;', 'docker', 'tag', 'fabricio-current-stack:stack', 'fabricio-backup-stack:stack;', 'docker', 'rmi', 'fabricio-current-stack:stack'],
                    },
                    {
                        'args': ['docker', 'stack', 'services', '--format', '{{.Name}} {{.Image}}', 'stack'],
                    },
                    {
                        'args': ['echo', 'FROM registry/account/image:new-tag\nLABEL fabricio.stack.compose.stack=Y29tcG9zZS55bWw= fabricio.stack.images.stack=e30=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                ],
                expected_result=True,
                expected_compose_file_name='docker-compose.yml',
                should_upload_compose_file=True,
            ),
            created_from_empty_image_with_custom_image_update_params=dict(
                init_kwargs=dict(name='stack'),
                update_kwargs=dict(tag='registry/account/image:tag'),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    docker.ImageNotFoundError(),  # image info
                    SucceededResult(),  # stack deploy
                    SucceededResult(),  # update sentinel images
                    SucceededResult(),  # stack images
                    SucceededResult(),  # build new sentinel image
                ],
                args_parser=[
                    args_parser,
                    docker_inspect_args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'fabricio-current-stack:stack',
                    },
                    {
                        'args': ['docker', 'stack', 'deploy', '--compose-file=docker-compose.yml', 'stack'],
                    },
                    {
                        'args': ['docker', 'rmi', 'fabricio-backup-stack:stack;', 'docker', 'tag', 'fabricio-current-stack:stack', 'fabricio-backup-stack:stack;', 'docker', 'rmi', 'fabricio-current-stack:stack'],
                    },
                    {
                        'args': ['docker', 'stack', 'services', '--format', '{{.Name}} {{.Image}}', 'stack'],
                    },
                    {
                        'args': ['echo', 'FROM registry/account/image:tag\nLABEL fabricio.stack.compose.stack=Y29tcG9zZS55bWw= fabricio.stack.images.stack=e30=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                ],
                expected_result=True,
                expected_compose_file_name='docker-compose.yml',
                should_upload_compose_file=True,
            ),
            updated_compose_changed=dict(
                init_kwargs=dict(name='stack'),
                update_kwargs=dict(),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult(json.dumps([{'Config': {
                        'Labels': {
                            'fabricio.stack.compose.stack': 'b2xkLWNvbXBvc2UueW1s',
                            'fabricio.stack.images.stack': 'eyJpbWFnZTp0YWciOiAiZGlnZXN0In0=',
                        },
                    }}])),  # image info
                    SucceededResult(),  # stack deploy
                    SucceededResult(),  # update sentinel images
                    SucceededResult('service image:tag'),  # stack images
                    SucceededResult(),  # image pull
                    SucceededResult('digest'),  # images digests
                    SucceededResult(),  # build new sentinel image
                ],
                args_parser=[
                    args_parser,
                    docker_inspect_args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'fabricio-current-stack:stack',
                    },
                    {
                        'args': ['docker', 'stack', 'deploy', '--compose-file=docker-compose.yml', 'stack'],
                    },
                    {
                        'args': ['docker', 'rmi', 'fabricio-backup-stack:stack;', 'docker', 'tag', 'fabricio-current-stack:stack', 'fabricio-backup-stack:stack;', 'docker', 'rmi', 'fabricio-current-stack:stack'],
                    },
                    {
                        'args': ['docker', 'stack', 'services', '--format', '{{.Name}} {{.Image}}', 'stack'],
                    },
                    {
                        'args': ['docker', 'pull', 'image:tag'],
                    },
                    {
                        'args': ['docker', 'inspect', '--type', 'image', '--format', '{{index .RepoDigests 0}}', 'image:tag'],
                    },
                    {
                        'args': ['echo', 'FROM scratch\nLABEL fabricio.stack.compose.stack=Y29tcG9zZS55bWw= fabricio.stack.images.stack=eyJpbWFnZTp0YWciOiAiZGlnZXN0In0=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                ],
                expected_result=True,
                expected_compose_file='docker-compose.yml',
                should_upload_compose_file=True,
            ),
            updated_image_changed=dict(
                init_kwargs=dict(name='stack'),
                update_kwargs=dict(),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult(json.dumps([{'Config': {
                        'Labels': {
                            'fabricio.stack.compose.stack': 'Y29tcG9zZS55bWw=',
                            'fabricio.stack.images.stack': 'eyJpbWFnZTp0YWciOiAiZGlnZXN0In0=',
                        },
                    }}])),  # image info
                    SucceededResult(),  # image pull
                    SucceededResult('new-digest'),  # images digests
                    SucceededResult(),  # stack deploy
                    SucceededResult(),  # update sentinel images
                    SucceededResult('service image:tag'),  # stack images
                    SucceededResult(),  # image pull
                    SucceededResult('new-digest'),  # images digests
                    SucceededResult(),  # build new sentinel image
                ],
                args_parser=[
                    args_parser,
                    docker_inspect_args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'fabricio-current-stack:stack',
                    },
                    {
                        'args': ['docker', 'pull', 'image:tag'],
                    },
                    {
                        'args': ['docker', 'inspect', '--type', 'image', '--format', '{{index .RepoDigests 0}}', 'image:tag'],
                    },
                    {
                        'args': ['docker', 'stack', 'deploy', '--compose-file=docker-compose.yml', 'stack'],
                    },
                    {
                        'args': ['docker', 'rmi', 'fabricio-backup-stack:stack;', 'docker', 'tag', 'fabricio-current-stack:stack', 'fabricio-backup-stack:stack;', 'docker', 'rmi', 'fabricio-current-stack:stack'],
                    },
                    {
                        'args': ['docker', 'stack', 'services', '--format', '{{.Name}} {{.Image}}', 'stack'],
                    },
                    {
                        'args': ['docker', 'pull', 'image:tag'],
                    },
                    {
                        'args': ['docker', 'inspect', '--type', 'image', '--format', '{{index .RepoDigests 0}}', 'image:tag'],
                    },
                    {
                        'args': ['echo', 'FROM scratch\nLABEL fabricio.stack.compose.stack=Y29tcG9zZS55bWw= fabricio.stack.images.stack=eyJpbWFnZTp0YWciOiAibmV3LWRpZ2VzdCJ9\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                ],
                expected_result=True,
                expected_compose_file='docker-compose.yml',
                should_upload_compose_file=True,
            ),
            updated_images_changed=dict(
                init_kwargs=dict(name='stack'),
                update_kwargs=dict(),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult(json.dumps([{'Config': {
                        'Labels': {
                            'fabricio.stack.compose.stack': 'Y29tcG9zZS55bWw=',
                            'fabricio.stack.images.stack': 'eyJpbWFnZTE6dGFnIjogImRpZ2VzdDEiLCAiaW1hZ2UyOnRhZyI6ICJkaWdlc3QyIn0=',
                        },
                    }}])),  # image info
                    SucceededResult(),  # image1 pull
                    SucceededResult(),  # image2 pull
                    SucceededResult('new-digest1\nnew-digest2\n'),  # images digests
                    SucceededResult(),  # stack deploy
                    SucceededResult(),  # update sentinel images
                    SucceededResult('service1 image1:tag\nservice2 image2:tag\n'),  # stack images
                    SucceededResult(),  # image1 pull
                    SucceededResult(),  # image2 pull
                    SucceededResult('new-digest1\nnew-digest2\n'),  # images digests
                    SucceededResult(),  # build new sentinel image
                ],
                args_parser=[
                    args_parser,
                    docker_inspect_args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                    args_parser,
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'fabricio-current-stack:stack',
                    },
                    {
                        'args': ['docker', 'pull', 'image1:tag'],
                    },
                    {
                        'args': ['docker', 'pull', 'image2:tag'],
                    },
                    {
                        'args': ['docker', 'inspect', '--type', 'image', '--format', '{{index .RepoDigests 0}}', 'image1:tag', 'image2:tag'],
                    },
                    {
                        'args': ['docker', 'stack', 'deploy', '--compose-file=docker-compose.yml', 'stack'],
                    },
                    {
                        'args': ['docker', 'rmi', 'fabricio-backup-stack:stack;', 'docker', 'tag', 'fabricio-current-stack:stack', 'fabricio-backup-stack:stack;', 'docker', 'rmi', 'fabricio-current-stack:stack'],
                    },
                    {
                        'args': ['docker', 'stack', 'services', '--format', '{{.Name}} {{.Image}}', 'stack'],
                    },
                    {
                        'args': ['docker', 'pull', 'image1:tag'],
                    },
                    {
                        'args': ['docker', 'pull', 'image2:tag'],
                    },
                    {
                        'args': ['docker', 'inspect', '--type', 'image', '--format', '{{index .RepoDigests 0}}', 'image1:tag', 'image2:tag'],
                    },
                    {
                        'args': ['echo', 'FROM scratch\nLABEL fabricio.stack.compose.stack=Y29tcG9zZS55bWw= fabricio.stack.images.stack=eyJpbWFnZTE6dGFnIjogIm5ldy1kaWdlc3QxIiwgImltYWdlMjp0YWciOiAibmV3LWRpZ2VzdDIifQ==\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                ],
                expected_result=True,
                expected_compose_file='docker-compose.yml',
                should_upload_compose_file=True,
            ),
        )
        for case, data in cases.items():
            with self.subTest(case):
                fab.env.command = '{0}__{1}'.format(self, case)
                with mock.patch.dict(fab.env, dict(all_hosts=data.get('all_hosts', ['host']))):
                    service.open.return_value = six.BytesIO(b'compose.yml')
                    service.open.reset_mock()
                    put.reset_mock()
                    stack = docker.Stack(**data.get('init_kwargs', {}))
                    side_effect = self.command_checker(
                        args_parsers=data.get('args_parser', []),
                        expected_args_set=data.get('expected_command_args', []),
                        side_effects=data.get('side_effect', []),
                    )
                    with mock.patch.object(fabricio, 'run', side_effect=side_effect):
                        with mock.patch('six.BytesIO') as compose_file:
                            result = stack.update(**data.get('update_kwargs', {}))
                    self.assertEqual(data['expected_result'], result)
                    expected_compose_file_name = data.get('expected_compose_file_name')
                    if expected_compose_file_name:
                        service.open.assert_called_once_with(expected_compose_file_name, 'rb')
                    if data.get('should_upload_compose_file', False):
                        put.assert_called_once()
                        compose_file.assert_called_once_with(b'compose.yml')
                    else:
                        put.assert_not_called()

    @mock.patch.object(service, 'dict', new=utils.OrderedDict)
    @mock.patch.object(fab, 'put')
    def test_revert(self, put, *args):
        cases = dict(
            worker=dict(
                init_kwargs=dict(name='stack'),
                side_effect=[
                    SucceededResult('  Is Manager: false'),  # manager status
                ],
                args_parser=[
                    args_parser,
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                ],
                all_hosts=['host1', 'host2'],
            ),
            reverted=dict(
                init_kwargs=dict(name='stack'),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult(json.dumps([{'Config': {
                        'Labels': {
                            'fabricio.stack.compose.stack': 'b2xkLWNvbXBvc2UueW1s',
                        },
                    }}])),  # image info
                    SucceededResult(),  # stack deploy
                    SucceededResult(),  # update sentinel images
                ],
                args_parser=[
                    args_parser,
                    docker_inspect_args_parser,
                    args_parser,
                    args_parser,
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'fabricio-backup-stack:stack',
                    },
                    {
                        'args': ['docker', 'stack', 'deploy', '--compose-file=docker-compose.yml', 'stack'],
                    },
                    {
                        'args': ['docker', 'rmi', 'fabricio-current-stack:stack;', 'docker', 'tag', 'fabricio-backup-stack:stack', 'fabricio-current-stack:stack;', 'docker', 'rmi', 'fabricio-backup-stack:stack'],
                    },
                ],
                expected_compose_file=b'old-compose.yml',
            ),
            reverted_with_service_update=dict(
                init_kwargs=dict(name='stack'),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult(json.dumps([{'Config': {
                        'Labels': {
                            'fabricio.stack.compose.stack': 'Y29tcG9zZS55bWw=',  # compose.yml
                            'fabricio.stack.images.stack': 'eyJpbWFnZTp0YWciOiAiZGlnZXN0In0=',  # {"image:tag": "digest"}
                        },
                    }}])),  # image info
                    SucceededResult(),  # stack deploy
                    SucceededResult('service image:tag\n'),  # stack services
                    SucceededResult(),  # service update
                    SucceededResult(),  # update sentinel images
                ],
                args_parser=[args_parser] * 6,
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {
                        'args': ['docker', 'inspect', '--type', 'image', 'fabricio-backup-stack:stack'],
                    },
                    {
                        'args': ['docker', 'stack', 'deploy', '--compose-file=docker-compose.yml', 'stack'],
                    },
                    {
                        'args': ['docker', 'stack', 'services', '--format', '{{.Name}} {{.Image}}', 'stack'],
                    },
                    {
                        'args': ['docker', 'service', 'update', '--image', 'digest', 'service'],
                    },
                    {
                        'args': ['docker', 'rmi', 'fabricio-current-stack:stack;', 'docker', 'tag', 'fabricio-backup-stack:stack', 'fabricio-current-stack:stack;', 'docker', 'rmi', 'fabricio-backup-stack:stack'],
                    },
                ],
                expected_compose_file=b'compose.yml',
            ),
            reverted_with_services_update=dict(
                init_kwargs=dict(name='stack'),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult(json.dumps([{'Config': {
                        'Labels': {
                            'fabricio.stack.compose.stack': 'Y29tcG9zZS55bWw=',  # compose.yml
                            'fabricio.stack.images.stack': 'eyJpbWFnZTE6dGFnIjogImRpZ2VzdDEiLCAiaW1hZ2UyOnRhZyI6ICJkaWdlc3QyIn0=',  # {"image1:tag": "digest1", "image2:tag": "digest2"}
                        },
                    }}])),  # image info
                    SucceededResult(),  # stack deploy
                    SucceededResult('service1 image1:tag\nservice2 image2:tag'),  # stack services
                    SucceededResult(),  # service update
                    SucceededResult(),  # service update
                    SucceededResult(),  # update sentinel images
                ],
                args_parser=[args_parser] * 7,
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {
                        'args': ['docker', 'inspect', '--type', 'image', 'fabricio-backup-stack:stack'],
                    },
                    {
                        'args': ['docker', 'stack', 'deploy', '--compose-file=docker-compose.yml', 'stack'],
                    },
                    {
                        'args': ['docker', 'stack', 'services', '--format', '{{.Name}} {{.Image}}', 'stack'],
                    },
                    {
                        'args': ['docker', 'service', 'update', '--image', 'digest1', 'service1'],
                    },
                    {
                        'args': ['docker', 'service', 'update', '--image', 'digest2', 'service2'],
                    },
                    {
                        'args': ['docker', 'rmi', 'fabricio-current-stack:stack;', 'docker', 'tag', 'fabricio-backup-stack:stack', 'fabricio-current-stack:stack;', 'docker', 'rmi', 'fabricio-backup-stack:stack'],
                    },
                ],
                expected_compose_file=b'compose.yml',
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                fab.env.command = '{0}__{1}'.format(self, case)
                put.reset_mock()
                with mock.patch.dict(fab.env, dict(all_hosts=data.get('all_hosts', ['host']))):
                    stack = docker.Stack(**data.get('init_kwargs', {}))
                    side_effects = data.get('side_effect', [])
                    side_effect = self.command_checker(
                        args_parsers=data.get('args_parser', []),
                        expected_args_set=data.get('expected_command_args', []),
                        side_effects=side_effects,
                    )
                    with mock.patch.object(fabricio, 'run', side_effect=side_effect) as run:
                        with mock.patch('six.BytesIO') as compose_file:
                            stack.revert()
                    self.assertEqual(run.call_count, len(side_effects))
                    expected_compose_file = data.get('expected_compose_file')
                    if expected_compose_file:
                        put.assert_called_once()
                        compose_file.assert_called_once_with(expected_compose_file)
                    else:
                        put.assert_not_called()

    def test_revert_raises_error_when_backup_not_found(self):
        side_effect = self.command_checker(
            args_parsers=[args_parser, docker_inspect_args_parser],
            expected_args_set=[
                {
                    'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                },
                {
                    'executable': ['docker', 'inspect'],
                    'type': 'image',
                    'image_or_container': 'fabricio-backup-stack:stack',
                },
            ],
            side_effects=[
                SucceededResult('  Is Manager: true'),  # manager status
                docker.ImageNotFoundError(),  # image info
            ],
        )
        with mock.patch.object(fabricio, 'run', side_effect=side_effect):
            stack = docker.Stack(name='stack')
            with self.assertRaises(docker.ServiceError):
                stack.revert()
