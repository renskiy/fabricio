import mock
import unittest2 as unittest

from fabric import api as fab

import fabricio

from fabricio import tasks


class FabricioTestCase(unittest.TestCase):

    def setUp(self):
        self.fab_settings = fab.settings(fab.hide('everything'))
        self.fab_settings.__enter__()
        fab.env.pop('infrastructure', None)

    def tearDown(self):
        self.fab_settings.__exit__(None, None, None)

    @mock.patch.object(fab, 'local', return_value=type('', (), {'failed': True}))
    def test_local(self, local):
        local.__name__ = 'mock'

        with self.assertRaises(RuntimeError):
            fabricio.local('command', use_cache=True)

        with self.assertRaises(RuntimeError):
            fabricio.local('command', use_cache=True)

        local.assert_has_calls([
            mock.call('command'),
            mock.call('command'),
        ])
        self.assertEqual(2, local.call_count)
        local.reset_mock()

        fabricio.local('command', ignore_errors=True)
        fabricio.local('command', ignore_errors=True)
        local.assert_has_calls([
            mock.call('command'),
            mock.call('command'),
        ])
        self.assertEqual(2, local.call_count)
        local.reset_mock()

        fabricio.local('command', ignore_errors=True, use_cache=True)
        fabricio.local('command', ignore_errors=True, use_cache=True)
        local.assert_called_once_with('command')
        local.reset_mock()

        fabricio.local('command1', ignore_errors=True, use_cache=True)
        fabricio.local('command2', ignore_errors=True, use_cache=True)
        local.assert_has_calls([
            mock.call('command1'),
            mock.call('command2'),
        ])
        self.assertEqual(2, local.call_count)
        local.reset_mock()
        fabricio.local.cache.clear()

        @tasks.infrastructure
        def inf1(): pass

        @tasks.infrastructure
        def inf2(): pass

        fab.execute(inf1.confirm)
        fabricio.local('command', ignore_errors=True, use_cache=True)
        fab.execute(inf2.confirm)
        fabricio.local('command', ignore_errors=True, use_cache=True)
        local.assert_called_once_with('command')
        local.reset_mock()

    @mock.patch.object(fab, 'run', return_value=type('', (), {'failed': True}))
    def test_run(self, run):
        run.__name__ = 'mock'

        with self.assertRaises(RuntimeError):
            fabricio.run('command', use_cache=True)

        with self.assertRaises(RuntimeError):
            fabricio.run('command', use_cache=True)

        run.assert_has_calls([
            mock.call('command', stdout=mock.ANY, stderr=mock.ANY),
            mock.call('command', stdout=mock.ANY, stderr=mock.ANY),
        ])
        self.assertEqual(2, run.call_count)
        run.reset_mock()

        fabricio.run('command', ignore_errors=True)
        fabricio.run('command', ignore_errors=True)
        run.assert_has_calls([
            mock.call('command', stdout=mock.ANY, stderr=mock.ANY),
            mock.call('command', stdout=mock.ANY, stderr=mock.ANY),
        ])
        self.assertEqual(2, run.call_count)
        run.reset_mock()

        fabricio.run('command', ignore_errors=True, use_cache=True)
        fabricio.run('command', ignore_errors=True, use_cache=True)
        run.assert_called_once_with('command', stdout=mock.ANY, stderr=mock.ANY)
        run.reset_mock()

        fabricio.run('command1', ignore_errors=True, use_cache=True)
        fabricio.run('command2', ignore_errors=True, use_cache=True)
        run.assert_has_calls([
            mock.call('command1', stdout=mock.ANY, stderr=mock.ANY),
            mock.call('command2', stdout=mock.ANY, stderr=mock.ANY),
        ])
        self.assertEqual(2, run.call_count)
        run.reset_mock()

        @tasks.infrastructure
        def inf1(): pass

        @tasks.infrastructure
        def inf2(): pass

        fabricio.run.cache.clear()
        fabricio.run('command', ignore_errors=True, use_cache=True)
        fab.execute(inf1.confirm)
        fabricio.run('command', ignore_errors=True, use_cache=True)
        fab.execute(inf2.confirm)
        fabricio.run('command', ignore_errors=True, use_cache=True)
        self.assertEqual(3, run.call_count)
        run.assert_has_calls([
            mock.call('command', stdout=mock.ANY, stderr=mock.ANY),
        ] * 3)
        run.reset_mock()
