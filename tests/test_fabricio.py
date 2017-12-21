import mock
import unittest2 as unittest

from fabric import api as fab

import fabricio

from tests import SucceededResult


class FabricioTestCase(unittest.TestCase):

    def setUp(self):
        self.fab_settings = fab.settings(fab.hide('everything'))
        self.fab_settings.__enter__()
        fab.env.infrastructure = None

    def tearDown(self):
        self.fab_settings.__exit__(None, None, None)
        fabricio.run.cache.clear()
        fabricio.local.cache.clear()

    @mock.patch.object(fab, 'run', return_value=type('', (), {'failed': True}))
    @mock.patch.object(fab, 'local', return_value=type('', (), {'failed': True}))
    def test_local_and_run(self, local, run):
        cases = dict(
            local=dict(
                mock=local,
                callback=fabricio.local,
            ),
            run=dict(
                mock=run,
                callback=fabricio.run,
            ),
        )
        for case, data in cases.items():
            with self.subTest(case=case):
                mocked_method = data['mock']
                callback = data['callback']
                mocked_method.__name__ = 'mock'

                callback.cache.clear()

                mocked_method.side_effect = RuntimeError
                with self.assertRaises(RuntimeError):
                    callback('command', use_cache=True)
        
                with self.assertRaises(RuntimeError):
                    callback('command', use_cache=True)
        
                self.assertEqual(2, mocked_method.call_count)
                mocked_method.reset_mock()

                mocked_method.side_effect = None
                callback('command', ignore_errors=True)
                callback('command', ignore_errors=True)
                self.assertEqual(2, mocked_method.call_count)
                mocked_method.reset_mock()

                callback('command', ignore_errors=True, use_cache=True)
                callback('command', ignore_errors=True, use_cache=True)
                mocked_method.assert_called_once()
                mocked_method.reset_mock()

                callback('command1', ignore_errors=True, use_cache=True)
                callback('command2', ignore_errors=True, use_cache=True)
                self.assertEqual(2, mocked_method.call_count)
                mocked_method.reset_mock()
                callback.cache.clear()

                @fabricio.infrastructure
                def inf1(): pass

                @fabricio.infrastructure
                def inf2(): pass

                fab.execute(inf1.confirm)
                callback('command', ignore_errors=True, use_cache=True)
                fab.execute(inf2.confirm)
                callback('command', ignore_errors=True, use_cache=True)
                mocked_method.assert_called_once()
                mocked_method.reset_mock()

        fab.env.host = 'host1'
        fabricio.run('command', ignore_errors=True, use_cache=True)
        fabricio.run('command', ignore_errors=True, use_cache=True)
        self.assertEqual(1, run.call_count)
        fab.env.host = 'host2'
        fabricio.run('command', ignore_errors=True, use_cache=True)
        fabricio.run('command', ignore_errors=True, use_cache=True)
        self.assertEqual(2, run.call_count)
        run.reset_mock()

    def test_run_with_cache_key(self):
        with mock.patch.object(fab, 'run', return_value=SucceededResult()) as run:
            run.__name__ = 'mocked_run'

            fabricio.run('command', use_cache=True)
            self.assertEqual(run.call_count, 1)
            fabricio.run('command', use_cache=True)
            self.assertEqual(run.call_count, 1)

            fabricio.run('command', cache_salt='key1', use_cache=True)
            self.assertEqual(run.call_count, 2)
            fabricio.run('command', cache_salt='key1', use_cache=True)
            self.assertEqual(run.call_count, 2)

            fabricio.run('command', cache_salt='key2', use_cache=True)
            self.assertEqual(run.call_count, 3)
            fabricio.run('command', cache_salt='key2', use_cache=True)
            self.assertEqual(run.call_count, 3)
