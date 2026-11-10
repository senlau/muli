"""Website stays vertical; local Markdown grids never migrate."""
import tempfile
import unittest
from pathlib import Path
from ingest import parse_brief, entry_from_md
from render_site import render_site

class PublicationRegression(unittest.TestCase):
    def test_local_grid_is_vertical_on_website(self):
        body = '### 2026-11-10｜测试\n\n<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;"><figure><img src="https://example.org/a.webp"></figure></div>\n'
        entry = entry_from_md(body, '28mm', '2026-11-10')
        page = render_site([entry], '2026-11-10', [])['28mm/2026-11-10.html']
        self.assertNotIn('lesson-grid', page)
        self.assertNotIn('&lt;div style=', page)
        self.assertIn('height:auto;aspect-ratio:auto', page)
    def test_same_day_photographers_survive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'作者长卷.md').write_text('## 每日推送\n\n### 2026-11-10｜李泛（大师）\n\n李泛正文。\n\n### 2026-11-10｜李振盛（纪实）\n\n李振盛正文。\n')
            entries = parse_brief(root)
            self.assertEqual(len(entries), 2)
            pages = render_site(entries, '2026-11-10', [])
            self.assertEqual(len([p for p in pages if p.startswith('photographer/')]), 2)

if __name__ == '__main__':
    unittest.main()
