import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from mutual_fund_ingestion.amfi_disclosure.discovery import Discoverer, extract_page_links, select_latest_per_amc
from mutual_fund_ingestion.amfi_disclosure.downloader import Downloader, build_download_name
from mutual_fund_ingestion.amfi_disclosure.models import DisclosureLink, read_jsonl, write_jsonl


FIXTURES = Path(__file__).parent / "fixtures"


class DiscoveryTests(unittest.TestCase):
    def test_extracts_direct_files_and_relevant_landing_pages(self):
        html = (FIXTURES / "amfi_portfolio.html").read_text()

        files, landing_pages = extract_page_links(
            html,
            "https://www.amfiindia.com/online-center/portfolio-disclosure",
            discovery_method="static_html",
            default_disclosure_type="Monthly Portfolio Disclosure",
        )

        self.assertEqual(1, len(files))
        self.assertEqual("xlsx", files[0].file_type)
        self.assertEqual("Axis Mutual Fund", files[0].amc_name)
        self.assertEqual("2026-05", files[0].month_or_date)
        self.assertEqual(
            ["https://example-amc.test/disclosures/portfolio"], landing_pages
        )

    def test_extracts_files_from_an_amc_landing_page(self):
        html = (FIXTURES / "amc_portfolio.html").read_text()

        files, landing_pages = extract_page_links(
            html,
            "https://example-amc.test/disclosures/portfolio",
            discovery_method="static_html",
            default_amc_name="Example Mutual Fund",
        )

        self.assertEqual(2, len(files))
        self.assertEqual([], landing_pages)
        self.assertEqual("Example Mutual Fund", files[0].amc_name)

    def test_extracts_file_urls_embedded_in_scripts(self):
        html = """
        <script>
          window.latestPortfolio = "/downloads/monthly-portfolio-2026-05.zip";
        </script>
        """

        files, _ = extract_page_links(
            html,
            "https://www.amfiindia.com/online-center/portfolio-disclosure",
            discovery_method="static_html",
        )

        self.assertEqual(1, len(files))
        self.assertEqual(
            "https://www.amfiindia.com/downloads/monthly-portfolio-2026-05.zip",
            files[0].file_url,
        )
        self.assertEqual("embedded_script", files[0].raw_metadata["source"])

    def test_selects_latest_five_files_per_amc(self):
        links = []
        for amc in ("A Mutual Fund", "B Mutual Fund"):
            for month in range(1, 8):
                links.append(
                    DisclosureLink(
                        source_page_url="https://source.test",
                        file_url=f"https://files.test/{amc[0]}-{month}.xlsx",
                        file_name=f"{month}.xlsx",
                        file_type="xlsx",
                        amc_name=amc,
                        month_or_date=f"2026-{month:02d}",
                        discovered_at="2026-06-06T00:00:00+00:00",
                        discovery_method="static_html",
                    )
                )

        selected = select_latest_per_amc(links, 5)

        self.assertEqual(10, len(selected))
        self.assertEqual(
            ["2026-07", "2026-06", "2026-05", "2026-04", "2026-03"],
            [link.month_or_date for link in selected if link.amc_name == "A Mutual Fund"],
        )

    def test_discovery_rejects_a_reachable_page_with_no_disclosure_files(self):
        class EmptyResponse:
            text = "<html><body>No disclosures</body></html>"

            def raise_for_status(self):
                return None

        class EmptySession:
            def get(self, *args, **kwargs):
                return EmptyResponse()

        discoverer = Discoverer(session=EmptySession(), browser_fallback=False)

        with self.assertRaisesRegex(RuntimeError, "zero disclosure files"):
            discoverer.discover()

    def test_dynamic_amc_page_uses_browser_fallback(self):
        class Response:
            def __init__(self, text):
                self.text = text

            def raise_for_status(self):
                return None

        class Session:
            def get(self, url, **kwargs):
                if "amfiindia.com" in url:
                    return Response(
                        '<div id="divMonthlyPortfolio">'
                        '<a href="https://example-amc.test/portfolio">Example Mutual Fund</a>'
                        "</div>"
                    )
                return Response("<html><body>Dynamic page</body></html>")

        browser_link = DisclosureLink(
            source_page_url="https://example-amc.test/portfolio",
            file_url="https://example-amc.test/files/report.xlsx",
            file_name="report.xlsx",
            file_type="xlsx",
            amc_name="Example Mutual Fund",
            discovered_at="2026-06-06T00:00:00+00:00",
            discovery_method="playwright",
        )
        with patch(
            "mutual_fund_ingestion.amfi_disclosure.discovery.discover_with_browser",
            return_value=([browser_link], []),
        ) as browser_discovery:
            links = Discoverer(session=Session(), browser_fallback=True).discover()

        self.assertEqual([browser_link], links)
        browser_discovery.assert_called_once()


