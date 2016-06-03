import mock
import unittest2 as unittest

import fabricio

from fabricio import docker


class TestContainer(docker.Container):

    image = docker.Image('image:tag')


class ContainerTestCase(unittest.TestCase):

    def test_info(self):
        return_value = '[{"Id": "123", "Image": "abc"}]'
        container = docker.Container(name='name')
        expected_command = 'docker inspect --type container name'
        with mock.patch.object(
            fabricio,
            'sudo',
            return_value=return_value,
        ) as sudo:
            self.assertEqual(dict(Id='123', Image='abc'), container.info)
            sudo.assert_called_once_with(expected_command)

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
                    'sudo',
                ) as sudo:
                    expected_command = params['expected_command']
                    delete_kwargs = params['delete_kwargs']

                    container.delete(**delete_kwargs)

                    sudo.assert_called_once_with(
                        expected_command,
                        ignore_errors=False,
                    )

    def test_execute(self):
        container = docker.Container(name='name')
        expected_command = 'docker exec --tty name cmd'
        with mock.patch.object(
            fabricio,
            'sudo',
            return_value='result'
        ) as sudo:
            result = container.execute('cmd')
            sudo.assert_called_once_with(
                expected_command,
                ignore_errors=False,
            )
            self.assertEqual('result', result)

    def test_start(self):
        container = docker.Container(name='name')
        expected_command = 'docker start name'
        with mock.patch.object(fabricio, 'sudo') as sudo:
            container.start()
            sudo.assert_called_once_with(expected_command)

    def test_stop(self):
        cases = dict(
            default=dict(
                timeout=None,
                expected_command='docker stop --time 10 name',
            ),
            positive_timeout=dict(
                timeout=30,
                expected_command='docker stop --time 30 name',
            ),
            zero_timeout=dict(
                timeout=0,
                expected_command='docker stop --time 0 name',
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                container = docker.Container(name='name')
                with mock.patch.object(fabricio, 'sudo') as sudo:
                    container.stop(timeout=data['timeout'])
                    sudo.assert_called_once_with(data['expected_command'])

    def test_restart(self):
        cases = dict(
            default=dict(
                timeout=None,
                expected_command='docker restart --time 10 name',
            ),
            positive_timeout=dict(
                timeout=30,
                expected_command='docker restart --time 30 name',
            ),
            zero_timeout=dict(
                timeout=0,
                expected_command='docker restart --time 0 name',
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                container = docker.Container(name='name')
                with mock.patch.object(fabricio, 'sudo') as sudo:
                    container.restart(timeout=data['timeout'])
                    sudo.assert_called_once_with(data['expected_command'])

    def test_rename(self):
        container = docker.Container(name='name')
        expected_command = 'docker rename name new_name'
        with mock.patch.object(fabricio, 'sudo') as sudo:
            container.rename('new_name')
            sudo.assert_called_once_with(expected_command)
            self.assertEqual('new_name', container.name)

    def test_signal(self):
        container = docker.Container(name='name')
        expected_command = 'docker kill --signal SIGTERM name'
        with mock.patch.object(fabricio, 'sudo') as sudo:
            container.signal('SIGTERM')
            sudo.assert_called_once_with(expected_command)

    def test_run(self):
        cases = dict(
            basic=dict(
                init_kwargs=dict(
                    name='name',
                ),
                class_kwargs=dict(image=docker.Image('image:tag')),
                expected_command='docker run --name name --detach image:tag ',
            ),
            complex=dict(
                init_kwargs=dict(
                    name='name',
                    options=dict(foo='bar'),
                ),
                class_kwargs=dict(
                    image=docker.Image('image:tag'),
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
                    'sudo',
                ) as sudo:
                    container.run()
                    sudo.assert_called_once_with(expected_command)

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
                excpected_result=False,
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
                excpected_result=False,
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
                excpected_result=True,
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
                update_kwargs=dict(),
                excpected_result=True,
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
                excpected_result=True,
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
                update_kwargs=dict(),
                excpected_result=True,
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
                update_kwargs=dict(),
                excpected_result=True,
            ),
        )
        for case, params in cases.items():
            with self.subTest(case=case):
                container = TestContainer(name='name')
                side_effect = params['side_effect']
                expected_commands = params['expected_commands']
                update_kwargs = params['update_kwargs']
                excpected_result = params['excpected_result']
                with mock.patch.object(
                    fabricio,
                    'sudo',
                    side_effect=side_effect,
                ) as sudo:
                    result = container.update(**update_kwargs)
                    sudo.assert_has_calls(expected_commands)
                    self.assertEqual(
                        len(expected_commands),
                        sudo.call_count,
                    )
                    self.assertEqual(excpected_result, result)

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
            'sudo',
            side_effect=side_effect,
        ) as sudo:
            container.revert()
            sudo.assert_has_calls(expected_commands)
            self.assertEqual(len(expected_commands), sudo.call_count)


class ImageTestCase(unittest.TestCase):

    def test_name_tag_registry(self):
        cases = dict(
            single=dict(
                init_kwargs=dict(
                    name='image',
                ),
                expected_name='image',
                expected_tag='latest',
                expected_registry='',
                expected_str='image:latest',
            ),
            with_tag=dict(
                init_kwargs=dict(
                    name='image',
                    tag='tag',
                ),
                expected_name='image',
                expected_tag='tag',
                expected_registry='',
                expected_str='image:tag',
            ),
            with_registry=dict(
                init_kwargs=dict(
                    name='image',
                    registry='registry',
                ),
                expected_name='image',
                expected_tag='latest',
                expected_registry='registry',
                expected_str='registry/image:latest',
            ),
            with_tag_and_registry=dict(
                init_kwargs=dict(
                    name='image',
                    tag='tag',
                    registry='registry',
                ),
                expected_name='image',
                expected_tag='tag',
                expected_registry='registry',
                expected_str='registry/image:tag',
            ),
            single_arg_with_tag=dict(
                init_kwargs=dict(
                    name='image:tag',
                ),
                expected_name='image',
                expected_tag='tag',
                expected_registry='',
                expected_str='image:tag',
            ),
            single_arg_with_registry=dict(
                init_kwargs=dict(
                    name='registry/image',
                ),
                expected_name='image',
                expected_tag='latest',
                expected_registry='registry',
                expected_str='registry/image:latest',
            ),
            single_arg_with_tag_and_registry=dict(
                init_kwargs=dict(
                    name='registry/image:tag',
                ),
                expected_name='image',
                expected_tag='tag',
                expected_registry='registry',
                expected_str='registry/image:tag',
            ),
            forced_with_tag=dict(
                init_kwargs=dict(
                    name='image:tag',
                    tag='foo',
                ),
                expected_name='image',
                expected_tag='foo',
                expected_registry='',
                expected_str='image:foo',
            ),
            forced_with_registry=dict(
                init_kwargs=dict(
                    name='registry/image',
                    registry='foo',
                ),
                expected_name='image',
                expected_tag='latest',
                expected_registry='foo',
                expected_str='foo/image:latest',
            ),
            forced_with_tag_and_registry=dict(
                init_kwargs=dict(
                    name='registry/image:tag',
                    tag='foo',
                    registry='bar',
                ),
                expected_name='image',
                expected_tag='foo',
                expected_registry='bar',
                expected_str='bar/image:foo',
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                image = docker.Image(**data['init_kwargs'])
                self.assertEqual(data['expected_name'], image.name)
                self.assertEqual(data['expected_tag'], image.tag)
                self.assertEqual(data['expected_registry'], image.registry)
                self.assertEqual(data['expected_str'], str(image))

    def test_getitem(self):
        cases = dict(
            none=dict(
                item=None,
                expected_tag='tag',
                expected_registry='registry',
            ),
            tag=dict(
                item='custom_tag',
                expected_tag='custom_tag',
                expected_registry='registry',
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                image = docker.Image(name='name', tag='tag', registry='registry')
                new_image = image[data['item']]
                self.assertEqual(data['expected_tag'], new_image.tag)
                self.assertEqual(data['expected_registry'], new_image.registry)

    def test_getitem_slice(self):
        cases = dict(
            none=dict(
                start=None,
                stop=None,
                expected_tag='tag',
                expected_registry='registry',
            ),
            tag=dict(
                start=None,
                stop='custom_tag',
                expected_tag='custom_tag',
                expected_registry='registry',
            ),
            registry=dict(
                start='custom_registry',
                stop=None,
                expected_tag='tag',
                expected_registry='custom_registry',
            ),
            tag_and_registry=dict(
                start='custom_registry',
                stop='custom_tag',
                expected_tag='custom_tag',
                expected_registry='custom_registry',
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                image = docker.Image(name='name', tag='tag', registry='registry')
                new_image = image[data['start']:data['stop']]
                self.assertEqual(data['expected_tag'], new_image.tag)
                self.assertEqual(data['expected_registry'], new_image.registry)
