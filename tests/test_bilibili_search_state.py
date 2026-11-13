import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BilibiliSearchStateTests(unittest.TestCase):
    def test_search_state_restores_cached_results_and_scroll_position(self):
        source = (ROOT / "app" / "misc_routes.py").read_text(encoding="utf-8")
        self.assertIn('sessionStorage.setItem(SEARCH_STATE_KEY', source)
        self.assertIn('sessionStorage.getItem(SEARCH_STATE_KEY', source)
        self.assertIn('page: Math.min(ST.page, Math.ceil(savedItems.length / 20))', source)
        self.assertIn('render(ST.items, false, true)', source)
        self.assertIn('window.scrollTo(0, Math.max(0, Number(snapshot.scrollY) || 0))', source)
        self.assertIn('a.addEventListener("click", function(){', source)
        self.assertIn('window.addEventListener("pagehide"', source)

    def test_search_state_includes_sort_type_duration_and_current_page(self):
        source = (ROOT / "app" / "misc_routes.py").read_text(encoding="utf-8")
        self.assertIn('&order=" + encodeURIComponent(ST.order)', source)
        self.assertIn('&type=" + encodeURIComponent(ST.type)', source)
        self.assertIn('&duration=" + ST.duration', source)
        self.assertIn('order: ST.order', source)
        self.assertIn('type: ST.type', source)
        self.assertIn('duration: ST.duration', source)
        self.assertIn('loadPagesThrough(p.page)', source)
        self.assertNotIn('setTimeout(step, 700)', source)


if __name__ == "__main__":
    unittest.main()
