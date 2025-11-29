import unittest
import pathlib


def read_index():
    p = pathlib.Path(__file__).resolve().parents[1] / 'templates' / 'index.html'
    return p.read_text(encoding='utf-8')


class TestFrontendJS(unittest.TestCase):
    def test_index_contains_event_handlers(self):
        s = read_index()
        # check for key functions and buttons that should be wired
        self.assertIn('function attachToggle', s)
        self.assertIn('function attachReviewButtons', s)
        self.assertIn('function attachScheduleButtons', s)
        self.assertIn('function attachResetButtons', s)
        self.assertIn('class="review-btn"', s)
        self.assertIn('class="schedule-btn"', s)

    def test_no_stray_closing_brace_in_toggle(self):
        s = read_index()
        # previously we had an extra stray '}' that broke JS; ensure we don't have two closing braces in a row
        self.assertNotIn('\n          }\n          }\n        });', s)


if __name__ == '__main__':
    unittest.main()
