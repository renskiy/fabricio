import mock
import unittest2 as unittest

import fabricio

from fabricio import docker


class TestContainer(docker.Container):

    image = 'image:tag'


class ContainerTestCase(unittest.TestCase):

    def test_info(self):
        return_value = '[{"Id": "123", "Image": "abc"}]'
        container = docker.Container(name='name')
        expected_command = 'docker inspect --type container name'
        with mock.patch.object(
            fabricio,
            'exec_command',
            return_value=return_value,
        ) as exec_command:
            self.assertEqual(dict(Id='123', Image='abc'), container.info)
            exec_command.assert_called_once_with(expected_command)

    def test_delete(self):
        cases = dict(
            regular=dict(
                delete_kwargs=dict(),
                expected_command='docker rm name',
            ),
            forced=dict(
                delete_kwargs=dict(force=True),
                expected_command='docker rm --force name',
            ),
        )
        for case, params in cases.items():
            with self.subTest(case=case):
                container = docker.Container(name='name')
                with mock.patch.object(
                    fabricio,
                    'exec_command',
                ) as exec_command:
                    expected_command = params['expected_command']
                    delete_kwargs = params['delete_kwargs']

                    container.delete(**delete_kwargs)

                    exec_command.assert_called_once_with(
                        expected_command,
                        ignore_errors=False,
                    )

    def test_execute(self):
        container = docker.Container(name='name')
        expected_command = 'docker exec --tty name cmd'
        with mock.patch.object(
            fabricio,
            'exec_command',
            return_value='result'
        ) as exec_command:
            result = container.execute('cmd')
            exec_command.assert_called_once_with(
                expected_command,
                ignore_errors=False,
            )
            self.assertEqual('result', result)

    def test_start(self):
        container = docker.Container(name='name')
        expected_command = 'docker start name'
        with mock.patch.object(fabricio, 'exec_command') as exec_command:
            container.start()
            exec_command.assert_called_once_with(expected_command)

    def test_stop(self):
        container = docker.Container(name='name')
        expected_command = 'docker stop --time 10 name'
        with mock.patch.object(fabricio, 'exec_command') as exec_command:
            container.stop()
            exec_command.assert_called_once_with(expected_command)

    def test_restart(self):
        container = docker.Container(name='name')
        expected_command = 'docker restart --time 10 name'
        with mock.patch.object(fabricio, 'exec_command') as exec_command:
            container.restart()
            exec_command.assert_called_once_with(expected_command)

    def test_rename(self):
        container = docker.Container(name='name')
        expected_command = 'docker rename name new_name'
        with mock.patch.object(fabricio, 'exec_command') as exec_command:
            container.rename('new_name')
            exec_command.assert_called_once_with(expected_command)
            self.assertEqual('new_name', container.name)

    def test_signal(self):
        container = docker.Container(name='name')
        expected_command = 'docker kill --signal SIGTERM name'
        with mock.patch.object(fabricio, 'exec_command') as exec_command:
            container.signal('SIGTERM')
            exec_command.assert_called_once_with(expected_command)

    def test_run(self):
        cases = dict(
            basic=dict(
                init_kwargs=dict(
                    name='name',
                ),
                class_kwargs=dict(image='image:tag'),
                expected_command='docker run --name name --detach image:tag ',
            ),
            complex=dict(
                init_kwargs=dict(
                    name='name',
                    options=dict(foo='bar'),
                ),
                class_kwargs=dict(
                    image='image:tag',
                    cmd='cmd',
                    user='user',
                    ports=['80:80', '443:443'],
                    env=['FOO=foo', 'BAR=bar'],
                    volumes=['/tmp:/tmp', '/root:/root:ro'],
                    links=['db:db'],
                    hosts=['host:192.168.0.1'],
                    network='network',
                    restart_policy='restart_policy',
                    stop_signal='stop_signal',
                ),
                expected_command=(
                    'docker run '
                    '--foo bar '
                    '--name name '
                    '--user user '
                    '--publish 80:80 --publish 443:443 '
                    '--env FOO=foo --env BAR=bar '
                    '--volume /tmp:/tmp --volume /root:/root:ro '
                    '--link db:db '
                    '--add-host host:192.168.0.1 '
                    '--net network '
                    '--restart restart_policy '
                    '--stop-signal stop_signal '
                    '--detach '
                    'image:tag cmd'
                ),
            ),
        )
        for case, params in cases.items():
            with self.subTest(case=case):
                init_kwargs = params['init_kwargs']
                class_kwargs = params['class_kwargs']
                expected_command = params['expected_command']
                Container = type(docker.Container)(
                    'Container',
                    (docker.Container, ),
                    class_kwargs,
                )
                container = Container(**init_kwargs)
                with mock.patch.object(
                    fabricio,
                    'exec_command',
                ) as exec_command:
                    container.run()
                    exec_command.assert_called_once_with(expected_command)

    @mock.patch.object(fabricio, 'log')
    def test_update(self, *args):
        cases = dict(
            no_change=dict(
                side_effect=(
                    '[{"Image": "image_id"}]',  # current container info
                    '[{"Id": "image_id"}]',  # new image info
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name'),
                    mock.call('docker inspect --type image image:tag'),
                ],
                update_kwargs=dict(),
            ),
            no_change_with_tag=dict(
                side_effect=(
                    '[{"Image": "image_id"}]',  # current container info
                    '[{"Id": "image_id"}]',  # new image info
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name'),
                    mock.call('docker inspect --type image image:foo'),
                ],
                update_kwargs=dict(tag='foo'),
            ),
            forced=dict(
                side_effect=(
                    '[{"Image": "image_id"}]',  # obsolete container info
                    '',  # delete obsolete container
                    '',  # delete obsolete container image
                    '',  # rename current container
                    '',  # stop current container
                    'new_container_id',  # run new container
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name_backup'),
                    mock.call('docker rm name_backup', ignore_errors=False),
                    mock.call('docker rmi image_id', ignore_errors=True),
                    mock.call('docker rename name name_backup'),
                    mock.call('docker stop --time 10 name_backup'),
                    mock.call('docker run --name name --detach image:tag '),
                ],
                update_kwargs=dict(force=True),
            ),
            regular=dict(
                side_effect=(
                    '[{"Image": "image_id"}]',  # current container info
                    '[{"Id": "new_image_id"}]',  # new image info
                    '[{"Image": "old_image_id"}]',  # obsolete container info
                    '',  # delete obsolete container
                    '',  # delete obsolete container image
                    '',  # rename current container
                    '',  # stop current container
                    'new_container_id',  # run new container
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name'),
                    mock.call('docker inspect --type image image:tag'),
                    mock.call('docker inspect --type container name_backup'),
                    mock.call('docker rm name_backup', ignore_errors=False),
                    mock.call('docker rmi old_image_id', ignore_errors=True),
                    mock.call('docker rename name name_backup'),
                    mock.call('docker stop --time 10 name_backup'),
                    mock.call('docker run --name name --detach image:tag '),
                ],
                update_kwargs=dict()
            ),
            regular_with_tag=dict(
                side_effect=(
                    '[{"Image": "image_id"}]',  # current container info
                    '[{"Id": "new_image_id"}]',  # new image info
                    '[{"Image": "old_image_id"}]',  # obsolete container info
                    '',  # delete obsolete container
                    '',  # delete obsolete container image
                    '',  # rename current container
                    '',  # stop current container
                    'new_container_id',  # run new container
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name'),
                    mock.call('docker inspect --type image image:foo'),
                    mock.call('docker inspect --type container name_backup'),
                    mock.call('docker rm name_backup', ignore_errors=False),
                    mock.call('docker rmi old_image_id', ignore_errors=True),
                    mock.call('docker rename name name_backup'),
                    mock.call('docker stop --time 10 name_backup'),
                    mock.call('docker run --name name --detach image:foo '),
                ],
                update_kwargs=dict(tag='foo'),
            ),
            without_backup=dict(
                side_effect=(
                    '[{"Image": "image_id"}]',  # current container info
                    '[{"Id": "new_image_id"}]',  # new image info
                    RuntimeError,  # obsolete container info
                    '',  # rename current container
                    '',  # stop current container
                    'new_container_id',  # run new container
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name'),
                    mock.call('docker inspect --type image image:tag'),
                    mock.call('docker inspect --type container name_backup'),
                    mock.call('docker rename name name_backup'),
                    mock.call('docker stop --time 10 name_backup'),
                    mock.call('docker run --name name --detach image:tag '),
                ],
                update_kwargs=dict()
            ),
            from_scratch=dict(
                side_effect=(
                    '[{"Image": "image_id"}]',  # current container info
                    '[{"Id": "new_image_id"}]',  # new image info
                    RuntimeError,  # obsolete container info
                    RuntimeError,  # rename current container
                    'new_container_id',  # run new container
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name'),
                    mock.call('docker inspect --type image image:tag'),
                    mock.call('docker inspect --type container name_backup'),
                    mock.call('docker rename name name_backup'),
                    mock.call('docker run --name name --detach image:tag '),
                ],
                update_kwargs=dict()
            ),
        )
        for case, params in cases.items():
            with self.subTest(case=case):
                container = TestContainer(name='name')
                side_effect = params['side_effect']
                expected_commands = params['expected_commands']
                update_kwargs = params['update_kwargs']
                with mock.patch.object(
                    fabricio,
                    'exec_command',
                    side_effect=side_effect,
                ) as exec_command:
                    container.update(**update_kwargs)
                    exec_command.assert_has_calls(expected_commands)
                    self.assertEqual(
                        len(expected_commands),
                        exec_command.call_count,
                    )

    def test_revert(self):
        side_effect = (
            '[{"Image": "failed_image_id"}]',  # current container info
            '',  # stop current container
            '',  # delete current container
            '',  # delete current container image
            '',  # start backup container
            '',  # rename backup container
        )
        expected_commands = [
            mock.call('docker inspect --type container name'),
            mock.call('docker stop --time 10 name'),
            mock.call('docker rm name', ignore_errors=False),
            mock.call('docker rmi failed_image_id', ignore_errors=True),
            mock.call('docker start name_backup'),
            mock.call('docker rename name_backup name'),
        ]
        container = TestContainer(name='name')
        with mock.patch.object(
            fabricio,
            'exec_command',
            side_effect=side_effect,
        ) as exec_command:
            container.revert()
            exec_command.assert_has_calls(expected_commands)
            self.assertEqual(len(expected_commands), exec_command.call_count)
