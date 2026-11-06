import unittest
from unittest.mock import Mock, patch

from src.open_llm_vtuber.live.classroom_transport import ClassroomTransport


class ClassroomTransportTests(unittest.TestCase):
    def test_one_reader_owned_by_class_and_stopped_with_its_child(self):
        process = Mock(pid=123456, poll=Mock(return_value=None))
        manager = ClassroomTransport()
        with (
            patch(
                "src.open_llm_vtuber.live.classroom_transport.subprocess.Popen",
                return_value=process,
            ) as spawn,
            patch(
                "src.open_llm_vtuber.live.classroom_transport.subprocess.run"
            ) as stop,
            patch("src.open_llm_vtuber.live.classroom_transport.sys.platform", "win32"),
        ):
            manager.sync(True, "@thanhoathirty6")
            manager.sync(True, "@thanhoathirty6")
            spawn.assert_called_once()
            self.assertNotIn("--no-host", spawn.call_args.args[0])
            self.assertIn("@thanhoathirty6", spawn.call_args.args[0])
            manager.sync(False, "@thanhoathirty6")
            self.assertEqual(
                stop.call_args.args[0], ["taskkill", "/PID", "123456", "/T", "/F"]
            )
            process.wait.assert_called_once()
            manager.sync(False, "@thanhoathirty6")
            stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
