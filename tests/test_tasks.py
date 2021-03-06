import shlex
import sys

import mock
import six
import unittest2 as unittest

from fabric import api as fab, state
from fabric.contrib import console
from fabric.main import load_tasks_from_module, is_task_module, is_task_object

import fabricio
import fabricio.tasks

from fabricio import docker, tasks, utils
from tests import docker_build_args_parser, SucceededResult


class TestContainer(docker.Container):

    image = docker.Image('test')


class TestCase(unittest.TestCase):

    def test_infrastructure(self):
        class AbortException(Exception):
            pass

        def task():
            pass

        cases = dict(
            default=dict(
                decorator=tasks.infrastructure,
                expected_infrastructure='task',
            ),
            invoked=dict(
                decorator=tasks.infrastructure(),
                expected_infrastructure='task',
            ),
        )

        with fab.settings(abort_on_prompts=True, abort_exception=AbortException):
            with mock.patch.object(fab, 'abort', side_effect=AbortException):
                for case, data in cases.items():
                    with self.subTest(case=case):
                        decorator = data['decorator']
                        infrastructure = decorator(task)

                        self.assertTrue(is_task_object(infrastructure.confirm))
                        self.assertTrue(is_task_object(infrastructure.default))

                        fab.execute(infrastructure.confirm)
                        self.assertEqual(data['expected_infrastructure'], fab.env.infrastructure)

                        fab.env.infrastructure = None
                        with mock.patch.object(console, 'confirm', side_effect=[True, False]):
                            fab.execute(infrastructure.default)
                            self.assertEqual(data['expected_infrastructure'], fab.env.infrastructure)
                            with self.assertRaises(AbortException):
                                fab.execute(infrastructure.default)

    def test_infrastructure_details(self):
        class Infrastructure(tasks.Infrastructure):
            """
            inf {name}
            """
        @Infrastructure
        def infrastructure(foo='bar'):
            """
            func
            """
        self.assertListEqual(
            ['inf', 'infrastructure', 'func', 'Arguments:', "foo='bar'"],
            infrastructure.__details__().split(),
        )

    def test_get_task_name(self):
        cases = dict(
            case1=dict(
                command='command1',
                expected='layer1.layer2.command1',
            ),
            case2=dict(
                command='command2',
                expected='layer1.layer2.command2',
            ),
            case3=dict(
                command='command3',
                expected='layer1.command3',
            ),
        )
        commands = dict(
            layer1=dict(
                layer2=dict(
                    command1='command1',
                    command2='command2',
                ),
                command3='command3',
            ),
        )
        with utils.patch(state, 'commands', commands):
            for case, data in cases.items():
                with self.subTest(case=case):
                    self.assertEqual(
                        tasks.get_task_name(data['command']),
                        data['expected'],
                    )


class TasksTestCase(unittest.TestCase):

    def test_tasks(self):
        class TestTasks(tasks.Tasks):

            @fab.task(default=True, aliases=['foo', 'bar'])
            def default(self):
                pass

            @fab.task(name='name', alias='alias')
            def task(self):
                pass

            @fab.task
            @fab.serial
            def serial(self):
                pass

            @fab.task
            @fab.parallel
            def parallel(self):
                pass

        roles = ['role_1', 'role_2']
        hosts = ['host_1', 'host_2']
        tasks_list = TestTasks(roles=roles, hosts=hosts)
        self.assertTrue(is_task_module(tasks_list))
        self.assertTrue(tasks_list.default.is_default)
        self.assertListEqual(['foo', 'bar'], tasks_list.default.aliases)
        self.assertEqual('name', tasks_list.task.name)
        self.assertListEqual(['alias'], tasks_list.task.aliases)
        for task in tasks_list:
            self.assertListEqual(roles, task.roles)
            self.assertListEqual(hosts, task.hosts)
        docstring, new_style, classic, default = load_tasks_from_module(tasks_list)
        self.assertIsNone(docstring)
        self.assertIn('default', new_style)
        self.assertIn('alias', new_style)
        self.assertIn('foo', new_style)
        self.assertIn('bar', new_style)
        self.assertIn('name', new_style)
        self.assertDictEqual({}, classic)
        self.assertIs(tasks_list.default, default)

        self.assertIn('serial', tasks_list.serial.wrapped.__dict__)
        self.assertTrue(tasks_list.serial.wrapped.serial)

        self.assertIn('parallel', tasks_list.parallel.wrapped.__dict__)
        self.assertTrue(tasks_list.parallel.wrapped.parallel)

    def test_super(self):
        class TestTasks1(tasks.Tasks):

            @fab.task
            def task(self):
                pass

            @fab.task
            def task2(self):
                pass

            @fab.task
            def task3(self, argument):
                pass

        class TestTasks2(TestTasks1):

            @fab.task
            def task(self):
                super(TestTasks2, self).task()

        roles = ['role_1', 'role_2']
        hosts = ['host_1', 'host_2']
        tasks_list = TestTasks2(roles=roles, hosts=hosts)
        self.assertListEqual(roles, tasks_list.task.roles)
        self.assertListEqual(hosts, tasks_list.task.hosts)
        self.assertIsNone(getattr(super(TestTasks2, tasks_list).task, 'roles', None))
        self.assertIsNone(getattr(super(TestTasks2, tasks_list).task, 'hosts', None))
        with fab.settings(fab.hide('everything')):
            fab.execute(tasks_list.task)

            # check if there is enough arguments passed to methods
            tasks_list.task()
            tasks_list.task2()
            tasks_list.task3('argument')
            super(TestTasks2, tasks_list).task()
            super(TestTasks2, tasks_list).task3('argument')


