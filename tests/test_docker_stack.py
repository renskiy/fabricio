import collections
import functools
import json

import mock
import six

from fabric import api as fab

import fabricio

from fabricio import docker, utils
from fabricio.docker import stack as stack_module
from tests import SucceededResult, args_parser, FabricioTestCase


def as_ordereddict(result):
    return collections.OrderedDict(sorted(result.items()))


class StackTestCase(FabricioTestCase):

    maxDiff = None

    def setUp(self):
        stack_module.open = mock.MagicMock()
        self.cd = mock.patch.object(fab, 'cd')
        self.cd.start()

    def tearDown(self):
        stack_module.open = open
        self.cd.stop()

    @mock.patch.object(fabricio, 'log')
    @mock.patch.object(stack_module, 'dict', new=collections.OrderedDict)
    @mock.patch.object(stack_module, 'set', new=utils.OrderedSet)
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
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                ],
                expected_result=None,
                all_hosts=['host1', 'host2'],
            ),
            no_changes=dict(
                init_kwargs=dict(name='stack'),
                update_kwargs={},
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult(json.dumps([{'Config': {
                        'Labels': {
                            'fabricio.configuration': 'Y29tcG9zZS55bWw=',
                            'fabricio.digests': 'e30=',
                        },
                    }}])),  # image info
                    SucceededResult(),  # remove config file
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-current-stack:stack']},
                    {'args': ['rm', '-f', 'docker-compose.yml']},
                ],
                expected_result=False,
                expected_config_filename='docker-compose.yml',
            ),
            forced=dict(
                init_kwargs=dict(name='stack'),
                update_kwargs=dict(force=True),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult(),  # stack deploy
                    docker.ImageNotFoundError(),  # backup image info
                    fabricio.Error(),  # update sentinel images
                    SucceededResult(),  # stack images
                    SucceededResult(),  # build new sentinel image
                    SucceededResult(),  # remove config file
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {
                        'args': ['docker', 'stack', 'deploy', '--compose-file=docker-compose.yml', 'stack'],
                    },
                    {
                        'args': ['docker', 'inspect', '--type', 'image', 'fabricio-backup-stack:stack'],
                    },
                    {
                        'args': ['docker', 'rmi', 'fabricio-backup-stack:stack;', 'docker', 'tag', 'fabricio-current-stack:stack', 'fabricio-backup-stack:stack;', 'docker', 'rmi', 'fabricio-current-stack:stack'],
                    },
                    {
                        'args': ['docker', 'stack', 'services', '--format', '{{.Name}} {{.Image}}', 'stack'],
                    },
                    {
                        'args': ['echo', 'FROM scratch\nLABEL fabricio.configuration=Y29tcG9zZS55bWw= fabricio.digests=e30=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                    {'args': ['rm', '-f', 'docker-compose.yml']},
                ],
                expected_result=True,
                expected_config_filename='docker-compose.yml',
            ),
            created=dict(
                init_kwargs=dict(name='stack'),
                update_kwargs=dict(),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    docker.ImageNotFoundError(),  # current image info
                    SucceededResult(),  # stack deploy
                    docker.ImageNotFoundError(),  # backup image info
                    SucceededResult(),  # update sentinel images
                    SucceededResult(),  # stack images
                    SucceededResult(),  # build new sentinel image
                    SucceededResult(),  # remove config file
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-current-stack:stack']},
                    {
                        'args': ['docker', 'stack', 'deploy', '--compose-file=docker-compose.yml', 'stack'],
                    },
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-backup-stack:stack']},
                    {
                        'args': ['docker', 'rmi', 'fabricio-backup-stack:stack;', 'docker', 'tag', 'fabricio-current-stack:stack', 'fabricio-backup-stack:stack;', 'docker', 'rmi', 'fabricio-current-stack:stack'],
                    },
                    {
                        'args': ['docker', 'stack', 'services', '--format', '{{.Name}} {{.Image}}', 'stack'],
                    },
                    {
                        'args': ['echo', 'FROM scratch\nLABEL fabricio.configuration=Y29tcG9zZS55bWw= fabricio.digests=e30=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                    {'args': ['rm', '-f', 'docker-compose.yml']},
                ],
                expected_result=True,
                expected_config_filename='docker-compose.yml',
            ),
            created_skip_sentinels_errors=dict(
                init_kwargs=dict(name='stack'),
                update_kwargs=dict(),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    docker.ImageNotFoundError(),  # image info
                    SucceededResult(),  # stack deploy
                    docker.ImageNotFoundError(),  # image info
                    fabricio.Error(),  # update sentinel images
                    fabricio.Error(),  # stack images
                    fabricio.Error(),  # build new sentinel image
                    SucceededResult(),  # remove config file
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-current-stack:stack']},
                    {
                        'args': ['docker', 'stack', 'deploy', '--compose-file=docker-compose.yml', 'stack'],
                    },
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-backup-stack:stack']},
                    {
                        'args': ['docker', 'rmi', 'fabricio-backup-stack:stack;', 'docker', 'tag', 'fabricio-current-stack:stack', 'fabricio-backup-stack:stack;', 'docker', 'rmi', 'fabricio-current-stack:stack'],
                    },
                    {
                        'args': ['docker', 'stack', 'services', '--format', '{{.Name}} {{.Image}}', 'stack'],
                    },
                    {
                        'args': ['echo', 'FROM scratch\nLABEL fabricio.configuration=Y29tcG9zZS55bWw=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                    {'args': ['rm', '-f', 'docker-compose.yml']},
                ],
                expected_result=True,
                expected_config_filename='docker-compose.yml',
            ),
            created_with_custom_compose=dict(
                init_kwargs=dict(name='stack', options=dict(config='compose.yml')),
                update_kwargs=dict(),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    docker.ImageNotFoundError(),  # image info
                    SucceededResult(),  # stack deploy
                    docker.ImageNotFoundError(),  # image info
                    SucceededResult(),  # update sentinel images
                    SucceededResult(),  # stack images
                    SucceededResult(),  # build new sentinel image
                    SucceededResult(),  # remove config file
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-current-stack:stack']},
                    {
                        'args': ['docker', 'stack', 'deploy', '--compose-file=compose.yml', 'stack'],
                    },
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-backup-stack:stack']},
                    {
                        'args': ['docker', 'rmi', 'fabricio-backup-stack:stack;', 'docker', 'tag', 'fabricio-current-stack:stack', 'fabricio-backup-stack:stack;', 'docker', 'rmi', 'fabricio-current-stack:stack'],
                    },
                    {
                        'args': ['docker', 'stack', 'services', '--format', '{{.Name}} {{.Image}}', 'stack'],
                    },
                    {
                        'args': ['echo', 'FROM scratch\nLABEL fabricio.configuration=Y29tcG9zZS55bWw= fabricio.digests=e30=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                    {'args': ['rm', '-f', 'compose.yml']},
                ],
                expected_result=True,
                expected_config_filename='compose.yml',
            ),
            created_with_custom_compose2=dict(
                init_kwargs=dict(name='stack', options={'compose-file': 'compose.yml'}),
                update_kwargs=dict(),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    docker.ImageNotFoundError(),  # image info
                    SucceededResult(),  # stack deploy
                    docker.ImageNotFoundError(),  # image info
                    SucceededResult(),  # update sentinel images
                    SucceededResult(),  # stack images
                    SucceededResult(),  # build new sentinel image
                    SucceededResult(),  # remove config file
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-current-stack:stack']},
                    {
                        'args': ['docker', 'stack', 'deploy', '--compose-file=compose.yml', 'stack'],
                    },
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-backup-stack:stack']},
                    {
                        'args': ['docker', 'rmi', 'fabricio-backup-stack:stack;', 'docker', 'tag', 'fabricio-current-stack:stack', 'fabricio-backup-stack:stack;', 'docker', 'rmi', 'fabricio-current-stack:stack'],
                    },
                    {
                        'args': ['docker', 'stack', 'services', '--format', '{{.Name}} {{.Image}}', 'stack'],
                    },
                    {
                        'args': ['echo', 'FROM scratch\nLABEL fabricio.configuration=Y29tcG9zZS55bWw= fabricio.digests=e30=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                    {'args': ['rm', '-f', 'compose.yml']},
                ],
                expected_result=True,
                expected_config_filename='compose.yml',
            ),
            created_with_custom_image=dict(
                init_kwargs=dict(name='stack', image='image:tag'),
                update_kwargs=dict(),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    docker.ImageNotFoundError(),  # image info
                    SucceededResult(),  # stack deploy
                    docker.ImageNotFoundError(),  # image info
                    SucceededResult(),  # update sentinel images
                    SucceededResult(),  # stack images
                    SucceededResult(),  # build new sentinel image
                    SucceededResult(),  # remove config file
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-current-stack:stack']},
                    {
                        'args': ['docker', 'stack', 'deploy', '--compose-file=docker-compose.yml', 'stack'],
                    },
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-backup-stack:stack']},
                    {
                        'args': ['docker', 'rmi', 'fabricio-backup-stack:stack;', 'docker', 'tag', 'fabricio-current-stack:stack', 'fabricio-backup-stack:stack;', 'docker', 'rmi', 'fabricio-current-stack:stack'],
                    },
                    {
                        'args': ['docker', 'stack', 'services', '--format', '{{.Name}} {{.Image}}', 'stack'],
                    },
                    {
                        'args': ['echo', 'FROM image:tag\nLABEL fabricio.configuration=Y29tcG9zZS55bWw= fabricio.digests=e30=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                    {'args': ['rm', '-f', 'docker-compose.yml']},
                ],
                expected_result=True,
                expected_config_filename='docker-compose.yml',
            ),
            created_with_custom_image_update_params=dict(
                init_kwargs=dict(name='stack', image='image:tag'),
                update_kwargs=dict(tag='new-tag', registry='registry', account='account'),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    docker.ImageNotFoundError(),  # image info
                    SucceededResult(),  # stack deploy
                    docker.ImageNotFoundError(),  # image info
                    SucceededResult(),  # update sentinel images
                    SucceededResult(),  # stack images
                    SucceededResult(),  # build new sentinel image
                    SucceededResult(),  # remove config file
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-current-stack:stack']},
                    {
                        'args': ['docker', 'stack', 'deploy', '--compose-file=docker-compose.yml', 'stack'],
                    },
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-backup-stack:stack']},
                    {
                        'args': ['docker', 'rmi', 'fabricio-backup-stack:stack;', 'docker', 'tag', 'fabricio-current-stack:stack', 'fabricio-backup-stack:stack;', 'docker', 'rmi', 'fabricio-current-stack:stack'],
                    },
                    {
                        'args': ['docker', 'stack', 'services', '--format', '{{.Name}} {{.Image}}', 'stack'],
                    },
                    {
                        'args': ['echo', 'FROM registry/account/image:new-tag\nLABEL fabricio.configuration=Y29tcG9zZS55bWw= fabricio.digests=e30=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                    {'args': ['rm', '-f', 'docker-compose.yml']},
                ],
                expected_result=True,
                expected_config_filename='docker-compose.yml',
            ),
            created_from_empty_image_with_custom_image_update_params=dict(
                init_kwargs=dict(name='stack'),
                update_kwargs=dict(tag='registry/account/image:tag'),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    docker.ImageNotFoundError(),  # image info
                    SucceededResult(),  # stack deploy
                    docker.ImageNotFoundError(),  # image info
                    SucceededResult(),  # update sentinel images
                    SucceededResult(),  # stack images
                    SucceededResult(),  # build new sentinel image
                    SucceededResult(),  # remove config file
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-current-stack:stack']},
                    {
                        'args': ['docker', 'stack', 'deploy', '--compose-file=docker-compose.yml', 'stack'],
                    },
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-backup-stack:stack']},
                    {
                        'args': ['docker', 'rmi', 'fabricio-backup-stack:stack;', 'docker', 'tag', 'fabricio-current-stack:stack', 'fabricio-backup-stack:stack;', 'docker', 'rmi', 'fabricio-current-stack:stack'],
                    },
                    {
                        'args': ['docker', 'stack', 'services', '--format', '{{.Name}} {{.Image}}', 'stack'],
                    },
                    {
                        'args': ['echo', 'FROM registry/account/image:tag\nLABEL fabricio.configuration=Y29tcG9zZS55bWw= fabricio.digests=e30=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                    {'args': ['rm', '-f', 'docker-compose.yml']},
                ],
                expected_result=True,
                expected_config_filename='docker-compose.yml',
            ),
            updated_compose_changed=dict(
                init_kwargs=dict(name='stack'),
                update_kwargs=dict(),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult(json.dumps([{'Config': {
                        'Labels': {
                            'fabricio.configuration': 'b2xkLWNvbXBvc2UueW1s',
                            'fabricio.digests': 'eyJpbWFnZTp0YWciOiAiZGlnZXN0In0=',
                        },
                    }}])),  # current image info
                    SucceededResult(),  # stack deploy
                    SucceededResult('[{"Parent": "backup_parent_id"}]'),  # backup image info
                    SucceededResult(),  # update sentinel images
                    SucceededResult('service image:tag'),  # stack images
                    SucceededResult(), SucceededResult(), SucceededResult(),  # image pull
                    SucceededResult('digest'),  # images digests
                    SucceededResult(),  # build new sentinel image
                    SucceededResult(),  # remove config file
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-current-stack:stack']},
                    {
                        'args': ['docker', 'stack', 'deploy', '--compose-file=docker-compose.yml', 'stack'],
                    },
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-backup-stack:stack']},
                    {
                        'args': ['docker', 'rmi', 'fabricio-backup-stack:stack' , 'backup_parent_id;', 'docker', 'tag', 'fabricio-current-stack:stack', 'fabricio-backup-stack:stack;', 'docker', 'rmi', 'fabricio-current-stack:stack'],
                    },
                    {
                        'args': ['docker', 'stack', 'services', '--format', '{{.Name}} {{.Image}}', 'stack'],
                    },
                    {'args': ['docker', 'tag', 'image:tag', 'fabricio-temp-image:image', '&&', 'docker', 'rmi', 'image:tag']}, {'args': ['docker', 'pull', 'image:tag']}, {'args': ['docker', 'rmi', 'fabricio-temp-image:image']},
                    {
                        'args': ['docker', 'inspect', '--type', 'image', '--format', '{{index .RepoDigests 0}}', 'image:tag'],
                    },
                    {
                        'args': ['echo', 'FROM scratch\nLABEL fabricio.configuration=Y29tcG9zZS55bWw= fabricio.digests=eyJpbWFnZTp0YWciOiAiZGlnZXN0In0=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                    {'args': ['rm', '-f', 'docker-compose.yml']},
                ],
                expected_result=True,
                expected_config_filename='docker-compose.yml',
            ),
            updated_image_changed=dict(
                init_kwargs=dict(name='stack'),
                update_kwargs=dict(),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult(json.dumps([{'Config': {
                        'Labels': {
                            'fabricio.configuration': 'Y29tcG9zZS55bWw=',
                            'fabricio.digests': 'eyJpbWFnZTp0YWciOiAiZGlnZXN0In0=',
                        },
                    }}])),  # image info
                    SucceededResult(), SucceededResult(), SucceededResult(),  # image pull
                    SucceededResult('new-digest'),  # images digests
                    SucceededResult(),  # stack deploy
                    docker.ImageNotFoundError(),  # backup image info
                    SucceededResult(),  # update sentinel images
                    SucceededResult('service image:tag'),  # stack images
                    SucceededResult(), SucceededResult(), SucceededResult(),  # image pull
                    SucceededResult('new-digest'),  # images digests
                    SucceededResult(),  # build new sentinel image
                    SucceededResult(),  # remove config file
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-current-stack:stack']},
                    {'args': ['docker', 'tag', 'image:tag', 'fabricio-temp-image:image', '&&', 'docker', 'rmi', 'image:tag']}, {'args': ['docker', 'pull', 'image:tag']}, {'args': ['docker', 'rmi', 'fabricio-temp-image:image']},
                    {
                        'args': ['docker', 'inspect', '--type', 'image', '--format', '{{index .RepoDigests 0}}', 'image:tag'],
                    },
                    {
                        'args': ['docker', 'stack', 'deploy', '--compose-file=docker-compose.yml', 'stack'],
                    },
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-backup-stack:stack']},
                    {
                        'args': ['docker', 'rmi', 'fabricio-backup-stack:stack;', 'docker', 'tag', 'fabricio-current-stack:stack', 'fabricio-backup-stack:stack;', 'docker', 'rmi', 'fabricio-current-stack:stack'],
                    },
                    {
                        'args': ['docker', 'stack', 'services', '--format', '{{.Name}} {{.Image}}', 'stack'],
                    },
                    {'args': ['docker', 'tag', 'image:tag', 'fabricio-temp-image:image', '&&', 'docker', 'rmi', 'image:tag']}, {'args': ['docker', 'pull', 'image:tag']}, {'args': ['docker', 'rmi', 'fabricio-temp-image:image']},
                    {
                        'args': ['docker', 'inspect', '--type', 'image', '--format', '{{index .RepoDigests 0}}', 'image:tag'],
                    },
                    {
                        'args': ['echo', 'FROM scratch\nLABEL fabricio.configuration=Y29tcG9zZS55bWw= fabricio.digests=eyJpbWFnZTp0YWciOiAibmV3LWRpZ2VzdCJ9\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                    {'args': ['rm', '-f', 'docker-compose.yml']},
                ],
                expected_result=True,
                expected_config_filename='docker-compose.yml',
            ),
            updated_images_changed=dict(
                init_kwargs=dict(name='stack'),
                update_kwargs=dict(),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult(json.dumps([{'Config': {
                        'Labels': {
                            'fabricio.configuration': 'Y29tcG9zZS55bWw=',
                            'fabricio.digests': 'eyJpbWFnZTE6dGFnIjogImRpZ2VzdDEiLCAiaW1hZ2UyOnRhZyI6ICJkaWdlc3QyIn0=',
                        },
                    }}])),  # image info
                    SucceededResult(), SucceededResult(), SucceededResult(),  # image1 pull
                    SucceededResult(), SucceededResult(), SucceededResult(),  # image2 pull
                    SucceededResult('new-digest1\nnew-digest2\n'),  # images digests
                    SucceededResult(),  # stack deploy
                    docker.ImageNotFoundError(),  # backup image info
                    SucceededResult(),  # update sentinel images
                    SucceededResult('service1 image1:tag\nservice2 image2:tag\n'),  # stack images
                    SucceededResult(), SucceededResult(), SucceededResult(),  # image1 pull
                    SucceededResult(), SucceededResult(), SucceededResult(),  # image2 pull
                    SucceededResult('new-digest1\nnew-digest2\n'),  # images digests
                    SucceededResult(),  # build new sentinel image
                    SucceededResult(),  # remove config file
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-current-stack:stack']},
                    {'args': ['docker', 'tag', 'image1:tag', 'fabricio-temp-image:image1', '&&', 'docker', 'rmi', 'image1:tag']}, {'args': ['docker', 'pull', 'image1:tag']}, {'args': ['docker', 'rmi', 'fabricio-temp-image:image1']},
                    {'args': ['docker', 'tag', 'image2:tag', 'fabricio-temp-image:image2', '&&', 'docker', 'rmi', 'image2:tag']}, {'args': ['docker', 'pull', 'image2:tag']}, {'args': ['docker', 'rmi', 'fabricio-temp-image:image2']},
                    {
                        'args': ['docker', 'inspect', '--type', 'image', '--format', '{{index .RepoDigests 0}}', 'image1:tag', 'image2:tag'],
                    },
                    {
                        'args': ['docker', 'stack', 'deploy', '--compose-file=docker-compose.yml', 'stack'],
                    },
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-backup-stack:stack']},
                    {
                        'args': ['docker', 'rmi', 'fabricio-backup-stack:stack;', 'docker', 'tag', 'fabricio-current-stack:stack', 'fabricio-backup-stack:stack;', 'docker', 'rmi', 'fabricio-current-stack:stack'],
                    },
                    {
                        'args': ['docker', 'stack', 'services', '--format', '{{.Name}} {{.Image}}', 'stack'],
                    },
                    {'args': ['docker', 'tag', 'image1:tag', 'fabricio-temp-image:image1', '&&', 'docker', 'rmi', 'image1:tag']}, {'args': ['docker', 'pull', 'image1:tag']}, {'args': ['docker', 'rmi', 'fabricio-temp-image:image1']},
                    {'args': ['docker', 'tag', 'image2:tag', 'fabricio-temp-image:image2', '&&', 'docker', 'rmi', 'image2:tag']}, {'args': ['docker', 'pull', 'image2:tag']}, {'args': ['docker', 'rmi', 'fabricio-temp-image:image2']},
                    {
                        'args': ['docker', 'inspect', '--type', 'image', '--format', '{{index .RepoDigests 0}}', 'image1:tag', 'image2:tag'],
                    },
                    {
                        'args': ['echo', 'FROM scratch\nLABEL fabricio.configuration=Y29tcG9zZS55bWw= fabricio.digests=eyJpbWFnZTE6dGFnIjogIm5ldy1kaWdlc3QxIiwgImltYWdlMjp0YWciOiAibmV3LWRpZ2VzdDIifQ==\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                    {'args': ['rm', '-f', 'docker-compose.yml']},
                ],
                expected_result=True,
                expected_config_filename='docker-compose.yml',
            ),
        )
        for case, data in cases.items():
            with self.subTest(case):
                fab.env.command = '{0}__{1}'.format(self, case)
                with mock.patch.dict(fab.env, dict(all_hosts=data.get('all_hosts', ['host']))):
                    stack_module.open.return_value = six.BytesIO(b'compose.yml')
                    stack_module.open.reset_mock()
                    put.reset_mock()
                    stack = docker.Stack(**data.get('init_kwargs', {}))
                    side_effect = self.command_checker(
                        args_parsers=args_parser,
                        expected_args_set=data.get('expected_command_args', []),
                        side_effects=data.get('side_effect', []),
                    )
                    with mock.patch.object(fabricio, 'run', side_effect=side_effect) as run:
                        with mock.patch('fabricio.operations.run', run):
                            with mock.patch('six.BytesIO') as compose_file:
                                result = stack.update(**data.get('update_kwargs', {}))
                    self.assertEqual(data['expected_result'], result)
                    expected_compose_file_name = data.get('expected_config_filename')
                    if expected_compose_file_name:
                        stack_module.open.assert_called_once_with(expected_compose_file_name, 'rb')
                        put.assert_called_once()
                        compose_file.assert_called_once_with(b'compose.yml')

    @mock.patch.object(stack_module, 'dict', new=collections.OrderedDict)
    @mock.patch.object(fab, 'put')
    def test_revert(self, put, *args):
        cases = dict(
            worker=dict(
                init_kwargs=dict(name='stack'),
                side_effect=[
                    SucceededResult('  Is Manager: false'),  # manager status
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
                            'fabricio.configuration': 'b2xkLWNvbXBvc2UueW1s',
                        },
                    }}])),  # backup image info
                    SucceededResult(),  # stack deploy
                    SucceededResult(),  # remove config file
                    SucceededResult('[{"Parent": "current_parent_id"}]'),  # current image info
                    SucceededResult(),  # update sentinel images
                ],
                expected_command_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-backup-stack:stack']},
                    {
                        'args': ['docker', 'stack', 'deploy', '--compose-file=docker-compose.yml', 'stack'],
                    },
                    {'args': ['rm', '-f',  'docker-compose.yml']},
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-current-stack:stack']},
                    {
                        'args': ['docker', 'rmi', 'fabricio-current-stack:stack', 'current_parent_id;', 'docker', 'tag', 'fabricio-backup-stack:stack', 'fabricio-current-stack:stack;', 'docker', 'rmi', 'fabricio-backup-stack:stack'],
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
                            'fabricio.configuration': 'Y29tcG9zZS55bWw=',  # compose.yml
                            'fabricio.digests': 'eyJpbWFnZTp0YWciOiAiZGlnZXN0In0=',  # {"image:tag": "digest"}
                        },
                    }}])),  # image info
                    SucceededResult(),  # stack deploy
                    SucceededResult('service image:tag\n'),  # stack services
                    SucceededResult(),  # service update
                    SucceededResult(),  # remove config file
                    SucceededResult('[{"Parent": "current_parent_id"}]'),  # current image info
                    SucceededResult(),  # update sentinel images
                ],
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
                    {'args': ['rm', '-f',  'docker-compose.yml']},
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-current-stack:stack']},
                    {
                        'args': ['docker', 'rmi', 'fabricio-current-stack:stack', 'current_parent_id;', 'docker', 'tag', 'fabricio-backup-stack:stack', 'fabricio-current-stack:stack;', 'docker', 'rmi', 'fabricio-backup-stack:stack'],
                    },
                ],
                expected_compose_file=b'compose.yml',
            ),
            reverted_with_services_updates=dict(
                init_kwargs=dict(name='stack'),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult(json.dumps([{'Config': {
                        'Labels': {
                            'fabricio.configuration': 'Y29tcG9zZS55bWw=',  # compose.yml
                            'fabricio.digests': 'eyJpbWFnZTE6dGFnIjogImRpZ2VzdDEiLCAiaW1hZ2UyOnRhZyI6ICJkaWdlc3QyIn0=',  # {"image1:tag": "digest1", "image2:tag": "digest2"}
                        },
                    }}])),  # image info
                    SucceededResult(),  # stack deploy
                    SucceededResult('service1 image1:tag\nservice2 image2:tag'),  # stack services
                    SucceededResult(),  # service update
                    SucceededResult(),  # service update
                    SucceededResult(),  # remove config file
                    SucceededResult('[{"Parent": "current_parent_id"}]'),  # current image info
                    SucceededResult(),  # update sentinel images
                ],
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
                    {'args': ['rm', '-f',  'docker-compose.yml']},
                    {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-current-stack:stack']},
                    {
                        'args': ['docker', 'rmi', 'fabricio-current-stack:stack', 'current_parent_id;', 'docker', 'tag', 'fabricio-backup-stack:stack', 'fabricio-current-stack:stack;', 'docker', 'rmi', 'fabricio-backup-stack:stack'],
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
                        args_parsers=args_parser,
                        expected_args_set=data.get('expected_command_args', []),
                        side_effects=side_effects,
                    )
                    with mock.patch.object(fabricio, 'run', side_effect=side_effect) as run:
                        with mock.patch('fabricio.operations.run', run):
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
            args_parsers=args_parser,
            expected_args_set=[
                {
                    'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                },
                {'args': ['docker', 'inspect', '--type', 'image', 'fabricio-backup-stack:stack']},
            ],
            side_effects=[
                SucceededResult('  Is Manager: true'),  # manager status
                docker.ImageNotFoundError(),  # image info
            ],
        )
        with mock.patch.object(fabricio, 'run', side_effect=side_effect):
            fab.env.command = 'test_stack_revert_raises_error_when_backup_not_found'
            stack = docker.Stack(name='stack')
            with self.assertRaises(docker.ServiceError):
                stack.revert()

    @mock.patch.object(docker.Stack, 'is_manager', return_value=True)
    @mock.patch.object(fabricio, 'run', side_effect=Exception())
    def test_revert_does_not_rollback_sentinels_on_error(self, *args):
        with mock.patch.object(docker.Stack, 'rotate_sentinel_images') as rotate_sentinel_images:
            fab.env.command = 'test_stack_revert_does_not_rollback_sentinels_on_error'
            stack = docker.Stack(name='stack')
            with self.assertRaises(Exception):
                stack.revert()
            stack.revert()
            rotate_sentinel_images.assert_not_called()

    @mock.patch.object(docker.ManagedService, 'is_manager', return_value=True)
    @mock.patch.object(fabricio, 'run')
    def test_destroy(self, run, *_):
        run.side_effect = [SucceededResult('service image')] + [SucceededResult('[{"Parent": "parent_id"}]')] * 4
        stack = docker.Stack(name='name')
        stack.destroy()
        self.assertListEqual(
            [
                mock.call('docker stack services --format "{{.Name}} {{.Image}}" name'),
                mock.call('docker stack rm  name'),
                mock.call('docker inspect --type image fabricio-current-stack:name', abort_exception=docker.ImageNotFoundError),
                mock.call('docker inspect --type image fabricio-backup-stack:name', abort_exception=docker.ImageNotFoundError),
                mock.call('docker rmi fabricio-current-stack:name fabricio-backup-stack:name parent_id parent_id image', ignore_errors=True),
            ],
            run.mock_calls,
        )
