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
from tests import docker_build_args_parser


class TestContainer(docker.Container):

    image = docker.Image('test')


class TestCase(unittest.TestCase):

    def setUp(self):
        self.stderr = sys.stderr
        sys.stderr = six.BytesIO()

    def tearDown(self):
        sys.stderr = self.stderr

    def test_skip_unknown_host(self):

        mocked_task = mock.Mock()

        @fabricio.tasks.skip_unknown_host
        def task():
            mocked_task()

        with fab.settings(fab.hide('everything')):
            fab.execute(task)
            mocked_task.assert_not_called()

            fab.execute(task, host='host')
            mocked_task.assert_called_once()

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
            with_custom_name=dict(
                decorator=tasks.infrastructure(name='infrastructure'),
                expected_infrastructure='infrastructure',
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

    def test__uncrawl(self):
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
                        tasks._uncrawl(data['command']),
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


class DockerTasksTestCase(unittest.TestCase):

    maxDiff = None

    def setUp(self):
        self.stderr, sys.stderr = sys.stderr, six.BytesIO()
        self.fab_settings = fab.settings(fab.hide('everything'))
        self.fab_settings.__enter__()

    def tearDown(self):
        self.fab_settings.__exit__(None, None, None)
        sys.stderr = self.stderr

    def test_commands_list(self):
        cases = dict(
            default=dict(
                init_kwargs=dict(service='service'),
                expected_commands_list=['upgrade', 'rollback', 'deploy'],
                unexpected_commands_list=['revert', 'migrate', 'migrate-back', 'backup', 'restore', 'pull', 'update', 'prepare', 'push'],
            ),
            prepare_tasks=dict(
                init_kwargs=dict(service='service', registry='registry'),
                expected_commands_list=['rollback', 'deploy', 'prepare', 'push', 'upgrade'],
                unexpected_commands_list=['backup', 'restore', 'migrate', 'migrate-back', 'pull', 'update', 'revert'],
            ),
            migrate_tasks=dict(
                init_kwargs=dict(service='service', migrate_commands=True),
                expected_commands_list=['rollback', 'deploy', 'migrate', 'migrate-back', 'upgrade'],
                unexpected_commands_list=['backup', 'restore', 'prepare', 'push', 'pull', 'update', 'revert'],
            ),
            backup_tasks=dict(
                init_kwargs=dict(service='service', backup_commands=True),
                expected_commands_list=['rollback', 'deploy', 'backup', 'restore', 'upgrade'],
                unexpected_commands_list=['migrate', 'migrate-back', 'prepare', 'push', 'pull', 'update', 'revert'],
            ),
            revert_task=dict(
                init_kwargs=dict(service='service', revert_command=True),
                expected_commands_list=['rollback', 'deploy', 'revert', 'upgrade'],
                unexpected_commands_list=['migrate', 'migrate-back', 'prepare', 'push', 'pull', 'update', 'backup', 'restore'],
            ),
            pull_task=dict(
                init_kwargs=dict(service='service', pull_command=True),
                expected_commands_list=['rollback', 'deploy', 'pull', 'upgrade'],
                unexpected_commands_list=['migrate', 'migrate-back', 'prepare', 'push', 'revert', 'update', 'backup', 'restore'],
            ),
            update_task=dict(
                init_kwargs=dict(service='service', update_command=True),
                expected_commands_list=['rollback', 'deploy', 'update', 'upgrade'],
                unexpected_commands_list=['migrate', 'migrate-back', 'prepare', 'push', 'pull', 'revert', 'backup', 'restore'],
            ),
            all_tasks=dict(
                init_kwargs=dict(service='service', backup_commands=True, migrate_commands=True, registry='registry', revert_command=True, update_command=True, pull_command=True),
                expected_commands_list=['pull', 'rollback', 'update', 'deploy', 'backup', 'restore', 'migrate', 'migrate-back', 'prepare', 'push', 'revert', 'upgrade'],
                unexpected_commands_list=[],
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                tasks_list = tasks.DockerTasks(**data['init_kwargs'])
                docstring, new_style, classic, default = load_tasks_from_module(tasks_list)
                for expected_command in data['expected_commands_list']:
                    self.assertIn(expected_command, new_style)
                for unexpected_command in data['unexpected_commands_list']:
                    self.assertNotIn(unexpected_command, new_style)

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

    def test_pull_raises_error_if_ssh_tunnel_credentials_can_not_be_obtained(self):
        tasks_list = tasks.DockerTasks(
            service=docker.Container(name='name', image='image'),
            ssh_tunnel_port=1234,
            hosts=['host'],
        )
        with self.assertRaises(ValueError):
            fab.execute(tasks_list.pull)

    @mock.patch.multiple(docker.Container, backup=mock.DEFAULT, migrate=mock.DEFAULT, update=mock.DEFAULT)
    @mock.patch.multiple(fabricio, run=mock.DEFAULT, local=mock.DEFAULT)
    @mock.patch.object(fab, 'remote_tunnel', return_value=mock.MagicMock())
    def test_deploy(self, remote_tunnel, run, local, backup, migrate, update):
        cases = dict(
            default=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.run('docker pull test:latest', quiet=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            custom_image_registry=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.run('docker pull registry:5000/test:latest', quiet=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry='registry:5000',
            ),
            custom_image_registry_with_ssh_tunnel=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(ssh_tunnel_port=1234),
                expected_calls=[
                    mock.call.run('docker pull localhost:1234/test:latest', quiet=False),
                    mock.call.migrate(tag=None, registry='localhost:1234', account=None),
                    mock.call.update(force=False, tag=None, registry='localhost:1234', account=None),
                ],
                image_registry='registry:5000',
            ),
            custom_registry=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(registry='host:5000'),
                expected_calls=[
                    mock.call.local('docker pull test:latest', quiet=False, use_cache=True),
                    mock.call.local('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                    mock.call.local('docker tag test:latest host:5000/test:latest', use_cache=True),
                    mock.call.local('docker push host:5000/test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi host:5000/test:latest', use_cache=True),
                    mock.call.run('docker pull host:5000/test:latest', quiet=False),
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
            custom_registry_with_ssh_tunnel=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(registry='host:5000', ssh_tunnel_port=1234),
                expected_calls=[
                    mock.call.local('docker pull test:latest', quiet=False, use_cache=True),
                    mock.call.local('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                    mock.call.local('docker tag test:latest host:5000/test:latest', use_cache=True),
                    mock.call.local('docker push host:5000/test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi host:5000/test:latest', use_cache=True),
                    mock.call.run('docker pull localhost:1234/test:latest', quiet=False),
                    mock.call.migrate(tag=None, registry='localhost:1234', account=None),
                    mock.call.update(force=False, tag=None, registry='localhost:1234', account=None),
                ],
                image_registry=None,
            ),
            custom_registry_with_ssh_tunnel_no_image=dict(
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
                    mock.call.local('docker pull test:latest', quiet=False, use_cache=True),
                    mock.call.local('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                    mock.call.local('docker tag test:latest account/test:latest', use_cache=True),
                    mock.call.local('docker push account/test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi account/test:latest', use_cache=True),
                    mock.call.run('docker pull account/test:latest', quiet=False),
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
            custom_account_with_ssh_tunnel=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(account='account', ssh_tunnel_port=1234),
                expected_calls=[
                    mock.call.local('docker pull registry:5000/test:latest', quiet=False, use_cache=True),
                    mock.call.local('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                    mock.call.local('docker tag registry:5000/test:latest registry:5000/account/test:latest', use_cache=True),
                    mock.call.local('docker push registry:5000/account/test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi registry:5000/account/test:latest', use_cache=True),
                    mock.call.run('docker pull localhost:1234/account/test:latest', quiet=False),
                    mock.call.migrate(tag=None, registry='localhost:1234', account='account'),
                    mock.call.update(force=False, tag=None, registry='localhost:1234', account='account'),
                ],
                image_registry='registry:5000',
            ),
            custom_registry_and_image_registry=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(registry='host:4000'),
                expected_calls=[
                    mock.call.local('docker pull registry:5000/test:latest', quiet=False, use_cache=True),
                    mock.call.local('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                    mock.call.local('docker tag registry:5000/test:latest host:4000/test:latest', use_cache=True),
                    mock.call.local('docker push host:4000/test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi host:4000/test:latest', use_cache=True),
                    mock.call.run('docker pull host:4000/test:latest', quiet=False),
                    mock.call.migrate(tag=None, registry='host:4000', account=None),
                    mock.call.update(force=False, tag=None, registry='host:4000', account=None),
                ],
                image_registry='registry:5000',
            ),
            custom_registry_and_image_registry_with_ssh_tunnel=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(registry='host:4000', ssh_tunnel_port=1234),
                expected_calls=[
                    mock.call.local('docker pull registry:5000/test:latest', quiet=False, use_cache=True),
                    mock.call.local('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                    mock.call.local('docker tag registry:5000/test:latest host:4000/test:latest', use_cache=True),
                    mock.call.local('docker push host:4000/test:latest', quiet=False, use_cache=True),
                    mock.call.local('docker rmi host:4000/test:latest', use_cache=True),
                    mock.call.run('docker pull localhost:1234/test:latest', quiet=False),
                    mock.call.migrate(tag=None, registry='localhost:1234', account=None),
                    mock.call.update(force=False, tag=None, registry='localhost:1234', account=None),
                ],
                image_registry='registry:5000',
            ),
            forced=dict(
                deploy_kwargs=dict(force='yes'),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.run('docker pull test:latest', quiet=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=True, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            explicit_not_forced=dict(
                deploy_kwargs=dict(force='no'),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.run('docker pull test:latest', quiet=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            custom_tag=dict(
                deploy_kwargs=dict(tag='tag'),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.run('docker pull test:tag', quiet=False),
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
                    mock.call.run('docker pull test:latest', quiet=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            explicit_backup_disabled=dict(
                deploy_kwargs=dict(backup='no'),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.run('docker pull test:latest', quiet=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            skip_migrations=dict(
                deploy_kwargs=dict(migrate='no'),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.run('docker pull test:latest', quiet=False),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            explicit_migrate=dict(
                deploy_kwargs=dict(migrate='yes'),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.run('docker pull test:latest', quiet=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            complex=dict(
                deploy_kwargs=dict(force=True, backup=True, tag='tag'),
                init_kwargs=dict(registry='host:4000', ssh_tunnel_port=1234, account='account'),
                expected_calls=[
                    mock.call.local('docker pull registry:5000/test:tag', quiet=False, use_cache=True),
                    mock.call.local('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                    mock.call.local('docker tag registry:5000/test:tag host:4000/account/test:tag', use_cache=True),
                    mock.call.local('docker push host:4000/account/test:tag', quiet=False, use_cache=True),
                    mock.call.local('docker rmi host:4000/account/test:tag', use_cache=True),
                    mock.call.backup(),
                    mock.call.run('docker pull localhost:1234/account/test:tag', quiet=False),
                    mock.call.migrate(tag='tag', registry='localhost:1234', account='account'),
                    mock.call.update(force=True, tag='tag', registry='localhost:1234', account='account'),
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

    def test_delete_dangling_images(self):
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
                    mock.call.local('docker build --tag=test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                    mock.call.local('docker push test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker pull test:latest', quiet=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            custom_image_registry=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.local('docker build --tag=registry:5000/test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                    mock.call.local('docker push registry:5000/test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker pull registry:5000/test:latest', quiet=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry='registry:5000',
            ),
            custom_image_registry_with_ssh_tunnel=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(ssh_tunnel_port=1234),
                expected_calls=[
                    mock.call.local('docker build --tag=registry:5000/test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                    mock.call.local('docker push registry:5000/test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker pull localhost:1234/test:latest', quiet=False),
                    mock.call.migrate(tag=None, registry='localhost:1234', account=None),
                    mock.call.update(force=False, tag=None, registry='localhost:1234', account=None),
                ],
                image_registry='registry:5000',
            ),
            custom_registry=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(registry='host:5000'),
                expected_calls=[
                    mock.call.local('docker build --tag=host:5000/test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                    mock.call.local('docker push host:5000/test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker pull host:5000/test:latest', quiet=False),
                    mock.call.migrate(tag=None, registry='host:5000', account=None),
                    mock.call.update(force=False, tag=None, registry='host:5000', account=None),
                ],
                image_registry=None,
            ),
            custom_registry_with_ssh_tunnel=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(registry='host:5000', ssh_tunnel_port=1234),
                expected_calls=[
                    mock.call.local('docker build --tag=host:5000/test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                    mock.call.local('docker push host:5000/test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker pull localhost:1234/test:latest', quiet=False),
                    mock.call.migrate(tag=None, registry='localhost:1234', account=None),
                    mock.call.update(force=False, tag=None, registry='localhost:1234', account=None),
                ],
                image_registry=None,
            ),
            custom_account=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(account='account'),
                expected_calls=[
                    mock.call.local('docker build --tag=account/test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                    mock.call.local('docker push account/test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker pull account/test:latest', quiet=False),
                    mock.call.migrate(tag=None, registry=None, account='account'),
                    mock.call.update(force=False, tag=None, registry=None, account='account'),
                ],
                image_registry=None,
            ),
            custom_account_with_ssh_tunnel=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(account='account', ssh_tunnel_port=1234),
                expected_calls=[
                    mock.call.local('docker build --tag=host:5000/account/test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                    mock.call.local('docker push host:5000/account/test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker pull localhost:1234/account/test:latest', quiet=False),
                    mock.call.migrate(tag=None, registry='localhost:1234', account='account'),
                    mock.call.update(force=False, tag=None, registry='localhost:1234', account='account'),
                ],
                image_registry='host:5000',
            ),
            custom_registry_and_image_registry=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(registry='host:4000'),
                expected_calls=[
                    mock.call.local('docker build --tag=host:4000/test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                    mock.call.local('docker push host:4000/test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker pull host:4000/test:latest', quiet=False),
                    mock.call.migrate(tag=None, registry='host:4000', account=None),
                    mock.call.update(force=False, tag=None, registry='host:4000', account=None),
                ],
                image_registry='registry:5000',
            ),
            custom_registry_and_image_registry_with_ssh_tunnel=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(registry='host:4000', ssh_tunnel_port=1234),
                expected_calls=[
                    mock.call.local('docker build --tag=host:4000/test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                    mock.call.local('docker push host:4000/test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker pull localhost:1234/test:latest', quiet=False),
                    mock.call.migrate(tag=None, registry='localhost:1234', account=None),
                    mock.call.update(force=False, tag=None, registry='localhost:1234', account=None),
                ],
                image_registry='registry:5000',
            ),
            forced=dict(
                deploy_kwargs=dict(force='yes'),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.local('docker build --tag=test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                    mock.call.local('docker push test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker pull test:latest', quiet=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=True, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            explicit_not_forced=dict(
                deploy_kwargs=dict(force='no'),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.local('docker build --tag=test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                    mock.call.local('docker push test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker pull test:latest', quiet=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            custom_build_path=dict(
                deploy_kwargs=dict(),
                init_kwargs=dict(build_path='foo'),
                expected_calls=[
                    mock.call.local('docker build --tag=test:latest --pull=1 --force-rm=1 foo', quiet=False, use_cache=True),
                    mock.call.local('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                    mock.call.local('docker push test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker pull test:latest', quiet=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            custom_tag=dict(
                deploy_kwargs=dict(tag='tag'),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.local('docker build --tag=test:tag --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                    mock.call.local('docker push test:tag', quiet=False, use_cache=True),
                    mock.call.run('docker pull test:tag', quiet=False),
                    mock.call.migrate(tag='tag', registry=None, account=None),
                    mock.call.update(force=False, tag='tag', registry=None, account=None),
                ],
                image_registry=None,
            ),
            backup_enabled=dict(
                deploy_kwargs=dict(backup='yes'),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.local('docker build --tag=test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                    mock.call.local('docker push test:latest', quiet=False, use_cache=True),
                    mock.call.backup(),
                    mock.call.run('docker pull test:latest', quiet=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            explicit_backup_disabled=dict(
                deploy_kwargs=dict(backup='no'),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.local('docker build --tag=test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                    mock.call.local('docker push test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker pull test:latest', quiet=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            skip_migrations=dict(
                deploy_kwargs=dict(migrate='no'),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.local('docker build --tag=test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                    mock.call.local('docker push test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker pull test:latest', quiet=False),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            explicit_migrate=dict(
                deploy_kwargs=dict(migrate='yes'),
                init_kwargs=dict(),
                expected_calls=[
                    mock.call.local('docker build --tag=test:latest --pull=1 --force-rm=1 .', quiet=False, use_cache=True),
                    mock.call.local('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                    mock.call.local('docker push test:latest', quiet=False, use_cache=True),
                    mock.call.run('docker pull test:latest', quiet=False),
                    mock.call.migrate(tag=None, registry=None, account=None),
                    mock.call.update(force=False, tag=None, registry=None, account=None),
                ],
                image_registry=None,
            ),
            complex=dict(
                deploy_kwargs=dict(force=True, backup=True, tag='tag'),
                init_kwargs=dict(registry='host:4000', ssh_tunnel_port=1234, build_path='foo', account='account'),
                expected_calls=[
                    mock.call.local('docker build --tag=host:4000/account/test:tag --pull=1 --force-rm=1 foo', quiet=False, use_cache=True),
                    mock.call.local('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                    mock.call.local('docker push host:4000/account/test:tag', quiet=False, use_cache=True),
                    mock.call.backup(),
                    mock.call.run('docker pull localhost:1234/account/test:tag', quiet=False),
                    mock.call.migrate(tag='tag', registry='localhost:1234', account='account'),
                    mock.call.update(force=True, tag='tag', registry='localhost:1234', account='account'),
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
                expected_calls=[
                    mock.call(mock.ANY, quiet=False, use_cache=True),
                    mock.call('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                ],
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
                expected_calls=[
                    mock.call(mock.ANY, quiet=False, use_cache=True),
                    mock.call('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                ],
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
                expected_calls=[
                    mock.call(mock.ANY, quiet=False, use_cache=True),
                    mock.call('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                ],
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
                expected_calls=[
                    mock.call(mock.ANY, quiet=False, use_cache=True),
                    mock.call('for img in $(docker images --filter "dangling=true" --quiet); do docker rmi "$img"; done', ignore_errors=True),
                ],
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

        def test_docker_build_command(command, **kwargs):
            command = command.split(';', 1)[-1].strip()
            if not command.startswith('docker build'):
                return
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
                    self.assertListEqual(local.mock_calls, data['expected_calls'])

    def test_prepare_and_push_are_in_the_commands_list_by_default(self):
        init_kwargs = dict(service='service')
        expected_commands_list = ['prepare', 'push']
        tasks_list = tasks.ImageBuildDockerTasks(**init_kwargs)
        docstring, new_style, classic, default = load_tasks_from_module(tasks_list)
        for expected_command in expected_commands_list:
            self.assertIn(expected_command, new_style)
