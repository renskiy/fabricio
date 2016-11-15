import mock
import unittest2 as unittest

import fabricio

from fabricio import docker
from fabricio.docker.container import Option, Attribute
from tests import SucceededResult


class TestContainer(docker.Container):

    image = docker.Image('image:tag')


class ContainerTestCase(unittest.TestCase):

    def test_options(self):
        cases = dict(
            default=dict(
                kwargs=dict(),
                expected={
                    'network': None,
                    'links': None,
                    'stop_signal': None,
                    'restart_policy': None,
                    'hosts': None,
                    'user': None,
                    'env': None,
                    'volumes': None,
                    'ports': None,
                },
            ),
            custom=dict(
                kwargs=dict(options=dict(foo='bar')),
                expected={
                    'network': None,
                    'links': None,
                    'stop_signal': None,
                    'restart_policy': None,
                    'hosts': None,
                    'user': None,
                    'env': None,
                    'volumes': None,
                    'ports': None,
                    'foo': 'bar',
                },
            ),
            collision=dict(
                kwargs=dict(options=dict(execute='execute')),
                expected={
                    'network': None,
                    'links': None,
                    'stop_signal': None,
                    'restart_policy': None,
                    'hosts': None,
                    'user': None,
                    'env': None,
                    'volumes': None,
                    'ports': None,
                    'execute': 'execute',
                },
            ),
            override=dict(
                kwargs=dict(options=dict(env='custom_env')),
                expected={
                    'network': None,
                    'links': None,
                    'stop_signal': None,
                    'restart_policy': None,
                    'hosts': None,
                    'user': None,
                    'env': 'custom_env',
                    'volumes': None,
                    'ports': None,
                },
            ),
            complex=dict(
                kwargs=dict(options=dict(env='custom_env', foo='bar')),
                expected={
                    'network': None,
                    'links': None,
                    'stop_signal': None,
                    'restart_policy': None,
                    'hosts': None,
                    'user': None,
                    'env': 'custom_env',
                    'volumes': None,
                    'ports': None,
                    'foo': 'bar',
                },
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                container = TestContainer('name', **data['kwargs'])
                self.assertDictEqual(data['expected'], dict(container.options))

    def test_options_inheritance(self):

        class Container(docker.Container):
            user = 'user'  # overridden property (simple)

            @property  # overridden property (dynamic)
            def ports(self):
                return 'ports'

            baz = Option(default=42)  # new property

            @Option  # new dynamic property
            def foo(self):
                return 'bar'

            null = Option()  # new empty property

        container = Container('name')

        self.assertIn('user', container.options)
        self.assertEqual(container.options['user'], 'user')
        container.user = 'fabricio'
        self.assertEqual(container.options['user'], 'fabricio')

        self.assertIn('ports', container.options)
        self.assertEqual(container.options['ports'], 'ports')

        self.assertIn('baz', container.options)
        self.assertEqual(container.options['baz'], 42)
        container.baz = 101
        self.assertEqual(container.options['baz'], 101)

        self.assertIn('foo', container.options)
        self.assertEqual(container.options['foo'], 'bar')
        container.foo = 'baz'
        self.assertEqual(container.options['foo'], 'baz')

        self.assertIn('null', container.options)
        self.assertIsNone(container.options['null'])
        container.null = 'value'
        self.assertEqual(container.options['null'], 'value')

    def test_attributes_inheritance(self):

        class Container(docker.Container):
            cmd = 'cmd'  # overridden property (simple)

            @property  # overridden property (dynamic)
            def stop_timeout(self):
                return 1001

            baz = Attribute(default=42)  # new property

            @Attribute  # new dynamic property
            def foo(self):
                return 'bar'

            null = Attribute()  # new empty property

        container = Container('name')

        self.assertEqual(container.cmd, 'cmd')
        container.cmd = 'command'
        self.assertEqual(container.cmd, 'command')

        self.assertEqual(container.stop_timeout, 1001)

        self.assertEqual(container.baz, 42)
        container.baz = 101
        self.assertEqual(container.baz, 101)

        self.assertEqual(container.foo, 'bar')
        container.foo = 'baz'
        self.assertEqual(container.foo, 'baz')

        self.assertIsNone(container.null)
        container.null = 'value'
        self.assertEqual(container.null, 'value')

    def test_container_does_not_allow_modify_options(self):
        container = TestContainer('name')

        # default options allowed to be modified
        container.user = 'user'
        self.assertEqual('user', container.user)

        # do not allow to modify additional options
        with self.assertRaises(TypeError):
            container.options['some-option'] = 'value'

    def test_container_raises_error_on_unknown_attr(self):
        with self.assertRaises(TypeError):
            docker.Container(name='name', unknown_attr='foo')

    def test_info(self):
        return_value = SucceededResult('[{"Id": "123", "Image": "abc"}]')
        expected = dict(Id='123', Image='abc')
        container = docker.Container(name='name')
        expected_command = 'docker inspect --type container name'
        with mock.patch.object(
            fabricio,
            'run',
            return_value=return_value,
        ) as run:
            self.assertEqual(expected, container.info)
            run.assert_called_once_with(expected_command)

    @mock.patch.object(fabricio, 'run', side_effect=RuntimeError)
    def test_info_raises_error_if_container_not_found(self, run):
        container = docker.Container(name='name')
        expected_command = 'docker inspect --type container name'
        with self.assertRaises(RuntimeError) as cm:
            container.info
        self.assertEqual(cm.exception.args[0], "Container 'name' not found")
        run.assert_called_once_with(expected_command)

    def test_delete(self):
        cases = dict(
            regular=dict(
                delete_kwargs=dict(),
                expected_commands=[
                    mock.call('docker rm name'),
                    mock.call('for volume in $(docker volume ls --filter "dangling=true" --quiet); do docker volume rm "$volume"; done'),
                ],
            ),
            with_image=dict(
                delete_kwargs=dict(delete_image=True),
                expected_commands=[
                    mock.call('docker inspect --type container name'),
                    mock.call('docker rm name'),
                    mock.call('for volume in $(docker volume ls --filter "dangling=true" --quiet); do docker volume rm "$volume"; done'),
                    mock.call('docker rmi image_id', ignore_errors=True),
                ],
            ),
            forced=dict(
                delete_kwargs=dict(force=True),
                expected_commands=[
                    mock.call('docker rm --force name'),
                    mock.call('for volume in $(docker volume ls --filter "dangling=true" --quiet); do docker volume rm "$volume"; done'),
                ],
            ),
            no_dangling_removal=dict(
                delete_kwargs=dict(delete_dangling_volumes=False),
                expected_commands=[
                    mock.call('docker rm name'),
                ],
            ),
            complex=dict(
                delete_kwargs=dict(force=True, delete_image=True),
                expected_commands=[
                    mock.call('docker inspect --type container name'),
                    mock.call('docker rm --force name'),
                    mock.call('for volume in $(docker volume ls --filter "dangling=true" --quiet); do docker volume rm "$volume"; done'),
                    mock.call('docker rmi image_id', ignore_errors=True),
                ],
            ),
        )
        for case, params in cases.items():
            with self.subTest(case=case):
                container = docker.Container(name='name')
                with mock.patch.object(
                    fabricio,
                    'run',
                    return_value=SucceededResult('[{"Image": "image_id"}]'),
                ) as run:
                    expected_commands = params['expected_commands']
                    delete_kwargs = params['delete_kwargs']

                    container.delete(**delete_kwargs)
                    self.assertListEqual(run.mock_calls, expected_commands)

    def test_execute(self):
        container = docker.Container(name='name')
        expected_command = 'docker exec --tty --interactive name cmd'
        with mock.patch.object(
            fabricio,
            'run',
            return_value='result'
        ) as run:
            result = container.execute('cmd')
            run.assert_called_once_with(
                expected_command,
                ignore_errors=False,
                quiet=True,
                use_cache=False,
            )
            self.assertEqual('result', result)

    def test_start(self):
        container = docker.Container(name='name')
        expected_command = 'docker start name'
        with mock.patch.object(fabricio, 'run') as run:
            container.start()
            run.assert_called_once_with(expected_command)

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
                with mock.patch.object(fabricio, 'run') as run:
                    container.stop(timeout=data['timeout'])
                    run.assert_called_once_with(data['expected_command'])

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
                with mock.patch.object(fabricio, 'run') as run:
                    container.restart(timeout=data['timeout'])
                    run.assert_called_once_with(data['expected_command'])

    def test_rename(self):
        container = docker.Container(name='name')
        expected_command = 'docker rename name new_name'
        with mock.patch.object(fabricio, 'run') as run:
            container.rename('new_name')
            run.assert_called_once_with(expected_command)
            self.assertEqual('new_name', container.name)

    def test_signal(self):
        container = docker.Container(name='name')
        expected_command = 'docker kill --signal SIGTERM name'
        with mock.patch.object(fabricio, 'run') as run:
            container.signal('SIGTERM')
            run.assert_called_once_with(expected_command)

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
                    options=dict(custom_option='foo', restart_policy='override'),
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
                    '--user user '
                    '--publish 80:80 --publish 443:443 '
                    '--env FOO=foo --env BAR=bar '
                    '--volume /tmp:/tmp --volume /root:/root:ro '
                    '--link db:db '
                    '--add-host host:192.168.0.1 '
                    '--net network '
                    '--restart override '
                    '--stop-signal stop_signal '
                    '--name name '
                    '--detach '
                    '--custom_option foo '
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
                    'run',
                ) as run:
                    container.run()
                    run.assert_called_once_with(expected_command, quiet=True)

    def test_fork(self):
        cases = dict(
            default=dict(
                init_kwargs=dict(name='name'),
                fork_kwargs=dict(),
                expected_properties=dict(
                    name='name',
                    cmd=None,
                    options={
                        'network': None,
                        'links': None,
                        'stop_signal': None,
                        'restart_policy': None,
                        'hosts': None,
                        'user': None,
                        'env': None,
                        'volumes': None,
                        'ports': None,
                    },
                ),
            ),
            predefined_default=dict(
                init_kwargs=dict(
                    name='name',
                    options=dict(user='fabricio', foo='baz'),
                    image='image:tag',
                    cmd='fab',
                ),
                fork_kwargs=dict(),
                expected_properties=dict(
                    name='name',
                    cmd='fab',
                    options={
                        'network': None,
                        'links': None,
                        'stop_signal': None,
                        'restart_policy': None,
                        'hosts': None,
                        'user': 'fabricio',
                        'env': None,
                        'volumes': None,
                        'ports': None,
                        'foo': 'baz',
                    },
                ),
                expected_image='image:tag',
            ),
            override_name=dict(
                init_kwargs=dict(name='name'),
                fork_kwargs=dict(name='another_name'),
                expected_properties=dict(
                    name='another_name',
                    cmd=None,
                    options={
                        'network': None,
                        'links': None,
                        'stop_signal': None,
                        'restart_policy': None,
                        'hosts': None,
                        'user': None,
                        'env': None,
                        'volumes': None,
                        'ports': None,
                    },
                ),
            ),
            override_cmd=dict(
                init_kwargs=dict(name='name'),
                fork_kwargs=dict(cmd='command'),
                expected_properties=dict(
                    name='name',
                    cmd='command',
                    options={
                        'network': None,
                        'links': None,
                        'stop_signal': None,
                        'restart_policy': None,
                        'hosts': None,
                        'user': None,
                        'env': None,
                        'volumes': None,
                        'ports': None,
                    },
                ),
            ),
            override_image_str=dict(
                init_kwargs=dict(name='name'),
                fork_kwargs=dict(image='image'),
                expected_properties=dict(
                    name='name',
                    cmd=None,
                    options={
                        'network': None,
                        'links': None,
                        'stop_signal': None,
                        'restart_policy': None,
                        'hosts': None,
                        'user': None,
                        'env': None,
                        'volumes': None,
                        'ports': None,
                    },
                ),
                expected_image='image:latest',
            ),
            override_image_instance=dict(
                init_kwargs=dict(name='name'),
                fork_kwargs=dict(image=docker.Image('image')),
                expected_properties=dict(
                    name='name',
                    cmd=None,
                    options={
                        'network': None,
                        'links': None,
                        'stop_signal': None,
                        'restart_policy': None,
                        'hosts': None,
                        'user': None,
                        'env': None,
                        'volumes': None,
                        'ports': None,
                    },
                ),
                expected_image='image:latest',
            ),
            override_default_option=dict(
                init_kwargs=dict(name='name'),
                fork_kwargs=dict(options=dict(user='user')),
                expected_properties=dict(
                    name='name',
                    cmd=None,
                    options={
                        'network': None,
                        'links': None,
                        'stop_signal': None,
                        'restart_policy': None,
                        'hosts': None,
                        'user': 'user',
                        'env': None,
                        'volumes': None,
                        'ports': None,
                    },
                ),
            ),
            override_custom_option=dict(
                init_kwargs=dict(name='name'),
                fork_kwargs=dict(options=dict(foo='bar')),
                expected_properties=dict(
                    name='name',
                    cmd=None,
                    options={
                        'network': None,
                        'links': None,
                        'stop_signal': None,
                        'restart_policy': None,
                        'hosts': None,
                        'user': None,
                        'env': None,
                        'volumes': None,
                        'ports': None,
                        'foo': 'bar',
                    },
                ),
            ),
            overrride_complex=dict(
                init_kwargs=dict(name='name'),
                fork_kwargs=dict(
                    options=dict(foo='bar', user='user'),
                    image='image',
                    cmd='command',
                    name='another_name',
                ),
                expected_properties=dict(
                    name='another_name',
                    cmd='command',
                    options={
                        'network': None,
                        'links': None,
                        'stop_signal': None,
                        'restart_policy': None,
                        'hosts': None,
                        'user': 'user',
                        'env': None,
                        'volumes': None,
                        'ports': None,
                        'foo': 'bar',
                    },
                ),
                expected_image='image:latest',
            ),
            predefined_override_cmd=dict(
                init_kwargs=dict(
                    name='name',
                    options=dict(user='fabricio', foo='baz'),
                    image='image:tag',
                    cmd='fab',
                ),
                fork_kwargs=dict(cmd='command'),
                expected_properties=dict(
                    name='name',
                    cmd='command',
                    options={
                        'network': None,
                        'links': None,
                        'stop_signal': None,
                        'restart_policy': None,
                        'hosts': None,
                        'user': 'fabricio',
                        'env': None,
                        'volumes': None,
                        'ports': None,
                        'foo': 'baz',
                    },
                ),
                expected_image='image:tag',
            ),
            predefined_override_image_str=dict(
                init_kwargs=dict(
                    name='name',
                    options=dict(user='fabricio', foo='baz'),
                    image='image:tag',
                    cmd='fab',
                ),
                fork_kwargs=dict(image='image'),
                expected_properties=dict(
                    name='name',
                    cmd='fab',
                    options={
                        'network': None,
                        'links': None,
                        'stop_signal': None,
                        'restart_policy': None,
                        'hosts': None,
                        'user': 'fabricio',
                        'env': None,
                        'volumes': None,
                        'ports': None,
                        'foo': 'baz',
                    },
                ),
                expected_image='image:latest',
            ),
            predefined_override_image_instance=dict(
                init_kwargs=dict(
                    name='name',
                    options=dict(user='fabricio', foo='baz'),
                    image='image:tag',
                    cmd='fab',
                ),
                fork_kwargs=dict(image=docker.Image('image')),
                expected_properties=dict(
                    name='name',
                    cmd='fab',
                    options={
                        'network': None,
                        'links': None,
                        'stop_signal': None,
                        'restart_policy': None,
                        'hosts': None,
                        'user': 'fabricio',
                        'env': None,
                        'volumes': None,
                        'ports': None,
                        'foo': 'baz',
                    },
                ),
                expected_image='image:latest',
            ),
            predefined_override_default_option=dict(
                init_kwargs=dict(
                    name='name',
                    options=dict(user='fabricio', foo='baz'),
                    image='image:tag',
                    cmd='fab',
                ),
                fork_kwargs=dict(options=dict(user='user')),
                expected_properties=dict(
                    name='name',
                    cmd='fab',
                    options={
                        'network': None,
                        'links': None,
                        'stop_signal': None,
                        'restart_policy': None,
                        'hosts': None,
                        'user': 'user',
                        'env': None,
                        'volumes': None,
                        'ports': None,
                        'foo': 'baz',
                    },
                ),
                expected_image='image:tag',
            ),
            predefined_override_custom_option=dict(
                init_kwargs=dict(
                    name='name',
                    options=dict(user='fabricio', foo='baz'),
                    image='image:tag',
                    cmd='fab',
                ),
                fork_kwargs=dict(options=dict(foo='bar')),
                expected_properties=dict(
                    name='name',
                    cmd='fab',
                    options={
                        'network': None,
                        'links': None,
                        'stop_signal': None,
                        'restart_policy': None,
                        'hosts': None,
                        'user': 'fabricio',
                        'env': None,
                        'volumes': None,
                        'ports': None,
                        'foo': 'bar',
                    },
                ),
                expected_image='image:tag',
            ),
            predefined_overrride_complex=dict(
                init_kwargs=dict(
                    name='name',
                    options=dict(user='fabricio', foo='baz', hello=42),
                    image='image:tag',
                    cmd='fab',
                ),
                fork_kwargs=dict(
                    options=dict(foo='bar', user='user'),
                    image='image',
                    cmd='command',
                    name='another_name',
                ),
                expected_properties=dict(
                    name='another_name',
                    cmd='command',
                    options={
                        'network': None,
                        'links': None,
                        'stop_signal': None,
                        'restart_policy': None,
                        'hosts': None,
                        'user': 'user',
                        'env': None,
                        'volumes': None,
                        'ports': None,
                        'foo': 'bar',
                        'hello': 42,
                    },
                ),
                expected_image='image:latest',
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                container = docker.Container(**data['init_kwargs'])
                forked_container = container.fork(**data['fork_kwargs'])
                expected_image = data.get('expected_image')
                if expected_image:
                    self.assertEqual(repr(forked_container.image), expected_image)
                for prop, value in data['expected_properties'].items():
                    self.assertEqual(value, getattr(forked_container, prop))

    @mock.patch.object(fabricio, 'log')
    def test_update(self, *args):
        cases = dict(
            no_change=dict(
                side_effect=(
                    SucceededResult('[{"Image": "image_id"}]'),  # current container info
                    SucceededResult('[{"Id": "image_id"}]'),  # new image info
                    SucceededResult(),  # force starting container
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name'),
                    mock.call('docker inspect --type image image:tag'),
                    mock.call('docker start name'),
                ],
                update_kwargs=dict(),
                excpected_result=False,
            ),
            no_change_with_tag=dict(
                side_effect=(
                    SucceededResult('[{"Image": "image_id"}]'),  # current container info
                    SucceededResult('[{"Id": "image_id"}]'),  # new image info
                    SucceededResult(),  # force starting container
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name'),
                    mock.call('docker inspect --type image image:foo'),
                    mock.call('docker start name'),
                ],
                update_kwargs=dict(tag='foo'),
                excpected_result=False,
            ),
            forced=dict(
                side_effect=(
                    SucceededResult('[{"Image": "image_id"}]'),  # obsolete container info
                    SucceededResult(),  # delete obsolete container
                    SucceededResult(),  # remove obsolete volumes
                    SucceededResult(),  # delete obsolete container image
                    SucceededResult(),  # rename current container
                    SucceededResult(),  # stop current container
                    SucceededResult('new_container_id'),  # run new container
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name_backup'),
                    mock.call('docker rm name_backup'),
                    mock.call('for volume in $(docker volume ls --filter "dangling=true" --quiet); do docker volume rm "$volume"; done'),
                    mock.call('docker rmi image_id', ignore_errors=True),
                    mock.call('docker rename name name_backup'),
                    mock.call('docker stop --time 10 name_backup'),
                    mock.call('docker run --name name --detach image:tag ', quiet=True),
                ],
                update_kwargs=dict(force=True),
                excpected_result=True,
            ),
            regular=dict(
                side_effect=(
                    SucceededResult('[{"Image": "image_id"}]'),  # current container info
                    SucceededResult('[{"Id": "new_image_id"}]'),  # new image info
                    SucceededResult('[{"Image": "old_image_id"}]'),  # obsolete container info
                    SucceededResult(),  # delete obsolete container
                    SucceededResult(),  # remove obsolete volumes
                    SucceededResult(),  # delete obsolete container image
                    SucceededResult(),  # rename current container
                    SucceededResult(),  # stop current container
                    SucceededResult('new_container_id'),  # run new container
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name'),
                    mock.call('docker inspect --type image image:tag'),
                    mock.call('docker inspect --type container name_backup'),
                    mock.call('docker rm name_backup'),
                    mock.call('for volume in $(docker volume ls --filter "dangling=true" --quiet); do docker volume rm "$volume"; done'),
                    mock.call('docker rmi old_image_id', ignore_errors=True),
                    mock.call('docker rename name name_backup'),
                    mock.call('docker stop --time 10 name_backup'),
                    mock.call('docker run --name name --detach image:tag ', quiet=True),
                ],
                update_kwargs=dict(),
                excpected_result=True,
            ),
            regular_with_tag=dict(
                side_effect=(
                    SucceededResult('[{"Image": "image_id"}]'),  # current container info
                    SucceededResult('[{"Id": "new_image_id"}]'),  # new image info
                    SucceededResult('[{"Image": "old_image_id"}]'),  # obsolete container info
                    SucceededResult(),  # delete obsolete container
                    SucceededResult(),  # remove obsolete volumes
                    SucceededResult(),  # delete obsolete container image
                    SucceededResult(),  # rename current container
                    SucceededResult(),  # stop current container
                    SucceededResult('new_container_id'),  # run new container
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name'),
                    mock.call('docker inspect --type image image:foo'),
                    mock.call('docker inspect --type container name_backup'),
                    mock.call('docker rm name_backup'),
                    mock.call('for volume in $(docker volume ls --filter "dangling=true" --quiet); do docker volume rm "$volume"; done'),
                    mock.call('docker rmi old_image_id', ignore_errors=True),
                    mock.call('docker rename name name_backup'),
                    mock.call('docker stop --time 10 name_backup'),
                    mock.call('docker run --name name --detach image:foo ', quiet=True),
                ],
                update_kwargs=dict(tag='foo'),
                excpected_result=True,
            ),
            regular_with_registry=dict(
                side_effect=(
                    SucceededResult('[{"Image": "image_id"}]'),  # current container info
                    SucceededResult('[{"Id": "new_image_id"}]'),  # new image info
                    SucceededResult('[{"Image": "old_image_id"}]'),  # obsolete container info
                    SucceededResult(),  # delete obsolete container
                    SucceededResult(),  # remove obsolete volumes
                    SucceededResult(),  # delete obsolete container image
                    SucceededResult(),  # rename current container
                    SucceededResult(),  # stop current container
                    SucceededResult('new_container_id'),  # run new container
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name'),
                    mock.call('docker inspect --type image registry/image:tag'),
                    mock.call('docker inspect --type container name_backup'),
                    mock.call('docker rm name_backup'),
                    mock.call('for volume in $(docker volume ls --filter "dangling=true" --quiet); do docker volume rm "$volume"; done'),
                    mock.call('docker rmi old_image_id', ignore_errors=True),
                    mock.call('docker rename name name_backup'),
                    mock.call('docker stop --time 10 name_backup'),
                    mock.call('docker run --name name --detach registry/image:tag ', quiet=True),
                ],
                update_kwargs=dict(registry='registry'),
                excpected_result=True,
            ),
            regular_with_tag_and_registry=dict(
                side_effect=(
                    SucceededResult('[{"Image": "image_id"}]'),  # current container info
                    SucceededResult('[{"Id": "new_image_id"}]'),  # new image info
                    SucceededResult('[{"Image": "old_image_id"}]'),  # obsolete container info
                    SucceededResult(),  # delete obsolete container
                    SucceededResult(),  # remove obsolete volumes
                    SucceededResult(),  # delete obsolete container image
                    SucceededResult(),  # rename current container
                    SucceededResult(),  # stop current container
                    SucceededResult('new_container_id'),  # run new container
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name'),
                    mock.call('docker inspect --type image registry/image:foo'),
                    mock.call('docker inspect --type container name_backup'),
                    mock.call('docker rm name_backup'),
                    mock.call('for volume in $(docker volume ls --filter "dangling=true" --quiet); do docker volume rm "$volume"; done'),
                    mock.call('docker rmi old_image_id', ignore_errors=True),
                    mock.call('docker rename name name_backup'),
                    mock.call('docker stop --time 10 name_backup'),
                    mock.call('docker run --name name --detach registry/image:foo ', quiet=True),
                ],
                update_kwargs=dict(tag='foo', registry='registry'),
                excpected_result=True,
            ),
            regular_without_backup_container=dict(
                side_effect=(
                    SucceededResult('[{"Image": "image_id"}]'),  # current container info
                    SucceededResult('[{"Id": "new_image_id"}]'),  # new image info
                    RuntimeError,  # obsolete container info
                    SucceededResult(),  # rename current container
                    SucceededResult(),  # stop current container
                    SucceededResult('new_container_id'),  # run new container
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name'),
                    mock.call('docker inspect --type image image:tag'),
                    mock.call('docker inspect --type container name_backup'),
                    mock.call('docker rename name name_backup'),
                    mock.call('docker stop --time 10 name_backup'),
                    mock.call('docker run --name name --detach image:tag ', quiet=True),
                ],
                update_kwargs=dict(),
                excpected_result=True,
            ),
            forced_without_backup_container=dict(
                side_effect=(
                    RuntimeError,  # obsolete container info
                    SucceededResult(),  # rename current container
                    SucceededResult(),  # stop current container
                    SucceededResult('new_container_id'),  # run new container
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name_backup'),
                    mock.call('docker rename name name_backup'),
                    mock.call('docker stop --time 10 name_backup'),
                    mock.call('docker run --name name --detach image:tag ', quiet=True),
                ],
                update_kwargs=dict(force=True),
                excpected_result=True,
            ),
            from_scratch=dict(
                side_effect=(
                    RuntimeError,  # current container info
                    RuntimeError,  # obsolete container info
                    RuntimeError,  # rename current container
                    SucceededResult('new_container_id'),  # run new container
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name'),
                    mock.call('docker inspect --type container name_backup'),
                    mock.call('docker rename name name_backup'),
                    mock.call('docker run --name name --detach image:tag ', quiet=True),
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
                    'run',
                    side_effect=side_effect,
                ) as run:
                    result = container.update(**update_kwargs)
                    self.assertEqual('name', container.name)
                    self.assertListEqual(run.mock_calls, expected_commands)
                    self.assertEqual(excpected_result, result)

    def test_revert(self):
        side_effect = (
            SucceededResult('[{"Image": "backup_image_id"}]'),  # backup container info
            SucceededResult(),  # stop current container
            SucceededResult(),  # start backup container
            SucceededResult('[{"Image": "failed_image_id"}]'),  # current container info
            SucceededResult(),  # delete current container
            SucceededResult(),  # delete dangling volumes
            SucceededResult(),  # delete current container image
            SucceededResult(),  # rename backup container
        )
        expected_commands = [
            mock.call('docker inspect --type container name_backup'),
            mock.call('docker stop --time 10 name'),
            mock.call('docker start name_backup'),
            mock.call('docker inspect --type container name'),
            mock.call('docker rm name'),
            mock.call('for volume in $(docker volume ls --filter "dangling=true" --quiet); do docker volume rm "$volume"; done'),
            mock.call('docker rmi failed_image_id', ignore_errors=True),
            mock.call('docker rename name_backup name'),
        ]
        container = TestContainer(name='name')
        with mock.patch.object(fabricio, 'run', side_effect=side_effect) as run:
            container.revert()
            self.assertListEqual(run.mock_calls, expected_commands)

    @mock.patch.object(fabricio, 'run', side_effect=RuntimeError)
    def test_revert_raises_error_if_backup_container_not_found(self, *args):
        container = docker.Container(name='name')
        with self.assertRaises(RuntimeError) as cm:
            container.revert()
        self.assertEqual(
            cm.exception.args[0],
            "Container 'name_backup' not found",
        )


class ImageTestCase(unittest.TestCase):

    def test_info(self):
        return_value = SucceededResult('[{"Id": "123", "Image": "abc"}]')
        expected = dict(Id='123', Image='abc')
        image = docker.Image(name='name')
        expected_command = 'docker inspect --type image name:latest'
        with mock.patch.object(
            fabricio,
            'run',
            return_value=return_value,
        ) as run:
            self.assertEqual(expected, image.info)
            run.assert_called_once_with(expected_command)

    @mock.patch.object(fabricio, 'run', side_effect=RuntimeError)
    def test_info_raises_error_if_image_not_found(self, run):
        image = docker.Image(name='name')
        expected_command = 'docker inspect --type image name:latest'
        with self.assertRaises(RuntimeError) as cm:
            image.info
        self.assertEqual(cm.exception.args[0], "Image 'name:latest' not found")
        run.assert_called_once_with(expected_command)

    def test_delete(self):
        cases = dict(
            default=dict(
                expeected_commands=[
                    mock.call('docker rmi image:latest', ignore_errors=True),
                ],
                kwargs=dict(),
            ),
            forced=dict(
                expeected_commands=[
                    mock.call('docker rmi --force image:latest', ignore_errors=True),
                ],
                kwargs=dict(force=True),
            ),
            do_not_ignore_errors=dict(
                expeected_commands=[
                    mock.call('docker rmi image:latest', ignore_errors=False),
                ],
                kwargs=dict(ignore_errors=False),
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                with mock.patch.object(fabricio, 'run') as run:
                    image = docker.Image('image')
                    image.delete(**data['kwargs'])
                    self.assertListEqual(
                        run.mock_calls,
                        data['expeected_commands'],
                    )

    def test_name_tag_registry(self):
        cases = dict(
            single=dict(
                init_kwargs=dict(
                    name='image',
                ),
                expected_name='image',
                expected_tag='latest',
                expected_registry=None,
                expected_str='image:latest',
            ),
            with_tag=dict(
                init_kwargs=dict(
                    name='image',
                    tag='tag',
                ),
                expected_name='image',
                expected_tag='tag',
                expected_registry=None,
                expected_str='image:tag',
            ),
            with_registry=dict(
                init_kwargs=dict(
                    name='image',
                    registry='registry:5000',
                ),
                expected_name='image',
                expected_tag='latest',
                expected_registry='registry:5000',
                expected_str='registry:5000/image:latest',
            ),
            with_tag_and_registry=dict(
                init_kwargs=dict(
                    name='image',
                    tag='tag',
                    registry='127.0.0.1:5000',
                ),
                expected_name='image',
                expected_tag='tag',
                expected_registry='127.0.0.1:5000',
                expected_str='127.0.0.1:5000/image:tag',
            ),
            with_tag_and_registry_and_user=dict(
                init_kwargs=dict(
                    name='user/image',
                    tag='tag',
                    registry='127.0.0.1:5000',
                ),
                expected_name='user/image',
                expected_tag='tag',
                expected_registry='127.0.0.1:5000',
                expected_str='127.0.0.1:5000/user/image:tag',
            ),
            single_arg_with_tag=dict(
                init_kwargs=dict(
                    name='image:tag',
                ),
                expected_name='image',
                expected_tag='tag',
                expected_registry=None,
                expected_str='image:tag',
            ),
            single_arg_with_registry=dict(
                init_kwargs=dict(
                    name='registry:123/image',
                ),
                expected_name='image',
                expected_tag='latest',
                expected_registry='registry:123',
                expected_str='registry:123/image:latest',
            ),
            single_arg_with_tag_and_registry=dict(
                init_kwargs=dict(
                    name='registry:123/image:tag',
                ),
                expected_name='image',
                expected_tag='tag',
                expected_registry='registry:123',
                expected_str='registry:123/image:tag',
            ),
            forced_with_tag=dict(
                init_kwargs=dict(
                    name='image:tag',
                    tag='foo',
                ),
                expected_name='image',
                expected_tag='foo',
                expected_registry=None,
                expected_str='image:foo',
            ),
            forced_with_registry=dict(
                init_kwargs=dict(
                    name='user/image',
                    registry='foo',
                ),
                expected_name='user/image',
                expected_tag='latest',
                expected_registry='foo',
                expected_str='foo/user/image:latest',
            ),
            forced_with_tag_and_registry=dict(
                init_kwargs=dict(
                    name='user/image:tag',
                    tag='foo',
                    registry='bar',
                ),
                expected_name='user/image',
                expected_tag='foo',
                expected_registry='bar',
                expected_str='bar/user/image:foo',
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
                start='registry:5000',
                stop=None,
                expected_tag='tag',
                expected_registry='registry:5000',
            ),
            tag_and_registry=dict(
                start='127.0.0.1:5000',
                stop='custom_tag',
                expected_tag='custom_tag',
                expected_registry='127.0.0.1:5000',
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                image = docker.Image(name='name', tag='tag', registry='registry')
                new_image = image[data['start']:data['stop']]
                self.assertEqual(data['expected_tag'], new_image.tag)
                self.assertEqual(data['expected_registry'], new_image.registry)

    def test_run(self):
        image = docker.Image('image')
        cases = dict(
            default=dict(
                kwargs=dict(),
                expected_command='docker run --rm --tty --interactive image:latest ',
            ),
            with_mapping_option=dict(
                kwargs=dict(options=dict(ports='80:80')),
                expected_command='docker run --publish 80:80 --rm --tty --interactive image:latest ',
            ),
            with_unknown_option=dict(
                kwargs=dict(options=dict(foo='bar')),
                expected_command='docker run --rm --tty --interactive --foo bar image:latest ',
            ),
            with_mapping_option_deprecated=dict(
                kwargs=dict(ports='80:80'),
                expected_command='docker run --publish 80:80 --rm --tty --interactive image:latest ',
            ),
            with_unknown_option_deprecated=dict(
                kwargs=dict(foo='bar'),
                expected_command='docker run --rm --tty --interactive --foo bar image:latest ',
            ),
            with_cmd=dict(
                kwargs=dict(cmd='cmd'),
                expected_command='docker run --rm --tty --interactive image:latest cmd',
            ),
            service=dict(
                kwargs=dict(temporary=False),
                expected_command='docker run --detach image:latest ',
            ),
            with_name=dict(
                kwargs=dict(name='name'),
                expected_command='docker run --name name --rm --tty --interactive image:latest ',
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                with mock.patch.object(fabricio, 'run') as run:
                    image.run(**data['kwargs'])
                    run.assert_called_once_with(data['expected_command'], quiet=True)

    def test_image_as_descriptor(self):
        class Container(docker.Container):
            info = dict(Image='image_id')
        cases = dict(
            none=dict(
                image=None,
                expected_name=None,
                expected_registry=None,
                expected_tag=None,
            ),
            name=dict(
                image='image',
                expected_name='image',
                expected_registry=None,
                expected_tag='latest',
            ),
            name_and_tag=dict(
                image='image:tag',
                expected_name='image',
                expected_registry=None,
                expected_tag='tag',
            ),
            name_and_registry=dict(
                image='host:5000/image',
                expected_name='image',
                expected_registry='host:5000',
                expected_tag='latest',
            ),
            complex=dict(
                image='host:5000/user/image:tag',
                expected_name='user/image',
                expected_registry='host:5000',
                expected_tag='tag',
            ),
        )
        image = Container.image
        self.assertIsInstance(image, docker.Image)
        self.assertIsNone(image.name)
        self.assertIsNone(image.registry)
        self.assertIsNone(image.tag)
        self.assertIs(Container.image, image)
        for case, data in cases.items():
            with self.subTest(case=case):
                container = Container('name', image=data['image'])
                self.assertIs(container.image, container.image)
                self.assertIsInstance(container.image, docker.Image)
                self.assertEqual(container.image.name, data['expected_name'])
                self.assertEqual(container.image.registry, data['expected_registry'])
                self.assertEqual(container.image.tag, data['expected_tag'])
                self.assertEqual(container.image.id, 'image_id')

                container.image = old_image = container.image
                self.assertIsNot(container.image, old_image)
                self.assertIsInstance(container.image, docker.Image)
                self.assertEqual(container.image.name, data['expected_name'])
                self.assertEqual(container.image.registry, data['expected_registry'])
                self.assertEqual(container.image.tag, data['expected_tag'])
                self.assertEqual(container.image.id, 'image_id')

        for case, data in cases.items():
            with self.subTest(case='redefine_' + case):
                container = Container('name')
                container.image = data['image']
                self.assertIs(container.image, container.image)
                self.assertIsInstance(container.image, docker.Image)
                self.assertEqual(container.image.name, data['expected_name'])
                self.assertEqual(container.image.registry, data['expected_registry'])
                self.assertEqual(container.image.tag, data['expected_tag'])
                self.assertEqual(container.image.id, 'image_id')

                container.image = old_image = container.image
                self.assertIsNot(container.image, old_image)
                self.assertIsInstance(container.image, docker.Image)
                self.assertEqual(container.image.name, data['expected_name'])
                self.assertEqual(container.image.registry, data['expected_registry'])
                self.assertEqual(container.image.tag, data['expected_tag'])
                self.assertEqual(container.image.id, 'image_id')

        for case, data in cases.items():
            with self.subTest(case='predefined_' + case):
                Container.image = docker.Image(data['image'])
                container = Container('name')
                self.assertIs(container.image, container.image)
                self.assertIsInstance(container.image, docker.Image)
                self.assertEqual(container.image.name, data['expected_name'])
                self.assertEqual(container.image.registry, data['expected_registry'])
                self.assertEqual(container.image.tag, data['expected_tag'])
                self.assertEqual(container.image.id, 'image_id')

                container.image = old_image = container.image
                self.assertIsNot(container.image, old_image)
                self.assertIsInstance(container.image, docker.Image)
                self.assertEqual(container.image.name, data['expected_name'])
                self.assertEqual(container.image.registry, data['expected_registry'])
                self.assertEqual(container.image.tag, data['expected_tag'])
                self.assertEqual(container.image.id, 'image_id')

    def test_get_field_name_raises_error_on_collision(self):
        class Container(docker.Container):
            image2 = docker.Container.image
        container = Container('name')
        with self.assertRaises(ValueError):
            _ = container.image
