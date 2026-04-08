import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.check_iaui_update import (  # noqa: E402
    build_fingerprint,
    discover_download_link,
    extract_updated_at,
)


class CheckIAUIUpdateTests(unittest.TestCase):
    def test_discover_download_link_prefers_registry_xls_over_other_downloads(self) -> None:
        page_html = """
        <html>
          <body>
            <a href="/lv/media/33944/download?attachment" title="promo.jpg">
              Kas jāņem vērā konkursu rīkotājiem?
            </a>
            <a
              href="/lv/media/34040/download?attachment"
              title="Loteriju_reģistrs_25.03.2026..xls"
              aria-label="XLS datne - Izsniegtās preču un pakalpojumu loteriju atļaujas"
            >
              Izsniegtās preču un pakalpojumu loteriju atļaujas
            </a>
          </body>
        </html>
        """

        download_url, link_text = discover_download_link(page_html, "https://www.vid.gov.lv/lv/loterijas")

        self.assertEqual(download_url, "https://www.vid.gov.lv/lv/media/34040/download?attachment")
        self.assertEqual(link_text, "Izsniegtās preču un pakalpojumu loteriju atļaujas")

    def test_discover_download_link_accepts_registry_filename_marker(self) -> None:
        page_html = """
        <html>
          <body>
            <a
              href="/lv/media/34040/download?attachment"
              title="Loteriju_reģistrs_25.03.2026..xls"
              aria-label="XLS datne - Publicētais reģistrs"
            >
              Publicētais reģistrs
            </a>
          </body>
        </html>
        """

        download_url, link_text = discover_download_link(page_html, "https://www.vid.gov.lv/lv/loterijas")

        self.assertEqual(download_url, "https://www.vid.gov.lv/lv/media/34040/download?attachment")
        self.assertEqual(link_text, "Publicētais reģistrs")

    def test_discover_download_link_rejects_unrelated_downloads(self) -> None:
        page_html = """
        <html>
          <body>
            <a href="/lv/media/33944/download?attachment" title="promo.jpg">
              Kas jāņem vērā konkursu rīkotājiem?
            </a>
          </body>
        </html>
        """

        with self.assertRaisesRegex(RuntimeError, "lottery registry download link"):
            discover_download_link(page_html, "https://www.vid.gov.lv/lv/loterijas")

    def test_extract_updated_at_returns_page_date(self) -> None:
        page_html = "<div><br>Atjaunināts: 26.03.2026.</div>"
        self.assertEqual(extract_updated_at(page_html), "26.03.2026")

    def test_build_fingerprint_changes_when_file_hash_changes(self) -> None:
        fingerprint_a = build_fingerprint(
            "https://www.vid.gov.lv/lv/media/34040/download?attachment",
            "Izsniegtās preču un pakalpojumu loteriju atļaujas",
            "26.03.2026",
            "aaa",
        )
        fingerprint_b = build_fingerprint(
            "https://www.vid.gov.lv/lv/media/34040/download?attachment",
            "Izsniegtās preču un pakalpojumu loteriju atļaujas",
            "26.03.2026",
            "bbb",
        )

        self.assertNotEqual(fingerprint_a, fingerprint_b)


if __name__ == "__main__":
    unittest.main()
