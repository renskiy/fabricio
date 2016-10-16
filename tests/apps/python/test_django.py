import mock
import unittest2 as unittest

from fabric import api as fab

import fabricio

from fabricio import docker
from fabricio.apps.python.django import DjangoContainer


class DjangoContainerTestCase(unittest.TestCase):

    @mock.patch.object(docker.Container, 'backup', return_value=mock.Mock())
    @mock.patch.object(fabricio, 'run', return_value=mock.Mock())
    def test_migrate(self, run, backup):
        cases = dict(
            no_new_migrations=dict(
                side_effect=('', ),
                expected_commands=[
                    mock.call.run('docker run --rm --tty image:tag python manage.py showmigrations --plan | egrep "^\[ \]"; true', quiet=True),
                ],
                kwargs=dict(),
                container_class_vars=dict(name='name'),
            ),
            new_migrations=dict(
                side_effect=(
                    '[ ]  app.0001_initial',
                    '',
                ),
                expected_commands=[
                    mock.call.run('docker run --rm --tty image:tag python manage.py showmigrations --plan | egrep "^\[ \]"; true', quiet=True),
                    mock.call.run('docker run --rm --tty image:tag python manage.py migrate --noinput', quiet=False),
                ],
                kwargs=dict(),
                container_class_vars=dict(name='name'),
            ),
            customized=dict(
                side_effect=(
                    '[ ]  app.0001_initial',
                    '',
                ),
                expected_commands=[
                    mock.call.run('docker run --rm --tty registry/image:foo python manage.py showmigrations --plan | egrep "^\[ \]"; true', quiet=True),
                    mock.call.run('docker run --rm --tty registry/image:foo python manage.py migrate --noinput', quiet=False),
                ],
                kwargs=dict(tag='foo', registry='registry'),
                container_class_vars=dict(name='name'),
            ),
            default_with_customized_container=dict(
                side_effect=(
                    '[ ]  app.0001_initial',
                    '',
                ),
                expected_commands=[
                    mock.call.run('docker run --user user --env env --volume volumes --link links --add-host hosts --net network --rm --tty image:tag python manage.py showmigrations --plan | egrep "^\[ \]"; true', quiet=True),
                    mock.call.run('docker run --user user --env env --volume volumes --link links --add-host hosts --net network --rm --tty image:tag python manage.py migrate --noinput', quiet=False),
                ],
                kwargs=dict(),
                container_class_vars=dict(
                    user='user',
                    env='env',
                    volumes='volumes',
                    links='links',
                    hosts='hosts',
                    network='network',

                    cmd='cmd',
                    ports='ports',
                    restart_policy='restart_policy',
                    stop_signal='stop_signal',
                    stop_timeout='stop_timeout',
                ),
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                run.side_effect = data['side_effect']
                migrate = mock.Mock()
                migrate.attach_mock(backup, 'backup')
                migrate.attach_mock(run, 'run')
                TestContainer = type(
                    'TestContainer',
                    (DjangoContainer, ),
                    dict(
                        dict(image=docker.Image('image:tag')),
                        **data['container_class_vars']
                    ),
                )
                container = TestContainer('test')
                with fab.settings(fab.hide('everything')):
                    container.migrate(**data['kwargs'])
                    self.assertListEqual(
                        data['expected_commands'],
                        migrate.mock_calls,
                    )

    def test_migrate_back(self):
        cases = dict(
            no_change=dict(
                side_effect=(
                    '[{"Image": "current_image_id"}]',
                    (
                        'app1.0001_initial\n'
                        'app1.0002_foo\n'
                        'app2.0001_initial\n'
                    ),
                    '[{"Image": "backup_image_id"}]',
                    (
                        'app1.0001_initial\n'
                        'app1.0002_foo\n'
                        'app2.0001_initial\n'
                    ),
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name'),
                    mock.call('docker run --rm --tty current_image_id python manage.py showmigrations --plan | egrep "^\[X\]" | awk "{print \$2}"', quiet=True),
                    mock.call('docker inspect --type container name_backup'),
                    mock.call('docker run --rm --tty backup_image_id python manage.py showmigrations --plan | egrep "^\[X\]" | awk "{print \$2}"', quiet=True),
                ],
            ),
            no_migrations=dict(
                side_effect=(
                    '[{"Image": "current_image_id"}]',
                    '',
                    '[{"Image": "backup_image_id"}]',
                    '',
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name'),
                    mock.call('docker run --rm --tty current_image_id python manage.py showmigrations --plan | egrep "^\[X\]" | awk "{print \$2}"', quiet=True),
                    mock.call('docker inspect --type container name_backup'),
                    mock.call('docker run --rm --tty backup_image_id python manage.py showmigrations --plan | egrep "^\[X\]" | awk "{print \$2}"', quiet=True),
                ],
            ),
            regular=dict(
                side_effect=(
                    '[{"Image": "current_image_id"}]',
                    (
                        'app0.0001_initial\n'
                        'app1.0001_initial\n'
                        'app1.0002_foo\n'
                        'app2.0001_initial\n'
                        'app3.0001_initial\n'
                        'app2.0002_foo\n'
                        'app3.0002_foo\n'
                    ),
                    '[{"Image": "backup_image_id"}]',
                    (
                        'app1.0001_initial\n'
                        'app1.0002_foo\n'
                        'app2.0001_initial\n'
                    ),
                    '',
                    '',
                    '',
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name'),
                    mock.call('docker run --rm --tty current_image_id python manage.py showmigrations --plan | egrep "^\[X\]" | awk "{print \$2}"', quiet=True),
                    mock.call('docker inspect --type container name_backup'),
                    mock.call('docker run --rm --tty backup_image_id python manage.py showmigrations --plan | egrep "^\[X\]" | awk "{print \$2}"', quiet=True),
                    mock.call('docker run --rm --tty current_image_id python manage.py migrate --no-input app3 zero', quiet=False),
                    mock.call('docker run --rm --tty current_image_id python manage.py migrate --no-input app2 0001_initial', quiet=False),
                    mock.call('docker run --rm --tty current_image_id python manage.py migrate --no-input app0 zero', quiet=False),
                ],
            ),
            with_container_custom_options=dict(
                side_effect=(
                    '[{"Image": "current_image_id"}]',
                    (
                        'app0.0001_initial\n'
                        'app1.0001_initial\n'
                        'app1.0002_foo\n'
                        'app2.0001_initial\n'
                        'app3.0001_initial\n'
                        'app2.0002_foo\n'
                        'app3.0002_foo\n'
                    ),
                    '[{"Image": "backup_image_id"}]',
                    (
                        'app1.0001_initial\n'
                        'app1.0002_foo\n'
                        'app2.0001_initial\n'
                    ),
                    '',
                    '',
                    '',
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name'),
                    mock.call('docker run --user user --env env --volume volumes --link links --add-host hosts --net network --rm --tty current_image_id python manage.py showmigrations --plan | egrep "^\[X\]" | awk "{print \$2}"', quiet=True),
                    mock.call('docker inspect --type container name_backup'),
                    mock.call('docker run --user user --env env --volume volumes --link links --add-host hosts --net network --rm --tty backup_image_id python manage.py showmigrations --plan | egrep "^\[X\]" | awk "{print \$2}"', quiet=True),
                    mock.call('docker run --user user --env env --volume volumes --link links --add-host hosts --net network --rm --tty current_image_id python manage.py migrate --no-input app3 zero', quiet=False),
                    mock.call('docker run --user user --env env --volume volumes --link links --add-host hosts --net network --rm --tty current_image_id python manage.py migrate --no-input app2 0001_initial', quiet=False),
                    mock.call('docker run --user user --env env --volume volumes --link links --add-host hosts --net network --rm --tty current_image_id python manage.py migrate --no-input app0 zero', quiet=False),
                ],
                container_class_vars=dict(
                    user='user',
                    env='env',
                    volumes='volumes',
                    links='links',
                    hosts='hosts',
                    network='network',

                    cmd='cmd',
                    ports='ports',
                    restart_policy='restart_policy',
                    stop_signal='stop_signal',
                    stop_timeout='stop_timeout',
                ),
            ),
            current_container_not_found=dict(
                side_effect=(
                    RuntimeError,
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name'),
                ],
            ),
            backup_container_not_found=dict(
                side_effect=(
                    '[{"Image": "current_image_id"}]',
                    (
                        'app1.0001_initial\n'
                    ),
                    RuntimeError,
                ),
                expected_commands=[
                    mock.call('docker inspect --type container name'),
                    mock.call('docker run --rm --tty current_image_id python manage.py showmigrations --plan | egrep "^\[X\]" | awk "{print \$2}"', quiet=True),
                    mock.call('docker inspect --type container name_backup'),
                ],
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                side_effect = data['side_effect']
                expected_commands = data['expected_commands']
                with mock.patch.object(
                    fabricio,
                    'run',
                    side_effect=side_effect,
                ) as run:
                    TestContainer = type(
                        'TestContainer',
                        (DjangoContainer, ),
                        dict(
                            dict(image=docker.Image('image:tag')),
                            **data.get('container_class_vars', {})
                        ),
                    )
                    container = TestContainer(name='name')
                    container.migrate_back()
                    run.assert_has_calls(expected_commands)
                    self.assertEqual(
                        len(expected_commands),
                        run.call_count,
                    )
