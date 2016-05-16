import mock
import unittest2 as unittest

import fabricio

from fabricio import docker


class TestContainer(docker.Container):

    image = 'image:tag'


class ContainerTestCase(unittest.TestCase):

    def test_info(self):
        return_value = '[{"Id": "123", "Image": "abc"}]'
        container = TestContainer(name='name')
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
                container = TestContainer(name='name')
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
        container = TestContainer(name='name')
        expected_command = 'docker exec --tty name cmd'
        with mock.patch.object(
            fabricio,
            'exec_command',
            return_value='result'
        ) as exec_command:
            result = container.execute('cmd')
            exec_command.assert_called_once_with(expected_command)
            self.assertEqual('result', result)

    def test_start(self):
        container = TestContainer(name='name')
        expected_command = 'docker start name'
        with mock.patch.object(fabricio, 'exec_command') as exec_command:
            container.start()
            exec_command.assert_called_once_with(expected_command)

    def test_stop(self):
        container = TestContainer(name='name')
        expected_command = 'docker stop --time 10 name'
        with mock.patch.object(fabricio, 'exec_command') as exec_command:
            container.stop()
            exec_command.assert_called_once_with(expected_command)

    def test_restart(self):
        container = TestContainer(name='name')
        expected_command = 'docker restart --time 10 name'
        with mock.patch.object(fabricio, 'exec_command') as exec_command:
            container.restart()
            exec_command.assert_called_once_with(expected_command)

    def test_rename(self):
        container = TestContainer(name='name')
        expected_command = 'docker rename name new_name'
        with mock.patch.object(fabricio, 'exec_command') as exec_command:
            container.rename('new_name')
            exec_command.assert_called_once_with(expected_command)
            self.assertEqual('new_name', container.name)

    def test_signal(self):
        container = TestContainer(name='name')
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
                expected_commands=[
                    mock.call('docker inspect --type image image:tag'),
                    mock.call('docker run --name name --detach image_id'),
                ],
                side_effect=(
                    '[{"Id": "image_id"}]',
                    'container_id',
                ),
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
                expected_commands=[
                    mock.call('docker inspect --type image image:tag'),
                    mock.call(
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
                        'image_id cmd'
                    ),
                ],
                side_effect=(
                    '[{"Id": "image_id"}]',
                    'container_id',
                ),
            ),
        )
        for case, params in cases.items():
            with self.subTest(case=case):
                init_kwargs = params['init_kwargs']
                class_kwargs = params['class_kwargs']
                expected_commands = params['expected_commands']
                side_effect = params['side_effect']
                Container = type(docker.Container)(
                    'Container',
                    (docker.Container, ),
                    class_kwargs,
                )
                container = Container(**init_kwargs)
                with mock.patch.object(
                    fabricio,
                    'exec_command',
                    side_effect=side_effect,
                ) as exec_command:
                    container.run()
                    exec_command.assert_has_calls(expected_commands)

