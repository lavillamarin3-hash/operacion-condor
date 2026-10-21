import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("user_service", Path(__file__).with_name("user_service.py"))
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


class UserServiceSafetyTests(unittest.TestCase):
    def test_process_match_requires_uid_exact_argv_and_start_ticks(self):
        record = {"pid":123,"uid":1000,"start_ticks":"99"}
        actual = dict(record, argv=["python", "own-helper", "serve"], state="S")
        argv = actual["argv"]
        with patch.object(service.os, "getuid", return_value=1000, create=True), patch.object(service, "process_identity", return_value=actual):
            self.assertTrue(service.matches_process(record, argv))
            self.assertFalse(service.matches_process(record, ["python", "another-service"]))
            self.assertFalse(service.matches_process(dict(record,uid=1001), argv))
            self.assertFalse(service.matches_process(dict(record,start_ticks="100"), argv))
            self.assertFalse(service.matches_process(None, argv))

    def test_stale_pid_cannot_trigger_any_signal(self):
        with patch.object(service, "read_record", return_value={"pid":123}), patch.object(service,"matches_process",return_value=False), patch.object(service,"signal_owned_manager") as signalling:
            service.stop(Path("/home/test/.ctf-condor"))
        signalling.assert_not_called()

    def test_private_file_must_have_exact_mode_and_current_owner(self):
        info = type("Info", (), {"st_mode":0o100644,"st_uid":1000})()
        with patch.object(service.os,"getuid",return_value=1000,create=True), patch.object(Path,"lstat",return_value=info), patch.object(service.subprocess,"run") as child:
            with self.assertRaisesRegex(RuntimeError,"permisos 600"):
                service.private_environment(Path("/home/test/.ctf-condor"))
        child.assert_not_called()

    def test_runtime_rejects_public_ip_and_privileged_port(self):
        for value in ('{"host":"8.8.8.8","port":18083}', '{"host":"192.168.146.137","port":80}'):
            with self.subTest(value=value), patch.object(Path,"read_text",return_value=value), self.assertRaises(RuntimeError):
                service.runtime(Path("/home/test/.ctf-condor"))

    def test_health_check_cannot_accept_unowned_or_foreign_listener(self):
        with patch.object(service,"matches_process",return_value=False), patch.object(service,"build_opener") as opener:
            self.assertFalse(service.ready(Path("/home/test/.ctf-condor"), None))
        opener.assert_not_called()
        record = {"release":"/home/test/.ctf-condor/releases/test","child":{"pid":123}}
        with patch.object(service,"matches_process",return_value=True), patch.object(service,"runtime",return_value=("192.168.146.137",18083)), patch.object(service,"owns_listener",return_value=False), patch.object(service,"build_opener") as opener:
            self.assertFalse(service.ready(Path("/home/test/.ctf-condor"), record))
        opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
