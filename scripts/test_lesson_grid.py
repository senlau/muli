"""Run after ingest.py --from-content; scoped gallery regression."""
from pathlib import Path
from html.parser import HTMLParser

class GalleryCheck(HTMLParser):
    def __init__(self):
        super().__init__()
        self.grid = False
        self.images = []
    def handle_starttag(self, tag, attrs):
        a = {key: value or '' for key, value in attrs}
        if tag == 'div' and a.get('class') == 'lesson-grid':
            self.grid = True
            assert 'repeat(3,minmax(0,1fr))' in a['style']
        if tag == 'img' and '28mm-20261110-edgoose-' in a.get('src', ''):
            self.images.append(a['src'].rsplit('-', 1)[1])
            assert 'height:auto' in a.get('style', '')
            assert 'aspect-ratio:auto' in a.get('style', '')
            expected = {'15.webp': (2500, 1667), '5.webp': (2250, 3000),
                        '7.webp': (2250, 3000), '16.webp': (1500, 2000),
                        '17.webp': (2500, 3750)}
            assert (int(a['width']), int(a['height'])) == expected[self.images[-1]]

root = Path(__file__).resolve().parents[1]
page = (root / '28mm/2026-11-10.html').read_text()
check = GalleryCheck()
check.feed(page)
assert check.grid
assert check.images == ['15.webp', '5.webp', '7.webp', '16.webp', '17.webp']
assert '&lt;div style=' not in page
print('lesson gallery regression ok')
