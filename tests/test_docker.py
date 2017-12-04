# coding: utf-8
import json
import shlex

import mock
import unittest2 as unittest

from fabric import api as fab

import fabricio

from fabricio import docker
from fabricio.utils import OrderedDict
from fabricio.docker.container import Option, Attribute
from tests import SucceededResult, docker_run_args_parser, \
    docker_service_update_args_parser, \
    docker_entity_inspect_args_parser, docker_inspect_args_parser, \
    docker_service_create_args_parser, args_parser, Command


class TestContainer(docker.Container):

    image = docker.Image('image:tag')


class ContainerTestCase(unittest.TestCase):

    maxDiff = None

    def test_options(self):
        cases = dict(
            default=dict(
                kwargs=dict(),
                expected={},
            ),
            custom=dict(
                kwargs=dict(options=dict(foo='bar')),
                expected={
                    'foo': 'bar',
                },
            ),
            collision=dict(
                kwargs=dict(options=dict(execute='execute')),
                expected={
                    'execute': 'execute',
                },
            ),
            override=dict(
                kwargs=dict(options=dict(env='custom_env')),
                expected={
                    'env': 'custom_env',
                },
            ),
            complex=dict(
                kwargs=dict(options=dict(
                    env='custom_env',
                    user=lambda service: 'user',
                    foo='foo',
                    bar=lambda service: 'bar',
                )),
                expected={
                    'env': 'custom_env',
                    'user': 'user',
                    'foo': 'foo',
                    'bar': 'bar',
                },
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                container = TestContainer(**data['kwargs'])
                self.assertDictEqual(data['expected'], dict(container.options))

    def test_safe_options(self):
        class TestService(docker.BaseService):
            option = docker.Option()
            safe_option = docker.Option(safe=True, name='safe-option')
            safe_overridden = docker.Option(safe=True)
            another_safe_option = docker.Option(safe_name='another-safe-option')
        service = TestService(
            options=dict(option=42, safe_option=42, another_safe_option=42, safe_overridden=42),
            safe_options=dict(foo='bar', option='hello', dyn=lambda s: 'dyn', safe_overridden='override'),
        )
        self.assertDictEqual(
            {
                'safe-option': 42,
                'another-safe-option': 42,
                'foo': 'bar',
                'option': 'hello',
                'dyn': 'dyn',
                'safe_overridden': 'override',
            },
            dict(service.safe_options),
        )

    def test_options_inheritance(self):

        class Parent(docker.Container):
            user = 'user'  # overridden property (simple)

            @property  # overridden property (dynamic)
            def publish(self):
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

        self.assertNotIn('null', container.options)
        container.null = 'value'
        self.assertIn('null', container.options)
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
                        'restart': 'override',
                    },
                ),
                class_kwargs=dict(
                    image=docker.Image('image:tag'),
                    command='command',
                    user='user',
                    publish=['80:80', '443:443'],
                    env=['FOO=foo', 'BAR=bar'],
                    volume=['/tmp:/tmp', '/root:/root:ro'],
                    link=['db:db'],
                    add_host=['host:192.168.0.1'],
                    network='network',
                    restart='restart_policy',
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
            options = docker_run_args_parser.parse_args(shlex.split(command))
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
                    options={},
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
                        'user': 'fabricio',
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
                    command=None,
                    options={},
                ),
            ),
            override_command=dict(
                init_kwargs=dict(name='name'),
                fork_kwargs=dict(command='command'),
                expected_properties=dict(
                    name='name',
                    command='command',
                    options={},
                ),
            ),
            override_image_str=dict(
                init_kwargs=dict(name='name'),
                fork_kwargs=dict(image='image'),
                expected_properties=dict(
                    name='name',
                    command=None,
                    options={},
                ),
                expected_image='image:latest',
            ),
            override_image_instance=dict(
                init_kwargs=dict(name='name'),
                fork_kwargs=dict(image=docker.Image('image')),
                expected_properties=dict(
                    name='name',
                    command=None,
                    options={},
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
                        'user': 'user',
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
                        'foo': 'bar',
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
                        'user': 'user',
                        'foo': 'bar',
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
                        'user': 'fabricio',
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
                    command='fab',
                ),
                fork_kwargs=dict(image='image'),
                expected_properties=dict(
                    name='name',
                    command='fab',
                    options={
                        'user': 'fabricio',
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
                    command='fab',
                ),
                fork_kwargs=dict(image=docker.Image('image')),
                expected_properties=dict(
                    name='name',
                    command='fab',
                    options={
                        'user': 'fabricio',
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
                    command='fab',
                ),
                fork_kwargs=dict(options=dict(user='user')),
                expected_properties=dict(
                    name='name',
                    command='fab',
                    options={
                        'user': 'user',
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
                    command='fab',
                ),
                fork_kwargs=dict(options=dict(foo='bar')),
                expected_properties=dict(
                    name='name',
                    command='fab',
                    options={
                        'user': 'fabricio',
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
                        'user': 'user',
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
                    mock.call(Command(docker_run_args_parser, {
                        'executable': ['docker'],
                        'run_or_create': ['run'],
                        'detach': True,
                        'name': 'name',
                        'image': 'image:tag',
                        'command': [],
                    }), quiet=True),
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
                    mock.call(Command(docker_run_args_parser, {
                        'executable': ['docker'],
                        'run_or_create': ['run'],
                        'detach': True,
                        'name': 'name',
                        'image': 'image:tag',
                        'command': [],
                    }), quiet=True),
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
                    mock.call(Command(docker_run_args_parser, {
                        'executable': ['docker'],
                        'run_or_create': ['run'],
                        'detach': True,
                        'name': 'name',
                        'image': 'image:foo',
                        'command': [],
                    }), quiet=True),
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
                    mock.call(Command(docker_run_args_parser, {
                        'executable': ['docker'],
                        'run_or_create': ['run'],
                        'detach': True,
                        'name': 'name',
                        'image': 'registry/image:tag',
                        'command': [],
                    }), quiet=True),
                ],
                update_kwargs=dict(registry='registry'),
                excpected_result=True,
            ),
            regular_complex=dict(  # TODO add more options
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
                    mock.call('docker inspect --type image registry/account/image:foo', abort_exception=docker.ImageNotFoundError),
                    mock.call('docker inspect --type container name_backup', abort_exception=docker.ContainerNotFoundError),
                    mock.call('docker rm name_backup'),
                    mock.call('for volume in $(docker volume ls --filter "dangling=true" --quiet); do docker volume rm "$volume"; done'),
                    mock.call('docker rmi old_image_id', ignore_errors=True),
                    mock.call('docker rename name name_backup'),
                    mock.call('docker stop --time 10 name_backup'),
                    mock.call(Command(docker_run_args_parser, {
                        'executable': ['docker'],
                        'run_or_create': ['run'],
                        'detach': True,
                        'name': 'name',
                        'image': 'registry/account/image:foo',
                        'command': [],
                    }), quiet=True),
                ],
                update_kwargs=dict(tag='foo', registry='registry', account='account'),
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
                    mock.call(Command(docker_run_args_parser, {
                        'executable': ['docker'],
                        'run_or_create': ['run'],
                        'detach': True,
                        'name': 'name',
                        'image': 'image:tag',
                        'command': [],
                    }), quiet=True),
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
                    mock.call(Command(docker_run_args_parser, {
                        'executable': ['docker'],
                        'run_or_create': ['run'],
                        'detach': True,
                        'name': 'name',
                        'image': 'image:tag',
                        'command': [],
                    }), quiet=True),
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
                    mock.call(Command(docker_run_args_parser, {
                        'executable': ['docker'],
                        'run_or_create': ['run'],
                        'detach': True,
                        'name': 'name',
                        'image': 'image:tag',
                        'command': [],
                    }), quiet=True),
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
                expected_str='registry/name:tag',
            ),
            tag=dict(
                image_init_kwargs=dict(name='name', tag='tag', registry='registry'),
                item='custom_tag',
                expected_str='registry/name:custom_tag',
            ),
            digest_none=dict(
                image_init_kwargs=dict(name='name@digest'),
                item=None,
                expected_str='name@digest',
            ),
            digest_tag=dict(
                image_init_kwargs=dict(name='name@digest'),
                item='custom_tag',
                expected_str='name:custom_tag',
            ),
            override_name=dict(
                image_init_kwargs=dict(name='default', tag='default', registry='default'),
                item='name:tag',
                expected_str='default/name:tag',
            ),
            override_name_from_empty=dict(
                image_init_kwargs=dict(),
                item='name:tag',
                expected_str='name:tag',
            ),
            override_name_and_digest=dict(
                image_init_kwargs=dict(name='default', tag='default', registry='default'),
                item='name@digest',
                expected_str='default/name@digest',
            ),
            override_name_and_digest_from_empty=dict(
                image_init_kwargs=dict(),
                item='name@digest',
                expected_str='name@digest',
            ),
            override_name_and_account=dict(
                image_init_kwargs=dict(name='default', tag='default', registry='default'),
                item='account/name:tag',
                expected_str='default/account/name:tag',
            ),
            override_name_and_account_from_empty=dict(
                image_init_kwargs=dict(),
                item='account/name:tag',
                expected_str='account/name:tag',
            ),
            override_name_and_registry=dict(
                image_init_kwargs=dict(name='default', tag='default', registry='default'),
                item='localhost:5000/name:tag',
                expected_str='localhost:5000/name:tag',
            ),
            override_name_and_registry_from_empty=dict(
                image_init_kwargs=dict(),
                item='localhost:5000/name:tag',
                expected_str='localhost:5000/name:tag',
            ),
            override_digest_and_registry=dict(
                image_init_kwargs=dict(name='default', tag='default', registry='default'),
                item='localhost:5000/name@digest',
                expected_str='localhost:5000/name@digest',
            ),
            override_digest_and_registry_from_empty=dict(
                image_init_kwargs=dict(),
                item='localhost:5000/name@digest',
                expected_str='localhost:5000/name@digest',
            ),
            override_name_and_registry_and_account=dict(
                image_init_kwargs=dict(name='default', tag='default', registry='default'),
                item='localhost:5000/account/name:tag',
                expected_str='localhost:5000/account/name:tag',
            ),
            override_name_and_registry_and_account_from_empty=dict(
                image_init_kwargs=dict(),
                item='localhost:5000/account/name:tag',
                expected_str='localhost:5000/account/name:tag',
            ),
            override_digest_and_registry_and_account=dict(
                image_init_kwargs=dict(name='default', tag='default', registry='default'),
                item='localhost:5000/account/name@digest',
                expected_str='localhost:5000/account/name@digest',
            ),
            override_digest_and_registry_and_account_from_empty=dict(
                image_init_kwargs=dict(),
                item='localhost:5000/account/name@digest',
                expected_str='localhost:5000/account/name@digest',
            ),
            override_name_and_registry_skip_tag=dict(
                image_init_kwargs=dict(name='default', tag='default', registry='default'),
                item='localhost:5000/name',
                expected_str='localhost:5000/name:latest',
            ),
            override_name_and_registry_skip_tag_from_empty=dict(
                image_init_kwargs=dict(),
                item='localhost:5000/name',
                expected_str='localhost:5000/name:latest',
            ),
            override_name_and_registry_skip_tag_from_digest=dict(
                image_init_kwargs=dict(name='name@digest'),
                item='localhost:5000/name',
                expected_str='localhost:5000/name:latest',
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                image = docker.Image(**data['image_init_kwargs'])
                new_image = image[data['item']]
                self.assertEqual(data['expected_str'], str(new_image))

    def test_getitem_slice(self):
        cases = dict(
            none=dict(
                image_init_kwargs=dict(name='name', tag='tag', registry='registry'),
                start=None,
                stop=None,
                step=None,
                expected_str='registry/name:tag',
            ),
            tag=dict(
                image_init_kwargs=dict(name='name', tag='tag', registry='registry'),
                start=None,
                stop='custom_tag',
                step=None,
                expected_str='registry/name:custom_tag',
            ),
            registry=dict(
                image_init_kwargs=dict(name='name', tag='tag', registry='registry'),
                start='registry:5000',
                stop=None,
                step=None,
                expected_str='registry:5000/name:tag',
            ),
            account=dict(
                image_init_kwargs=dict(name='name', tag='tag', registry='registry'),
                start=None,
                stop=None,
                step='account',
                expected_str='registry/account/name:tag',
            ),
            account_replace=dict(
                image_init_kwargs=dict(name='original/name', tag='tag', registry='registry'),
                start=None,
                stop=None,
                step='account',
                expected_str='registry/account/name:tag',
            ),
            complex=dict(
                image_init_kwargs=dict(name='name', tag='tag', registry='registry'),
                start='127.0.0.1:5000',
                stop='custom_tag',
                step='account',
                expected_str='127.0.0.1:5000/account/name:custom_tag',
            ),
            override_name=dict(
                image_init_kwargs=dict(name='default', tag='default', registry='default'),
                start='127.0.0.1:5000',
                stop='name:tag',
                step='account',
                expected_str='127.0.0.1:5000/name:tag',
            ),
            override_name_and_account=dict(
                image_init_kwargs=dict(name='default', tag='default', registry='default'),
                start='127.0.0.1:5000',
                stop='acc/name:tag',
                step='account',
                expected_str='127.0.0.1:5000/acc/name:tag',
            ),
            override_name_and_registry=dict(
                image_init_kwargs=dict(name='default', tag='default', registry='default'),
                start='127.0.0.1:5000',
                stop='localhost:5000/name:tag',
                step='account',
                expected_str='localhost:5000/name:tag',
            ),
            override_name_and_registry_skip_tag=dict(
                image_init_kwargs=dict(name='default', tag='default', registry='default'),
                start='127.0.0.1:5000',
                stop='localhost:5000/name',
                step='account',
                expected_str='localhost:5000/name:latest',
            ),
            override_name_and_registry_skip_tag_digest=dict(
                image_init_kwargs=dict(name='name@digest'),
                start='127.0.0.1:5000',
                stop='localhost:5000/name',
                step='account',
                expected_str='localhost:5000/name:latest',
            ),
            digest_none=dict(
                image_init_kwargs=dict(name='name@digest'),
                start=None,
                stop=None,
                step=None,
                expected_str='name@digest',
            ),
            digest_tag=dict(
                image_init_kwargs=dict(name='name@digest'),
                start=None,
                stop='custom_tag',
                step=None,
                expected_str='name:custom_tag',
            ),
            digest_registry=dict(
                image_init_kwargs=dict(name='name@digest'),
                start='registry:5000',
                stop=None,
                step=None,
                expected_str='registry:5000/name@digest',
            ),
            digest_complex=dict(
                image_init_kwargs=dict(name='name@digest'),
                start='127.0.0.1:5000',
                stop='custom_tag',
                step='account',
                expected_str='127.0.0.1:5000/account/name:custom_tag',
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                image = docker.Image(**data['image_init_kwargs'])
                new_image = image[data['start']:data['stop']:data['step']]
                self.assertEqual(data['expected_str'], str(new_image))

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
            options = docker_run_args_parser.parse_args(shlex.split(command))
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
                    SucceededResult('  Is Manager: false'),  # manager status
                ),
                args_parsers=[
                    args_parser,
                ],
                expected_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                ],
                expected_result=False,
                all_hosts=['host1', 'host2'],
            ),
            worker_without_manager=dict(
                init_kwargs=dict(
                    name='service',
                    image='image:tag',
                ),
                update_kwargs=dict(),
                side_effect=(
                    SucceededResult('  Is Manager: false'),  # manager status
                ),
                args_parsers=[
                    args_parser,
                ],
                expected_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                ],
                expected_result=docker.ServiceError,
            ),
            is_manager_fails=dict(
                init_kwargs=dict(
                    name='service',
                    image='image:tag',
                ),
                update_kwargs=dict(),
                side_effect=(
                    RuntimeError(),  # manager status
                ),
                args_parsers=[
                    args_parser,
                ],
                expected_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                ],
                expected_result=docker.ServiceError,
            ),
            is_manager_fails_multiple_hosts=dict(
                init_kwargs=dict(
                    name='service',
                    image='image:tag',
                ),
                update_kwargs=dict(),
                side_effect=(
                    RuntimeError(),  # manager status
                ),
                args_parsers=[
                    args_parser,
                ],
                expected_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                ],
                expected_result=False,
                all_hosts=['host1', 'host2'],
            ),
            no_changes=dict(
                init_kwargs=dict(
                    name='service',
                    image='image:tag',
                    options=dict(
                        secret='secret',
                    ),
                ),
                update_kwargs=dict(),
                side_effect=(
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult('[{"RepoDigests": ["digest"]}]'),  # image info
                    SucceededResult(json.dumps([{"Spec": {
                        "Labels": {
                            "fabricio.service.options": "b1a9a7833e4ca8b5122b9db71844ed33",
                        },
                        "TaskTemplate": {
                            "ContainerSpec": {
                                "Secrets": [
                                    {
                                        "File": {
                                            "Name": "secret",
                                        },
                                        "SecretID": "secret",
                                        "SecretName": "secret",
                                    },
                                ],
                            },
                        },
                    }}])),  # service info
                ),
                args_parsers=[
                    args_parser,
                    docker_inspect_args_parser,
                    docker_entity_inspect_args_parser,
                ],
                expected_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'image:tag',
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
                    options=dict(
                        secret='secret',
                    ),
                ),
                update_kwargs=dict(force=True),
                side_effect=(
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult('[{"RepoDigests": ["digest"]}]'),  # image info
                    SucceededResult(json.dumps([{"Spec": {
                        "Labels": {
                            "fabricio.service.options": "b1a9a7833e4ca8b5122b9db71844ed33",
                        },
                        "TaskTemplate": {
                            "ContainerSpec": {
                                "Secrets": [
                                    {
                                        "File": {
                                            "Name": "secret",
                                        },
                                        "SecretID": "secret",
                                        "SecretName": "secret",
                                    },
                                ],
                            },
                        },
                    }}])),  # service info
                    SucceededResult(),  # service update
                ),
                args_parsers=[
                    args_parser,
                    docker_inspect_args_parser,
                    docker_entity_inspect_args_parser,
                    docker_service_update_args_parser,
                ],
                expected_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'image:tag',
                    },
                    {
                        'executable': ['docker', 'service', 'inspect'],
                        'service': 'service',
                    },
                    {
                        'executable': ['docker', 'service', 'update'],
                        'image': 'digest',
                        'service': 'service',
                        'args': '',
                        'label-add': [
                            'fabricio.service.options=b1a9a7833e4ca8b5122b9db71844ed33',
                        ],
                        'secret-add': ['secret'],
                        'secret-rm': ['secret'],
                    },
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
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult('[{"RepoDigests": ["digest"]}]'),  # image info
                    SucceededResult('[{"Spec": {}}]'),  # service info
                    SucceededResult(),  # service update
                ),
                args_parsers=[
                    args_parser,
                    docker_inspect_args_parser,
                    docker_entity_inspect_args_parser,
                    docker_service_update_args_parser,
                ],
                expected_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'image:tag',
                    },
                    {
                        'executable': ['docker', 'service', 'inspect'],
                        'service': 'service',
                    },
                    {
                        'executable': ['docker', 'service', 'update'],
                        'image': 'digest',
                        'service': 'service',
                        'args': '',
                        'label-add': [
                            'fabricio.service.options=5ed89ef87bc69f63506f92169933231d',
                        ],
                    },
                ],
                expected_result=True,
            ),
            updated_with_custom_labels_and_args=dict(
                init_kwargs=dict(
                    name='service',
                    image='image:tag',
                    options=dict(label=['label1=label1', 'label2=label2']),
                    args='foo bar',
                ),
                update_kwargs=dict(),
                side_effect=(
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult('[{"RepoDigests": ["digest"]}]'),  # image info
                    SucceededResult('[{"Spec": {}}]'),  # service info
                    SucceededResult(),  # service update
                ),
                args_parsers=[
                    args_parser,
                    docker_inspect_args_parser,
                    docker_entity_inspect_args_parser,
                    docker_service_update_args_parser,
                ],
                expected_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'image:tag',
                    },
                    {
                        'executable': ['docker', 'service', 'inspect'],
                        'service': 'service',
                    },
                    {
                        'executable': ['docker', 'service', 'update'],
                        'image': 'digest',
                        'service': 'service',
                        'label-add': [
                            'label1=label1',
                            'label2=label2',
                            'fabricio.service.options=0a4991404e926ea32115d3ad6debf1c7',
                        ],
                        'args': 'foo bar',
                    },
                ],
                expected_result=True,
            ),
            updated_with_custom_tag_and_registry_and_account=dict(
                init_kwargs=dict(
                    name='service',
                    image='image:tag',
                ),
                update_kwargs=dict(tag='custom_tag', registry='registry', account='account'),
                side_effect=(
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult('[{"RepoDigests": ["digest"]}]'),  # image info
                    SucceededResult('[{"Spec": {}}]'),  # service info
                    SucceededResult(),  # service update
                ),
                args_parsers=[
                    args_parser,
                    docker_inspect_args_parser,
                    docker_entity_inspect_args_parser,
                    docker_service_update_args_parser,
                ],
                expected_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'registry/account/image:custom_tag',
                    },
                    {
                        'executable': ['docker', 'service', 'inspect'],
                        'service': 'service',
                    },
                    {
                        'executable': ['docker', 'service', 'update'],
                        'image': 'digest',
                        'service': 'service',
                        'args': '',
                        'label-add': [
                            'fabricio.service.options=5ed89ef87bc69f63506f92169933231d',
                        ],
                    },
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
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult('[{"RepoDigests": ["digest"]}]'),  # image info
                    docker.ServiceNotFoundError(),  # service info
                    SucceededResult(),  # service create
                ),
                args_parsers=[
                    args_parser,
                    docker_inspect_args_parser,
                    docker_entity_inspect_args_parser,
                    docker_service_create_args_parser,
                ],
                expected_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'image:tag',
                    },
                    {
                        'executable': ['docker', 'service', 'inspect'],
                        'service': 'service',
                    },
                    {
                        'executable': ['docker', 'service', 'create'],
                        'image': ['digest'],
                        'name': 'service',
                        'args': [],
                        'label': [
                            'fabricio.service.options=5ed89ef87bc69f63506f92169933231d',
                        ],
                    },
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
                    SucceededResult('  Is Manager: true'),  # manager status
                    SucceededResult('[{"RepoDigests": ["digest"]}]'),  # image info
                    docker.ServiceNotFoundError(),  # service info
                    SucceededResult(),  # service create
                ),
                args_parsers=[
                    args_parser,
                    docker_inspect_args_parser,
                    docker_entity_inspect_args_parser,
                    docker_service_create_args_parser,
                ],
                expected_args=[
                    {
                        'args': ['docker', 'info', '2>&1', '|', 'grep', 'Is Manager:'],
                    },
                    {
                        'executable': ['docker', 'inspect'],
                        'type': 'image',
                        'image_or_container': 'registry/image:custom_tag',
                    },
                    {
                        'executable': ['docker', 'service', 'inspect'],
                        'service': 'service',
                    },
                    {
                        'executable': ['docker', 'service', 'create'],
                        'image': ['digest'],
                        'name': 'service',
                        'args': [],
                        'label': [
                            'fabricio.service.options=5ed89ef87bc69f63506f92169933231d',
                        ],
                    },
                ],
                expected_result=True,
            ),
        )

        def test_command(command, **kwargs):
            args = shlex.split(command)
            parser = next(args_parsers)
            options = vars(parser.parse_args(args))
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
                with mock.patch.dict(fab.env, dict(all_hosts=data.get('all_hosts', ['host']))):
                    with mock.patch.object(fab, 'run', side_effect=test_command) as run:
                        run.__name__ = 'mocked_run'
                        service = docker.Service(**data['init_kwargs'])
                        expected_result = data['expected_result']
                        try:
                            result = service.update(**data['update_kwargs'])
                            self.assertEqual(result, expected_result)
                        except AssertionError:
                            raise
                        except Exception as exception:
                            try:
                                is_exception_expected = issubclass(expected_result, Exception)
                            except TypeError:
                                is_exception_expected = False
                            if not is_exception_expected:
                                raise
                            self.assertIsInstance(exception, expected_result)
                        self.assertEqual(run.call_count, len(data['expected_args']))

    @mock.patch.dict(fab.env, dict(all_hosts=['host1', 'host2']))
    def test_is_manager_returns_false_if_pull_error(self, *args):
        with mock.patch.object(fabricio, 'run') as run:
            service = docker.Service(name='service')
            service.pull_errors[fab.env.host] = True
            self.assertFalse(service.is_manager())
            run.assert_not_called()

    @mock.patch.dict(fab.env, dict(all_hosts=['host']))
    def test_is_manager_raises_error_if_all_pulls_failed(self, *args):
        with mock.patch.object(fabricio, 'run') as run:
            service = docker.Service(name='service')
            service.pull_errors[fab.env.host] = True
            with self.assertRaises(docker.ServiceError):
                service.is_manager()
            run.assert_not_called()

    def test_pull_image(self):
        cases = dict(
            no_errors=dict(
                side_effect=(SucceededResult(), ),
                expected_pull_error=None,
            ),
            error=dict(
                side_effect=(RuntimeError(), ),
                expected_pull_error=True,
            ),
        )
        for case, test_data in cases.items():
            with self.subTest(case=case):
                service = docker.Service(name='service', image='image')
                with mock.patch.object(
                    fabricio,
                    'run',
                    side_effect=test_data['side_effect']
                ):
                    service.pull_image()
                    self.assertEqual(
                        test_data['expected_pull_error'],
                        service.pull_errors.get(fab.env.host),
                    )

    def test_update_options(self):
        cases = dict(
            default=dict(
                init_kwargs=dict(name='name'),
                service_info=dict(),
                expected={
                    'args': '',
                },
            ),
            empty_args=dict(
                init_kwargs=dict(name='name', command='', args=''),
                service_info=dict(),
                expected={
                    'args': '',
                },
            ),
            command=dict(
                init_kwargs=dict(name='name', command='command'),
                service_info=dict(),
                expected={
                    'args': 'command',
                },
            ),
            args_and_command=dict(
                init_kwargs=dict(name='name', command='command', args='arg1 arg2'),
                service_info=dict(),
                expected={
                    'args': 'command arg1 arg2',
                },
            ),
            new_option_value=dict(
                init_kwargs=dict(
                    name='service',
                    args='arg1 "arg2" \'arg3\'',
                    options=dict(
                        publish='80:80',
                        mount='type=volume,destination=/path',
                        label='label=value',
                        env='FOO=bar',
                        constraint='node.role == manager',
                        container_label='label=value',
                        network='network',
                        restart_condition='on-failure',
                        stop_grace_period=20,
                        custom_option='custom_value',
                        replicas=3,
                        user='user',
                        host='foo:127.0.0.2',
                        secret='source=secret,target=/secret2',
                        config='config',
                        group='42',
                        placement_pref='spread=node.role',
                        dns='8.8.8.8',
                        dns_option='option',
                        dns_search='domain',
                    ),
                    mode='mode',
                ),
                service_info=dict(),
                expected={
                    'env-add': ['FOO=bar'],
                    'constraint-add': ['node.role == manager'],
                    'publish-add': ['80:80'],
                    'label-add': ['label=value'],
                    'args': 'arg1 "arg2" \'arg3\'',
                    'user': 'user',
                    'replicas': 3,
                    'mount-add': ['type=volume,destination=/path'],
                    'network-add': ['network'],
                    'stop-grace-period': 20,
                    'restart-condition': 'on-failure',
                    'custom_option': 'custom_value',
                    'container-label-add': ['label=value'],
                    'host-add': ['foo:127.0.0.2'],
                    'secret-add': ['source=secret,target=/secret2'],
                    'config-add': ['config'],
                    'group-add': ['42'],
                    'placement-pref-add': ['spread=node.role'],
                    'dns-add': ['8.8.8.8'],
                    'dns-option-add': ['option'],
                    'dns-search-add': ['domain'],
                },
            ),
            new_option_value_with_custom_name=dict(
                init_kwargs=dict(
                    name='service',
                    args='arg1 "arg2" \'arg3\'',
                    options={
                        'container-label': 'label=value',
                        'restart-condition': 'on-failure',
                        'stop-grace-period': 20,
                        'placement-pref': 'spread=node.role',
                        'dns-option': 'option',
                        'dns-search': 'domain',
                    },
                    mode='mode',
                ),
                service_info=dict(),
                expected={
                    'args': 'arg1 "arg2" \'arg3\'',
                    'stop-grace-period': 20,
                    'restart-condition': 'on-failure',
                    'container-label-add': ['label=value'],
                    'placement-pref-add': ['spread=node.role'],
                    'dns-option-add': ['option'],
                    'dns-search-add': ['domain'],
                },
            ),
            changed_option_value=dict(
                init_kwargs=dict(
                    name='service',
                    args='arg1 "arg2" \'arg3\'',
                    options=dict(
                        publish=['8000:80', 81, '82'],
                        mount=[
                            'type=new_type,destination=/path',
                            'type=new_type,dst=/path2',
                            'type=new_type,target=/path3',
                        ],
                        label='label=new_value',
                        env='FOO=baz',
                        constraint='node.role == worker',
                        container_label='label=container_new_value',
                        network='new_network',
                        restart_condition='any',
                        stop_grace_period=20,
                        custom_option='new_custom_value',
                        replicas=2,
                        user='new_user',
                        host='foo:127.0.0.2',
                        secret='source=secret,target=/secret2',
                        config='source=config,target=/config2',
                        group='new',
                        placement_pref='spread=new',
                        dns='new',
                        dns_option='new',
                        dns_search='new',
                    ),
                    mode='mode',
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
                                    dict(
                                        Type='bind',
                                        Source='/source2',
                                        Target='/path2',
                                    ),
                                    dict(
                                        Type='volume',
                                        Source='/source3',
                                        Target='/path3',
                                    ),
                                ],
                                Hosts=[
                                    "127.0.0.1 foo",
                                ],
                                Secrets=[
                                    dict(
                                        File=dict(
                                            Name='/secret1',
                                        ),
                                        SecretID='secret',
                                        SecretName='secret',
                                    ),
                                ],
                                Configs=[
                                    dict(
                                        File=dict(
                                            Name='/config1',
                                        ),
                                        ConfigID='config',
                                        ConfigName='config',
                                    ),
                                ],
                                Groups=[
                                    'old',
                                ],
                                DNSConfig=dict(
                                    Nameservers=[
                                        'old',
                                    ],
                                    Options=[
                                        'old',
                                    ],
                                    Search=[
                                        'old',
                                    ],
                                ),
                            ),
                            Placement=dict(
                                Constraints=[
                                    'node.role == manager',
                                ],
                                Preferences=[
                                    dict(
                                        Spread=dict(
                                            SpreadDescriptor='old',
                                        ),
                                    ),
                                ],
                            ),
                            Networks=[
                                {
                                    'Target': 'old_network_id',
                                },
                            ],
                        ),
                        EndpointSpec=dict(
                            Ports=[
                                dict(
                                    TargetPort=80,
                                    Protocol='tcp',
                                    PublishedPort=8080,
                                ),
                                dict(
                                    TargetPort=81,
                                    Protocol='tcp',
                                    PublishedPort=8081,
                                ),
                                dict(
                                    TargetPort=82,
                                    Protocol='udp',
                                    PublishedPort=8082,
                                ),
                            ],
                        ),
                    ),
                ),
                expected={
                    'env-add': ['FOO=baz'],
                    'constraint-add': ['node.role == worker'],
                    'label-add': ['label=new_value'],
                    'args': 'arg1 "arg2" \'arg3\'',
                    'user': 'new_user',
                    'replicas': 2,
                    'mount-add': [
                        'type=new_type,destination=/path',
                        'type=new_type,dst=/path2',
                        'type=new_type,target=/path3',
                    ],
                    'network-add': ['new_network'],
                    'network-rm': ['old_network_id'],
                    'publish-add': ['8000:80', 81, '82'],
                    'constraint-rm': ['node.role == manager'],
                    'stop-grace-period': 20,
                    'restart-condition': 'any',
                    'custom_option': 'new_custom_value',
                    'container-label-add': ['label=container_new_value'],
                    'host-add': ['foo:127.0.0.2'],
                    'host-rm': ['foo:127.0.0.1'],
                    'secret-add': ['source=secret,target=/secret2'],
                    'secret-rm': ['secret'],
                    'config-add': ['source=config,target=/config2'],
                    'config-rm': ['config'],
                    'group-add': ['new'],
                    'group-rm': ['old'],
                    'dns-add': ['new'],
                    'dns-rm': ['old'],
                    'dns-option-add': ['new'],
                    'dns-option-rm': ['old'],
                    'dns-search-add': ['new'],
                    'dns-search-rm': ['old'],
                    'placement-pref-add': ['spread=new'],
                    'placement-pref-rm': ['spread=old'],
                },
            ),
            changed_option_value_with_custom_name=dict(
                init_kwargs=dict(
                    name='service',
                    args='arg1 "arg2" \'arg3\'',
                    options={
                        'container-label': 'label=container_new_value',
                        'restart-condition': 'any',
                        'stop-grace-period': 20,
                        'placement-pref': 'spread=new',
                        'dns-option': 'new',
                        'dns-search': 'new',
                    },
                    mode='mode',
                ),
                service_info=dict(
                    Spec=dict(
                        TaskTemplate=dict(
                            ContainerSpec=dict(
                                Labels=dict(
                                    label='value',
                                ),
                                DNSConfig=dict(
                                    Options=[
                                        'old',
                                    ],
                                    Search=[
                                        'old',
                                    ],
                                ),
                            ),
                            Placement=dict(
                                Preferences=[
                                    dict(
                                        Spread=dict(
                                            SpreadDescriptor='old',
                                        ),
                                    ),
                                ],
                            ),
                        ),
                    ),
                ),
                expected={
                    'args': 'arg1 "arg2" \'arg3\'',
                    'stop-grace-period': 20,
                    'restart-condition': 'any',
                    'container-label-add': ['label=container_new_value'],
                    'dns-option-add': ['new'],
                    'dns-option-rm': ['old'],
                    'dns-search-add': ['new'],
                    'dns-search-rm': ['old'],
                    'placement-pref-add': ['spread=new'],
                    'placement-pref-rm': ['spread=old'],
                },
            ),
            no_changes=dict(
                init_kwargs=dict(
                    name='service',
                    args='arg1 "arg2" \'arg3\'',
                    options=dict(
                        publish='8080:80',
                        mount='type=type,destination=/path',
                        label='label=value',
                        env='FOO=bar',
                        constraint='node.role == manager',
                        container_label='label=value',
                        network='network',
                        restart_condition='any',
                        stop_grace_period=20,
                        custom_option='new_custom_value',
                        replicas=2,
                        user='user',
                        host='foo:127.0.0.1',
                        secret='source=secret,target=/secret',
                        config='config',
                        group='old',
                        placement_pref='spread=old',
                        dns='old',
                        dns_option='old',
                        dns_search='old',
                    ),
                    mode='mode',
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
                                ],
                                Hosts=[
                                    "127.0.0.1 foo",
                                ],
                                Secrets=[
                                    dict(
                                        File=dict(
                                            Name='/secret',
                                        ),
                                        SecretID='secret',
                                        SecretName='secret',
                                    ),
                                ],
                                Configs=[
                                    dict(
                                        File=dict(
                                            Name='/config',
                                        ),
                                        ConfigID='config',
                                        ConfigName='config',
                                    ),
                                ],
                                Groups=[
                                    'old',
                                ],
                                DNSConfig=dict(
                                    Nameservers=[
                                        'old',
                                    ],
                                    Options=[
                                        'old',
                                    ],
                                    Search=[
                                        'old',
                                    ],
                                ),
                            ),
                            Placement=dict(
                                Constraints=[
                                    'node.role == manager',
                                ],
                                Preferences=[
                                    dict(
                                        Spread=dict(
                                            SpreadDescriptor='old',
                                        ),
                                    ),
                                ],
                            ),
                            Networks=[
                                {
                                    'Target': 'network_id',
                                },
                            ],
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
                    'container-label-add': ['label=value'],
                    'env-add': ['FOO=bar'],
                    'label-add': ['label=value'],
                    'publish-add': ['8080:80'],
                    'args': 'arg1 "arg2" \'arg3\'',
                    'user': 'user',
                    'replicas': 2,
                    'mount-add': ['type=type,destination=/path'],
                    'network-add': ['network'],
                    'network-rm': ['network_id'],
                    'stop-grace-period': 20,
                    'restart-condition': 'any',
                    'custom_option': 'new_custom_value',
                    'secret-add': ['source=secret,target=/secret'],
                    'secret-rm': ['secret'],
                    'config-add': ['config'],
                    'config-rm': ['config'],
                    'placement-pref-add': ['spread=old'],
                    'placement-pref-rm': ['spread=old'],
                },
            ),
            no_changes_with_custom_name=dict(
                init_kwargs=dict(
                    name='service',
                    args='arg1 "arg2" \'arg3\'',
                    options={
                        'container-label': 'label=value',
                        'restart-condition': 'any',
                        'stop-grace-period': 20,
                        'placement-pref': 'spread=old',
                        'dns-option': 'old',
                        'dns-search': 'old',
                    },
                    mode='mode',
                ),
                service_info=dict(
                    Spec=dict(
                        TaskTemplate=dict(
                            ContainerSpec=dict(
                                Labels=dict(
                                    label='value',
                                ),
                                DNSConfig=dict(
                                    Options=[
                                        'old',
                                    ],
                                    Search=[
                                        'old',
                                    ],
                                ),
                            ),
                            Placement=dict(
                                Preferences=[
                                    dict(
                                        Spread=dict(
                                            SpreadDescriptor='old',
                                        ),
                                    ),
                                ],
                            ),
                        ),
                    ),
                ),
                expected={
                    'container-label-add': ['label=value'],
                    'args': 'arg1 "arg2" \'arg3\'',
                    'stop-grace-period': 20,
                    'restart-condition': 'any',
                    'placement-pref-add': ['spread=old'],
                    'placement-pref-rm': ['spread=old'],
                },
            ),
            no_changes_callable=dict(
                init_kwargs=dict(
                    name='service',
                    args='arg1 "arg2" \'arg3\'',
                    options=dict(
                        publish=lambda service: '8080:80',
                        mount=lambda service: 'type=type,destination=/path',
                        label=lambda service: 'label=value',
                        env=lambda service: 'FOO=bar',
                        constraint=lambda service: 'node.role == manager',
                        container_label=lambda service: 'label=value',
                        network=lambda service: 'network',
                        restart_condition=lambda service: 'any',
                        stop_grace_period=lambda service: 20,
                        custom_option=lambda service: 'new_custom_value',
                        replicas=lambda service: 2,
                        user=lambda service: 'user',
                        host=lambda service: 'foo:127.0.0.1',
                        secret=lambda service: 'source=secret,target=/secret',
                        config=lambda service: 'config',
                        group=lambda service: 'old',
                        placement_pref=lambda service: 'spread=old',
                        dns=lambda service: 'old',
                        dns_option=lambda service: 'old',
                        dns_search=lambda service: 'old',
                    ),
                    mode='mode',
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
                                ],
                                Hosts=[
                                    "127.0.0.1 foo",
                                ],
                                Secrets=[
                                    dict(
                                        File=dict(
                                            Name='/secret',
                                        ),
                                        SecretID='secret',
                                        SecretName='secret',
                                    ),
                                ],
                                Configs=[
                                    dict(
                                        File=dict(
                                            Name='/config',
                                        ),
                                        ConfigID='config',
                                        ConfigName='config',
                                    ),
                                ],
                                Groups=[
                                    'old',
                                ],
                                DNSConfig=dict(
                                    Nameservers=[
                                        'old',
                                    ],
                                    Options=[
                                        'old',
                                    ],
                                    Search=[
                                        'old',
                                    ],
                                ),
                            ),
                            Placement=dict(
                                Constraints=[
                                    'node.role == manager',
                                ],
                                Preferences=[
                                    dict(
                                        Spread=dict(
                                            SpreadDescriptor='old',
                                        ),
                                    ),
                                ],
                            ),
                            Networks=[
                                {
                                    'Target': 'network_id',
                                },
                            ],
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
                    'container-label-add': ['label=value'],
                    'env-add': ['FOO=bar'],
                    'label-add': ['label=value'],
                    'publish-add': ['8080:80'],
                    'args': 'arg1 "arg2" \'arg3\'',
                    'user': 'user',
                    'replicas': 2,
                    'mount-add': ['type=type,destination=/path'],
                    'network-add': ['network'],
                    'network-rm': ['network_id'],
                    'stop-grace-period': 20,
                    'restart-condition': 'any',
                    'custom_option': 'new_custom_value',
                    'secret-add': ['source=secret,target=/secret'],
                    'secret-rm': ['secret'],
                    'config-add': ['config'],
                    'config-rm': ['config'],
                    'placement-pref-add': ['spread=old'],
                    'placement-pref-rm': ['spread=old'],
                },
            ),
            no_changes_callable_with_custom_name=dict(
                init_kwargs=dict(
                    name='service',
                    args='arg1 "arg2" \'arg3\'',
                    options={
                        'container-label': lambda service: 'label=value',
                        'restart-condition': lambda service: 'any',
                        'stop-grace-period': lambda service: 20,
                        'placement-pref': lambda service: 'spread=old',
                        'dns-option': lambda service: 'old',
                        'dns-search': lambda service: 'old',
                    },
                    mode='mode',
                ),
                service_info=dict(
                    Spec=dict(
                        TaskTemplate=dict(
                            ContainerSpec=dict(
                                Labels=dict(
                                    label='value',
                                ),
                                DNSConfig=dict(
                                    Options=[
                                        'old',
                                    ],
                                    Search=[
                                        'old',
                                    ],
                                ),
                            ),
                            Placement=dict(
                                Preferences=[
                                    dict(
                                        Spread=dict(
                                            SpreadDescriptor='old',
                                        ),
                                    ),
                                ],
                            ),
                        ),
                    ),
                ),
                expected={
                    'container-label-add': ['label=value'],
                    'args': 'arg1 "arg2" \'arg3\'',
                    'stop-grace-period': 20,
                    'restart-condition': 'any',
                    'placement-pref-add': ['spread=old'],
                    'placement-pref-rm': ['spread=old'],
                },
            ),
            new_options_values=dict(
                init_kwargs=dict(
                    name='service',
                    options=dict(
                        publish=[
                            '80:80',
                            '81:81',
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
                        network=[
                            'network1',
                            'network2',
                        ],
                        host=[
                            'foo:127.0.0.2',
                            'bar:127.0.0.3',
                        ],
                        secret=[
                            'secret',
                            'source=secret,target=/secret2',
                        ],
                        config=[
                            'config',
                            'source=config,target=/config2',
                        ],
                        group=['group1', 'group2'],
                        placement_pref=['spread=spread1', 'spread=spread2,foo=bar'],
                        dns=['dns1', 'dns2'],
                        dns_option=['option1', 'option2'],
                        dns_search=['domain1', 'domain2'],
                    ),
                ),
                service_info=dict(),
                expected={
                    'env-add': ['FOO=bar', 'FOO2=bar2'],
                    'constraint-add': ['node.role == manager', 'node.role == worker'],
                    'publish-add': ['80:80', '81:81'],
                    'label-add': ['label=value', 'label2=value2'],
                    'mount-add': ['type=volume,destination=/path', 'type=volume,destination="/path2"'],
                    'container-label-add': ['label=value', 'label2=value2'],
                    'network-add': ['network1', 'network2'],
                    'args': '',
                    'host-add': ['foo:127.0.0.2', 'bar:127.0.0.3'],
                    'secret-add': ['secret', 'source=secret,target=/secret2'],
                    'config-add': ['config', 'source=config,target=/config2'],
                    'group-add': ['group1', 'group2'],
                    'dns-add': ['dns1', 'dns2'],
                    'dns-option-add': ['option1', 'option2'],
                    'dns-search-add': ['domain1', 'domain2'],
                    'placement-pref-add': ['spread=spread1', 'spread=spread2,foo=bar'],
                },
            ),
            new_options_values_with_custom_name=dict(
                init_kwargs=dict(
                    name='service',
                    options={
                        'container-label': [
                            'label=value',
                            'label2=value2',
                        ],
                        'placement-pref': ['spread=spread1', 'spread=spread2,foo=bar'],
                        'dns-option': ['option1', 'option2'],
                        'dns-search': ['domain1', 'domain2'],
                    },
                ),
                service_info=dict(),
                expected={
                    'container-label-add': ['label=value', 'label2=value2'],
                    'args': '',
                    'dns-option-add': ['option1', 'option2'],
                    'dns-search-add': ['domain1', 'domain2'],
                    'placement-pref-add': ['spread=spread1', 'spread=spread2,foo=bar'],
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
                                ],
                                Hosts=[
                                    "127.0.0.1 foo",
                                ],
                                Secrets=[
                                    dict(
                                        File=dict(
                                            Name='/secret1',
                                        ),
                                        SecretID='secret1',
                                        SecretName='secret1',
                                    ),
                                ],
                                Configs=[
                                    dict(
                                        File=dict(
                                            Name='/config',
                                        ),
                                        ConfigID='config',
                                        ConfigName='config',
                                    ),
                                ],
                                Groups=[
                                    'old',
                                ],
                                DNSConfig=dict(
                                    Nameservers=[
                                        'old',
                                    ],
                                    Options=[
                                        'old',
                                    ],
                                    Search=[
                                        'old',
                                    ],
                                ),
                            ),
                            Placement=dict(
                                Constraints=[
                                    'node.role == manager',
                                ],
                                Preferences=[
                                    dict(
                                        Spread=dict(
                                            SpreadDescriptor='old',
                                        ),
                                    ),
                                ],
                            ),
                            Networks=[
                                {
                                    'Target': 'old_network_id',
                                },
                            ],
                        ),
                        EndpointSpec=dict(
                            Ports=[
                                dict(
                                    TargetPort=80,
                                    Protocol='tcp',
                                    PublishedPort=80,
                                ),
                            ],
                        ),
                    ),
                ),
                expected={
                    'args': '',
                    'label-rm': ['label'],
                    'env-rm': ['FOO'],
                    'mount-rm': ['/path'],
                    'container-label-rm': ['label'],
                    'publish-rm': [80],
                    'network-rm': ['old_network_id'],
                    'constraint-rm': ['node.role == manager'],
                    'host-rm': ['foo:127.0.0.1'],
                    'secret-rm': ['secret1'],
                    'config-rm': ['config'],
                    'group-rm': ['old'],
                    'dns-rm': ['old'],
                    'dns-option-rm': ['old'],
                    'dns-search-rm': ['old'],
                    'placement-pref-rm': ['spread=old'],
                },
            ),
            remove_option_value_with_custom_name=dict(
                init_kwargs=dict(
                    name='service',
                ),
                service_info=dict(
                    Spec=dict(
                        TaskTemplate=dict(
                            ContainerSpec=dict(
                                Labels=dict(
                                    label='value',
                                ),
                                DNSConfig=dict(
                                    Options=[
                                        'old',
                                    ],
                                    Search=[
                                        'old',
                                    ],
                                ),
                            ),
                            Placement=dict(
                                Preferences=[
                                    dict(
                                        Spread=dict(
                                            SpreadDescriptor='old',
                                        ),
                                    ),
                                ],
                            ),
                        ),
                    ),
                ),
                expected={
                    'args': '',
                    'container-label-rm': ['label'],
                    'dns-option-rm': ['old'],
                    'dns-search-rm': ['old'],
                    'placement-pref-rm': ['spread=old'],
                },
            ),
            remove_single_option_value_from_two=dict(
                init_kwargs=dict(
                    name='service',
                    options=dict(
                        publish='80:80',
                        mount='type=volume,destination=/path',
                        label='label=value',
                        env='FOO=bar',
                        constraint='node.role == manager',
                        container_label='label=value',
                        network='network2',
                        host='foo:127.0.0.1',
                        secret='source=secret1,target=/secret1',
                        config='config',
                        group='new',
                        placement_pref='spread=new',
                        dns='new',
                        dns_option='new',
                        dns_search='new',
                    ),
                ),
                service_info=dict(
                    Spec=dict(
                        Labels=OrderedDict([
                            ('label', 'value'),
                            ('label2', 'value2'),
                        ]),
                        TaskTemplate=dict(
                            ContainerSpec=dict(
                                Labels=OrderedDict([
                                    ('label', 'value'),
                                    ('label2', 'value2'),
                                ]),
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
                                ],
                                Hosts=[
                                    "127.0.0.1 foo",
                                    "127.0.0.1 bar",
                                ],
                                Secrets=[
                                    dict(
                                        File=dict(
                                            Name='/secret1',
                                        ),
                                        SecretID='secret1',
                                        SecretName='secret1',
                                    ),
                                    dict(
                                        File=dict(
                                            Name='/secret2',
                                        ),
                                        SecretID='secret2',
                                        SecretName='secret2',
                                    ),
                                ],
                                Configs=[
                                    dict(
                                        File=dict(
                                            Name='/config',
                                        ),
                                        ConfigID='config',
                                        ConfigName='config',
                                    ),
                                    dict(
                                        File=dict(
                                            Name='/config2',
                                        ),
                                        ConfigID='config2',
                                        ConfigName='config2',
                                    ),
                                ],
                                Groups=[
                                    'new',
                                    'old',
                                ],
                                DNSConfig=dict(
                                    Nameservers=[
                                        'new',
                                        'old',
                                    ],
                                    Options=[
                                        'new',
                                        'old',
                                    ],
                                    Search=[
                                        'new',
                                        'old',
                                    ],
                                ),
                            ),
                            Placement=dict(
                                Constraints=[
                                    'node.role == manager',
                                    'node.role == worker',
                                ],
                                Preferences=[
                                    dict(
                                        Spread=dict(
                                            SpreadDescriptor='new',
                                        ),
                                    ),
                                    OrderedDict((
                                        ('Spread', dict(
                                            SpreadDescriptor='old',
                                        )),
                                        ('Foo', dict(
                                            FooDescriptor='old',
                                        )),
                                    )),
                                ],
                            ),
                            Networks=[
                                {
                                    'Target': 'network1_id',
                                },
                                {
                                    'Target': 'network2_id',
                                },
                            ],
                        ),
                        EndpointSpec=dict(
                            Ports=[
                                dict(
                                    TargetPort=80,
                                    Protocol='tcp',
                                    PublishedPort=80,
                                ),
                                dict(
                                    TargetPort=81,
                                    Protocol='tcp',
                                    PublishedPort=81,
                                ),
                            ],
                        ),
                    ),
                ),
                expected={
                    'container-label-add': ['label=value'],
                    'container-label-rm': ['label2'],
                    'env-add': ['FOO=bar'],
                    'env-rm': ['FOO2'],
                    'label-add': ['label=value'],
                    'label-rm': ['label2'],
                    'args': '',
                    'publish-add': ['80:80'],
                    'publish-rm': [81],
                    'mount-rm': ['/path2'],
                    'network-add': ['network2'],
                    'network-rm': ['network1_id', 'network2_id'],
                    'mount-add': ['type=volume,destination=/path'],
                    'constraint-rm': ['node.role == worker'],
                    'host-rm': ['bar:127.0.0.1'],
                    'secret-add': ['source=secret1,target=/secret1'],
                    'secret-rm': ['secret1', 'secret2'],
                    'config-add': ['config'],
                    'config-rm': ['config', 'config2'],
                    'group-rm': ['old'],
                    'dns-rm': ['old'],
                    'dns-option-rm': ['old'],
                    'dns-search-rm': ['old'],
                    'placement-pref-add': ['spread=new'],
                    'placement-pref-rm': ['spread=new', 'spread=old,foo=old'],
                },
            ),
            remove_single_option_value_from_two_with_custom_name=dict(
                init_kwargs=dict(
                    name='service',
                    options={
                        'container-label': 'label=value',
                        'placement-pref': 'spread=new',
                        'dns-option': 'new',
                        'dns-search': 'new',
                    },
                ),
                service_info=dict(
                    Spec=dict(
                        TaskTemplate=dict(
                            ContainerSpec=dict(
                                Labels=OrderedDict([
                                    ('label', 'value'),
                                    ('label2', 'value2'),
                                ]),
                                DNSConfig=dict(
                                    Options=[
                                        'new',
                                        'old',
                                    ],
                                    Search=[
                                        'new',
                                        'old',
                                    ],
                                ),
                            ),
                            Placement=dict(
                                Preferences=[
                                    dict(
                                        Spread=dict(
                                            SpreadDescriptor='new',
                                        ),
                                    ),
                                    OrderedDict((
                                        ('Spread', dict(
                                            SpreadDescriptor='old',
                                        )),
                                        ('Foo', dict(
                                            FooDescriptor='old',
                                        )),
                                    )),
                                ],
                            ),
                        ),
                    ),
                ),
                expected={
                    'container-label-add': ['label=value'],
                    'container-label-rm': ['label2'],
                    'args': '',
                    'dns-option-rm': ['old'],
                    'dns-search-rm': ['old'],
                    'placement-pref-add': ['spread=new'],
                    'placement-pref-rm': ['spread=new', 'spread=old,foo=old'],
                },
            ),
            remove_single_option_value_from_three=dict(
                init_kwargs=dict(
                    name='service',
                    options=dict(
                        publish='80-81:80-81/tcp',
                        mount=[
                            'type=volume,target=/path',
                            'type=volume,dst="/path2"',
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
                        network=[
                            'network1',
                            'network2',
                        ],
                        host=[
                            'foo:127.0.0.1',
                            'bar:127.0.0.1',
                        ],
                        secret=[
                            'secret',
                            'source=secret,target=/secret2',
                        ],
                        config=[
                            'config1',
                            'config2',
                        ],
                        group=['group1', 'group2'],
                        placement_pref=['spread=pref1', 'spread=pref2'],
                        dns=['dns1', 'dns2'],
                        dns_option=['option1', 'option2'],
                        dns_search=['domain1', 'domain2'],
                    ),
                ),
                service_info=dict(
                    Spec=dict(
                        Labels=OrderedDict([
                            ('label', 'value'),
                            ('label2', 'value2'),
                            ('label3', 'value3'),
                        ]),
                        TaskTemplate=dict(
                            ContainerSpec=dict(
                                Labels=OrderedDict([
                                    ('label', 'value'),
                                    ('label2', 'value2'),
                                    ('label3', 'value3'),
                                ]),
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
                                ],
                                Hosts=[
                                    "127.0.0.1 foo",
                                    "127.0.0.1 bar",
                                    "127.0.0.1 baz",
                                ],
                                Secrets=[
                                    dict(
                                        File=dict(
                                            Name='secret',
                                        ),
                                        SecretID='secret',
                                        SecretName='secret',
                                    ),
                                    dict(
                                        File=dict(
                                            Name='/secret2',
                                        ),
                                        SecretID='secret',
                                        SecretName='secret',
                                    ),
                                    dict(
                                        File=dict(
                                            Name='/secret3',
                                        ),
                                        SecretID='secret3',
                                        SecretName='secret3',
                                    ),
                                ],
                                Configs=[
                                    dict(
                                        File=dict(
                                            Name='/config1',
                                        ),
                                        ConfigID='config1',
                                        ConfigName='config1',
                                    ),
                                    dict(
                                        File=dict(
                                            Name='/config2',
                                        ),
                                        ConfigID='config2',
                                        ConfigName='config2',
                                    ),
                                    dict(
                                        File=dict(
                                            Name='/config3',
                                        ),
                                        ConfigID='config3',
                                        ConfigName='config3',
                                    ),
                                ],
                                Groups=[
                                    'group1',
                                    'group2',
                                    'group3',
                                ],
                                DNSConfig=dict(
                                    Nameservers=[
                                        'dns1',
                                        'dns2',
                                        'dns3',
                                    ],
                                    Options=[
                                        'option1',
                                        'option2',
                                        'option3',
                                    ],
                                    Search=[
                                        'domain1',
                                        'domain2',
                                        'domain3',
                                    ],
                                ),
                            ),
                            Placement=dict(
                                Constraints=[
                                    'node.role == manager',
                                    'node.role == worker',
                                    'constraint',
                                ],
                                Preferences=[
                                    dict(
                                        Spread=dict(
                                            SpreadDescriptor='pref1',
                                        ),
                                    ),
                                    dict(
                                        Spread=dict(
                                            SpreadDescriptor='pref2',
                                        ),
                                    ),
                                    dict(
                                        Spread=dict(
                                            SpreadDescriptor='pref3',
                                        ),
                                    ),
                                ],
                            ),
                            Networks=[
                                {
                                    'Target': 'network1_id',
                                },
                                {
                                    'Target': 'network2_id',
                                },
                                {
                                    'Target': 'network3_id',
                                },
                            ],
                        ),
                        EndpointSpec=dict(
                            Ports=[
                                dict(
                                    TargetPort=80,
                                    Protocol='tcp',
                                    PublishedPort=80,
                                ),
                                dict(
                                    TargetPort=81,
                                    Protocol='tcp',
                                    PublishedPort=81,
                                ),
                                dict(
                                    TargetPort=82,
                                    Protocol='tcp',
                                    PublishedPort=82,
                                ),
                            ],
                        ),
                    ),
                ),
                expected={
                    'container-label-add': ['label=value', 'label2=value2'],
                    'container-label-rm': ['label3'],
                    'env-add': ['FOO=bar', 'FOO2=bar2'],
                    'env-rm': ['FOO3'],
                    'label-add': ['label=value', 'label2=value2'],
                    'label-rm': ['label3'],
                    'args': '',
                    'publish-add': ['80-81:80-81/tcp'],
                    'publish-rm': [82],
                    'mount-rm': ['/path3'],
                    'mount-add': ['type=volume,target=/path', 'type=volume,dst="/path2"'],
                    'constraint-rm': ['constraint'],
                    'network-add': ['network1', 'network2'],
                    'network-rm': ['network1_id', 'network2_id', 'network3_id'],
                    'host-rm': ['baz:127.0.0.1'],
                    'secret-add': ['secret', 'source=secret,target=/secret2'],
                    'secret-rm': ['secret', 'secret3'],
                    'config-add': ['config1', 'config2'],
                    'config-rm': ['config1', 'config2', 'config3'],
                    'group-rm': ['group3'],
                    'dns-rm': ['dns3'],
                    'dns-option-rm': ['option3'],
                    'dns-search-rm': ['domain3'],
                    'placement-pref-add': ['spread=pref1', 'spread=pref2'],
                    'placement-pref-rm': ['spread=pref1', 'spread=pref2', 'spread=pref3'],
                },
            ),
            remove_single_option_value_from_three_with_custom_name=dict(
                init_kwargs=dict(
                    name='service',
                    options={
                        'container_label': ['label=value', 'label2=value2'],
                        'placement_pref': ['spread=pref1', 'spread=pref2'],
                        'dns_option': ['option1', 'option2'],
                        'dns_search': ['domain1', 'domain2'],
                    },
                ),
                service_info=dict(
                    Spec=dict(
                        TaskTemplate=dict(
                            ContainerSpec=dict(
                                Labels=OrderedDict([
                                    ('label', 'value'),
                                    ('label2', 'value2'),
                                    ('label3', 'value3'),
                                ]),
                                DNSConfig=dict(
                                    Options=[
                                        'option1',
                                        'option2',
                                        'option3',
                                    ],
                                    Search=[
                                        'domain1',
                                        'domain2',
                                        'domain3',
                                    ],
                                ),
                            ),
                            Placement=dict(
                                Preferences=[
                                    dict(
                                        Spread=dict(
                                            SpreadDescriptor='pref1',
                                        ),
                                    ),
                                    dict(
                                        Spread=dict(
                                            SpreadDescriptor='pref2',
                                        ),
                                    ),
                                    dict(
                                        Spread=dict(
                                            SpreadDescriptor='pref3',
                                        ),
                                    ),
                                ],
                            ),
                        ),
                    ),
                ),
                expected={
                    'container-label-add': ['label=value', 'label2=value2'],
                    'container-label-rm': ['label3'],
                    'args': '',
                    'dns-option-rm': ['option3'],
                    'dns-search-rm': ['domain3'],
                    'placement-pref-add': ['spread=pref1', 'spread=pref2'],
                    'placement-pref-rm': ['spread=pref1', 'spread=pref2', 'spread=pref3'],
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
                expected_service_labels=['label=label', 'new_label={"foo": "bar"}'],
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
                service._update_labels(data['kwargs'])
                for label in data['expected_service_labels']:
                    self.assertIn(label, service.label)
                self.assertEqual(len(service.label), len(data['expected_service_labels']))
                # make sure original container's labels not changed
                self.assertNotEqual(id(service.label), old_labels_id)

    def test__create_service(self):
        cases = dict(
            default=dict(
                service_init_kwargs=dict(name='service'),
                expected_args={
                    'executable': ['docker', 'service', 'create'],
                    'image': ['image:tag'],
                    'name': 'service',
                    'args': [],
                },
            ),
            custom_image=dict(
                service_init_kwargs=dict(name='service', image='custom'),
                expected_args={
                    'executable': ['docker', 'service', 'create'],
                    'image': ['image:tag'],
                    'name': 'service',
                    'args': [],
                },
            ),
            custom_command=dict(
                service_init_kwargs=dict(name='service', command='command'),
                expected_args={
                    'executable': ['docker', 'service', 'create'],
                    'image': ['image:tag'],
                    'name': 'service',
                    'args': ['command'],
                },
            ),
            custom_args=dict(
                service_init_kwargs=dict(name='service', args='arg1 arg2'),
                expected_args={
                    'executable': ['docker', 'service', 'create'],
                    'image': ['image:tag'],
                    'name': 'service',
                    'args': ['arg1', 'arg2'],
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
                    'args': ['command', 'arg1', 'arg2'],
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
                        restart_condition='restart_condition',
                        user='user',
                        stop_grace_period=20,
                        host=['foo:127.0.0.1', 'bar:127.0.0.1'],
                        secret=['secret1', 'secret2'],
                        config=['config1', 'config2'],
                        group=['group1', 'group2'],
                        placement_pref=['pref1', 'pref2'],
                        dns=['dns1', 'dns2'],
                        dns_option=['dns-option1', 'dns-option2'],
                        dns_search=['domain1', 'domain2'],
                    ),
                    mode='mode',
                ),
                expected_args={
                    'executable': ['docker', 'service', 'create'],
                    'args': ['command1', 'command2', 'arg1', 'arg2'],
                    'network': 'network',
                    'mode': 'mode',
                    'constraint': ['constraint1', 'constraint2'],
                    'mount': ['mount1', 'mount2'],
                    'replicas': '5',
                    'publish': ['port1', 'port2'],
                    'label': ['label1', 'label2'],
                    'container-label': ['c_label1', 'c_label2'],
                    'user': 'user',
                    'env': ['en1', 'env2'],
                    'host': ['foo:127.0.0.1', 'bar:127.0.0.1'],
                    'secret': ['secret1', 'secret2'],
                    'config': ['config1', 'config2'],
                    'group': ['group1', 'group2'],
                    'placement-pref': ['pref1', 'pref2'],
                    'dns': ['dns1', 'dns2'],
                    'dns-option': ['dns-option1', 'dns-option2'],
                    'dns-search': ['domain1', 'domain2'],
                    'stop-grace-period': '20',
                    'restart-condition': 'restart_condition',
                    'image': ['image:tag'],
                    'name': 'service',
                },
            ),
        )

        def test_command(command, *args, **kwargs):
            args = shlex.split(command)
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