#     @mock.patch.object(fabric.api, 'puts')
#     def test_update(self, *args):
#         def side_effect(command):
#             result = next(sudo_results)
#             if callable(result):
#                 result = result() or AttributeString(succeeded=False)
#             return result
#         cases = dict(
#             no_change=dict(
#                 sudo_results=(
#                     AttributeString('[{"Image": "image_id"}]'),  # current container info
#                     AttributeString('[{"Id": "image_id"}]'),  # current container image info
#                     AttributeString('[{"Id": "image_id"}]'),  # new image info
#                 ),
#                 expected_commands=[
#                     mock.call(docker.Container.COMMAND_INFO.format(container='name')),
#                     mock.call(docker.Image.COMMAND_INFO.format(image='image_id')),
#                     mock.call(docker.Image.COMMAND_INFO.format(image='image:latest')),
#                 ],
#                 update_kwargs=dict(),
#             ),
#             no_change_with_tag=dict(
#                 sudo_results=(
#                     AttributeString('[{"Image": "image_id"}]'),  # current container info
#                     AttributeString('[{"Id": "image_id"}]'),  # current container image info
#                     AttributeString('[{"Id": "image_id"}]'),  # new image info
#                 ),
#                 expected_commands=[
#                     mock.call(docker.Container.COMMAND_INFO.format(container='name')),
#                     mock.call(docker.Image.COMMAND_INFO.format(image='image_id')),
#                     mock.call(docker.Image.COMMAND_INFO.format(image='image:tag')),
#                 ],
#                 update_kwargs=dict(tag='tag'),
#             ),
#             no_change_forced=dict(
#                 sudo_results=(
#                     AttributeString('[{"Image": "image_id"}]'),  # obsolete container info
#                     AttributeString('[{"Id": "image_id"}]'),  # obsolete container image info
#                     AttributeString(''),  # delete obsolete container
#                     functools.partial(error, 'can not delete image'),  # delete obsolete container image
#                     AttributeString(''),  # rename current container
#                     AttributeString(''),  # stop current container
#                     AttributeString('new_container_id'),  # run new container
#                 ),
#                 expected_commands=[
#                     mock.call(docker.Container.COMMAND_INFO.format(container='name_backup')),
#                     mock.call(docker.Image.COMMAND_INFO.format(image='image_id')),
#                     mock.call(docker.Container.COMMAND_DELETE.format(container='name_backup')),
#                     mock.call(docker.Image.COMMAND_DELETE.format(image='image_id')),
#                     mock.call(docker.Container.COMMAND_RENAME.format(container='name', new_name='name_backup')),
#                     mock.call(docker.Container.COMMAND_STOP.format(container='name_backup', timeout=10)),
#                     mock.call(docker.Container.COMMAND_RUN.format(
#                         cmd='',
#                         image='image:latest',
#                         options=Options([
#                             ('name', 'name'),
#                             ('detach', True),
#                         ]),
#                     )),
#                 ],
#                 update_kwargs=dict(force=True),
#             ),
#             regular=dict(
#                 sudo_results=(
#                     AttributeString('[{"Image": "image_id"}]'),  # current container info
#                     AttributeString('[{"Id": "image_id"}]'),  # current container image info
#                     AttributeString('[{"Id": "new_image_id"}]'),  # new image info
#                     AttributeString('[{"Image": "old_image_id"}]'),  # obsolete container info
#                     AttributeString('[{"Id": "old_image_id"}]'),  # obsolete container image info
#                     AttributeString(''),  # delete obsolete container
#                     AttributeString(''),  # delete obsolete container image
#                     AttributeString(''),  # rename current container
#                     AttributeString(''),  # stop current container
#                     AttributeString('new_container_id'),  # run new container
#                 ),
#                 expected_commands=[
#                     mock.call(docker.Container.COMMAND_INFO.format(container='name')),
#                     mock.call(docker.Image.COMMAND_INFO.format(image='image_id')),
#                     mock.call(docker.Image.COMMAND_INFO.format(image='image:latest')),
#                     mock.call(docker.Container.COMMAND_INFO.format(container='name_backup')),
#                     mock.call(docker.Image.COMMAND_INFO.format(image='old_image_id')),
#                     mock.call(docker.Container.COMMAND_DELETE.format(container='name_backup')),
#                     mock.call(docker.Image.COMMAND_DELETE.format(image='old_image_id')),
#                     mock.call(docker.Container.COMMAND_RENAME.format(container='name', new_name='name_backup')),
#                     mock.call(docker.Container.COMMAND_STOP.format(container='name_backup', timeout=10)),
#                     mock.call(docker.Container.COMMAND_RUN.format(
#                         cmd='',
#                         image='image:latest',
#                         options=Options([
#                             ('name', 'name'),
#                             ('detach', True),
#                         ]),
#                     )),
#                 ],
#                 update_kwargs=dict(),
#             ),
#             regular_with_tag=dict(
#                 sudo_results=(
#                     AttributeString('[{"Image": "image_id"}]'),  # current container info
#                     AttributeString('[{"Id": "image_id"}]'),  # current container image info
#                     AttributeString('[{"Id": "new_image_id"}]'),  # new image info
#                     AttributeString('[{"Image": "old_image_id"}]'),  # obsolete container info
#                     AttributeString('[{"Id": "old_image_id"}]'),  # obsolete container image info
#                     AttributeString(''),  # delete obsolete container
#                     AttributeString(''),  # delete obsolete container image
#                     AttributeString(''),  # rename current container
#                     AttributeString(''),  # stop current container
#                     AttributeString('new_container_id'),  # run new container
#                 ),
#                 expected_commands=[
#                     mock.call(docker.Container.COMMAND_INFO.format(container='name')),
#                     mock.call(docker.Image.COMMAND_INFO.format(image='image_id')),
#                     mock.call(docker.Image.COMMAND_INFO.format(image='image:tag')),
#                     mock.call(docker.Container.COMMAND_INFO.format(container='name_backup')),
#                     mock.call(docker.Image.COMMAND_INFO.format(image='old_image_id')),
#                     mock.call(docker.Container.COMMAND_DELETE.format(container='name_backup')),
#                     mock.call(docker.Image.COMMAND_DELETE.format(image='old_image_id')),
#                     mock.call(docker.Container.COMMAND_RENAME.format(container='name', new_name='name_backup')),
#                     mock.call(docker.Container.COMMAND_STOP.format(container='name_backup', timeout=10)),
#                     mock.call(docker.Container.COMMAND_RUN.format(
#                         cmd='',
#                         image='image:latest',
#                         options=Options([
#                             ('name', 'name'),
#                             ('detach', True),
#                         ]),
#                     )),
#                 ],
#                 update_kwargs=dict(tag='tag'),
#             ),
#             regular_without_backup=dict(
#                 sudo_results=(
#                     AttributeString('[{"Image": "image_id"}]'),  # current container info
#                     AttributeString('[{"Id": "image_id"}]'),  # current container image info
#                     AttributeString('[{"Id": "new_image_id"}]'),  # new image info
#                     functools.partial(error, 'backup container not found'),  # obsolete container info
#                     AttributeString(''),  # rename current container
#                     AttributeString(''),  # stop current container
#                     AttributeString('new_container_id'),  # run new container
#                 ),
#                 expected_commands=[
#                     mock.call(docker.Container.COMMAND_INFO.format(container='name')),
#                     mock.call(docker.Image.COMMAND_INFO.format(image='image_id')),
#                     mock.call(docker.Image.COMMAND_INFO.format(image='image:latest')),
#                     mock.call(docker.Container.COMMAND_INFO.format(container='name_backup')),
#                     mock.call(docker.Container.COMMAND_RENAME.format(container='name', new_name='name_backup')),
#                     mock.call(docker.Container.COMMAND_STOP.format(container='name_backup', timeout=10)),
#                     mock.call(docker.Container.COMMAND_RUN.format(
#                         cmd='',
#                         image='image:latest',
#                         options=Options([
#                             ('name', 'name'),
#                             ('detach', True),
#                         ]),
#                     )),
#                 ],
#                 update_kwargs=dict(),
#             ),
#             from_scratch=dict(
#                 sudo_results=(
#                     functools.partial(error, 'current container not found'),  # current container info
#                     functools.partial(error, 'backup container not found'),  # obsolete container info
#                     functools.partial(error, 'current container not found'),  # rename current container
#                     functools.partial(error, 'current container not found'),  # stop current container
#                     AttributeString('new_container_id'),  # run new container
#                 ),
#                 expected_commands=[
#                     mock.call(docker.Container.COMMAND_INFO.format(container='name')),
#                     mock.call(docker.Container.COMMAND_INFO.format(container='name_backup')),
#                     mock.call(docker.Container.COMMAND_RENAME.format(container='name', new_name='name_backup')),
#                     mock.call(docker.Container.COMMAND_STOP.format(container='name_backup', timeout=10)),
#                     mock.call(docker.Container.COMMAND_RUN.format(
#                         cmd='',
#                         image='image:latest',
#                         options=Options([
#                             ('name', 'name'),
#                             ('detach', True),
#                         ]),
#                     )),
#                 ],
#                 update_kwargs=dict(),
#             ),
#         )
#         for case, params in cases.items():
#             with self.subTest(case=case):
#                 container = docker.Container(image='image', name='name')
#                 sudo_results = iter(params['sudo_results'])
#                 expected_commands = params['expected_commands']
#                 update_kwargs = params['update_kwargs']
#                 commands_count = len(expected_commands)
#                 with mock.patch.object(fabric.api, 'sudo', side_effect=side_effect) as sudo:
#                     container.update(**update_kwargs)
#                     sudo.assert_has_calls(expected_commands)
#                     self.assertEqual(commands_count, sudo.call_count)
#
#     def test_revert(self):
#         def side_effect(command):
#             result = next(sudo_results)
#             if callable(result):
#                 result = result() or AttributeString(succeeded=False)
#             return result
#         cases = dict(
#             regular=dict(
#                 sudo_results=(
#                     AttributeString('[{"Image": "failed_image_id"}]'),  # failed container info
#                     AttributeString('[{"Id": "failed_image_id"}]'),  # failed container image info
#                     AttributeString(''),  # delete failed container
#                     AttributeString(''),  # delete failed container image
#                     AttributeString(''),  # start backup container
#                     AttributeString(''),  # rename backup container
#                 ),
#                 expected_commands=[
#                     mock.call(docker.Container.COMMAND_INFO.format(container='name')),
#                     mock.call(docker.Image.COMMAND_INFO.format(image='failed_image_id')),
#                     mock.call(docker.Container.COMMAND_FORCE_DELETE.format(container='name')),
#                     mock.call(docker.Image.COMMAND_DELETE.format(image='failed_image_id')),
#                     mock.call(docker.Container.COMMAND_START.format(container='name_backup')),
#                     mock.call(docker.Container.COMMAND_RENAME.format(container='name_backup', new_name='name')),
#                 ],
#                 revert_kwargs=dict(),
#             ),
#             can_not_delete_failed_image=dict(
#                 sudo_results=(
#                     AttributeString('[{"Image": "failed_image_id"}]'),  # failed container info
#                     AttributeString('[{"Id": "failed_image_id"}]'),  # failed container image info
#                     AttributeString(''),  # delete failed container
#                     functools.partial(error, 'can not delete image'),  # delete failed container image
#                     AttributeString(''),  # start backup container
#                     AttributeString(''),  # rename backup container
#                 ),
#                 expected_commands=[
#                     mock.call(docker.Container.COMMAND_INFO.format(container='name')),
#                     mock.call(docker.Image.COMMAND_INFO.format(image='failed_image_id')),
#                     mock.call(docker.Container.COMMAND_FORCE_DELETE.format(container='name')),
#                     mock.call(docker.Image.COMMAND_DELETE.format(image='failed_image_id')),
#                     mock.call(docker.Container.COMMAND_START.format(container='name_backup')),
#                     mock.call(docker.Container.COMMAND_RENAME.format(container='name_backup', new_name='name')),
#                 ],
#                 revert_kwargs=dict(),
#             ),
#         )
#         for case, params in cases.items():
#             with self.subTest(case=case):
#                 container = docker.Container(image='image', name='name')
#                 sudo_results = iter(params['sudo_results'])
#                 expected_commands = params['expected_commands']
#                 revert_kwargs = params['revert_kwargs']
#                 with mock.patch.object(fabric.api, 'sudo', side_effect=side_effect) as sudo:
#                     container.revert(**revert_kwargs)
#                     sudo.assert_has_calls(expected_commands)
#                     self.assertEqual(len(expected_commands), sudo.call_count)
