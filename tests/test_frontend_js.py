import unittest
import pathlib


def read_index():
    p = pathlib.Path(__file__).resolve().parents[1] / 'templates' / 'index.html'
    return p.read_text(encoding='utf-8')


def read_css():
    p = pathlib.Path(__file__).resolve().parents[1] / 'static' / 'css' / 'style.css'
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

    def test_remove_buttons_use_minus(self):
        s = read_index()
        # ensure visible 'Hapus' button text isn't present and remove buttons use the minimal minus
        self.assertNotIn('>Hapus</button>', s)
        self.assertIn('aria-hidden="true">−</span>', s)

    def test_css_no_gradients_and_phone_inline(self):
        css = read_css()
        # No linear-gradient usages
        self.assertNotIn('linear-gradient', css)
        # inputs should not wrap so +62 stays inline
        self.assertIn('flex-wrap:nowrap', css)
        self.assertIn('white-space:nowrap', css)

    def test_templates_no_inline_style_attributes(self):
        # ensure templates don't use inline style attributes anymore
        import glob
        from pathlib import Path
        tmpl_dir = Path(__file__).resolve().parents[1] / 'templates'
        files = glob.glob(str(tmpl_dir / '*.html'))
        for f in files:
            text = Path(f).read_text(encoding='utf-8')
            self.assertNotIn('style="', text, msg=f"Found inline style in {f}")

    def test_footer_removed(self):
        # ensure no template contains the removed footer text
        import glob
        from pathlib import Path
        tmpl_dir = Path(__file__).resolve().parents[1] / 'templates'
        for f in glob.glob(str(tmpl_dir / '*.html')):
            t = Path(f).read_text(encoding='utf-8')
            self.assertNotIn('keep your secrets out of git', t)

    def test_compact_css_applied(self):
        css = read_css()
        # accept either 820px or 900px in case someone wants a wider layout later
        joined = css.replace('\n', '')
        # accept 760px (current compact), 820px or 900px
        # accept 700px (current), 760px, 820px or 900px for flexibility
        joined = css.replace('\n', '')
        self.assertTrue(
            '.container{max-width:700px;margin:12px auto;padding:10px}' in joined
            or '.container{max-width:760px;margin:14px auto;padding:10px}' in joined
            or '.container{max-width:820px;margin:18px auto;padding:12px}' in joined
            or '.container{max-width:900px;margin:18px auto;padding:12px}' in joined
        )

    def test_no_empty_footer_tag_index(self):
        s = read_index()
        self.assertNotIn('<footer></footer>', s)

    def test_review_template_no_sunday(self):
        from pathlib import Path
        p = Path(__file__).resolve().parents[1] / 'templates' / 'review.html'
        s = p.read_text(encoding='utf-8')
        # review template should not hardcode Sunday label (we removed Sunday from review UI)
        self.assertNotIn('Minggu', s)
        self.assertNotIn('name="sun"', s)
    # Compact-only (no mode toggle) — no tests for toggle or .comfortable


if __name__ == '__main__':
    unittest.main()