class MetadataTests(unittest.TestCase):
    def test_jsonl_round_trip_preserves_schema(self):
        link = DisclosureLink(
            source_page_url="https://source.test",
            file_url="https://files.test/report.xlsx",
            file_name="report.xlsx",
            file_type="xlsx",
            disclosure_type="Monthly Portfolio Disclosure",
            amc_name="Example Mutual Fund",
            month_or_date="2026-05",
            discovered_at=datetime.now(timezone.utc).isoformat(),
            discovery_method="network_request",
            raw_metadata={"label": "Report"},
        )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "links.jsonl"
            write_jsonl([link], path)
            data = json.loads(path.read_text().strip())
            loaded = read_jsonl(path)

        self.assertEqual(
            {
                "source_page_url",
                "file_url",
                "file_name",
                "file_type",
                "disclosure_type",
                "amc_name",
                "month_or_date",
                "discovered_at",
                "discovery_method",
                "raw_metadata",
            },
            set(data),
        )
        self.assertEqual(link, loaded[0])

    def test_download_name_is_safe_and_deterministic(self):
        link = DisclosureLink(
            source_page_url="https://source.test",
            file_url="https://files.test/Report%20May.xlsx?download=1",
            file_name="Report May.xlsx",
            file_type="xlsx",
            amc_name="A/B: Mutual Fund",
            month_or_date="2026-05",
            discovered_at="2026-06-06T00:00:00+00:00",
            discovery_method="static_html",
        )

        name = build_download_name(link)

        self.assertRegex(name, r"^a-b-mutual-fund_2026-05_report-may_[a-f0-9]{10}\.xlsx$")


class FakeResponse:
    status_code = 200
    headers = {"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        yield b"valid workbook bytes"

    def close(self):
        return None


class FakeSession:
    def __init__(self):
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        return FakeResponse()


class HtmlResponse(FakeResponse):
    headers = {"content-type": "application/octet-stream"}

    def iter_content(self, chunk_size):
        yield b"<html><body>Access denied</body></html>"


class HtmlSession:
    def get(self, *args, **kwargs):
        return HtmlResponse()


class BrokenStreamResponse(FakeResponse):
    def iter_content(self, chunk_size):
        yield b"partial"
        raise OSError("connection lost")


class BrokenStreamSession:
    def get(self, *args, **kwargs):
        return BrokenStreamResponse()


class DownloaderTests(unittest.TestCase):
    def test_downloader_skips_existing_file_unless_forced(self):
        link = DisclosureLink(
            source_page_url="https://source.test",
            file_url="https://files.test/report.xlsx",
            file_name="report.xlsx",
            file_type="xlsx",
            amc_name="Example Mutual Fund",
            month_or_date="2026-05",
            discovered_at="2026-06-06T00:00:00+00:00",
            discovery_method="static_html",
        )
        session = FakeSession()

        with tempfile.TemporaryDirectory() as directory:
            downloader = Downloader(Path(directory), session=session, delay_seconds=0)
            first = downloader.download(link)
            skipped = downloader.download(link)
            forced = downloader.download(link, force=True)

        self.assertEqual("downloaded", first.status)
        self.assertEqual("skipped", skipped.status)
        self.assertEqual("downloaded", forced.status)
        self.assertEqual(2, session.calls)

    def test_downloader_rejects_html_error_pages(self):
        link = DisclosureLink(
            source_page_url="https://source.test",
            file_url="https://files.test/report.xlsx",
            file_name="report.xlsx",
            file_type="xlsx",
            discovered_at="2026-06-06T00:00:00+00:00",
            discovery_method="static_html",
        )

        with tempfile.TemporaryDirectory() as directory:
            downloader = Downloader(Path(directory), session=HtmlSession(), delay_seconds=0)
            with self.assertRaisesRegex(ValueError, "HTML"):
                downloader.download(link)
            self.assertEqual([], list(Path(directory).glob("*.xlsx")))

    def test_downloader_removes_partial_file_after_stream_failure(self):
        link = DisclosureLink(
            source_page_url="https://source.test",
            file_url="https://files.test/report.xlsx",
            file_name="report.xlsx",
            file_type="xlsx",
            discovered_at="2026-06-06T00:00:00+00:00",
            discovery_method="static_html",
        )

        with tempfile.TemporaryDirectory() as directory:
            downloader = Downloader(Path(directory), session=BrokenStreamSession(), delay_seconds=0)
            with self.assertRaisesRegex(OSError, "connection lost"):
                downloader.download(link)
            self.assertEqual([], list(Path(directory).glob("*.part")))


if __name__ == "__main__":
    unittest.main()
