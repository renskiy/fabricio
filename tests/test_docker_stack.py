import json

import mock
import six

from fabric import api as fab

import fabricio

from fabricio import docker
from fabricio.docker import service
from tests import SucceededResult, args_parser, FabricioTestCase, \
    docker_inspect_args_parser


class ContainerTestCase(FabricioTestCase):

    def setUp(self):
        service.open = mock.MagicMock()
        self.cd = mock.patch.object(fab, 'cd')
        self.cd.start()

    def tearDown(self):
        service.open = open
        self.cd.stop()

    @mock.patch.object(fabricio, 'log')
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
                    SucceededResult(),  # build new sentinel image
                ],
                args_parser=[
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
                        'args': ['echo', 'FROM scratch\nLABEL fabricio.stack.compose.stack=Y29tcG9zZS55bWw=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                ],
                expected_result=True,
                expected_compose_file='docker-compose.yml',
                should_upload_compose_file=True,
            ),
            updated=dict(
                init_kwargs=dict(name='stack'),
                update_kwargs=dict(),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult('[{}]'),  # image info
                    SucceededResult(),  # stack deploy
                    SucceededResult(),  # update sentinel images
                    SucceededResult(),  # build new sentinel image
                ],
                args_parser=[
                    args_parser,
                    docker_inspect_args_parser,
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
                        'args': ['echo', 'FROM scratch\nLABEL fabricio.stack.compose.stack=Y29tcG9zZS55bWw=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                ],
                expected_result=True,
                expected_compose_file='docker-compose.yml',
                should_upload_compose_file=True,
            ),
            updated_skip_sentinels_errors=dict(
                init_kwargs=dict(name='stack'),
                update_kwargs=dict(),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult('[{}]'),  # image info
                    SucceededResult(),  # stack deploy
                    SucceededResult(),  # update sentinel images
                    SucceededResult(),  # build new sentinel image
                ],
                args_parser=[
                    args_parser,
                    docker_inspect_args_parser,
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
                        'args': ['echo', 'FROM scratch\nLABEL fabricio.stack.compose.stack=Y29tcG9zZS55bWw=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                ],
                expected_result=True,
                expected_compose_file='docker-compose.yml',
                should_upload_compose_file=True,
            ),
            updated_with_custom_compose=dict(
                init_kwargs=dict(name='stack', options=dict(compose_file='compose.yml')),
                update_kwargs=dict(),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult('[{}]'),  # image info
                    SucceededResult(),  # stack deploy
                    RuntimeError(),  # update sentinel images
                    RuntimeError(),  # build new sentinel image
                ],
                args_parser=[
                    args_parser,
                    docker_inspect_args_parser,
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
                        'args': ['echo', 'FROM scratch\nLABEL fabricio.stack.compose.stack=Y29tcG9zZS55bWw=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                ],
                expected_result=True,
                expected_compose_file='compose.yml',
                should_upload_compose_file=True,
            ),
            updated_with_custom_compose2=dict(
                init_kwargs=dict(name='stack', options={'compose-file': 'compose.yml'}),
                update_kwargs=dict(),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult('[{}]'),  # image info
                    SucceededResult(),  # stack deploy
                    SucceededResult(),  # update sentinel images
                    SucceededResult(),  # build new sentinel image
                ],
                args_parser=[
                    args_parser,
                    docker_inspect_args_parser,
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
                        'args': ['echo', 'FROM scratch\nLABEL fabricio.stack.compose.stack=Y29tcG9zZS55bWw=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                ],
                expected_result=True,
                expected_compose_file='compose.yml',
                should_upload_compose_file=True,
            ),
            updated_with_custom_image=dict(
                init_kwargs=dict(name='stack', image='image:tag'),
                update_kwargs=dict(),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult('[{}]'),  # image info
                    SucceededResult(),  # stack deploy
                    SucceededResult(),  # update sentinel images
                    SucceededResult(),  # build new sentinel image
                ],
                args_parser=[
                    args_parser,
                    docker_inspect_args_parser,
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
                        'args': ['echo', 'FROM image:tag\nLABEL fabricio.stack.compose.stack=Y29tcG9zZS55bWw=\n', '|', 'docker', 'build', '--tag', 'fabricio-current-stack:stack', '-'],
                    },
                ],
                expected_result=True,
                expected_compose_file_name='docker-compose.yml',
                should_upload_compose_file=True,
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
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

    @mock.patch.object(fab, 'put')
    def test_revert(self, put):
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
            reverted_with_same_compose=dict(
                init_kwargs=dict(name='stack'),
                side_effect=[
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult(json.dumps([{'Config': {
                        'Labels': {
                            'fabricio.stack.compose.stack': 'Y29tcG9zZS55bWw=',
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
                expected_compose_file=b'compose.yml',
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                fab.env.command = '{0}__{1}'.format(self, case)
                put.reset_mock()
                with mock.patch.dict(fab.env, dict(all_hosts=data.get('all_hosts', ['host']))):
                    stack = docker.Stack(**data.get('init_kwargs', {}))
                    side_effect = self.command_checker(
                        args_parsers=data.get('args_parser', []),
                        expected_args_set=data.get('expected_command_args', []),
                        side_effects=data.get('side_effect', []),
                    )
                    with mock.patch.object(fabricio, 'run', side_effect=side_effect):
                        with mock.patch('six.BytesIO') as compose_file:
                            stack.revert()
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
