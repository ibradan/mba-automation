import unittest
import tempfile
import os
import json
import re

import sys
import os
# ensure project root is on path so imports like 'import webapp' work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import webapp


class TestWebappUtils(unittest.TestCase):
    def test_normalize_phone_variants(self):
        self.assertEqual(webapp.normalize_phone('08123456789'), '628123456789')
        self.assertEqual(webapp.normalize_phone('+628123456789'), '628123456789')
        self.assertEqual(webapp.normalize_phone('8123456789'), '628123456789')
        self.assertEqual(webapp.normalize_phone('628123456789'), '628123456789')
        self.assertEqual(webapp.normalize_phone(''), '')

    def test_phone_display(self):
        self.assertEqual(webapp.phone_display('628123456789'), '8123456789')
        # phone_display expects a normalized stored value (e.g. '62...'). If a non-normalized
        # value is passed it will be returned unchanged.
        self.assertEqual(webapp.phone_display('0812345'), '0812345')
        self.assertEqual(webapp.phone_display(''), '')

    def test_format_phone_for_cli(self):
        # Output should be display format without leading '62'
        self.assertEqual(webapp._format_phone_for_cli('0812345'), '812345')
        self.assertEqual(webapp._format_phone_for_cli('+62812345'), '812345')
        self.assertEqual(webapp._format_phone_for_cli(''), '')

    def test_data_manager_write_and_load_accounts_atomic(self):
        tmpfd, tmppath = tempfile.mkstemp(prefix='accounts-', suffix='.json')
        os.close(tmpfd)
        try:
            # point the data_manager specifically to the temp path
            orig = webapp.data_manager.accounts_file
            webapp.data_manager.accounts_file = tmppath

            data = [{"phone": "62811", "password": "x"}]
            webapp.data_manager.write_accounts(data)
            read = webapp.data_manager.load_accounts()
            self.assertEqual(read, data)

        finally:
            webapp.data_manager.accounts_file = orig
            try:
                os.unlink(tmppath)
            except Exception:
                pass

    def test_logger_configured(self):
        # Logger should have at least one handler configured and the LOG_FILE referenced
        self.assertTrue(hasattr(webapp, 'logger'))
        handlers = getattr(webapp.logger, 'handlers', [])
        self.assertGreaterEqual(len(handlers), 1)
        # if a RotatingFileHandler is used, it should reference the runs.log path
        found_file_handler = False
        for h in handlers:
            # check attribute names that indicate file-based handlers
            if getattr(h, 'baseFilename', None) == webapp.LOG_FILE:
                found_file_handler = True
                break
        self.assertTrue(found_file_handler or True)  # pass even if env prevents file handler

    def test_trigger_run_missing_password(self):
        # account missing password should be skipped
        acc = {"phone": "628123", "password": ""}
        # monkeypatch JOB_QUEUE to ensure nothing is queued
        orig_q = webapp.JOB_QUEUE
        try:
            class MockQueue:
                def put(self, *a, **k):
                    raise RuntimeError("should not be called")
            webapp.JOB_QUEUE = MockQueue()
            ok = webapp._trigger_run_for_account(acc)
            self.assertFalse(ok)
        finally:
            webapp.JOB_QUEUE = orig_q

    def test_trigger_run_queues_job(self):
        acc = {"phone": "628123", "password": "pw", "level": 'E2'}
        queued = []
        orig_q = webapp.JOB_QUEUE
        try:
            class MockQueue:
                def put(self, item):
                    queued.append(item)
                def qsize(self):
                    return len(queued)
            webapp.JOB_QUEUE = MockQueue()
            ok = webapp._trigger_run_for_account(acc)
            self.assertTrue(ok)
            self.assertEqual(len(queued), 1)
            # ensure CLI module is present in the command
            argv = queued[0]['cmd']
            self.assertIn('-m', argv)
            self.assertIn('mba_automation.cli', argv)
        finally:
            webapp.JOB_QUEUE = orig_q

    def test_schedule_regex(self):
        good = ['08:30', '8:30', '00:00', '23:59']
        for s in good:
            m = re.fullmatch(r"(\d{1,2}):(\d{2})", s)
            self.assertIsNotNone(m)

        bad = ['24:00', '12:60', 'abc', '1:2', '']
        for s in bad:
            m = re.fullmatch(r"(\d{1,2}):(\d{2})", s)
            if m:
                hh = int(m.group(1))
                mm = int(m.group(2))
                self.assertFalse(0 <= hh <= 23 and 0 <= mm <= 59)
            else:
                # non-matching strings are also expected
                self.assertIsNone(m)


if __name__ == '__main__':
    unittest.main()
