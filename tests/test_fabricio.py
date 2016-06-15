import mock
import unittest2 as unittest

from fabric import api as fab

import fabricio


class FabricioTestCase(unittest.TestCase):

    @mock.patch.object(fab, 'local', return_value=type('', (), {'failed': True}))
    def test_local(self, local):
        with fab.settings(fab.hide('everything')):
            local.__name__ = 'mock'

            try:
                fabricio.local('command', use_cache=True)
            except RuntimeError:
                pass
            try:
                fabricio.local('command', use_cache=True)
            except RuntimeError:
                pass
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
