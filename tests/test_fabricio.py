import mock
import unittest2 as unittest

from fabric import api as fab

import fabricio

from fabricio import tasks


class FabricioTestCase(unittest.TestCase):

    def setUp(self):
        self.fab_settings = fab.settings(fab.hide('everything'))
        self.fab_settings.__enter__()
        fab.env.infrastructure = None

    def tearDown(self):
        self.fab_settings.__exit__(None, None, None)

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
        
                with self.assertRaises(RuntimeError):
                    callback('command', use_cache=True)
        
                with self.assertRaises(RuntimeError):
                    callback('command', use_cache=True)
        
                self.assertEqual(2, mocked_method.call_count)
                mocked_method.reset_mock()
        
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
        
                @tasks.infrastructure
                def inf1(): pass
        
                @tasks.infrastructure
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
