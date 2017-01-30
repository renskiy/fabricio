# coding: utf-8
import json

import mock
import re
import unittest2 as unittest

from fabric import api as fab

import fabricio

from fabricio import docker
from fabricio.docker import ImageNotFoundError
from fabricio.docker.container import Option, Attribute
from tests import SucceededResult, docker_run_args_parser, \
    docker_service_update_args_parser, \
    docker_entity_inspect_args_parser, docker_inspect_args_parser, \
    docker_service_create_args_parser, args_parser, FailedResult


class TestContainer(docker.Container):

    image = docker.Image('image:tag')


class ContainerTestCase(unittest.TestCase):

    def test_options(self):
        cases = dict(
            default=dict(
                kwargs=dict(),
                expected={
                    'net': None,
                    'link': None,
                    'stop-signal': None,
                    'restart': None,
                    'add-host': None,
                    'user': None,
                    'env': None,
                    'volume': None,
                    'publish': None,
                    'label': None,
                },
            ),
            custom=dict(
                kwargs=dict(options=dict(foo='bar')),
                expected={
                    'net': None,
                    'link': None,
                    'stop-signal': None,
                    'restart': None,
                    'add-host': None,
                    'user': None,
                    'env': None,
                    'volume': None,
                    'publish': None,
                    'foo': 'bar',
                    'label': None,
                },
            ),
            collision=dict(
                kwargs=dict(options=dict(execute='execute')),
                expected={
                    'net': None,
                    'link': None,
                    'stop-signal': None,
                    'restart': None,
                    'add-host': None,
                    'user': None,
                    'env': None,
                    'volume': None,
                    'publish': None,
                    'execute': 'execute',
                    'label': None,
                },
            ),
            override=dict(
                kwargs=dict(options=dict(env='custom_env')),
                expected={
                    'net': None,
                    'link': None,
                    'stop-signal': None,
                    'restart': None,
                    'add-host': None,
                    'user': None,
                    'env': 'custom_env',
                    'volume': None,
                    'publish': None,
                    'label': None,
                },
            ),
            complex=dict(
                kwargs=dict(options=dict(env='custom_env', foo='bar')),
                expected={
                    'net': None,
                    'link': None,
                    'stop-signal': None,
                    'restart': None,
                    'add-host': None,
                    'user': None,
                    'env': 'custom_env',
                    'volume': None,
                    'publish': None,
                    'foo': 'bar',
                    'label': None,
                },
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                container = TestContainer(**data['kwargs'])
                self.assertDictEqual(data['expected'], dict(container.options))

    def test_options_inheritance(self):

        class Parent(docker.Container):
            user = 'user'  # overridden property (simple)

            @property  # overridden property (dynamic)
            def ports(self):
                return 'ports'

            baz = Option(default=42)  # new property

            @Option  # new dynamic property
            def foo(self):
                return 'bar'

            @Option()  # new dynamic property
            def foo2(self):
                return 'bar2'

            @Option(default='not_used')  # new dynamic property
            def foo3(self):
                return 'bar3'

            null = Option()  # new empty property

            @Option(name='real-name')
            def alias(self):
                return 'value'

            @Option(name='real-name2')
            def overridden_alias(self):
                return 'value'

            @Option(name='real-name3')
            def overridden_alias2(self):
                return 'value'

        class Child(Parent):

            overridden_alias = 'overridden_value'

            @Option(name='overridden-name')
            def overridden_alias2(self):
                return 'overridden_value'

        container = Child()

        self.assertIn('user', container.options)
        self.assertEqual(container.options['user'], 'user')
        container.user = 'fabricio'
        self.assertEqual(container.options['user'], 'fabricio')

        self.assertIn('publish', container.options)
        self.assertEqual(container.options['publish'], 'ports')

        self.assertIn('baz', container.options)
        self.assertEqual(container.options['baz'], 42)
        container.baz = 101
        self.assertEqual(container.options['baz'], 101)

        self.assertIn('foo', container.options)
        self.assertEqual(container.options['foo'], 'bar')
        container.foo = 'baz'
        self.assertEqual(container.options['foo'], 'baz')

        self.assertIn('foo2', container.options)
        self.assertEqual(container.options['foo2'], 'bar2')
        container.foo2 = 'baz2'
        self.assertEqual(container.options['foo2'], 'baz2')

        self.assertIn('foo3', container.options)
        self.assertEqual(container.options['foo3'], 'bar3')
        container.foo3 = 'baz3'
        self.assertEqual(container.options['foo3'], 'baz3')

        self.assertIn('real-name', container.options)
        self.assertEqual(container.options['real-name'], 'value')
        container.alias = 'another_value'
        self.assertEqual(container.options['real-name'], 'another_value')

        self.assertIn('real-name2', container.options)
        self.assertEqual(container.options['real-name2'], 'overridden_value')
        container.overridden_alias = 'another_value'
        self.assertEqual(container.options['real-name2'], 'another_value')

        self.assertIn('overridden-name', container.options)
        self.assertEqual(container.options['overridden-name'], 'overridden_value')
        container.overridden_alias2 = 'another_value'
        self.assertEqual(container.options['overridden-name'], 'another_value')

        self.assertIn('null', container.options)
        self.assertIsNone(container.options['null'])
        container.null = 'value'
        self.assertEqual(container.options['null'], 'value')

    def test_attributes_inheritance(self):

        class Container(docker.Container):
            command = 'command'  # overridden property (simple)

            @property  # overridden property (dynamic)
            def stop_timeout(self):
                return 1001

            baz = Attribute(default=42)  # new property

            @Attribute  # new dynamic property
            def foo(self):
                return 'bar'

            @Attribute()  # new dynamic property
            def foo2(self):
                return 'bar2'

            @Attribute(default='not_used')  # new dynamic property
            def foo3(self):
                return 'bar3'

            null = Attribute()  # new empty property

        container = Container()

        self.assertEqual(container.command, 'command')
        container.command = 'command2'
        self.assertEqual(container.command, 'command2')

        self.assertEqual(container.stop_timeout, 1001)

        self.assertEqual(container.baz, 42)
        container.baz = 101
        self.assertEqual(container.baz, 101)

        self.assertEqual(container.foo, 'bar')
        container.foo = 'baz'
        self.assertEqual(container.foo, 'baz')

        self.assertEqual(container.foo2, 'bar2')
        container.foo2 = 'baz2'
        self.assertEqual(container.foo2, 'baz2')

        self.assertEqual(container.foo3, 'bar3')
        container.foo3 = 'baz3'
        self.assertEqual(container.foo3, 'baz3')

        self.assertIsNone(container.null)
        container.null = 'value'
        self.assertEqual(container.null, 'value')

    def test_container_does_not_allow_modify_options(self):
        container = TestContainer()

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
            run.assert_called_once_with(
                expected_command,
                abort_exception=docker.ContainerNotFoundError,
            )

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
                    mock.call('docker inspect --type container name', abort_exception=docker.ContainerNotFoundError),
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
                    mock.call('docker inspect --type container name', abort_exception=docker.ContainerNotFoundError),
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
        expected_command = 'docker exec --tty --interactive name command'
        with mock.patch.object(
            fabricio,
            'run',
            return_value='result'
        ) as run:
            result = container.execute('command')
            run.assert_called_once_with(
                expected_command,
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

    def test_reload(self):
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
                    container.reload(timeout=data['timeout'])
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
                expected_args={
                    'executable': ['docker'],
                    'run_or_create': ['run'],
                    'name': 'name',
                    'detach': True,
                    'image': 'image:tag',
                    'command': [],
                },
            ),
            complex=dict(
                init_kwargs=dict(
                    name='name',
                    options={
                        'custom-option': 'foo',
                        'restart_policy': 'override',
                    },
                ),
                class_kwargs=dict(
                    image=docker.Image('image:tag'),
                    command='command',
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
                expected_args={
                    'executable': ['docker'],
                    'run_or_create': ['run'],
                    'user': 'user',
                    'publish': ['80:80', '443:443'],
                    'env': ['FOO=foo', 'BAR=bar'],
                    'volume': ['/tmp:/tmp', '/root:/root:ro'],
                    'link': ['db:db'],
                    'add-host': ['host:192.168.0.1'],
                    'net': 'network',
                    'restart': 'override',
                    'stop-signal': 'stop_signal',
                    'name': 'name',
                    'detach': True,
                    'custom-option': 'foo',
                    'image': 'image:tag',
                    'command': ['command'],
                },
            ),
        )

        def test_command(command, *args, **kwargs):
            options = docker_run_args_parser.parse_args(command.split())
            self.assertDictEqual(vars(options), params['expected_args'])
        for case, params in cases.items():
            with self.subTest(case=case):
                init_kwargs = params['init_kwargs']
                class_kwargs = params['class_kwargs']
                Container = type(docker.Container)(
                    'Container',
                    (docker.Container, ),
                    class_kwargs,
                )
                container = Container(**init_kwargs)
                with mock.patch.object(fabricio, 'run', side_effect=test_command):
                    container.run()

    def test_fork(self):
        cases = dict(
            default=dict(
                init_kwargs=dict(name='name'),
                fork_kwargs=dict(),
                expected_properties=dict(
                    name='name',
                    command=None,
                    options={
                        'net': None,
                        'link': None,
                        'stop-signal': None,
                        'restart': None,
                        'add-host': None,
                        'user': None,
                        'env': None,
                        'volume': None,
                        'publish': None,
                        'label': None,
                    },
                ),
            ),
            predefined_default=dict(
                init_kwargs=dict(
                    name='name',
                    options=dict(user='fabricio', foo='baz'),
                    image='image:tag',
                    command='fab',
                ),
                fork_kwargs=dict(),
                expected_properties=dict(
                    name='name',
                    command='fab',
                    options={
                        'net': None,
                        'link': None,
                        'stop-signal': None,
                        'restart': None,
                        'add-host': None,
                        'user': 'fabricio',
                        'env': None,
                        'volume': None,
                        'publish': None,
                        'foo': 'baz',
                        'label': None,
                    },
                ),
                expected_image='image:tag',
            ),
            override_name=dict(
                init_kwargs=dict(name='name'),
                fork_kwargs=dict(name='another_name'),
                expected_properties=dict(
                    name='another_name',
                    command=None,
                    options={
                        'net': None,
                        'link': None,
                        'stop-signal': None,
                        'restart': None,
                        'add-host': None,
                        'user': None,
                        'env': None,
                        'volume': None,
                        'publish': None,
                        'label': None,
                    },
                ),
            ),
            override_command=dict(
                init_kwargs=dict(name='name'),
                fork_kwargs=dict(command='command'),
                expected_properties=dict(
                    name='name',
                    command='command',
                    options={
                        'net': None,
                        'link': None,
                        'stop-signal': None,
                        'restart': None,
                        'add-host': None,
                        'user': None,
                        'env': None,
                        'volume': None,
                        'publish': None,
                        'label': None,
                    },
                ),
            ),
            override_image_str=dict(
                init_kwargs=dict(name='name'),
                fork_kwargs=dict(image='image'),
                expected_properties=dict(
                    name='name',
                    command=None,
                    options={
                        'net': None,
                        'link': None,
                        'stop-signal': None,
                        'restart': None,
                        'add-host': None,
                        'user': None,
                        'env': None,
                        'volume': None,
                        'publish': None,
                        'label': None,
                    },
                ),
                expected_image='image:latest',
            ),
            override_image_instance=dict(
                init_kwargs=dict(name='name'),
                fork_kwargs=dict(image=docker.Image('image')),
                expected_properties=dict(
                    name='name',
                    command=None,
                    options={
                        'net': None,
                        'link': None,
                        'stop-signal': None,
                        'restart': None,
                        'add-host': None,
                        'user': None,
                        'env': None,
                        'volume': None,
                        'publish': None,
                        'label': None,
                    },
                ),
                expected_image='image:latest',
            ),
            override_default_option=dict(
                init_kwargs=dict(name='name'),
                fork_kwargs=dict(options=dict(user='user')),
                expected_properties=dict(
                    name='name',
                    command=None,
                    options={
                        'net': None,
                        'link': None,
                        'stop-signal': None,
                        'restart': None,
                        'add-host': None,
                        'user': 'user',
                        'env': None,
                        'volume': None,
                        'publish': None,
                        'label': None,
                    },
                ),
            ),
            override_custom_option=dict(
                init_kwargs=dict(name='name'),
                fork_kwargs=dict(options=dict(foo='bar')),
                expected_properties=dict(
                    name='name',
                    command=None,
                    options={
                        'net': None,
                        'link': None,
                        'stop-signal': None,
                        'restart': None,
                        'add-host': None,
                        'user': None,
                        'env': None,
                        'volume': None,
                        'publish': None,
                        'foo': 'bar',
                        'label': None,
                    },
                ),
            ),
            overrride_complex=dict(
                init_kwargs=dict(name='name'),
                fork_kwargs=dict(
                    options=dict(foo='bar', user='user'),
                    image='image',
                    command='command',
                    name='another_name',
                ),
                expected_properties=dict(
                    name='another_name',
                    command='command',
                    options={
                        'net': None,
                        'link': None,
                        'stop-signal': None,
                        'restart': None,
                        'add-host': None,
                        'user': 'user',
                        'env': None,
                        'volume': None,
                        'publish': None,
                        'foo': 'bar',
                        'label': None,
                    },
                ),
                expected_image='image:latest',
            ),
            predefined_override_command=dict(
                init_kwargs=dict(
                    name='name',
                    options=dict(user='fabricio', foo='baz'),
                    image='image:tag',
                    command='fab',
                ),
                fork_kwargs=dict(command='command'),
                expected_properties=dict(
                    name='name',
                    command='command',
                    options={
                        'net': None,
                        'link': None,
                        'stop-signal': None,
                        'restart': None,
                        'add-host': None,
                        'user': 'fabricio',
                        'env': None,
                        'volume': None,
                        'publish': None,
                        'foo': 'baz',
                        'label': None,
                    },
                ),
                expected_image='image:tag',
            ),
            predefined_override_image_str=dict(
                init_kwargs=dict(
                    name='name',
                    options=dict(user='fabricio', foo='baz'),
                    image='image:tag',
                    command='fab',
                ),
                fork_kwargs=dict(image='image'),
                expected_properties=dict(
                    name='name',
                    command='fab',
                    options={
                        'net': None,
                        'link': None,
                        'stop-signal': None,
                        'restart': None,
                        'add-host': None,
                        'user': 'fabricio',
                        'env': None,
                        'volume': None,
                        'publish': None,
                        'foo': 'baz',
                        'label': None,
                    },
                ),
                expected_image='image:latest',
            ),
            predefined_override_image_instance=dict(
                init_kwargs=dict(
                    name='name',
                    options=dict(user='fabricio', foo='baz'),
                    image='image:tag',
                    command='fab',
                ),
                fork_kwargs=dict(image=docker.Image('image')),
                expected_properties=dict(
                    name='name',
                    command='fab',
                    options={
                        'net': None,
                        'link': None,
                        'stop-signal': None,
                        'restart': None,
                        'add-host': None,
                        'user': 'fabricio',
                        'env': None,
                        'volume': None,
                        'publish': None,
                        'foo': 'baz',
                        'label': None,
                    },
                ),
                expected_image='image:latest',
            ),
            predefined_override_default_option=dict(
                init_kwargs=dict(
                    name='name',
                    options=dict(user='fabricio', foo='baz'),
                    image='image:tag',
                    command='fab',
                ),
                fork_kwargs=dict(options=dict(user='user')),
                expected_properties=dict(
                    name='name',
                    command='fab',
                    options={
                        'net': None,
                        'link': None,
                        'stop-signal': None,
                        'restart': None,
                        'add-host': None,
                        'user': 'user',
                        'env': None,
                        'volume': None,
                        'publish': None,
                        'foo': 'baz',
                        'label': None,
                    },
                ),
                expected_image='image:tag',
            ),
            predefined_override_custom_option=dict(
                init_kwargs=dict(
                    name='name',
                    options=dict(user='fabricio', foo='baz'),
                    image='image:tag',
                    command='fab',
                ),
                fork_kwargs=dict(options=dict(foo='bar')),
                expected_properties=dict(
                    name='name',
                    command='fab',
                    options={
                        'net': None,
                        'link': None,
                        'stop-signal': None,
                        'restart': None,
                        'add-host': None,
                        'user': 'fabricio',
                        'env': None,
                        'volume': None,
                        'publish': None,
                        'foo': 'bar',
                        'label': None,
                    },
                ),
                expected_image='image:tag',
            ),
            predefined_overrride_complex=dict(
                init_kwargs=dict(
                    name='name',
                    options=dict(user='fabricio', foo='baz', hello=42),
                    image='image:tag',
                    command='fab',
                ),
                fork_kwargs=dict(
                    options=dict(foo='bar', user='user'),
                    image='image',
                    command='command',
                    name='another_name',
                ),
                expected_properties=dict(
                    name='another_name',
                    command='command',
                    options={
                        'net': None,
                        'link': None,
                        'stop-signal': None,
                        'restart': None,
                        'add-host': None,
                        'user': 'user',
                        'env': None,
                        'volume': None,
                        'publish': None,
                        'foo': 'bar',
                        'hello': 42,
                        'label': None,
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
                    mock.call('docker inspect --type container name', abort_exception=docker.ContainerNotFoundError),
                    mock.call('docker inspect --type image image:tag', abort_exception=docker.ImageNotFoundError),
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
                    mock.call('docker inspect --type container name', abort_exception=docker.ContainerNotFoundError),
                    mock.call('docker inspect --type image image:foo', abort_exception=docker.ImageNotFoundError),
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
                    mock.call('docker inspect --type container name_backup', abort_exception=docker.ContainerNotFoundError),
                    mock.call('docker rm name_backup'),
                    mock.call('for volume in $(docker volume ls --filter "dangling=true" --quiet); do docker volume rm "$volume"; done'),
                    mock.call('docker rmi image_id', ignore_errors=True),
                    mock.call('docker rename name name_backup'),
                    mock.call('docker stop --time 10 name_backup'),
                    mock.call('docker run --detach --name name image:tag ', quiet=True),
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
                    mock.call('docker inspect --type container name', abort_exception=docker.ContainerNotFoundError),
                    mock.call('docker inspect --type image image:tag', abort_exception=docker.ImageNotFoundError),
                    mock.call('docker inspect --type container name_backup', abort_exception=docker.ContainerNotFoundError),
                    mock.call('docker rm name_backup'),
                    mock.call('for volume in $(docker volume ls --filter "dangling=true" --quiet); do docker volume rm "$volume"; done'),
                    mock.call('docker rmi old_image_id', ignore_errors=True),
                    mock.call('docker rename name name_backup'),
                    mock.call('docker stop --time 10 name_backup'),
                    mock.call('docker run --detach --name name image:tag ', quiet=True),
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
                    mock.call('docker inspect --type container name', abort_exception=docker.ContainerNotFoundError),
                    mock.call('docker inspect --type image image:foo', abort_exception=docker.ImageNotFoundError),
                    mock.call('docker inspect --type container name_backup', abort_exception=docker.ContainerNotFoundError),
                    mock.call('docker rm name_backup'),
                    mock.call('for volume in $(docker volume ls --filter "dangling=true" --quiet); do docker volume rm "$volume"; done'),
                    mock.call('docker rmi old_image_id', ignore_errors=True),
                    mock.call('docker rename name name_backup'),
                    mock.call('docker stop --time 10 name_backup'),
                    mock.call('docker run --detach --name name image:foo ', quiet=True),
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
                    mock.call('docker inspect --type container name', abort_exception=docker.ContainerNotFoundError),
                    mock.call('docker inspect --type image registry/image:tag', abort_exception=docker.ImageNotFoundError),
                    mock.call('docker inspect --type container name_backup', abort_exception=docker.ContainerNotFoundError),
                    mock.call('docker rm name_backup'),
                    mock.call('for volume in $(docker volume ls --filter "dangling=true" --quiet); do docker volume rm "$volume"; done'),
                    mock.call('docker rmi old_image_id', ignore_errors=True),
                    mock.call('docker rename name name_backup'),
                    mock.call('docker stop --time 10 name_backup'),
                    mock.call('docker run --detach --name name registry/image:tag ', quiet=True),
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
                    mock.call('docker inspect --type container name', abort_exception=docker.ContainerNotFoundError),
                    mock.call('docker inspect --type image registry/image:foo', abort_exception=docker.ImageNotFoundError),
                    mock.call('docker inspect --type container name_backup', abort_exception=docker.ContainerNotFoundError),
                    mock.call('docker rm name_backup'),
                    mock.call('for volume in $(docker volume ls --filter "dangling=true" --quiet); do docker volume rm "$volume"; done'),
                    mock.call('docker rmi old_image_id', ignore_errors=True),
                    mock.call('docker rename name name_backup'),
                    mock.call('docker stop --time 10 name_backup'),
                    mock.call('docker run --detach --name name registry/image:foo ', quiet=True),
                ],
                update_kwargs=dict(tag='foo', registry='registry'),
                excpected_result=True,
            ),
            regular_without_backup_container=dict(
                side_effect=(
                    SucceededResult('[{"Image": "image_id"}]'),  # current container info
                    SucceededResult('[{"Id": "new_image_id"}]'),  # new image info
                    docker.ContainerNotFoundError,  # obsolete container info
                    SucceededResult(),  # rename current container
                    SucceededResult(),  # stop current container
                    SucceededResult('new_container_id'),  # run new container
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name', abort_exception=docker.ContainerNotFoundError),
                    mock.call('docker inspect --type image image:tag', abort_exception=docker.ImageNotFoundError),
                    mock.call('docker inspect --type container name_backup', abort_exception=docker.ContainerNotFoundError),
                    mock.call('docker rename name name_backup'),
                    mock.call('docker stop --time 10 name_backup'),
                    mock.call('docker run --detach --name name image:tag ', quiet=True),
                ],
                update_kwargs=dict(),
                excpected_result=True,
            ),
            forced_without_backup_container=dict(
                side_effect=(
                    docker.ContainerNotFoundError,  # obsolete container info
                    SucceededResult(),  # rename current container
                    SucceededResult(),  # stop current container
                    SucceededResult('new_container_id'),  # run new container
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name_backup', abort_exception=docker.ContainerNotFoundError),
                    mock.call('docker rename name name_backup'),
                    mock.call('docker stop --time 10 name_backup'),
                    mock.call('docker run --detach --name name image:tag ', quiet=True),
                ],
                update_kwargs=dict(force=True),
                excpected_result=True,
            ),
            from_scratch=dict(
                side_effect=(
                    docker.ContainerNotFoundError,  # current container info
                    docker.ContainerNotFoundError,  # obsolete container info
                    RuntimeError,  # rename current container
                    SucceededResult('new_container_id'),  # run new container
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name', abort_exception=docker.ContainerNotFoundError),
                    mock.call('docker inspect --type container name_backup', abort_exception=docker.ContainerNotFoundError),
                    mock.call('docker rename name name_backup'),
                    mock.call('docker run --detach --name name image:tag ', quiet=True),
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
            mock.call('docker inspect --type container name_backup', abort_exception=docker.ContainerNotFoundError),
            mock.call('docker stop --time 10 name'),
            mock.call('docker start name_backup'),
            mock.call('docker inspect --type container name', abort_exception=docker.ContainerNotFoundError),
            mock.call('docker rm name'),
            mock.call('for volume in $(docker volume ls --filter "dangling=true" --quiet); do docker volume rm "$volume"; done'),
            mock.call('docker rmi failed_image_id', ignore_errors=True),
            mock.call('docker rename name_backup name'),
        ]
        container = TestContainer(name='name')
        with mock.patch.object(fabricio, 'run', side_effect=side_effect) as run:
            container.revert()
            self.assertListEqual(run.mock_calls, expected_commands)

    @mock.patch.object(
        docker.Container,
        'info',
        new_callable=mock.PropertyMock,
        side_effect=docker.ContainerNotFoundError,
    )
    @mock.patch.object(fabricio, 'run')
    def test_revert_raises_error_if_backup_container_not_found(self, run, *args):
        container = docker.Container(name='name')
        with self.assertRaises(docker.ContainerError):
            container.revert()
        run.assert_not_called()


class ImageTestCase(unittest.TestCase):

    def test___init___can_take_another_image_as_argument(self):
        cases = dict(
            default_image=dict(
                source_image=docker.Image(),
                name=None,
                tag=None,
                registry=None,
            ),
            filled_image_1=dict(
                source_image=docker.Image(name='name', tag='tag', registry='registry:5000'),
                name='name',
                tag='tag',
                registry='registry:5000',
                repr='registry:5000/name:tag',
            ),
            filled_image_2=dict(
                source_image=docker.Image('registry:5000/name:tag'),
                name='name',
                tag='tag',
                registry='registry:5000',
                repr='registry:5000/name:tag',
            ),
            digest=dict(
                source_image=docker.Image('registry:5000/name@digest'),
                name='name',
                tag='digest',
                registry='registry:5000',
                repr='registry:5000/name@digest',
                digest='registry:5000/name@digest',
            ),
            from_container=dict(
                source_image=docker.Container(image='registry:5000/name:tag').image,
                name='name',
                tag='tag',
                registry='registry:5000',
                repr='registry:5000/name:tag',
            ),
            digest_from_container=dict(
                source_image=docker.Container(image='registry:5000/name@digest').image,
                name='name',
                tag='digest',
                registry='registry:5000',
                repr='registry:5000/name@digest',
                digest='registry:5000/name@digest',
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                image = docker.Image(data['source_image'])
                self.assertEqual(image.name, data['name'])
                self.assertEqual(image.tag, data['tag'])
                self.assertEqual(image.registry, data['registry'])
                if 'repr' in data:
                    self.assertEqual(repr(image), data['repr'])
                if 'digest' in data:
                    self.assertEqual(image.digest, data['digest'])

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
            run.assert_called_once_with(
                expected_command,
                abort_exception=docker.ImageNotFoundError,
            )

    @mock.patch.object(fabricio, 'run', side_effect=RuntimeError)
    def test_info_raises_error_if_image_not_found(self, run):
        image = docker.Image(name='name')
        expected_command = 'docker inspect --type image name:latest'
        with self.assertRaises(RuntimeError):
            image.info
        run.assert_called_once_with(
            expected_command,
            abort_exception=docker.ImageNotFoundError,
        )

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
            digest_with_registry=dict(
                init_kwargs=dict(
                    name='image@digest',
                    registry='registry:5000',
                ),
                expected_name='image',
                expected_tag='digest',
                expected_registry='registry:5000',
                expected_str='registry:5000/image@digest',
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
            single_arg_with_digest=dict(
                init_kwargs=dict(
                    name='image@digest',
                ),
                expected_name='image',
                expected_tag='digest',
                expected_registry=None,
                expected_str='image@digest',
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
            single_arg_with_digest_and_registry=dict(
                init_kwargs=dict(
                    name='registry:123/image@digest',
                ),
                expected_name='image',
                expected_tag='digest',
                expected_registry='registry:123',
                expected_str='registry:123/image@digest',
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
            digest_forced_with_tag=dict(
                init_kwargs=dict(
                    name='image@digest',
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
            digest_forced_with_tag_and_registry=dict(
                init_kwargs=dict(
                    name='user/image@digest',
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
                image_init_kwargs=dict(name='name', tag='tag', registry='registry'),
                item=None,
                expected_tag='tag',
                expected_registry='registry',
            ),
            tag=dict(
                image_init_kwargs=dict(name='name', tag='tag', registry='registry'),
                item='custom_tag',
                expected_tag='custom_tag',
                expected_registry='registry',
            ),
            digest_none=dict(
                image_init_kwargs=dict(name='name@digest'),
                item=None,
                expected_tag='digest',
                expected_registry=None,
            ),
            digest_tag=dict(
                image_init_kwargs=dict(name='name@digest'),
                item='custom_tag',
                expected_tag='custom_tag',
                expected_registry=None,
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                image = docker.Image(**data['image_init_kwargs'])
                new_image = image[data['item']]
                self.assertEqual(data['expected_tag'], new_image.tag)
                self.assertEqual(data['expected_registry'], new_image.registry)

    def test_getitem_slice(self):
        cases = dict(
            none=dict(
                image_init_kwargs=dict(name='name', tag='tag', registry='registry'),
                start=None,
                stop=None,
                expected_tag='tag',
                expected_registry='registry',
            ),
            tag=dict(
                image_init_kwargs=dict(name='name', tag='tag', registry='registry'),
                start=None,
                stop='custom_tag',
                expected_tag='custom_tag',
                expected_registry='registry',
            ),
            registry=dict(
                image_init_kwargs=dict(name='name', tag='tag', registry='registry'),
                start='registry:5000',
                stop=None,
                expected_tag='tag',
                expected_registry='registry:5000',
            ),
            tag_and_registry=dict(
                image_init_kwargs=dict(name='name', tag='tag', registry='registry'),
                start='127.0.0.1:5000',
                stop='custom_tag',
                expected_tag='custom_tag',
                expected_registry='127.0.0.1:5000',
            ),
            digest_none=dict(
                image_init_kwargs=dict(name='name@digest'),
                start=None,
                stop=None,
                expected_tag='digest',
                expected_registry=None,
            ),
            digest_tag=dict(
                image_init_kwargs=dict(name='name@digest'),
                start=None,
                stop='custom_tag',
                expected_tag='custom_tag',
                expected_registry=None,
            ),
            digest_registry=dict(
                image_init_kwargs=dict(name='name@digest'),
                start='registry:5000',
                stop=None,
                expected_tag='digest',
                expected_registry='registry:5000',
            ),
            digest_tag_and_registry=dict(
                image_init_kwargs=dict(name='name@digest'),
                start='127.0.0.1:5000',
                stop='custom_tag',
                expected_tag='custom_tag',
                expected_registry='127.0.0.1:5000',
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                image = docker.Image(**data['image_init_kwargs'])
                new_image = image[data['start']:data['stop']]
                self.assertEqual(data['expected_tag'], new_image.tag)
                self.assertEqual(data['expected_registry'], new_image.registry)

    def test_run(self):
        image = docker.Image('image')
        cases = dict(
            default=dict(
                kwargs=dict(),
                expected_args={
                    'executable': ['docker'],
                    'run_or_create': ['run'],
                    'rm': True,
                    'tty': True,
                    'interactive': True,
                    'image': 'image:latest',
                    'command': [],
                },
            ),
            with_main_option=dict(
                kwargs=dict(options={'user': 'user'}),
                expected_args={
                    'executable': ['docker'],
                    'run_or_create': ['run'],
                    'rm': True,
                    'tty': True,
                    'interactive': True,
                    'user': 'user',
                    'image': 'image:latest',
                    'command': [],
                },
            ),
            with_additional_option=dict(
                kwargs=dict(options={'custom-option': 'bar'}),
                expected_args={
                    'executable': ['docker'],
                    'run_or_create': ['run'],
                    'rm': True,
                    'tty': True,
                    'interactive': True,
                    'custom-option': 'bar',
                    'image': 'image:latest',
                    'command': [],
                },
            ),
            with_main_option_deprecated=dict(
                kwargs=dict(user='user'),
                expected_args={
                    'executable': ['docker'],
                    'run_or_create': ['run'],
                    'rm': True,
                    'tty': True,
                    'interactive': True,
                    'user': 'user',
                    'image': 'image:latest',
                    'command': [],
                },
            ),
            with_additional_option_deprecated=dict(
                kwargs={'custom-option': 'bar'},
                expected_args={
                    'executable': ['docker'],
                    'run_or_create': ['run'],
                    'rm': True,
                    'tty': True,
                    'interactive': True,
                    'custom-option': 'bar',
                    'image': 'image:latest',
                    'command': [],
                },
            ),
            with_command=dict(
                kwargs=dict(command='command'),
                expected_args={
                    'executable': ['docker'],
                    'run_or_create': ['run'],
                    'rm': True,
                    'tty': True,
                    'interactive': True,
                    'image': 'image:latest',
                    'command': ['command'],
                },
            ),
            detached=dict(
                kwargs=dict(temporary=False, name='name'),
                expected_command='docker run --detach image:latest ',
                expected_args={
                    'executable': ['docker'],
                    'run_or_create': ['run'],
                    'name': 'name',
                    'detach': True,
                    'image': 'image:latest',
                    'command': [],
                },
            ),
            with_name=dict(
                kwargs=dict(name='name'),
                expected_command='docker run --name name --rm --tty --interactive image:latest ',
                expected_args={
                    'executable': ['docker'],
                    'run_or_create': ['run'],
                    'rm': True,
                    'tty': True,
                    'interactive': True,
                    'image': 'image:latest',
                    'name': 'name',
                    'command': [],
                },
            ),
        )

        def test_command(command, *args, **kwargs):
            options = docker_run_args_parser.parse_args(command.split())
            self.assertDictEqual(vars(options), data['expected_args'])
        for case, data in cases.items():
            with self.subTest(case=case):
                with mock.patch.object(fabricio, 'run', side_effect=test_command):
                    image.run(**data['kwargs'])

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
                container = Container(image=data['image'])
                self.assertIs(container.image, container.image)
                self.assertIsInstance(container.image, docker.Image)
                self.assertEqual(container.image.name, data['expected_name'])
                self.assertEqual(container.image.registry, data['expected_registry'])
                self.assertEqual(container.image.tag, data['expected_tag'])
                self.assertEqual(str(container.image), 'image_id')

                container.image = old_image = container.image
                self.assertIsNot(container.image, old_image)
                self.assertIsInstance(container.image, docker.Image)
                self.assertEqual(container.image.name, data['expected_name'])
                self.assertEqual(container.image.registry, data['expected_registry'])
                self.assertEqual(container.image.tag, data['expected_tag'])
                self.assertEqual(str(container.image), 'image_id')

        for case, data in cases.items():
            with self.subTest(case='redefine_' + case):
                container = Container()
                container.image = data['image']
                self.assertIs(container.image, container.image)
                self.assertIsInstance(container.image, docker.Image)
                self.assertEqual(container.image.name, data['expected_name'])
                self.assertEqual(container.image.registry, data['expected_registry'])
                self.assertEqual(container.image.tag, data['expected_tag'])
                self.assertEqual(str(container.image), 'image_id')

                container.image = old_image = container.image
                self.assertIsNot(container.image, old_image)
                self.assertIsInstance(container.image, docker.Image)
                self.assertEqual(container.image.name, data['expected_name'])
                self.assertEqual(container.image.registry, data['expected_registry'])
                self.assertEqual(container.image.tag, data['expected_tag'])
                self.assertEqual(str(container.image), 'image_id')

        for case, data in cases.items():
            with self.subTest(case='predefined_' + case):
                Container.image = docker.Image(data['image'])
                container = Container()
                self.assertIs(container.image, container.image)
                self.assertIsInstance(container.image, docker.Image)
                self.assertEqual(container.image.name, data['expected_name'])
                self.assertEqual(container.image.registry, data['expected_registry'])
                self.assertEqual(container.image.tag, data['expected_tag'])
                self.assertEqual(str(container.image), 'image_id')

                container.image = old_image = container.image
                self.assertIsNot(container.image, old_image)
                self.assertIsInstance(container.image, docker.Image)
                self.assertEqual(container.image.name, data['expected_name'])
                self.assertEqual(container.image.registry, data['expected_registry'])
                self.assertEqual(container.image.tag, data['expected_tag'])
                self.assertEqual(str(container.image), 'image_id')

    def test_get_field_name_raises_error_on_collision(self):
        class Container(docker.Container):
            image2 = docker.Container.image
        container = Container(name='name')
        with self.assertRaises(ValueError):
            _ = container.image


class ServiceTestCase(unittest.TestCase):

    maxDiff = None

    def setUp(self):
        self.fab_settings = fab.settings(fab.hide('everything'))
        self.fab_settings.__enter__()

    def tearDown(self):
        fabricio.run.cache.clear()
        self.fab_settings.__exit__(None, None, None)

    def test_update(self):
        cases = dict(
            worker=dict(
                init_kwargs=dict(
                    name='service',
                    image='image:tag',
                ),
                update_kwargs=dict(),
                side_effect=(
                    SucceededResult('[{"RepoDigests": ["digest"]}]'),  # image info
                    SucceededResult('  Is Manager: false'),  # manager status
                ),
                args_parsers=[
                    docker_inspect_args_parser,
                    args_parser,
                ],
                expected_args=[
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'image:tag',
                    },
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', "'Is Manager:'"],
                    },
                ],
                expected_result=False,
            ),
            worker_failed_sentinels_update=dict(
                init_kwargs=dict(
                    name='service',
                    image='image:tag',
                ),
                update_kwargs=dict(),
                side_effect=(
                    SucceededResult('[{"RepoDigests": ["digest"]}]'),  # image info
                    SucceededResult('  Is Manager: false'),  # manager status
                ),
                args_parsers=[
                    docker_inspect_args_parser,
                    args_parser,
                ],
                expected_args=[
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'image:tag',
                    },
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', "'Is Manager:'"],
                    },
                ],
                expected_result=False,
                _update_sentinels_fails=True,
            ),
            no_changes=dict(
                init_kwargs=dict(
                    name='service',
                    image='image:tag',
                ),
                update_kwargs=dict(),
                side_effect=(
                    SucceededResult('[{"RepoDigests": ["digest"]}]'),  # image info
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult('[{"Spec": {"Labels":{"_backup_options":"{}","_current_options":"{\\"env-add\\": null, \\"constraint-add\\": null, \\"args\\": null, \\"label-rm\\": null, \\"env-rm\\": null, \\"publish-add\\": null, \\"label-add\\": null, \\"replicas\\": 1, \\"mount-rm\\": null, \\"container-label-rm\\": null, \\"user\\": null, \\"publish-rm\\": null, \\"mount-add\\": null, \\"constraint-rm\\": null, \\"stop-grace-period\\": \\"10s\\", \\"restart-condition\\": null, \\"container-label-add\\": null, \\"image\\": \\"digest\\"}"}}}]'),  # service info
                ),
                args_parsers=[
                    docker_inspect_args_parser,
                    args_parser,
                    docker_entity_inspect_args_parser,
                ],
                expected_args=[
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'image:tag',
                    },
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', "'Is Manager:'"],
                    },
                    {
                        'executable': ['docker', 'service', 'inspect'],
                        'service': 'service',
                    },
                ],
                expected_result=False,
            ),
            forced=dict(
                init_kwargs=dict(
                    name='service',
                    image='image:tag',
                ),
                update_kwargs=dict(force=True),
                side_effect=(
                    SucceededResult('[{"RepoDigests": ["digest"]}]'),  # image info
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult('[{"Spec": {"Labels":{"_backup_options":"{}","_current_options":"{\\"env-add\\": null, \\"constraint-add\\": null, \\"args\\": null, \\"label-rm\\": null, \\"env-rm\\": null, \\"publish-add\\": null, \\"label-add\\": null, \\"replicas\\": 1, \\"mount-rm\\": null, \\"container-label-rm\\": null, \\"user\\": null, \\"publish-rm\\": null, \\"mount-add\\": null, \\"constraint-rm\\": null, \\"stop-grace-period\\": \\"10s\\", \\"restart-condition\\": null, \\"container-label-add\\": null, \\"image\\": \\"digest\\"}"}}}]'),  # service info
                    SucceededResult(),  # service update
                ),
                args_parsers=[
                    docker_inspect_args_parser,
                    args_parser,
                    docker_entity_inspect_args_parser,
                    docker_service_update_args_parser,
                ],
                expected_args=[
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'image:tag',
                    },
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', "'Is Manager:'"],
                    },
                    {
                        'executable': ['docker', 'service', 'inspect'],
                        'service': 'service',
                    },
                    {
                        'executable': ['docker', 'service', 'update'],
                        'image': 'digest',
                        'replicas': '1',
                        'service': 'service',
                        'stop-grace-period': '10s',
                    },
                ],
                expected_service_labels=[
                    '"_current_options={\\"env-add\\": null, \\"constraint-add\\": null, \\"label-rm\\": null, \\"env-rm\\": null, \\"publish-add\\": null, \\"label-add\\": null, \\"image\\": \\"digest\\", \\"args\\": null, \\"mount-rm\\": null, \\"container-label-rm\\": null, \\"user\\": null, \\"replicas\\": 1, \\"publish-rm\\": null, \\"mount-add\\": null, \\"constraint-rm\\": null, \\"stop-grace-period\\": \\"10s\\", \\"restart-condition\\": null, \\"container-label-add\\": null}"',
                    '"_backup_options={\\"env-add\\": null, \\"constraint-add\\": null, \\"args\\": null, \\"label-rm\\": null, \\"env-rm\\": null, \\"publish-add\\": null, \\"label-add\\": null, \\"replicas\\": 1, \\"mount-rm\\": null, \\"container-label-rm\\": null, \\"user\\": null, \\"publish-rm\\": null, \\"mount-add\\": null, \\"constraint-rm\\": null, \\"stop-grace-period\\": \\"10s\\", \\"restart-condition\\": null, \\"container-label-add\\": null, \\"image\\": \\"digest\\"}"',
                ],
                expected_result=True,
            ),
            updated=dict(
                init_kwargs=dict(
                    name='service',
                    image='image:tag',
                ),
                update_kwargs=dict(),
                side_effect=(
                    SucceededResult('[{"RepoDigests": ["digest"]}]'),  # image info
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult('[{"Spec": {"Labels":{"_backup_options":"{}","_current_options":"{}"}}}]'),  # service info
                    SucceededResult(),  # service update
                ),
                args_parsers=[
                    docker_inspect_args_parser,
                    args_parser,
                    docker_entity_inspect_args_parser,
                    docker_service_update_args_parser,
                ],
                expected_args=[
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'image:tag',
                    },
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', "'Is Manager:'"],
                    },
                    {
                        'executable': ['docker', 'service', 'inspect'],
                        'service': 'service',
                    },
                    {
                        'executable': ['docker', 'service', 'update'],
                        'image': 'digest',
                        'replicas': '1',
                        'service': 'service',
                        'stop-grace-period': '10s',
                    },
                ],
                expected_service_labels=[
                    '"_current_options={\\"env-add\\": null, \\"constraint-add\\": null, \\"label-rm\\": null, \\"env-rm\\": null, \\"publish-add\\": null, \\"label-add\\": null, \\"image\\": \\"digest\\", \\"args\\": null, \\"mount-rm\\": null, \\"container-label-rm\\": null, \\"user\\": null, \\"replicas\\": 1, \\"publish-rm\\": null, \\"mount-add\\": null, \\"constraint-rm\\": null, \\"stop-grace-period\\": \\"10s\\", \\"restart-condition\\": null, \\"container-label-add\\": null}"',
                    '_backup_options={}',
                ],
                expected_result=True,
            ),
            updated_with_custom_labels=dict(
                init_kwargs=dict(
                    name='service',
                    image='image:tag',
                    options=dict(label=['label1=label1', 'label2=label2']),
                ),
                update_kwargs=dict(),
                side_effect=(
                    SucceededResult('[{"RepoDigests": ["digest"]}]'),  # image info
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult('[{"Spec": {"Labels":{"_backup_options":"{}","_current_options":"{}"}}}]'),  # service info
                    SucceededResult(),  # service update
                ),
                args_parsers=[
                    docker_inspect_args_parser,
                    args_parser,
                    docker_entity_inspect_args_parser,
                    docker_service_update_args_parser,
                ],
                expected_args=[
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'image:tag',
                    },
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', "'Is Manager:'"],
                    },
                    {
                        'executable': ['docker', 'service', 'inspect'],
                        'service': 'service',
                    },
                    {
                        'executable': ['docker', 'service', 'update'],
                        'image': 'digest',
                        'replicas': '1',
                        'service': 'service',
                        'stop-grace-period': '10s',
                    },
                ],
                expected_service_labels=[
                    '"_current_options={\\"env-add\\": null, \\"constraint-add\\": null, \\"label-rm\\": null, \\"env-rm\\": null, \\"publish-add\\": null, \\"label-add\\": [\\"label1=label1\\", \\"label2=label2\\"], \\"image\\": \\"digest\\", \\"args\\": null, \\"mount-rm\\": null, \\"container-label-rm\\": null, \\"user\\": null, \\"replicas\\": 1, \\"publish-rm\\": null, \\"mount-add\\": null, \\"constraint-rm\\": null, \\"stop-grace-period\\": \\"10s\\", \\"restart-condition\\": null, \\"container-label-add\\": null}"',
                    '_backup_options={}',
                    'label1=label1',
                    'label2=label2',
                ],
                expected_result=True,
            ),
            updated_with_custom_tag_and_registry=dict(
                init_kwargs=dict(
                    name='service',
                    image='image:tag',
                ),
                update_kwargs=dict(tag='custom_tag', registry='registry'),
                side_effect=(
                    SucceededResult('[{"RepoDigests": ["digest"]}]'),  # image info
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult('[{"Spec": {"Labels":{"_backup_options":"{}","_current_options":"{}"}}}]'),  # service info
                    SucceededResult(),  # service update
                ),
                args_parsers=[
                    docker_inspect_args_parser,
                    args_parser,
                    docker_entity_inspect_args_parser,
                    docker_service_update_args_parser,
                ],
                expected_args=[
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'registry/image:custom_tag',
                    },
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', "'Is Manager:'"],
                    },
                    {
                        'executable': ['docker', 'service', 'inspect'],
                        'service': 'service',
                    },
                    {
                        'executable': ['docker', 'service', 'update'],
                        'image': 'digest',
                        'replicas': '1',
                        'service': 'service',
                        'stop-grace-period': '10s',
                    },
                ],
                expected_service_labels=[
                    '"_current_options={\\"env-add\\": null, \\"constraint-add\\": null, \\"label-rm\\": null, \\"env-rm\\": null, \\"publish-add\\": null, \\"label-add\\": null, \\"image\\": \\"digest\\", \\"args\\": null, \\"mount-rm\\": null, \\"container-label-rm\\": null, \\"user\\": null, \\"replicas\\": 1, \\"publish-rm\\": null, \\"mount-add\\": null, \\"constraint-rm\\": null, \\"stop-grace-period\\": \\"10s\\", \\"restart-condition\\": null, \\"container-label-add\\": null}"',
                    '_backup_options={}',
                ],
                expected_result=True,
            ),
            created=dict(
                init_kwargs=dict(
                    name='service',
                    image='image:tag',
                ),
                update_kwargs=dict(),
                side_effect=(
                    SucceededResult('[{"RepoDigests": ["digest"]}]'),  # image info
                    SucceededResult('  Is Manager: true'),  # manager status
                    docker.ServiceNotFoundError(),  # service info
                    SucceededResult(),  # service create
                ),
                args_parsers=[
                    docker_inspect_args_parser,
                    args_parser,
                    docker_entity_inspect_args_parser,
                    docker_service_create_args_parser,
                ],
                expected_args=[
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'image:tag',
                    },
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', "'Is Manager:'"],
                    },
                    {
                        'executable': ['docker', 'service', 'inspect'],
                        'service': 'service',
                    },
                    {
                        'executable': ['docker', 'service', 'create'],
                        'image': ['digest'],
                        'name': 'service',
                        'replicas': '1',
                        'args': [],
                        'stop-grace-period': '10s',
                    },
                ],
                expected_service_labels=[
                    '"_current_options={\\"env-add\\": null, \\"constraint-add\\": null, \\"label-rm\\": null, \\"env-rm\\": null, \\"publish-add\\": null, \\"label-add\\": null, \\"image\\": \\"digest\\", \\"args\\": null, \\"mount-rm\\": null, \\"container-label-rm\\": null, \\"user\\": null, \\"replicas\\": 1, \\"publish-rm\\": null, \\"mount-add\\": null, \\"constraint-rm\\": null, \\"stop-grace-period\\": \\"10s\\", \\"restart-condition\\": null, \\"container-label-add\\": null}"',
                ],
                expected_result=True,
            ),
            created_with_custom_tag_and_registry=dict(
                init_kwargs=dict(
                    name='service',
                    image='image:tag',
                ),
                update_kwargs=dict(tag='custom_tag', registry='registry'),
                side_effect=(
                    SucceededResult('[{"RepoDigests": ["digest"]}]'),  # image info
                    SucceededResult('  Is Manager: true'),  # manager status
                    docker.ServiceNotFoundError(),  # service info
                    SucceededResult(),  # service create
                ),
                args_parsers=[
                    docker_inspect_args_parser,
                    args_parser,
                    docker_entity_inspect_args_parser,
                    docker_service_create_args_parser,
                ],
                expected_args=[
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'registry/image:custom_tag',
                    },
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', "'Is Manager:'"],
                    },
                    {
                        'executable': ['docker', 'service', 'inspect'],
                        'service': 'service',
                    },
                    {
                        'executable': ['docker', 'service', 'create'],
                        'image': ['digest'],
                        'name': 'service',
                        'replicas': '1',
                        'args': [],
                        'stop-grace-period': '10s',
                    },
                ],
                expected_service_labels=[
                    '"_current_options={\\"env-add\\": null, \\"constraint-add\\": null, \\"label-rm\\": null, \\"env-rm\\": null, \\"publish-add\\": null, \\"label-add\\": null, \\"image\\": \\"digest\\", \\"args\\": null, \\"mount-rm\\": null, \\"container-label-rm\\": null, \\"user\\": null, \\"replicas\\": 1, \\"publish-rm\\": null, \\"mount-add\\": null, \\"constraint-rm\\": null, \\"stop-grace-period\\": \\"10s\\", \\"restart-condition\\": null, \\"container-label-add\\": null}"',
                ],
                expected_result=True,
            ),
        )
        current_options_re = re.compile('"_current_options=(.*)"')

        def test_command(command, **kwargs):
            args = re.findall('".+?(?<!\\\\)"|\'.+?(?<!\\\\)\'|[^\s]+', command)
            parser = next(args_parsers)
            options = vars(parser.parse_args(args))
            labels = None
            if command.startswith('docker service create'):
                labels = options.pop('label', [])
            elif command.startswith('docker service update'):
                labels = options.pop('label-add', [])
            if labels is not None:
                self.assertEqual(len(labels), len(data['expected_service_labels']))
                for expected_label in data['expected_service_labels']:
                    match = current_options_re.match(expected_label)
                    if match:
                        expected_value = json.loads(match.group(1).replace('\\', ''))
                        value = None
                        for label in labels:
                            match = current_options_re.match(label)
                            if match:
                                value = json.loads(match.group(1).replace('\\', ''))
                                break
                        self.assertEqual(expected_value, value)
                    else:
                        self.assertIn(expected_label.replace('\\', '\\\\'), labels)
            self.assertDictEqual(options, next(expected_args))
            result = next(side_effect)
            if isinstance(result, Exception):
                raise result
            return result
        for case, data in cases.items():
            expected_args = iter(data['expected_args'])
            args_parsers = iter(data['args_parsers'])
            side_effect = iter(data['side_effect'])
            with self.subTest(case=case):
                fab.env.command = '{0}__{1}'.format(self, case)
                fabricio.run.cache.clear()  # reset Service.is_manager()
                with mock.patch.object(fab, 'run', side_effect=test_command) as run:
                    with mock.patch.object(docker.Service, '_update_sentinels') as _update_sentinels:
                        if data.get('_update_sentinels_fails', False):
                            _update_sentinels.side_effect = RuntimeError()
                        run.__name__ = 'mocked_run'
                        service = docker.Service(**data['init_kwargs'])
                        result = service.update(**data['update_kwargs'])
                        self.assertEqual(run.call_count, len(data['expected_args']))
                        self.assertEqual(result, data['expected_result'])

    def test_update_options(self, *args):
        cases = dict(
            default=dict(
                init_kwargs=dict(name='name'),
                service_info=dict(),
                expected={
                    'env-add': None,
                    'constraint-add': None,
                    'label-rm': None,
                    'env-rm': None,
                    'publish-add': None,
                    'label-add': None,
                    'args': None,
                    'mount-rm': None,
                    'container-label-rm': None,
                    'user': None,
                    'replicas': 1,
                    'publish-rm': None,
                    'mount-add': None,
                    'constraint-rm': None,
                    'stop-grace-period': '10s',
                    'restart-condition': None,
                    'container-label-add': None,
                },
            ),
            empty_args=dict(
                init_kwargs=dict(name='name', args=''),
                service_info=dict(),
                expected={
                    'env-add': None,
                    'constraint-add': None,
                    'label-rm': None,
                    'env-rm': None,
                    'publish-add': None,
                    'label-add': None,
                    'args': '',
                    'mount-rm': None,
                    'container-label-rm': None,
                    'user': None,
                    'replicas': 1,
                    'publish-rm': None,
                    'mount-add': None,
                    'constraint-rm': None,
                    'stop-grace-period': '10s',
                    'restart-condition': None,
                    'container-label-add': None,
                },
            ),
            new_option_value=dict(
                init_kwargs=dict(
                    name='service',
                    args='arg1 "arg2" \'arg3\'',
                    options=dict(
                        publish='source:target',
                        mount='type=volume,destination=/path',
                        label='label=value',
                        env='FOO=bar',
                        constraint='node.role == manager',
                        container_label='label=value',
                        network='network',
                        mode='mode',
                        restart_condition='on-failure',
                        stop_grace_period=20,
                        custom_option='custom_value',
                        replicas=3,
                        user='user',
                    ),
                ),
                service_info=dict(),
                expected={
                    'env-add': 'FOO=bar',
                    'constraint-add': 'node.role == manager',
                    'label-rm': None,
                    'env-rm': None,
                    'publish-add': 'source:target',
                    'label-add': 'label=value',
                    'args': 'arg1 "arg2" \'arg3\'',
                    'mount-rm': None,
                    'container-label-rm': None,
                    'user': 'user',
                    'replicas': 3,
                    'publish-rm': None,
                    'mount-add': 'type=volume,destination=/path',
                    'constraint-rm': None,
                    'stop-grace-period': 20,
                    'restart-condition': 'on-failure',
                    'custom_option': 'custom_value',
                    'container-label-add': 'label=value',
                },
            ),
            changed_option_value=dict(
                init_kwargs=dict(
                    name='service',
                    args='arg1 "arg2" \'arg3\'',
                    options=dict(
                        publish='8000:80',
                        mount='type=new_type,destination=/path',
                        label='label=new_value',
                        env='FOO=baz',
                        constraint='node.role == worker',
                        container_label='label=container_new_value',
                        network='new_network',
                        mode='mode',
                        restart_condition='any',
                        stop_grace_period=20,
                        custom_option='new_custom_value',
                        replicas=2,
                        user='new_user',
                    ),
                ),
                service_info=dict(
                    Spec=dict(
                        Labels=dict(
                            label='value',
                        ),
                        TaskTemplate=dict(
                            ContainerSpec=dict(
                                Labels=dict(
                                    label='value',
                                ),
                                Env=[
                                    'FOO=bar',
                                ],
                                Mounts=[
                                    dict(
                                        Type='volume',
                                        Source='/source',
                                        Target='/path',
                                    ),
                                ]
                            ),
                            Placement=dict(
                                Constraints=[
                                    'node.role == manager',
                                ],
                            ),
                        ),
                        EndpointSpec=dict(
                            Ports=[
                                dict(
                                    TargetPort=80,
                                    Protocol='tcp',
                                    PublishedPort=8080,
                                ),
                            ],
                        ),
                    ),
                ),
                expected={
                    'env-add': 'FOO=baz',
                    'constraint-add': 'node.role == worker',
                    'label-rm': [],
                    'env-rm': [],
                    'publish-add': '8000:80',
                    'label-add': 'label=new_value',
                    'args': 'arg1 "arg2" \'arg3\'',
                    'mount-rm': [],
                    'container-label-rm': [],
                    'user': 'new_user',
                    'replicas': 2,
                    'publish-rm': [],
                    'mount-add': 'type=new_type,destination=/path',
                    'constraint-rm': ['node.role == manager'],
                    'stop-grace-period': 20,
                    'restart-condition': 'any',
                    'custom_option': 'new_custom_value',
                    'container-label-add': 'label=container_new_value',
                },
            ),
            new_options_values=dict(
                init_kwargs=dict(
                    name='service',
                    options=dict(
                        publish=[
                            'source:target',
                            'source2:target2',
                        ],
                        mount=[
                            'type=volume,destination=/path',
                            'type=volume,destination="/path2"',
                        ],
                        label=[
                            'label=value',
                            'label2=value2',
                        ],
                        container_label=[
                            'label=value',
                            'label2=value2',
                        ],
                        constraint=[
                            'node.role == manager',
                            'node.role == worker',
                        ],
                        env=[
                            'FOO=bar',
                            'FOO2=bar2',
                        ],
                    ),
                ),
                service_info=dict(),
                expected={
                    'env-add': ['FOO=bar', 'FOO2=bar2'],
                    'constraint-add': ['node.role == manager', 'node.role == worker'],
                    'label-rm': None,
                    'env-rm': None,
                    'publish-add': ['source:target', 'source2:target2'],
                    'label-add': ['label=value', 'label2=value2'],
                    'args': None,
                    'mount-rm': None,
                    'container-label-rm': None,
                    'user': None,
                    'replicas': 1,
                    'publish-rm': None,
                    'mount-add': ['type=volume,destination=/path', 'type=volume,destination="/path2"'],
                    'constraint-rm': None,
                    'stop-grace-period': '10s',
                    'restart-condition': None,
                    'container-label-add': ['label=value', 'label2=value2'],
                },
            ),
            remove_option_value=dict(
                init_kwargs=dict(
                    name='service',
                ),
                service_info=dict(
                    Spec=dict(
                        Labels=dict(
                            label='value',
                        ),
                        TaskTemplate=dict(
                            ContainerSpec=dict(
                                Labels=dict(
                                    label='value',
                                ),
                                Env=[
                                    'FOO=bar',
                                ],
                                Mounts=[
                                    dict(
                                        Type='volume',
                                        Source='/source',
                                        Target='/path',
                                    ),
                                ]
                            ),
                            Placement=dict(
                                Constraints=[
                                    'node.role == manager',
                                ],
                            ),
                        ),
                        EndpointSpec=dict(
                            Ports=[
                                dict(
                                    TargetPort='target',
                                    Protocol='tcp',
                                    PublishedPort='source',
                                ),
                            ],
                        ),
                    ),
                ),
                expected={
                    'env-add': None,
                    'constraint-add': None,
                    'label-rm': ['label'],
                    'env-rm': ['FOO'],
                    'publish-add': None,
                    'label-add': None,
                    'args': None,
                    'mount-rm': ['/path'],
                    'container-label-rm': ['label'],
                    'user': None,
                    'replicas': 1,
                    'publish-rm': ['target'],
                    'mount-add': None,
                    'constraint-rm': ['node.role == manager'],
                    'stop-grace-period': '10s',
                    'restart-condition': None,
                    'container-label-add': None,
                },
            ),
            remove_single_option_value_from_two=dict(
                init_kwargs=dict(
                    name='service',
                    options=dict(
                        publish='source2:target2',
                        mount='type=volume,destination=/path',
                        label='label=value',
                        env='FOO=bar',
                        constraint='node.role == manager',
                        container_label='label=value',
                    ),
                ),
                service_info=dict(
                    Spec=dict(
                        Labels=dict(
                            label='value',
                            label2='value2',
                        ),
                        TaskTemplate=dict(
                            ContainerSpec=dict(
                                Labels=dict(
                                    label='value',
                                    label2='value2',
                                ),
                                Env=[
                                    'FOO=bar',
                                    'FOO2=bar2',
                                ],
                                Mounts=[
                                    dict(
                                        Type='volume',
                                        Source='/source',
                                        Target='/path',
                                    ),
                                    dict(
                                        Type='volume',
                                        Source='/source2',
                                        Target='/path2',
                                    ),
                                ]
                            ),
                            Placement=dict(
                                Constraints=[
                                    'node.role == manager',
                                    'node.role == worker',
                                ],
                            ),
                        ),
                        EndpointSpec=dict(
                            Ports=[
                                dict(
                                    TargetPort='target',
                                    Protocol='tcp',
                                    PublishedPort='source',
                                ),
                                dict(
                                    TargetPort='target2',
                                    Protocol='tcp',
                                    PublishedPort='source2',
                                ),
                            ],
                        ),
                    ),
                ),
                expected={
                    'env-add': 'FOO=bar',
                    'constraint-add': 'node.role == manager',
                    'label-rm': ['label2'],
                    'env-rm': ['FOO2'],
                    'publish-add': 'source2:target2',
                    'label-add': 'label=value',
                    'args': None,
                    'mount-rm': ['/path2'],
                    'container-label-rm': ['label2'],
                    'user': None,
                    'replicas': 1,
                    'publish-rm': ['target'],
                    'mount-add': 'type=volume,destination=/path',
                    'constraint-rm': ['node.role == worker'],
                    'stop-grace-period': '10s',
                    'restart-condition': None,
                    'container-label-add': 'label=value',
                },
            ),
            remove_single_option_value_from_three=dict(
                init_kwargs=dict(
                    name='service',
                    options=dict(
                        publish=[
                            'source2:target2',
                            'source3:target3',
                        ],
                        mount=[
                            'type=volume,destination=/path',
                            'type=volume,destination="/path2"',
                        ],
                        label=[
                            'label=value',
                            'label2=value2',
                        ],
                        env=[
                            'FOO=bar',
                            'FOO2=bar2',
                        ],
                        constraint=[
                            'node.role == manager',
                            'node.role == worker',
                        ],
                        container_label=[
                            'label=value',
                            'label2=value2',
                        ],
                    ),
                ),
                service_info=dict(
                    Spec=dict(
                        Labels=dict(
                            label='value',
                            label2='value2',
                            label3='value3',
                        ),
                        TaskTemplate=dict(
                            ContainerSpec=dict(
                                Labels=dict(
                                    label='value',
                                    label2='value2',
                                    label3='value3',
                                ),
                                Env=[
                                    'FOO=bar',
                                    'FOO2=bar2',
                                    'FOO3=bar3',
                                ],
                                Mounts=[
                                    dict(
                                        Type='volume',
                                        Source='/source',
                                        Target='/path',
                                    ),
                                    dict(
                                        Type='volume',
                                        Source='/source2',
                                        Target='/path2',
                                    ),
                                    dict(
                                        Type='volume',
                                        Source='/source3',
                                        Target='/path3',
                                    ),
                                ]
                            ),
                            Placement=dict(
                                Constraints=[
                                    'node.role == manager',
                                    'node.role == worker',
                                    'constraint',
                                ],
                            ),
                        ),
                        EndpointSpec=dict(
                            Ports=[
                                dict(
                                    TargetPort='target',
                                    Protocol='tcp',
                                    PublishedPort='source',
                                ),
                                dict(
                                    TargetPort='target2',
                                    Protocol='tcp',
                                    PublishedPort='source2',
                                ),
                                dict(
                                    TargetPort='target3',
                                    Protocol='tcp',
                                    PublishedPort='source3',
                                ),
                            ],
                        ),
                    ),
                ),
                expected={
                    'env-add': ['FOO=bar', 'FOO2=bar2'],
                    'constraint-add': ['node.role == manager', 'node.role == worker'],
                    'label-rm': ['label3'],
                    'env-rm': ['FOO3'],
                    'publish-add': ['source2:target2', 'source3:target3'],
                    'label-add': ['label=value', 'label2=value2'],
                    'args': None,
                    'mount-rm': ['/path3'],
                    'container-label-rm': ['label3'],
                    'user': None,
                    'replicas': 1,
                    'publish-rm': ['target'],
                    'mount-add': ['type=volume,destination=/path', 'type=volume,destination="/path2"'],
                    'constraint-rm': ['constraint'],
                    'stop-grace-period': '10s',
                    'restart-condition': None,
                    'container-label-add': ['label=value', 'label2=value2'],
                },
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                with mock.patch.object(
                    docker.Service,
                    'info',
                    new_callable=mock.PropertyMock,
                    return_value=data['service_info'],
                    __delete__=lambda *_: None,
                ):
                    service = docker.Service(**data['init_kwargs'])
                    self.assertDictEqual(
                        dict(service.update_options),
                        data['expected'],
                    )

    def test__update_labels(self):
        cases = dict(
            empty=dict(
                service_init_kwargs=dict(),
                kwargs={},
                expected_service_labels=[],
            ),
            existing_label_str=dict(
                service_init_kwargs=dict(options=dict(label='label=label')),
                kwargs={},
                expected_service_labels=['label=label'],
            ),
            existing_label_list=dict(
                service_init_kwargs=dict(options=dict(label=['label1=label1', 'label2=label2'])),
                kwargs={},
                expected_service_labels=['label1=label1', 'label2=label2'],
            ),
            existing_label_tuple=dict(
                service_init_kwargs=dict(options=dict(label=('label1=label1', 'label2=label2'))),
                kwargs={},
                expected_service_labels=['label1=label1', 'label2=label2'],
            ),
            existing_label_str_add_json=dict(
                service_init_kwargs=dict(options=dict(label='label=label')),
                kwargs={'new_label': '{"foo": "bar"}'},
                expected_service_labels=['label=label', 'new_label={\\"foo\\": \\"bar\\"}'],
            ),
            existing_label_str_add_one=dict(
                service_init_kwargs=dict(options=dict(label='label=label')),
                kwargs={'new_label': 'new_label'},
                expected_service_labels=['label=label', 'new_label=new_label'],
            ),
            existing_label_object_add_one=dict(
                service_init_kwargs=dict(options=dict(label=42)),
                kwargs={'new_label': 'new_label'},
                expected_service_labels=['42', 'new_label=new_label'],
            ),
            existing_label_list_add_one=dict(
                service_init_kwargs=dict(options=dict(label=['label1=label1', 'label2=label2'])),
                kwargs={'new_label': 'new_label'},
                expected_service_labels=['label1=label1', 'label2=label2', 'new_label=new_label'],
            ),
            existing_label_tuple_add_one=dict(
                service_init_kwargs=dict(options=dict(label=('label1=label1', 'label2=label2'))),
                kwargs={'new_label': 'new_label'},
                expected_service_labels=['label1=label1', 'label2=label2', 'new_label=new_label'],
            ),
            existing_label_str_add_two=dict(
                service_init_kwargs=dict(options=dict(label='label=label')),
                kwargs={'new_label1': 'new_label1', 'new_label2': 'new_label2'},
                expected_service_labels=['label=label', 'new_label1=new_label1', 'new_label2=new_label2'],
            ),
            existing_label_object_add_two=dict(
                service_init_kwargs=dict(options=dict(label=42)),
                kwargs={'new_label1': 'new_label1', 'new_label2': 'new_label2'},
                expected_service_labels=['42', 'new_label1=new_label1', 'new_label2=new_label2'],
            ),
            existing_label_list_add_two=dict(
                service_init_kwargs=dict(options=dict(label=['label1=label1', 'label2=label2'])),
                kwargs={'new_label1': 'new_label1', 'new_label2': 'new_label2'},
                expected_service_labels=['label1=label1', 'label2=label2', 'new_label1=new_label1', 'new_label2=new_label2'],
            ),
            existing_label_tuple_add_two=dict(
                service_init_kwargs=dict(options=dict(label=('label1=label1', 'label2=label2'))),
                kwargs={'new_label1': 'new_label1', 'new_label2': 'new_label2'},
                expected_service_labels=['label1=label1', 'label2=label2', 'new_label1=new_label1', 'new_label2=new_label2'],
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                service = docker.Service(**data['service_init_kwargs'])
                old_labels_id = id(service.label)
                service._update_labels(**data['kwargs'])
                for label in data['expected_service_labels']:
                    self.assertIn(label, service.label)
                self.assertEqual(len(service.label), len(data['expected_service_labels']))
                # make sure original container's labels not changed
                self.assertNotEqual(id(service.label), old_labels_id)

    def test__service_need_update(self):
        cases = dict(
            empty_options=dict(
                options_old={},
                options_new={},
                are_different=False,
            ),
            empty_values_to_remove=dict(
                options_old={},
                options_new={
                    'env-rm': None,
                    'custom': set(),
                    'custom-rm': [],
                },
                are_different=False,
            ),
            simply_equal=dict(
                options_old={
                    'env-add': ['FOO=foo', 'BAR=bar'],
                    'custom': 'custom',
                    'custom2': None,
                    'custom3': [],
                    'custom4': None,
                    'custom-rm': 'custom',
                    'env-rm': ['BAZ'],
                    'iterable1': ['foo'],
                    'iterable2': 'foo',
                },
                options_new={
                    'env-add': set(['BAR=bar', 'FOO=foo']),
                    'custom': 'custom',
                    'custom2': False,
                    'custom3': None,
                    'custom4': [],
                    'custom-rm': 'custom',
                    'iterable1': 'foo',
                    'iterable2': ['foo'],
                },
                are_different=False,
            ),
            int_option_changed=dict(
                options_old={
                    'replicas': 1,
                },
                options_new={
                    'replicas': 2,
                },
                are_different=True,
            ),
            str_option_changed=dict(
                options_old={
                    'str': 'foo',
                },
                options_new={
                    'str': 'bar',
                },
                are_different=True,
            ),
            key_changed=dict(
                options_old={
                    'key1': 'foo',
                },
                options_new={
                    'key2': 'foo',
                },
                are_different=True,
            ),
            bool_option_changed=dict(
                options_old={
                    'bool': True,
                },
                options_new={
                    'bool': False,
                },
                are_different=True,
            ),
            list_option_changed=dict(
                options_old={
                    'list': ['foo', 'bar'],
                },
                options_new={
                    'list': ['foo'],
                },
                are_different=True,
            ),
            option_type_changed_1=dict(
                options_old={
                    'list': None,
                },
                options_new={
                    'list': ['foo'],
                },
                are_different=True,
            ),
            option_type_changed_2=dict(
                options_old={
                    'list': ['foo'],
                },
                options_new={
                    'list': None,
                },
                are_different=True,
            ),
            default_not_changed=dict(
                options_old={
                    "env-add": None,
                    "constraint-add": None,
                    "label-rm": None,
                    "network": None,
                    "env-rm": None,
                    "publish-add": None,
                    "label-add": None,
                    "image": "digest",
                    "args": None,
                    "mount-rm": None,
                    "container-label-rm": None,
                    "user": None,
                    "replicas": 1,
                    "publish-rm": None,
                    "mount-add": None,
                    "constraint-rm": None,
                    "stop-grace-period": 10,
                    "restart-condition": None,
                    "container-label-add": None,
                },
                options_new={
                    "env-add": None,
                    "constraint-add": None,
                    "args": None,
                    "label-rm": None,
                    "network": None,
                    "env-rm": None,
                    "publish-add": None,
                    "label-add": None,
                    "replicas": 1,
                    "mount-rm": None,
                    "container-label-rm": None,
                    "user": None,
                    "publish-rm": None,
                    "mount-add": None,
                    "constraint-rm": None,
                    "stop-grace-period": 10,
                    "restart-condition": None,
                    "container-label-add": None,
                    "image": "digest",
                },
                are_different=False,
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                service = docker.Service(name='name')
                result = service._service_need_update(
                    data['options_old'],
                    data['options_new'],
                )
                self.assertEqual(result, data['are_different'])

    @mock.patch.object(docker.Service, 'is_manager', return_value=True)
    @mock.patch.object(docker.Service, '_revert_sentinels')
    @mock.patch.object(docker.Service, '_update_service')
    def test_revert(self, _update_service, *args):
        cases = dict(
            remove_single_option_value=dict(
                service_info=dict(
                    Spec=dict(
                        Labels=dict(
                            bar='BAR',
                            _backup_options='{}',
                            _current_options='{}',
                        ),
                        TaskTemplate=dict(
                            ContainerSpec=dict(
                                Labels=dict(
                                    bar='BAR',
                                ),
                                Env=[
                                    'FOO=bar',
                                ],
                                Mounts=[
                                    dict(
                                        Type='volume',
                                        Source='/source',
                                        Target='/path',
                                    ),
                                ]
                            ),
                            Placement=dict(
                                Constraints=[
                                    'bar',
                                ],
                            ),
                        ),
                        EndpointSpec=dict(
                            Ports=[
                                dict(
                                    TargetPort='8000',
                                    Protocol='tcp',
                                    PublishedPort='80',
                                ),
                            ],
                        ),
                    ),
                ),
                expected_result={
                    'env-rm': ['FOO'],
                    'constraint-rm': ['bar'],
                    'label-add': ['_current_options={}'],
                    'label-rm': ['bar', '_backup_options'],
                    'container-label-rm': ['bar'],
                    'publish-rm': ['8000'],
                    'mount-rm': ['/path'],
                },
            ),
            change_single_option_value=dict(
                service_info=dict(
                    Spec=dict(
                        Labels=dict(
                            bar='BAR',
                            _backup_options='{"custom-option": "another value", "constraint-add": ["foo"], "publish-add": ["8000:8000"], "image": "another value", "args": "another value", "user": "another value", "mount-add": ["type=volume,destination=/path"], "container-label-add": ["bar=FOO"], "restart-condition": "another value", "env-add": ["FOO=baz"], "label-add": "bar=FOO", "stop-grace-period": "another value"}',
                            _current_options='{}',
                        ),
                        TaskTemplate=dict(
                            ContainerSpec=dict(
                                Labels=dict(
                                    bar='BAR',
                                ),
                                Env=[
                                    'FOO=bar',
                                ],
                                Mounts=[
                                    dict(
                                        Type='volume',
                                        Source='/source',
                                        Target='/path',
                                    ),
                                ]
                            ),
                            Placement=dict(
                                Constraints=[
                                    'bar',
                                ],
                            ),
                        ),
                        EndpointSpec=dict(
                            Ports=[
                                dict(
                                    TargetPort='8000',
                                    Protocol='tcp',
                                    PublishedPort='80',
                                ),
                            ],
                        ),
                    ),
                ),
                expected_result={
                    'env-add': ['FOO=baz'],
                    'constraint-add': ['foo'],
                    'constraint-rm': ['bar'],
                    'label-add': ['bar=FOO', '_current_options={\\"custom-option\\": \\"another value\\", \\"constraint-add\\": [\\"foo\\"], \\"publish-add\\": [\\"8000:8000\\"], \\"image\\": \\"another value\\", \\"args\\": \\"another value\\", \\"user\\": \\"another value\\", \\"mount-add\\": [\\"type=volume,destination=/path\\"], \\"container-label-add\\": [\\"bar=FOO\\"], \\"restart-condition\\": \\"another value\\", \\"env-add\\": [\\"FOO=baz\\"], \\"label-add\\": \\"bar=FOO\\", \\"stop-grace-period\\": \\"another value\\"}'],
                    'label-rm': ['_backup_options'],
                    'container-label-add': ['bar=FOO'],
                    'publish-add': ['8000:8000'],
                    'mount-add': ['type=volume,destination=/path'],
                    'custom-option': 'another value',
                    'restart-condition': 'another value',
                    'stop-grace-period': 'another value',
                    'user': 'another value',
                    'args': 'another value',
                    'image': 'another value',
                },
            ),
            add_single_option_value=dict(
                service_info=dict(
                    Spec=dict(
                        Labels=dict(
                            _backup_options='{"env-add": ["FOO=baz"], "constraint-add": ["foo"], "constraint-rm": ["bar"], "custom-option": "another value", "env-rm": ["BAR"], "publish-add": ["8000:8000"], "label-add": ["bar=FOO"], "image": "another value", "args": "another value", "label-rm": ["bar"], "mount-rm": ["/path"], "container-label-rm": ["bar"], "user": "another value", "publish-rm": ["8000"], "mount-add": ["type=volume,destination=/path"], "container-label-add": ["bar=FOO"], "stop-grace-period": "another value", "restart-condition": "another value", "custom-rm": "rm", "custom-add": "add"}',
                            _current_options='{}',
                        ),
                    ),
                ),
                expected_result={
                    'env-add': ['FOO=baz'],
                    'constraint-add': ['foo'],
                    'label-add': ['bar=FOO', '_current_options={\\"env-add\\": [\\"FOO=baz\\"], \\"constraint-add\\": [\\"foo\\"], \\"constraint-rm\\": [\\"bar\\"], \\"custom-option\\": \\"another value\\", \\"env-rm\\": [\\"BAR\\"], \\"publish-add\\": [\\"8000:8000\\"], \\"label-add\\": [\\"bar=FOO\\"], \\"image\\": \\"another value\\", \\"args\\": \\"another value\\", \\"label-rm\\": [\\"bar\\"], \\"mount-rm\\": [\\"/path\\"], \\"container-label-rm\\": [\\"bar\\"], \\"user\\": \\"another value\\", \\"publish-rm\\": [\\"8000\\"], \\"mount-add\\": [\\"type=volume,destination=/path\\"], \\"container-label-add\\": [\\"bar=FOO\\"], \\"stop-grace-period\\": \\"another value\\", \\"restart-condition\\": \\"another value\\", \\"custom-rm\\": \\"rm\\", \\"custom-add\\": \\"add\\"}'],
                    'label-rm': ['_backup_options'],
                    'container-label-add': ['bar=FOO'],
                    'custom-option': 'another value',
                    'restart-condition': 'another value',
                    'stop-grace-period': 'another value',
                    'user': 'another value',
                    'args': 'another value',
                    'image': 'another value',
                    'publish-add': ['8000:8000'],
                    'mount-add': ['type=volume,destination=/path'],
                    'custom-rm': 'rm',
                    'custom-add': 'add',
                },
            ),
            remove_single_option_value_from_two=dict(
                service_info=dict(
                    Spec=dict(
                        Labels=dict(
                            FOO='foo',
                            bar='BAR',
                            _backup_options='{"env-add": ["FOO=foo"], "constraint-add": ["foo"], "publish-add": ["8080:8080"], "label-add": ["FOO=foo"], "mount-add": ["destination=/"], "container-label-add": ["FOO=foo"]}',
                            _current_options='{}',
                        ),
                        TaskTemplate=dict(
                            ContainerSpec=dict(
                                Labels=dict(
                                    FOO='foo',
                                    bar='BAR',
                                ),
                                Env=[
                                    'FOO=foo',
                                    'BAR=bar',
                                ],
                                Mounts=[
                                    dict(
                                        Type='volume',
                                        Source='/source',
                                        Target='/path',
                                    ),
                                    dict(
                                        Type='volume',
                                        Source='/source',
                                        Target='/',
                                    ),
                                ]
                            ),
                            Placement=dict(
                                Constraints=[
                                    'foo',
                                    'bar',
                                ],
                            ),
                        ),
                        EndpointSpec=dict(
                            Ports=[
                                dict(
                                    TargetPort='8000',
                                    Protocol='tcp',
                                    PublishedPort='80',
                                ),
                                dict(
                                    TargetPort='8080',
                                    Protocol='tcp',
                                    PublishedPort='8080',
                                ),
                            ],
                        ),
                    ),
                ),
                expected_result={
                    'env-add': ['FOO=foo'],
                    'constraint-add': ['foo'],
                    'label-add': ['FOO=foo', '_current_options={\\"env-add\\": [\\"FOO=foo\\"], \\"constraint-add\\": [\\"foo\\"], \\"publish-add\\": [\\"8080:8080\\"], \\"label-add\\": [\\"FOO=foo\\"], \\"mount-add\\": [\\"destination=/\\"], \\"container-label-add\\": [\\"FOO=foo\\"]}'],
                    'container-label-add': ['FOO=foo'],
                    'publish-add': ['8080:8080'],
                    'mount-add': ['destination=/'],
                    'constraint-rm': ['bar'],
                    'container-label-rm': ['bar'],
                    'label-rm': ['bar', '_backup_options'],
                    'publish-rm': ['8000'],
                    'env-rm': ['BAR'],
                    'mount-rm': ['/path'],
                },
            ),
        )
        for case, data in cases.items():
            fab.env.command = '{0}__{1}'.format(self, case)
            _update_service.reset_mock()
            with self.subTest(case=case):
                with mock.patch.object(
                    docker.Service,
                    'info',
                    new_callable=mock.PropertyMock,
                    return_value=data['service_info'],
                    __delete__=lambda *_: None,
                ):
                    service = docker.Service(name='service')
                    service.revert()
                    _update_service.assert_called_once_with(data['expected_result'])

    @mock.patch.object(docker.Service, 'is_manager', return_value=True)
    @mock.patch.object(docker.Service, '_update_service')
    @mock.patch.object(docker.Service, '_revert_sentinels')
    def test_revert_errors(self, *args):
        cases = dict(
            _backup_options_not_found=dict(
                service_info=dict(
                    Spec=dict(
                        Labels={},
                    ),
                ),
            ),
            labels_not_found=dict(
                service_info={},
            ),
        )
        for case, data in cases.items():
            fab.env.command = '{0}__{1}'.format(self, case)
            with self.subTest(case=case):
                with mock.patch.object(
                    docker.Service,
                    'info',
                    new_callable=mock.PropertyMock,
                    return_value=data['service_info'],
                    __delete__=lambda *_: None,
                ):
                    service = docker.Service()
                    with self.assertRaises(docker.ServiceError):
                        service.revert()

    def test__create_service(self):
        cases = dict(
            default=dict(
                service_init_kwargs=dict(name='service'),
                expected_args={
                    'executable': ['docker', 'service', 'create'],
                    'image': ['image:tag'],
                    'name': 'service',
                    'replicas': '1',
                    'args': [],
                    'stop-grace-period': '10s',
                },
            ),
            custom_image=dict(
                service_init_kwargs=dict(name='service', image='custom'),
                expected_args={
                    'executable': ['docker', 'service', 'create'],
                    'image': ['image:tag'],
                    'name': 'service',
                    'replicas': '1',
                    'args': [],
                    'stop-grace-period': '10s',
                },
            ),
            custom_command=dict(
                service_init_kwargs=dict(name='service', command='command'),
                expected_args={
                    'executable': ['docker', 'service', 'create'],
                    'image': ['image:tag'],
                    'name': 'service',
                    'replicas': '1',
                    'args': [],
                    'command': '"command"',
                    'stop-grace-period': '10s',
                },
            ),
            custom_args=dict(
                service_init_kwargs=dict(name='service', args='arg1 arg2'),
                expected_args={
                    'executable': ['docker', 'service', 'create'],
                    'image': ['image:tag'],
                    'name': 'service',
                    'replicas': '1',
                    'args': ['arg1', 'arg2'],
                    'command': '""',
                    'stop-grace-period': '10s',
                },
            ),
            custom_command_and_args=dict(
                service_init_kwargs=dict(
                    name='service',
                    command='command',
                    args='arg1 arg2',
                ),
                expected_args={
                    'executable': ['docker', 'service', 'create'],
                    'image': ['image:tag'],
                    'name': 'service',
                    'replicas': '1',
                    'args': ['arg1', 'arg2'],
                    'command': '"command"',
                    'stop-grace-period': '10s',
                },
            ),
            complex=dict(
                service_init_kwargs=dict(
                    name='service',
                    command='command1 command2',
                    args='arg1 arg2',
                    options=dict(
                        mount=['mount1', 'mount2'],
                        constraint=['constraint1', 'constraint2'],
                        container_label=['c_label1', 'c_label2'],
                        label=['label1', 'label2'],
                        env=['en1', 'env2'],
                        publish=['port1', 'port2'],
                        replicas=5,
                        network='network',
                        mode='mode',
                        restart_condition='restart_condition',
                        user='user',
                        stop_grace_period=20,
                    ),
                ),
                expected_args={
                    'executable': ['docker', 'service', 'create'],
                    'args': ['arg1', 'arg2'],
                    'network': 'network',
                    'mode': 'mode',
                    'constraint': ['constraint1', 'constraint2'],
                    'mount': ['mount1', 'mount2'],
                    'replicas': '5',
                    'publish': ['port1', 'port2'],
                    'label': ['label1', 'label2'],
                    'container-label': ['c_label1', 'c_label2'],
                    'command': '"command1 command2"',
                    'user': 'user',
                    'env': ['en1', 'env2'],
                    'stop-grace-period': '20',
                    'restart-condition': 'restart_condition',
                    'image': ['image:tag'],
                    'name': 'service',
                },
            ),
        )

        def test_command(command, *args, **kwargs):
            args = re.findall(
                '".+?(?<!\\\\)"|\'.+?(?<!\\\\)\'|[^\s]+',
                command,
            )
            options = docker_service_create_args_parser.parse_args(args)
            self.assertDictEqual(vars(options), data['expected_args'])
        image = docker.Image('image:tag')
        for case, data in cases.items():
            with self.subTest(case=case):
                service = docker.Service(**data['service_init_kwargs'])
                with mock.patch.object(
                    fabricio,
                    'run',
                    side_effect=test_command,
                ) as run:
                    service._create_service(image)
                    run.assert_called_once()

    @mock.patch.object(fabricio, 'run', side_effect=RuntimeError())
    def test_pull_image_raises_error_when_pull_failed_on_manager(self, run):
        service = docker.Service(name='service', image='image:tag')
        with mock.patch.object(docker.Service, 'is_manager', return_value=True):
            with self.assertRaises(RuntimeError):
                service.pull_image()
            run.assert_called_once_with('docker pull image:tag', quiet=False)
        run.reset_mock()
        with mock.patch.object(docker.Service, 'is_manager', return_value=False):
            service.pull_image()
            run.assert_called_once_with('docker pull image:tag', quiet=False)

    def test__update_sentinels(self):
        cases = dict(
            regular=dict(
                kwargs={},
                expected_calls=[
                    mock.call('docker inspect --type container service_current', abort_exception=mock.ANY),
                    mock.call('docker inspect --type image image:tag', abort_exception=mock.ANY),
                    mock.call('docker rm service_backup'),
                    mock.call('for volume in $(docker volume ls --filter "dangling=true" --quiet); do docker volume rm "$volume"; done'),
                    mock.call('docker rename service_current service_backup'),
                    mock.call('docker rm service_revert'),
                    mock.call('docker create --name service_current image:tag'),
                    mock.call(
                        'docker rmi $(docker images --no-trunc --quiet image)',
                        ignore_errors=True),
                ],
                side_effect=(
                    SucceededResult('[{"Image": "current_image_id"}]'),
                    SucceededResult('[{"Id": "new_image_id"}]'),
                    SucceededResult(),
                    SucceededResult(),
                    SucceededResult(),
                    SucceededResult(),
                    SucceededResult(),
                    SucceededResult(),
                ),
            ),
            revert_not_dound=dict(
                kwargs={},
                expected_calls=[
                    mock.call('docker inspect --type container service_current', abort_exception=mock.ANY),
                    mock.call('docker inspect --type image image:tag', abort_exception=mock.ANY),
                    mock.call('docker rm service_backup'),
                    mock.call('for volume in $(docker volume ls --filter "dangling=true" --quiet); do docker volume rm "$volume"; done'),
                    mock.call('docker rename service_current service_backup'),
                    mock.call('docker rm service_revert'),
                    mock.call('docker create --name service_current image:tag'),
                    mock.call(
                        'docker rmi $(docker images --no-trunc --quiet image)',
                        ignore_errors=True),
                ],
                side_effect=(
                    SucceededResult('[{"Image": "current_image_id"}]'),
                    SucceededResult('[{"Id": "new_image_id"}]'),
                    SucceededResult(),
                    SucceededResult(),
                    SucceededResult(),
                    RuntimeError(),
                    SucceededResult(),
                    SucceededResult(),
                ),
            ),
            image_not_changed=dict(
                kwargs={},
                expected_calls=[
                    mock.call('docker inspect --type container service_current', abort_exception=mock.ANY),
                    mock.call('docker inspect --type image image:tag', abort_exception=mock.ANY),
                ],
                side_effect=(
                    SucceededResult('[{"Image": "current_image_id"}]'),
                    SucceededResult('[{"Id": "current_image_id"}]'),
                ),
            ),
            backup_not_found=dict(
                kwargs={},
                expected_calls=[
                    mock.call('docker inspect --type container service_current', abort_exception=mock.ANY),
                    mock.call('docker inspect --type image image:tag', abort_exception=mock.ANY),
                    mock.call('docker rm service_backup'),
                    mock.call('docker rename service_current service_backup'),
                    mock.call('docker rm service_revert'),
                    mock.call('docker create --name service_current image:tag'),
                    mock.call(
                        'docker rmi $(docker images --no-trunc --quiet image)',
                        ignore_errors=True),
                ],
                side_effect=(
                    SucceededResult('[{"Image": "current_image_id"}]'),
                    SucceededResult('[{"Id": "new_image_id"}]'),
                    RuntimeError(),
                    SucceededResult(),
                    SucceededResult(),
                    SucceededResult(),
                    SucceededResult(),
                ),
            ),
            from_scratch=dict(
                kwargs={},
                expected_calls=[
                    mock.call('docker inspect --type container service_current', abort_exception=mock.ANY),
                    mock.call('docker rm service_revert'),
                    mock.call('docker create --name service_current image:tag'),
                    mock.call('docker rmi $(docker images --no-trunc --quiet image)', ignore_errors=True),
                ],
                side_effect=(
                    docker.ContainerNotFoundError(),
                    SucceededResult(),
                    SucceededResult(),
                    SucceededResult(),
                ),
            ),
            regular_with_tag_and_registry=dict(
                kwargs=dict(tag='foo', registry='registry'),
                expected_calls=[
                    mock.call('docker inspect --type container service_current', abort_exception=mock.ANY),
                    mock.call('docker inspect --type image registry/image:foo', abort_exception=mock.ANY),
                    mock.call('docker rm service_backup'),
                    mock.call('for volume in $(docker volume ls --filter "dangling=true" --quiet); do docker volume rm "$volume"; done'),
                    mock.call('docker rename service_current service_backup'),
                    mock.call('docker rm service_revert'),
                    mock.call('docker create --name service_current registry/image:foo'),
                    mock.call('docker rmi $(docker images --no-trunc --quiet registry/image)', ignore_errors=True),
                ],
                side_effect=(
                    SucceededResult('[{"Image": "current_image_id"}]'),
                    SucceededResult('[{"Id": "new_image_id"}]'),
                    SucceededResult(),
                    SucceededResult(),
                    SucceededResult(),
                    SucceededResult(),
                    SucceededResult(),
                    SucceededResult(),
                    SucceededResult(),
                ),
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                with mock.patch.object(fabricio, 'run', side_effect=data['side_effect']) as run:
                    service = docker.Service(name='service')
                    service._update_sentinels(docker.Image(name='image:tag', **data['kwargs']))
                    self.assertListEqual(run.mock_calls, data['expected_calls'])

    def test__revert_sentinels(self):
        cases = dict(
            regular=dict(
                expected_calls=[
                    mock.call('docker rename service_current service_revert'),
                    mock.call('docker rename service_revert service_backup'),
                ],
                side_effect=(
                    SucceededResult(),
                    RuntimeError(),
                ),
            ),
            revert_without_backup=dict(
                expected_calls=[
                    mock.call('docker rename service_current service_revert'),
                    mock.call('docker rename service_revert service_backup'),
                ],
                side_effect=(
                    SucceededResult(),
                    SucceededResult(),
                ),
            ),
            double_revert=dict(
                expected_calls=[
                    mock.call('docker rename service_current service_revert'),
                ],
                side_effect=(
                    RuntimeError(),
                ),
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                with mock.patch.object(fabricio, 'run', side_effect=data['side_effect']) as run:
                    service = docker.Service(name='service')
                    service._revert_sentinels()
                    self.assertListEqual(run.mock_calls, data['expected_calls'])