class DockerTasksTestCase(unittest.TestCase):

    maxDiff = None

    def setUp(self):
        self.stderr, sys.stderr = sys.stderr, six.StringIO()
        self.fab_settings = fab.settings(fab.hide('everything'))
        self.fab_settings.__enter__()

    def tearDown(self):
        self.fab_settings.__exit__(None, None, None)
        sys.stderr = self.stderr

    def test_commands_list(self):
        cases = dict(
            default=dict(
                init_kwargs=dict(service='service'),
                expected_commands={'deploy'},
            ),
            prepare_tasks=dict(
                init_kwargs=dict(service='service', registry='registry', prepare_command=True, push_command=True, upgrade_command=True),
                expected_commands={'deploy', 'prepare', 'push', 'upgrade'},
            ),
            migrate_tasks=dict(
                init_kwargs=dict(service='service', migrate_commands=True),
                expected_commands={'deploy', 'migrate', 'migrate-back'},
            ),
            backup_tasks=dict(
                init_kwargs=dict(service='service', backup_commands=True),
                expected_commands={'deploy', 'backup', 'restore'},
            ),
            revert_task=dict(
                init_kwargs=dict(service='service', revert_command=True),
                expected_commands={'deploy', 'revert'},
            ),
            pull_task=dict(
                init_kwargs=dict(service='service', pull_command=True),
                expected_commands={'deploy', 'pull'},
            ),
            update_task=dict(
                init_kwargs=dict(service='service', update_command=True),
                expected_commands={'deploy', 'update'},
            ),
            destroy_task=dict(
                init_kwargs=dict(service='service', destroy_command=True),
                expected_commands={'deploy', 'destroy'},
            ),
            complex=dict(
                init_kwargs=dict(service='service', backup_commands=True, migrate_commands=True, registry='registry', revert_command=True, update_command=True, pull_command=True, destroy_command=True),
                expected_commands={'pull', 'deploy', 'update', 'backup', 'restore', 'migrate', 'migrate-back', 'revert', 'destroy'},
            ),
            task_mode=dict(
                init_kwargs=dict(service='service', backup_commands=True, migrate_commands=True, registry='registry', revert_command=True, update_command=True, pull_command=True),
                expected_commands={'pull', 'rollback', 'update', 'backup', 'restore', 'migrate', 'migrate-back', 'prepare', 'push', 'revert', 'upgrade', 'deploy', 'destroy', 'deploy'},
                env=dict(tasks='task'),
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                with mock.patch.dict(fab.env, data.get('env', {})):
                    tasks_list = tasks.DockerTasks(**data['init_kwargs'])
                docstring, new_style, classic, default = load_tasks_from_module(tasks_list)
                self.assertSetEqual(set(new_style), data['expected_commands'])

    @mock.patch.object(docker.Container, 'destroy')
    @mock.patch.object(console, 'confirm', return_value=True)
    @mock.patch.dict(fab.env, dict(tasks='task'))
    def test_destroy(self, confirm, destroy):
        service = docker.Container(name='name')
        tasks_list = tasks.DockerTasks(service=service)
        cases = dict(
            explicit=dict(
                execute=tasks_list.destroy,
                expected_calls=[mock.call.destroy('args', kwargs='kwargs')],
            ),
            default=dict(
                execute=tasks_list.destroy.default,
                expected_calls=[
                    mock.call.confirm(mock.ANY, default=mock.ANY),
                    mock.call.destroy('args', kwargs='kwargs'),
                ],
            ),
            confirm=dict(
                execute=tasks_list.destroy.confirm,
                expected_calls=[mock.call.destroy('args', kwargs='kwargs')],
            ),
        )
        calls = mock.Mock()
        calls.attach_mock(destroy, 'destroy')
        calls.attach_mock(confirm, 'confirm')
        for case, data in cases.items():
            with self.subTest(case):
                calls.reset_mock()
                fab.execute(data['execute'], 'args', kwargs='kwargs')
                self.assertListEqual(data['expected_calls'], calls.mock_calls)

    @mock.patch.dict(fab.env, dict(tasks='task'))
    def test_destroy_details(self):
        class Service(docker.Container):
            def destroy(self, foo='bar'):
                """
                service doc
                """
        class DockerTasks(tasks.DockerTasks):
            class DestroyTask(tasks.DockerTasks.DestroyTask):
                """
                tasks doc
                """
        self.assertEqual(
            "\ntasks doc\n\nservice doc\n\nArguments: self, foo='bar'",
            DockerTasks(Service()).destroy.__details__(),
        )

    @mock.patch.multiple(TestContainer, revert=mock.DEFAULT, migrate_back=mock.DEFAULT)
    def test_rollback(self, revert, migrate_back):
        tasks_list = tasks.DockerTasks(service=TestContainer(), hosts=['host'])
        rollback = mock.Mock()
        rollback.attach_mock(migrate_back, 'migrate_back')
        rollback.attach_mock(revert, 'revert')
        revert.return_value = True

        # with migrate_back disabled
        tasks_list.rollback.name = '{0}__migrate_disabled'.format(self)
        fab.execute(tasks_list.rollback, migrate_back='no')
        migrate_back.assert_not_called()
        revert.assert_called_once()
        rollback.reset_mock()

        # default case
        tasks_list.rollback.name = '{0}__default'.format(self)
        fab.execute(tasks_list.rollback)
        self.assertListEqual(
            [mock.call.migrate_back(), mock.call.revert()],
            rollback.mock_calls,
        )
        rollback.reset_mock()

    @mock.patch.multiple(docker.Container, backup=mock.DEFAULT, migrate=mock.DEFAULT, update=mock.DEFAULT)
    @mock.patch.multiple(fabricio, run=mock.DEFAULT, local=mock.DEFAULT)
    @mock.patch.object(fab, 'remote_tunnel', return_value=mock.MagicMock())
    def test_deploy(self, remote_tunnel, run, local, backup, migrate, update):
        cases = dict(
            # TODO empty registry
            # TODO empty account
            default=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.run('docker tag test:latest fabricio-temp-image:test && docker rmi test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            custom_image_registry=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.run('docker tag registry:5000/test:latest fabricio-temp-image:test && docker rmi registry:5000/test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull registry:5000/test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry='registry:5000',
            ),
            custom_image_registry_with_ssh_tunnel_deprecated=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(ssh_tunnel_port=1234),
                expected_calls=[
                    mock.call.run('docker tag localhost:1234/test:latest fabricio-temp-image:test && docker rmi localhost:1234/test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull localhost:1234/test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry='localhost:1234', account=None),
                    mock.call.update(force=False, tag=None, registry='localhost:1234', account=None),
                ],
                image_registry='registry:5000',
            ),
            custom_registry=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(registry='host:5000'),
                expected_calls=[
                    mock.call.local('docker tag test:latest fabricio-temp-image:test && docker rmi test:latest', ignore_errors=True, use_cache=True),
                    mock.call.local('docker pull test:latest', quiet=False, use_cache=True, ignore_errors=False),
                    mock.call.local('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=True),
                    mock.call.local('docker tag test:latest host:5000/test:latest', use_cache=True),
                    mock.call.local('docker push host:5000/test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi host:5000/test:latest', use_cache=True),
                    mock.call.run('docker tag host:5000/test:latest fabricio-temp-image:test && docker rmi host:5000/test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull host:5000/test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry='host:5000', account=None),
                    mock.call.update(force=False, tag=None, registry='host:5000', account=None),
                ],
                image_registry=None,
            ),
            custom_registry_no_image=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(registry='host:5000'),
                expected_calls=[
                    mock.call.migrate(tag=None, registry='host:5000', account=None),
                    mock.call.update(force=False, tag=None, registry='host:5000', account=None),
                ],
                image_registry=None,
                service=docker.Container(name='name'),
            ),
            custom_registry_with_ssh_tunnel_deprecated=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(registry='host:5000', ssh_tunnel_port=1234),
                expected_calls=[
                    mock.call.local('docker tag test:latest fabricio-temp-image:test && docker rmi test:latest', ignore_errors=True, use_cache=True),
                    mock.call.local('docker pull test:latest', quiet=False, use_cache=True, ignore_errors=False),
                    mock.call.local('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=True),
                    mock.call.local('docker tag test:latest host:5000/test:latest', use_cache=True),
                    mock.call.local('docker push host:5000/test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi host:5000/test:latest', use_cache=True),
                    mock.call.run('docker tag localhost:1234/test:latest fabricio-temp-image:test && docker rmi localhost:1234/test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull localhost:1234/test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry='localhost:1234', account=None),
                    mock.call.update(force=False, tag=None, registry='localhost:1234', account=None),
                ],
                image_registry=None,
            ),
            custom_registry_with_ssh_tunnel_no_image_deprecated=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(registry='host:5000', ssh_tunnel_port=1234),
                expected_calls=[
                    mock.call.migrate(tag=None, registry='localhost:1234', account=None),
                    mock.call.update(force=False, tag=None, registry='localhost:1234', account=None),
                ],
                image_registry=None,
                service=docker.Container(name='name'),
            ),
            custom_account=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(account='account'),
                expected_calls=[
                    mock.call.local('docker tag test:latest fabricio-temp-image:test && docker rmi test:latest', ignore_errors=True, use_cache=True),
                    mock.call.local('docker pull test:latest', quiet=False, use_cache=True, ignore_errors=False),
                    mock.call.local('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=True),
                    mock.call.local('docker tag test:latest account/test:latest', use_cache=True),
                    mock.call.local('docker push account/test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi account/test:latest', use_cache=True),
                    mock.call.run('docker tag account/test:latest fabricio-temp-image:test && docker rmi account/test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull account/test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry=None, account='account'),
                    mock.call.update(force=False, tag=None, registry=None, account='account'),
                ],
                image_registry=None,
            ),
            custom_account_no_image=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(account='account'),
                expected_calls=[
                    mock.call.migrate(tag=None, registry=None, account='account'),
                    mock.call.update(force=False, tag=None, registry=None, account='account'),
                ],
                image_registry=None,
                service=docker.Container(name='name'),
            ),
            custom_account_with_ssh_tunnel_deprecated=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(account='account', ssh_tunnel_port=1234),
                expected_calls=[
                    mock.call.local('docker tag registry:5000/test:latest fabricio-temp-image:test && docker rmi registry:5000/test:latest', ignore_errors=True, use_cache=True),
                    mock.call.local('docker pull registry:5000/test:latest', quiet=False, use_cache=True, ignore_errors=False),
                    mock.call.local('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=True),
                    mock.call.local('docker tag registry:5000/test:latest registry:5000/account/test:latest', use_cache=True),
                    mock.call.local('docker push registry:5000/account/test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi registry:5000/account/test:latest', use_cache=True),
                    mock.call.run('docker tag localhost:1234/account/test:latest fabricio-temp-image:test && docker rmi localhost:1234/account/test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull localhost:1234/account/test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry='localhost:1234', account='account'),
                    mock.call.update(force=False, tag=None, registry='localhost:1234', account='account'),
                ],
                image_registry='registry:5000',
            ),
            custom_registry_and_image_registry=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(registry='host:4000'),
                expected_calls=[
                    mock.call.local('docker tag registry:5000/test:latest fabricio-temp-image:test && docker rmi registry:5000/test:latest', ignore_errors=True, use_cache=True),
                    mock.call.local('docker pull registry:5000/test:latest', quiet=False, use_cache=True, ignore_errors=False),
                    mock.call.local('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=True),
                    mock.call.local('docker tag registry:5000/test:latest host:4000/test:latest', use_cache=True),
                    mock.call.local('docker push host:4000/test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi host:4000/test:latest', use_cache=True),
                    mock.call.run('docker tag host:4000/test:latest fabricio-temp-image:test && docker rmi host:4000/test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull host:4000/test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry='host:4000', account=None),
                    mock.call.update(force=False, tag=None, registry='host:4000', account=None),
                ],
                image_registry='registry:5000',
            ),
            custom_registry_and_image_registry_with_ssh_tunnel_deprecated=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(registry='host:4000', ssh_tunnel_port=1234),
                expected_calls=[
                    mock.call.local('docker tag registry:5000/test:latest fabricio-temp-image:test && docker rmi registry:5000/test:latest', ignore_errors=True, use_cache=True),
                    mock.call.local('docker pull registry:5000/test:latest', quiet=False, use_cache=True, ignore_errors=False),
                    mock.call.local('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=True),
                    mock.call.local('docker tag registry:5000/test:latest host:4000/test:latest', use_cache=True),
                    mock.call.local('docker push host:4000/test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi host:4000/test:latest', use_cache=True),
                    mock.call.run('docker tag localhost:1234/test:latest fabricio-temp-image:test && docker rmi localhost:1234/test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull localhost:1234/test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry='localhost:1234', account=None),
                    mock.call.update(force=False, tag=None, registry='localhost:1234', account=None),
                ],
                image_registry='registry:5000',
            ),
            forced=dict(
                deploy_kwargs=dict(force='yes'),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.run('docker tag test:latest fabricio-temp-image:test && docker rmi test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=True, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            explicit_not_forced=dict(
                deploy_kwargs=dict(force='no'),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.run('docker tag test:latest fabricio-temp-image:test && docker rmi test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            custom_tag=dict(
                deploy_kwargs=dict(tag='tag'),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.run('docker tag test:tag fabricio-temp-image:test && docker rmi test:tag', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull test:tag', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag='tag', registry=None, account=None),
                    mock.call.update(force=False, tag='tag', registry=None, account=None),
                ],
                image_registry=None,
            ),
            backup_enabled=dict(
                deploy_kwargs=dict(backup='yes'),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.backup(),
                    mock.call.run('docker tag test:latest fabricio-temp-image:test && docker rmi test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            explicit_backup_disabled=dict(
                deploy_kwargs=dict(backup='no'),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.run('docker tag test:latest fabricio-temp-image:test && docker rmi test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            skip_migrations=dict(
                deploy_kwargs=dict(migrate='no'),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.run('docker tag test:latest fabricio-temp-image:test && docker rmi test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            explicit_migrate=dict(
                deploy_kwargs=dict(migrate='yes'),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.run('docker tag test:latest fabricio-temp-image:test && docker rmi test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            complex=dict(
                deploy_kwargs=dict(force=True, backup=True, tag='tag'),
                init_kwargs=dict(registry='host:4000', account='account'),
                expected_calls=[
                    mock.call.local('docker tag registry:5000/test:tag fabricio-temp-image:test && docker rmi registry:5000/test:tag', ignore_errors=True, use_cache=True),
                    mock.call.local('docker pull registry:5000/test:tag', quiet=False, use_cache=True, ignore_errors=False),
                    mock.call.local('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=True),
                    mock.call.local('docker tag registry:5000/test:tag host:4000/account/test:tag', use_cache=True),
                    mock.call.local('docker push host:4000/account/test:tag', quiet=False, use_cache=True),
                    mock.call.local('docker rmi host:4000/account/test:tag', use_cache=True),
                    mock.call.backup(),
                    mock.call.run('docker tag host:4000/account/test:tag fabricio-temp-image:test && docker rmi host:4000/account/test:tag', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull host:4000/account/test:tag', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag='tag', registry='host:4000', account='account'),
                    mock.call.update(force=True, tag='tag', registry='host:4000', account='account'),
                ],
                image_registry='registry:5000',
            ),
        )
        deploy = mock.Mock()
        deploy.attach_mock(backup, 'backup')
        deploy.attach_mock(migrate, 'migrate')
        deploy.attach_mock(update, 'update')
        deploy.attach_mock(run, 'run')
        deploy.attach_mock(local, 'local')
        update.return_value = False
        run.return_value = SucceededResult()
        local.return_value = SucceededResult()
        for case, data in cases.items():
            with self.subTest(case=case):
                deploy.reset_mock()
                tasks_list = tasks.DockerTasks(
                    service=data.get('service') or docker.Container(
                        name='name',
                        image=docker.Image('test', registry=data['image_registry']),
                    ),
                    hosts=['host'],
                    **data['init_kwargs']
                )
                tasks_list.deploy.name = '{0}__{1}'.format(self, case)
                fab.execute(tasks_list.deploy, **data['deploy_kwargs'])
                self.assertListEqual(data['expected_calls'], deploy.mock_calls)

    def test_delete_dangling_images_deprecated(self):
        cases = dict(
            windows=dict(
                os_name='nt',
                expected_command="for /F %i in ('docker images --filter \"dangling=true\" --quiet') do @docker rmi %i",
            ),
            posix=dict(
                os_name='posix',
                expected_command='for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done',
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                with mock.patch.object(fabricio, 'local') as local:
                    with mock.patch('os.name', data['os_name']):
                        tasks_list = tasks.DockerTasks(service=docker.Container(name='name'))
                        tasks_list.delete_dangling_images()
                        local.assert_called_once_with(
                            data['expected_command'],
                            ignore_errors=True,
                        )


class ImageBuildDockerTasksTestCase(unittest.TestCase):

    maxDiff = None

    def setUp(self):
        self.fab_settings = fab.settings(fab.hide('everything'))
        self.fab_settings.__enter__()

    def tearDown(self):
        self.fab_settings.__exit__(None, None, None)

    @mock.patch.multiple(docker.Container, backup=mock.DEFAULT, migrate=mock.DEFAULT, update=mock.DEFAULT)
    @mock.patch.multiple(fabricio, run=mock.DEFAULT)
    @mock.patch.object(fab, 'remote_tunnel', return_value=mock.MagicMock())
    def test_deploy(self, remote_tunnel, run, backup, migrate, update):
        cases = dict(
            default=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.local('docker inspect --type image test:latest', capture=True, use_cache=True, abort_exception=docker.ImageNotFoundError),
                    mock.call.local('docker tag test:latest fabricio-temp-image:test && docker rmi test:latest', ignore_errors=True, use_cache=True),
                    mock.call.local('docker build --tag=test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('docker rmi fabricio-temp-image:test old_parent_id', ignore_errors=True, use_cache=True),
                    mock.call.local('docker push test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker tag test:latest fabricio-temp-image:test && docker rmi test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            custom_image_registry=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.local('docker inspect --type image registry:5000/test:latest', capture=True, use_cache=True, abort_exception=docker.ImageNotFoundError),
                    mock.call.local('docker tag registry:5000/test:latest fabricio-temp-image:test && docker rmi registry:5000/test:latest', ignore_errors=True, use_cache=True),
                    mock.call.local('docker build --tag=registry:5000/test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('docker rmi fabricio-temp-image:test old_parent_id', ignore_errors=True, use_cache=True),
                    mock.call.local('docker push registry:5000/test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker tag registry:5000/test:latest fabricio-temp-image:test && docker rmi registry:5000/test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull registry:5000/test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry='registry:5000',
            ),
            custom_image_registry_with_ssh_tunnel_deprecated=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(ssh_tunnel_port=1234),
                expected_calls=[
                    mock.call.local('docker inspect --type image registry:5000/test:latest', capture=True, use_cache=True, abort_exception=docker.ImageNotFoundError),
                    mock.call.local('docker tag registry:5000/test:latest fabricio-temp-image:test && docker rmi registry:5000/test:latest', ignore_errors=True, use_cache=True),
                    mock.call.local('docker build --tag=registry:5000/test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('docker rmi fabricio-temp-image:test old_parent_id', ignore_errors=True, use_cache=True),
                    mock.call.local('docker push registry:5000/test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker tag localhost:1234/test:latest fabricio-temp-image:test && docker rmi localhost:1234/test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull localhost:1234/test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry='localhost:1234', account=None),
                    mock.call.update(force=False, tag=None, registry='localhost:1234', account=None),
                ],
                image_registry='registry:5000',
            ),
            custom_registry=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(registry='host:5000'),
                expected_calls=[
                    mock.call.local('docker inspect --type image host:5000/test:latest', capture=True, use_cache=True, abort_exception=docker.ImageNotFoundError),
                    mock.call.local('docker tag host:5000/test:latest fabricio-temp-image:test && docker rmi host:5000/test:latest', ignore_errors=True, use_cache=True),
                    mock.call.local('docker build --tag=host:5000/test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('docker rmi fabricio-temp-image:test old_parent_id', ignore_errors=True, use_cache=True),
                    mock.call.local('docker push host:5000/test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker tag host:5000/test:latest fabricio-temp-image:test && docker rmi host:5000/test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull host:5000/test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry='host:5000', account=None),
                    mock.call.update(force=False, tag=None, registry='host:5000', account=None),
                ],
                image_registry=None,
            ),
            custom_registry_with_ssh_tunnel_deprecated=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(registry='host:5000', ssh_tunnel_port=1234),
                expected_calls=[
                    mock.call.local('docker inspect --type image host:5000/test:latest', capture=True, use_cache=True, abort_exception=docker.ImageNotFoundError),
                    mock.call.local('docker tag host:5000/test:latest fabricio-temp-image:test && docker rmi host:5000/test:latest', ignore_errors=True, use_cache=True),
                    mock.call.local('docker build --tag=host:5000/test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('docker rmi fabricio-temp-image:test old_parent_id', ignore_errors=True, use_cache=True),
                    mock.call.local('docker push host:5000/test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker tag localhost:1234/test:latest fabricio-temp-image:test && docker rmi localhost:1234/test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull localhost:1234/test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry='localhost:1234', account=None),
                    mock.call.update(force=False, tag=None, registry='localhost:1234', account=None),
                ],
                image_registry=None,
            ),
            custom_account=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(account='account'),
                expected_calls=[
                    mock.call.local('docker inspect --type image account/test:latest', capture=True, use_cache=True, abort_exception=docker.ImageNotFoundError),
                    mock.call.local('docker tag account/test:latest fabricio-temp-image:test && docker rmi account/test:latest', ignore_errors=True, use_cache=True),
                    mock.call.local('docker build --tag=account/test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('docker rmi fabricio-temp-image:test old_parent_id', ignore_errors=True, use_cache=True),
                    mock.call.local('docker push account/test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker tag account/test:latest fabricio-temp-image:test && docker rmi account/test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull account/test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry=None, account='account'),
                    mock.call.update(force=False, tag=None, registry=None, account='account'),
                ],
                image_registry=None,
            ),
            custom_account_with_ssh_tunnel_deprecated=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(account='account', ssh_tunnel_port=1234),
                expected_calls=[
                    mock.call.local('docker inspect --type image host:5000/account/test:latest', capture=True, use_cache=True, abort_exception=docker.ImageNotFoundError),
                    mock.call.local('docker tag host:5000/account/test:latest fabricio-temp-image:test && docker rmi host:5000/account/test:latest', ignore_errors=True, use_cache=True),
                    mock.call.local('docker build --tag=host:5000/account/test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('docker rmi fabricio-temp-image:test old_parent_id', ignore_errors=True, use_cache=True),
                    mock.call.local('docker push host:5000/account/test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker tag localhost:1234/account/test:latest fabricio-temp-image:test && docker rmi localhost:1234/account/test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull localhost:1234/account/test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry='localhost:1234', account='account'),
                    mock.call.update(force=False, tag=None, registry='localhost:1234', account='account'),
                ],
                image_registry='host:5000',
            ),
            custom_registry_and_image_registry=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(registry='host:4000'),
                expected_calls=[
                    mock.call.local('docker inspect --type image host:4000/test:latest', capture=True, use_cache=True, abort_exception=docker.ImageNotFoundError),
                    mock.call.local('docker tag host:4000/test:latest fabricio-temp-image:test && docker rmi host:4000/test:latest', ignore_errors=True, use_cache=True),
                    mock.call.local('docker build --tag=host:4000/test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('docker rmi fabricio-temp-image:test old_parent_id', ignore_errors=True, use_cache=True),
                    mock.call.local('docker push host:4000/test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker tag host:4000/test:latest fabricio-temp-image:test && docker rmi host:4000/test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull host:4000/test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry='host:4000', account=None),
                    mock.call.update(force=False, tag=None, registry='host:4000', account=None),
                ],
                image_registry='registry:5000',
            ),
            custom_registry_and_image_registry_with_ssh_tunnel_deprecated=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(registry='host:4000', ssh_tunnel_port=1234),
                expected_calls=[
                    mock.call.local('docker inspect --type image host:4000/test:latest', capture=True, use_cache=True, abort_exception=docker.ImageNotFoundError),
                    mock.call.local('docker tag host:4000/test:latest fabricio-temp-image:test && docker rmi host:4000/test:latest', ignore_errors=True, use_cache=True),
                    mock.call.local('docker build --tag=host:4000/test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('docker rmi fabricio-temp-image:test old_parent_id', ignore_errors=True, use_cache=True),
                    mock.call.local('docker push host:4000/test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker tag localhost:1234/test:latest fabricio-temp-image:test && docker rmi localhost:1234/test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull localhost:1234/test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry='localhost:1234', account=None),
                    mock.call.update(force=False, tag=None, registry='localhost:1234', account=None),
                ],
                image_registry='registry:5000',
            ),
            forced=dict(
                deploy_kwargs=dict(force='yes'),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.local('docker inspect --type image test:latest', capture=True, use_cache=True, abort_exception=docker.ImageNotFoundError),
                    mock.call.local('docker tag test:latest fabricio-temp-image:test && docker rmi test:latest', ignore_errors=True, use_cache=True),
                    mock.call.local('docker build --tag=test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('docker rmi fabricio-temp-image:test old_parent_id', ignore_errors=True, use_cache=True),
                    mock.call.local('docker push test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker tag test:latest fabricio-temp-image:test && docker rmi test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=True, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            explicit_not_forced=dict(
                deploy_kwargs=dict(force='no'),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.local('docker inspect --type image test:latest', capture=True, use_cache=True, abort_exception=docker.ImageNotFoundError),
                    mock.call.local('docker tag test:latest fabricio-temp-image:test && docker rmi test:latest', ignore_errors=True, use_cache=True),
                    mock.call.local('docker build --tag=test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('docker rmi fabricio-temp-image:test old_parent_id', ignore_errors=True, use_cache=True),
                    mock.call.local('docker push test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker tag test:latest fabricio-temp-image:test && docker rmi test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            custom_build_path=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(build_path='foo'),
                expected_calls=[
                    mock.call.local('docker inspect --type image test:latest', capture=True, use_cache=True, abort_exception=docker.ImageNotFoundError),
                    mock.call.local('docker tag test:latest fabricio-temp-image:test && docker rmi test:latest', ignore_errors=True, use_cache=True),
                    mock.call.local('docker build --tag=test:latest --pull=1 --force-rm=1 foo', quiet=False, use_cache=True),
                    mock.call.local('docker rmi fabricio-temp-image:test old_parent_id', ignore_errors=True, use_cache=True),
                    mock.call.local('docker push test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker tag test:latest fabricio-temp-image:test && docker rmi test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            custom_tag=dict(
                deploy_kwargs=dict(tag='tag'),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.local('docker inspect --type image test:tag', capture=True, use_cache=True, abort_exception=docker.ImageNotFoundError),
                    mock.call.local('docker tag test:tag fabricio-temp-image:test && docker rmi test:tag', ignore_errors=True, use_cache=True),
                    mock.call.local('docker build --tag=test:tag --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('docker rmi fabricio-temp-image:test old_parent_id', ignore_errors=True, use_cache=True),
                    mock.call.local('docker push test:tag', quiet=False, use_cache=True),
                    mock.call.run('docker tag test:tag fabricio-temp-image:test && docker rmi test:tag', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull test:tag', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag='tag', registry=None, account=None),
                    mock.call.update(force=False, tag='tag', registry=None, account=None),
                ],
                image_registry=None,
            ),
            backup_enabled=dict(
                deploy_kwargs=dict(backup='yes'),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.local('docker inspect --type image test:latest', capture=True, use_cache=True, abort_exception=docker.ImageNotFoundError),
                    mock.call.local('docker tag test:latest fabricio-temp-image:test && docker rmi test:latest', ignore_errors=True, use_cache=True),
                    mock.call.local('docker build --tag=test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('docker rmi fabricio-temp-image:test old_parent_id', ignore_errors=True, use_cache=True),
                    mock.call.local('docker push test:latest', quiet=False, use_cache=True),
                    mock.call.backup(),
                    mock.call.run('docker tag test:latest fabricio-temp-image:test && docker rmi test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            explicit_backup_disabled=dict(
                deploy_kwargs=dict(backup='no'),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.local('docker inspect --type image test:latest', capture=True, use_cache=True, abort_exception=docker.ImageNotFoundError),
                    mock.call.local('docker tag test:latest fabricio-temp-image:test && docker rmi test:latest', ignore_errors=True, use_cache=True),
                    mock.call.local('docker build --tag=test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('docker rmi fabricio-temp-image:test old_parent_id', ignore_errors=True, use_cache=True),
                    mock.call.local('docker push test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker tag test:latest fabricio-temp-image:test && docker rmi test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            skip_migrations=dict(
                deploy_kwargs=dict(migrate='no'),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.local('docker inspect --type image test:latest', capture=True, use_cache=True, abort_exception=docker.ImageNotFoundError),
                    mock.call.local('docker tag test:latest fabricio-temp-image:test && docker rmi test:latest', ignore_errors=True, use_cache=True),
                    mock.call.local('docker build --tag=test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('docker rmi fabricio-temp-image:test old_parent_id', ignore_errors=True, use_cache=True),
                    mock.call.local('docker push test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker tag test:latest fabricio-temp-image:test && docker rmi test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            explicit_migrate=dict(
                deploy_kwargs=dict(migrate='yes'),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.local('docker inspect --type image test:latest', capture=True, use_cache=True, abort_exception=docker.ImageNotFoundError),
                    mock.call.local('docker tag test:latest fabricio-temp-image:test && docker rmi test:latest', ignore_errors=True, use_cache=True),
                    mock.call.local('docker build --tag=test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('docker rmi fabricio-temp-image:test old_parent_id', ignore_errors=True, use_cache=True),
                    mock.call.local('docker push test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker tag test:latest fabricio-temp-image:test && docker rmi test:latest', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull test:latest', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            complex=dict(
                deploy_kwargs=dict(force=True, backup=True, tag='tag'),
                init_kwargs=dict(registry='host:4000', build_path='foo', account='account'),
                expected_calls=[
                    mock.call.local('docker inspect --type image host:4000/account/test:tag', capture=True, use_cache=True, abort_exception=docker.ImageNotFoundError),
                    mock.call.local('docker tag host:4000/account/test:tag fabricio-temp-image:test && docker rmi host:4000/account/test:tag', ignore_errors=True, use_cache=True),
                    mock.call.local('docker build --tag=host:4000/account/test:tag --pull=1 --force-rm=1 foo', quiet=False, use_cache=True),
                    mock.call.local('docker rmi fabricio-temp-image:test old_parent_id', ignore_errors=True, use_cache=True),
                    mock.call.local('docker push host:4000/account/test:tag', quiet=False, use_cache=True),
                    mock.call.backup(),
                    mock.call.run('docker tag host:4000/account/test:tag fabricio-temp-image:test && docker rmi host:4000/account/test:tag', ignore_errors=True, use_cache=False),
                    mock.call.run('docker pull host:4000/account/test:tag', quiet=False, use_cache=False, ignore_errors=False),
                    mock.call.run('docker rmi fabricio-temp-image:test', ignore_errors=True, use_cache=False),
                    mock.call.migrate(tag='tag', registry='host:4000', account='account'),
                    mock.call.update(force=True, tag='tag', registry='host:4000', account='account'),
                ],
                image_registry='registry:5000',
            ),
        )
        with mock.patch.object(fabricio, 'local') as local:
            deploy = mock.Mock()
            deploy.attach_mock(backup, 'backup')
            deploy.attach_mock(migrate, 'migrate')
            deploy.attach_mock(update, 'update')
            deploy.attach_mock(run, 'run')
            deploy.attach_mock(local, 'local')
            update.return_value = False
            run.return_value = SucceededResult()
            local.return_value = SucceededResult('[{"Parent": "old_parent_id"}]')
            for case, data in cases.items():
                with self.subTest(case=case):
                    deploy.reset_mock()
                    tasks_list = tasks.ImageBuildDockerTasks(
                        service=docker.Container(
                            name='name',
                            image=docker.Image('test', registry=data['image_registry']),
                        ),
                        hosts=['host'],
                        **data['init_kwargs']
                    )
                    tasks_list.deploy.name = '{0}__{1}'.format(self, case)
                    fab.execute(tasks_list.deploy, **data['deploy_kwargs'])
                    self.assertListEqual(data['expected_calls'], deploy.mock_calls)

    def test_prepare(self):
        cases = dict(
            default=dict(
                kwargs=dict(),
                expected_docker_build_command={
                    'executable': ['docker', 'build'],
                    'tag': 'image:latest',
                    'pull': True,
                    'force-rm': True,
                    'path': '.',
                },
            ),
            no_force_rm=dict(
                kwargs={'force-rm': 'no'},
                expected_docker_build_command={
                    'executable': ['docker', 'build'],
                    'tag': 'image:latest',
                    'pull': True,
                    'path': '.',
                    'force-rm': 0,
                },
            ),
            no_pull=dict(
                kwargs={'pull': 'no'},
                expected_docker_build_command={
                    'executable': ['docker', 'build'],
                    'tag': 'image:latest',
                    'force-rm': True,
                    'path': '.',
                    'pull': 0,
                },
            ),
            complex=dict(
                kwargs={'pull': 'no', 'force-rm': 'no', 'custom': 'custom', 'custom-bool': 'yes'},
                expected_docker_build_command={
                    'executable': ['docker', 'build'],
                    'tag': 'image:latest',
                    'custom-bool': 1,
                    'custom': 'custom',
                    'path': '.',
                    'pull': 0,
                    'force-rm': 0,
                },
            ),
        )

        expected_calls = [
            mock.call('docker inspect --type image image:latest', use_cache=True, capture=True, abort_exception=docker.ImageNotFoundError),
            mock.call('docker tag image:latest fabricio-temp-image:image && docker rmi image:latest', use_cache=True, ignore_errors=True),
            mock.call(mock.ANY, quiet=False, use_cache=True),  # docker build
            mock.call('docker rmi fabricio-temp-image:image old_parent_id', use_cache=True, ignore_errors=True),
        ]

        def test_docker_build_command(command, **kwargs):
            command = command.split(';', 1)[-1].strip()
            if not command.startswith('docker build'):
                return SucceededResult('[{"Parent": "old_parent_id"}]')
            args = shlex.split(command)
            actual_docker_build_command = vars(docker_build_args_parser.parse_args(args))
            self.assertDictEqual(
                expected_docker_build_command,
                actual_docker_build_command,
            )

        for case, data in cases.items():
            with self.subTest(case=case):
                with mock.patch.object(fabricio, 'local', side_effect=test_docker_build_command) as local:
                    expected_docker_build_command = data['expected_docker_build_command']
                    tasks_list = tasks.ImageBuildDockerTasks(
                        service=docker.Container(name='name', image='image'),
                        hosts=['host'],
                    )
                    fab.execute(tasks_list.prepare, **data['kwargs'])
                    self.assertListEqual(local.mock_calls, expected_calls)


class SshTunnelTestCase(unittest.TestCase):

    def test_init(self):
        cases = dict(
            full=dict(
                mapping='bind_address:1111:host:2222',
                expected_bind_address='bind_address',
                expected_port=1111,
                expected_host='host',
                expected_host_port=2222,
            ),
            single_port_int=dict(
                mapping=1111,
                expected_bind_address='127.0.0.1',
                expected_port=1111,
                expected_host='localhost',
                expected_host_port=1111,
            ),
            single_port_str=dict(
                mapping='1111',
                expected_bind_address='127.0.0.1',
                expected_port=1111,
                expected_host='localhost',
                expected_host_port=1111,
            ),
            double_ports=dict(
                mapping='1111:2222',
                expected_bind_address='127.0.0.1',
                expected_port=1111,
                expected_host='localhost',
                expected_host_port=2222,
            ),
            double_ports_with_host=dict(
                mapping='1111:host:2222',
                expected_bind_address='127.0.0.1',
                expected_port=1111,
                expected_host='host',
                expected_host_port=2222,
            ),
        )
        for case, data in cases.items():
            with self.subTest(case):
                tunnel = tasks.SshTunnel(data['mapping'])
                self.assertEqual(tunnel.bind_address, data['expected_bind_address'])
                self.assertEqual(tunnel.port, data['expected_port'])
                self.assertEqual(tunnel.host, data['expected_host'])
                self.assertEqual(tunnel.host_port, data['expected_host_port'])

    def test_init_none_mapping(self):
        self.assertIsNone(tasks.SshTunnel(None))
