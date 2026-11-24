"""Offline chrome regressions; structure/CSS contracts, not browser rendering."""
from __future__ import annotations
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

STATIC = Path(__file__).resolve().parents[1] / 'src/knowledge_sdk/ui/static'
MARKER = '/* Workbench chrome: independent icon / translated label / index tracks. */'


class ChromeParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.navs = []
        self.current = None
        self.ids = set()
        self.fields = set()
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'): self.ids.add(attrs['id'])
        if attrs.get('name'): self.fields.add(attrs['name'])
        if tag == 'button' and 'data-view' in attrs:
            self.current = {'view': attrs['data-view'], 'children': []}
        elif self.current is not None:
            self.current['children'].append((tag, attrs))

    def handle_endtag(self, tag):
        if tag == 'button' and self.current is not None:
            self.navs.append(self.current)
            self.current = None


def rules(source, media=''):
    """Parse only the small appended chrome rules, without third-party CSS deps."""
    position = 0
    while position < len(source):
        opening = source.find('{', position)
        if opening == -1: return
        selector = source[position:opening].strip()
        depth, end = 1, opening + 1
        while depth:
            if source[end] == '{': depth += 1
            elif source[end] == '}': depth -= 1
            end += 1
        body = source[opening + 1:end - 1]
        if selector.startswith('@media'):
            yield from rules(body, selector)
        else:
            properties = dict(part.strip().split(':', 1) for part in body.split(';') if ':' in part)
            for selected in selector.split(','):
                yield media, selected.strip(), properties
        position = end


def active_rules(source, width, height):
    result = {}
    for media, selector, properties in rules(source):
        matches = re.findall(r'(min|max)-(width|height)\s*:\s*(\d+)px', media)
        active = all(({'width': width, 'height': height}[axis] >= int(value) if boundary == 'min'
                      else {'width': width, 'height': height}[axis] <= int(value))
                     for boundary, axis, value in matches)
        if active: result.setdefault(selector, {}).update(properties)
    return result


class WorkbenchChromeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (STATIC / 'index.html').read_text()
        cls.script = (STATIC / 'workbench.js').read_text()
        cls.css = (STATIC / 'workbench.css').read_text().split(MARKER, 1)[1]
        cls.parsed = ChromeParser(cls.html)

    def test_navigation_has_separate_icon_translation_and_index_tracks(self):
        self.assertEqual([n['view'] for n in self.parsed.navs], ['spaces', 'documents', 'search', 'receipts'])
        for nav in self.parsed.navs:
            children = nav['children']
            self.assertEqual([attrs.get('class') for _, attrs in children], ['nav-icon', 'nav-label', 'nav-index'])
            self.assertIn('data-i18n', children[1][1])
            self.assertEqual(children[0][1].get('aria-hidden'), 'true')
            self.assertEqual(children[2][1].get('aria-hidden'), 'true')

    def test_desktop_label_cannot_inherit_icon_width_or_vertical_wrapping(self):
        for width in (941, 1024, 1440):
            css = active_rules(self.css, width, 576)
            self.assertEqual(css['.shell']['grid-template-columns'], '264px minmax(0,1fr)')
            self.assertEqual(css['.sidebar-nav .nav']['grid-template-columns'], '20px minmax(0,1fr) 16px')
            self.assertEqual(css['.nav>.nav-label']['width'], 'auto')
            self.assertEqual(css['.nav>.nav-label']['white-space'], 'nowrap')
            self.assertEqual(css['.nav>.nav-label']['writing-mode'], 'horizontal-tb')
            self.assertEqual(css['.nav>.nav-label']['font-size'], '12px')
            self.assertEqual(css['.nav>.nav-index']['display'], 'block')

    def test_short_desktop_sidebar_keeps_all_navigation_reachable(self):
        for height in (360, 576, 900):
            css = active_rules(self.css, 1024, height)
            self.assertEqual(css['.sidebar']['overflow-y'], 'auto')
            self.assertEqual(css['.sidebar>.sidebar-nav']['flex-shrink'], '0')
            self.assertEqual(css['.sidebar-nav .nav']['min-height'], '44px')

    def test_tablet_and_phone_use_page_flow_not_horizontal_overflow(self):
        for width in (320, 375, 560, 768, 940):
            css = active_rules(self.css, width, 576)
            self.assertEqual(css['.shell']['grid-template-columns'], 'minmax(0,1fr)')
            self.assertEqual(css['.sidebar']['height'], 'auto')
            self.assertEqual(css['.sidebar']['position'], 'relative')
            self.assertEqual(css['.sidebar']['overflow'], 'visible')
            columns = 'minmax(0,1fr)' if width <= 560 else 'repeat(2,minmax(0,1fr))'
            self.assertEqual(css['.sidebar-nav']['grid-template-columns'], columns)
            self.assertEqual(css['.nav>.nav-index']['display'], 'block')

    def test_compact_toolbar_has_intrinsic_height_and_keeps_essential_controls(self):
        for width in (320, 768, 1024):
            css = active_rules(self.css, width, 576)
            self.assertEqual(css['.topbar']['height'], 'auto')
            self.assertEqual(css['.topbar']['flex-wrap'], 'wrap')
            self.assertEqual(css['.topbar>.topbar-actions']['flex-wrap'], 'wrap')
            self.assertEqual(css['.language-control']['margin'], '0')
            self.assertEqual(css['.breadcrumb span']['margin'], '0')
        self.assertIn('language', self.parsed.ids)
        self.assertIn('auth-badge', self.parsed.ids)
        self.assertIn('class="topbar-actions"', self.html)

    def test_requested_noise_is_removed_without_removing_actor_settings(self):
        self.assertNotIn('identity-summary', self.html)
        self.assertNotIn('identity-summary', self.script)
        self.assertNotIn('文档正文、标题及标识保留原文，切换界面语言不会翻译知识内容。', self.html)
        self.assertIn('identity-label', self.parsed.ids)
        self.assertIn('identity-panel', self.parsed.ids)
        self.assertIn('identity-form', self.parsed.ids)
        self.assertIn('identity-warning', self.parsed.ids)
        for field in ('org_id', 'user_id', 'department_ids', 'ancestor_department_ids', 'org_roles', 'clearance_level'):
            self.assertIn(field, self.parsed.fields)
        self.assertIn("` · ${actor.user_id} / ${actor.org_id}`", self.script)
