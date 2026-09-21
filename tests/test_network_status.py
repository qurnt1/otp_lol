import unittest
from unittest.mock import Mock

from src.services.network_status import NetworkStatusService


class NetworkStatusServiceTests(unittest.TestCase):
    def test_probe_failure_is_reported_as_offline_and_published(self):
        broker = Mock()
        service = NetworkStatusService(broker, probe=lambda: (False, "timeout"))

        status = service.check()

        self.assertEqual(status["state"], "offline")
        self.assertFalse(status["online"])
        self.assertEqual(status["reason"], "timeout")
        broker.publish.assert_called_once_with("network_status", status)

    def test_recent_result_is_reused_until_a_forced_check(self):
        probe = Mock(side_effect=[(True, None), (False, "request_error")])
        service = NetworkStatusService(probe=probe)

        first = service.check()
        cached = service.check()
        forced = service.check(force=True)

        self.assertTrue(first["online"])
        self.assertEqual(cached, first)
        self.assertFalse(forced["online"])
        self.assertEqual(probe.call_count, 2)


if __name__ == "__main__":
    unittest.main()
