import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mutual_fund_ingestion.artifacts import ArtifactPaths, load_latest_profiles, write_profile_artifacts
from mutual_fund_ingestion.browser import augment_with_network_evidence, save_browser_failure_artifacts
from mutual_fund_ingestion.cli import build_parser, main
from mutual_fund_ingestion.extract import extract_page_evidence
from utils.url_utils import safe_name
from mutual_fund_ingestion.models import (
    AMCSource,
    CandidateLink,
    ProviderProfile,
    SourceCandidate,
    SourcePage,
    SourceRegistryEntry,
)
from mutual_fund_ingestion.profiler import ProfileContext, ProfileOptions, profile_source, profile_sources
from mutual_fund_ingestion.registry import load_registry, load_sources
from mutual_fund_ingestion.reports import calculate_metrics, generate_profile_reports
from mutual_fund_ingestion.source_registry import (
    SourceRegistryPaths,
    candidates_from_registry,
    calculate_source_registry_metrics,
    generate_source_registry_report,
    merge_source_candidates,
    normalize_amc_name,
    write_source_registry_artifacts,
)
from mutual_fund_ingestion.source_discovery import discover_amfi_candidates, discover_sebi_candidates


FIXTURES = Path(__file__).parent / "fixtures"


def make_source(name="Example Mutual Fund", url="https://example.test/downloads"):
    return AMCSource(
        amc_name=name,
        seed_url=url,
        enabled=True,
        source_type="provider_download_page",
        expected_document_types=("portfolio_disclosure", "factsheet"),
        notes="",
    )


def make_profile(name="Example Mutual Fund", status="success", strategy="static_html"):
    return ProviderProfile(
        run_id="20260606_120000_ab12cd",
        created_at="2026-06-06T12:00:00Z",
        amc_name=name,
        seed_url="https://example.test/downloads",
        status=status,
        detected_strategy=strategy,
        requires_javascript=False,
        static_links_found=4,
        download_links_found=2,
        candidate_document_links_found=3,
        file_types_found=("pdf", "xlsx"),
        document_type_hints=("factsheet", "portfolio_disclosure"),
        candidate_links=(
            CandidateLink(
                url="https://example.test/report.xlsx",
                text="Portfolio",
                file_type="xlsx",
                document_type_hint="portfolio_disclosure",
                source_page_url="https://example.test/downloads",
                discovery_method="static_html",
            ),
        ),
    )


class RegistryTests(unittest.TestCase):
    def test_registry_supports_reference_entries_and_provider_projection(self):
        content = """
sources:
  - amc_name: Example Mutual Fund
    seed_url: https://example.test/downloads
    enabled: true
    source_role: primary_provider
    source_type: provider_download_page
    expected_document_types: [portfolio_disclosure]
    discovered_from: [manual_curated, existing_config]
    confidence: high
    priority: primary
    manual_overrides: [seed_url]
  - source_name: AMFI
    seed_url: https://www.amfiindia.com/
    enabled: true
    source_role: reference_index
    source_type: industry_reference_portal
    expected_document_types: [scheme_metadata]
    discovered_from: [manual_reference]
    confidence: high
    priority: secondary
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sources.yaml"
            path.write_text(content)
            registry = load_registry(path)
            providers = load_sources(path)

        self.assertEqual(2, len(registry))
        self.assertEqual("reference_index", registry[1].source_role)
        self.assertEqual(["Example Mutual Fund"], [source.amc_name for source in providers])
        self.assertEqual(("manual_curated", "existing_config"), providers[0].discovered_from)
        self.assertEqual(("seed_url",), providers[0].manual_overrides)

    def test_registry_allows_unresolved_provider_but_excludes_it_from_profiling(self):
        content = """
sources:
  - amc_name: Unresolved Mutual Fund
    seed_url:
    enabled: true
    source_role: primary_provider
    source_type: provider_homepage
    discovered_from: [amfi_reference]
    unresolved_reasons: [missing_provider_url]
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sources.yaml"
            path.write_text(content)
            registry = load_registry(path)
            providers = load_sources(path)

        self.assertEqual("missing_provider_url", registry[0].unresolved_reasons[0])
        self.assertEqual([], providers)

    def test_source_candidate_merge_preserves_locks_and_unions_provenance(self):
        existing = SourceRegistryEntry(
            amc_name="Example Mutual Fund",
            seed_url="https://curated.example/disclosures",
            enabled=True,
            source_role="primary_provider",
            source_type="provider_disclosure_page",
            expected_document_types=("portfolio_disclosure",),
            discovered_from=("existing_config", "manual_curated"),
            confidence="high",
            priority="primary",
            manual_overrides=("seed_url", "source_type"),
        )
        discovered = SourceCandidate(
            amc_name="Example MF",
            seed_url="https://discovered.example/",
            source_role="primary_provider",
            source_type="provider_homepage",
            expected_document_types=("factsheet",),
            discovered_from="amfi_reference",
            confidence="high",
            evidence_url="https://www.amfiindia.com/member/1",
            normalized_amc_name=normalize_amc_name("Example Mutual Fund"),
        )

        candidates = candidates_from_registry([existing])
        merged, decisions = merge_source_candidates(candidates + [discovered])

        self.assertEqual(1, len(merged))
        self.assertEqual("https://curated.example/disclosures", merged[0].seed_url)
        self.assertEqual("provider_disclosure_page", merged[0].source_type)
        self.assertEqual(
            {"existing_config", "manual_curated", "amfi_reference"},
            set(merged[0].discovered_from),
        )
        self.assertEqual({"portfolio_disclosure", "factsheet"}, set(merged[0].expected_document_types))
        self.assertTrue(decisions)

    def test_source_candidate_merge_deduplicates_provider_name_variants_by_domain(self):
        candidates = [
            SourceCandidate(
                amc_name="Example Mutual Fund",
                seed_url="https://www.example.test/downloads",
                source_role="primary_provider",
                source_type="provider_download_page",
                discovered_from="existing_config",
                confidence="high",
                normalized_amc_name=normalize_amc_name("Example Mutual Fund"),
            ),
            SourceCandidate(
                amc_name="Example Investments",
                seed_url="https://example.test/",
                source_role="primary_provider",
                source_type="provider_homepage",
                discovered_from="amfi_reference",
                confidence="high",
                normalized_amc_name=normalize_amc_name("Example Investments"),
            ),
        ]

        merged, decisions = merge_source_candidates(candidates)

        self.assertEqual(1, len(merged))
        self.assertEqual(1, len(decisions))

    def test_normalize_amc_name_collapses_common_suffixes(self):
        self.assertEqual(normalize_amc_name("Example Mutual Fund"), normalize_amc_name("Example MF"))

    def test_amfi_discovery_follows_member_pages_and_returns_unresolved_candidates(self):
        members_html = (FIXTURES / "amfi_members.html").read_text()
        detail_html = (FIXTURES / "amfi_member_detail.html").read_text()

        class DiscoverySession:
            def get(self, url, **kwargs):
                response = FakeResponse()
                response.text = detail_html if "/member/1" in url else members_html if "members" in url else "<html></html>"
                response.url = url
                return response

        candidates, warnings = discover_amfi_candidates(
            DiscoverySession(),
            "https://www.amfiindia.com/members",
            timeout_seconds=5,
        )

        by_name = {candidate.amc_name: candidate for candidate in candidates}
        self.assertEqual("https://example.test/", by_name["Example Mutual Fund"].seed_url)
        self.assertIn("missing_provider_url", by_name["Unresolved Mutual Fund"].unresolved_reasons)
        self.assertEqual([], warnings)

    def test_amfi_discovery_uses_optional_browser_fallback_for_empty_static_page(self):
        rendered_members = (FIXTURES / "amfi_members.html").read_text()

        class EmptySession:
            def get(self, url, **kwargs):
                response = FakeResponse()
                response.text = "<html></html>"
                response.url = url
                return response

        candidates, warnings = discover_amfi_candidates(
            EmptySession(),
            "https://www.amfiindia.com/members",
            timeout_seconds=5,
            browser_fetcher=lambda url, timeout: rendered_members if "members" in url else "<html></html>",
        )

        self.assertEqual(2, len(candidates))
        self.assertIn("missing_provider_url", candidates[0].unresolved_reasons)
        self.assertEqual([], warnings)

    def test_sebi_binary_or_unreachable_reference_is_nonfatal(self):
        class BinaryResponse(FakeResponse):
            text = ""
            content = b"%PDF"
            headers = {"content-type": "application/pdf"}

        class BinarySession:
            def get(self, *args, **kwargs):
                return BinaryResponse()

        candidates, warnings = discover_sebi_candidates(
            BinarySession(),
            "https://www.sebi.gov.in/registered-mutual-funds.pdf",
            timeout_seconds=5,
        )

        self.assertEqual([], candidates)
        self.assertIn("binary", warnings[0].casefold())

    def test_default_registry_covers_current_amfi_member_roster_with_provider_urls(self):
        sources = load_sources(Path("configs/amc_sources.yaml"))

        self.assertGreaterEqual(len(sources), 50)
        self.assertEqual(len(sources), len({source.amc_name.casefold() for source in sources}))
        self.assertTrue(all("amfiindia.com" not in source.seed_url for source in sources))
        self.assertIn("JioBlackRock Mutual Fund", {source.amc_name for source in sources})
        self.assertIn("The Wealth Company Mutual Fund", {source.amc_name for source in sources})

    def test_load_sources_filters_disabled_and_supports_limit_and_amc(self):
        content = """
sources:
  - amc_name: A Mutual Fund
    seed_url: https://a.example/downloads
    enabled: true
    source_type: provider_download_page
    expected_document_types: [portfolio_disclosure]
    notes: ""
  - amc_name: B Mutual Fund
    seed_url: https://b.example/
    enabled: false
    source_type: provider_homepage
    expected_document_types: [factsheet]
    notes: disabled
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sources.yaml"
            path.write_text(content)
            sources = load_sources(path, limit=1)
            selected = load_sources(path, amc="A Mutual Fund")

        self.assertEqual(["A Mutual Fund"], [source.amc_name for source in sources])
        self.assertEqual(["A Mutual Fund"], [source.amc_name for source in selected])

    def test_registry_rejects_duplicate_provider_amcs(self):
        content = """
sources:
  - amc_name: A Mutual Fund
    seed_url: https://www.amfiindia.com/provider
    enabled: true
    source_type: provider_homepage
    expected_document_types: []
    notes: ""
  - amc_name: A Mutual Fund
    seed_url: https://a.example/
    enabled: true
    source_type: provider_homepage
    expected_document_types: []
    notes: ""
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sources.yaml"
            path.write_text(content)
            with self.assertRaises(ValueError):
                load_registry(path)


class ModelTests(unittest.TestCase):
    def test_provider_profile_validates_schema_and_caps_candidate_links(self):
        candidates = tuple(
            CandidateLink(
                url=f"https://example.test/{index}.pdf",
                text="Factsheet",
                file_type="pdf",
                document_type_hint="factsheet",
                source_page_url="https://example.test",
                discovery_method="static_html",
            )
            for index in range(30)
        )
        profile = make_profile()
        profile = ProviderProfile(**(profile.to_dict() | {"candidate_links": candidates}))

        self.assertEqual("provider_profile_v1", profile.schema_version)
        self.assertEqual(25, len(profile.candidate_links))
        with self.assertRaises(ValueError):
            ProviderProfile(**(profile.to_dict() | {"status": "not-a-status"}))

    def test_provider_profile_loads_old_records_with_new_field_defaults(self):
        profile = make_profile()
        old_record = profile.to_dict()
        for field_name in (
            "source_name",
            "source_role",
            "source_type",
            "source_provenance",
            "strategy_confidence",
            "rendered_links_found",
        ):
            old_record.pop(field_name, None)

        loaded = ProviderProfile.from_dict(old_record)

        self.assertEqual("primary_provider", loaded.source_role)
        self.assertEqual((), loaded.source_provenance)
        self.assertEqual(0, loaded.rendered_links_found)


class ExtractionTests(unittest.TestCase):
    def test_browser_failure_artifacts_preserve_available_evidence(self):
        class FakePage:
            def content(self):
                return "<html>failure</html>"

            def screenshot(self, **kwargs):
                Path(kwargs["path"]).write_bytes(b"png")

        with tempfile.TemporaryDirectory() as directory:
            artifacts = save_browser_failure_artifacts(
                FakePage(),
                [{"url": "https://example.test/api", "status": 500}],
                Path(directory),
            )

            self.assertEqual("<html>failure</html>", Path(artifacts["rendered_html"]).read_text())
            self.assertTrue(Path(artifacts["screenshot"]).exists())
            self.assertIn("https://example.test/api", Path(artifacts["network_log"]).read_text())

    def test_network_responses_add_api_hints_and_direct_file_candidates(self):
        page = extract_page_evidence("<html></html>", "https://example.test/downloads", "playwright")

        evidence = augment_with_network_evidence(
            page,
            [
                {"url": "https://example.test/api/v1/disclosures", "status": 200},
                {"url": "https://cdn.example.test/monthly-portfolio.xlsx", "status": 200},
            ],
            "https://example.test/downloads",
        )

        self.assertIn("https://example.test/api/v1/disclosures", evidence.api_hints)
        self.assertEqual("xlsx", evidence.candidate_links[0].file_type)
        self.assertEqual("network_api", evidence.candidate_links[0].discovery_method)

    def test_extracts_links_files_document_hints_forms_scripts_and_api_hints(self):
        evidence = extract_page_evidence(
            (FIXTURES / "provider_static.html").read_text(),
            "https://example.test/downloads",
            "static_html",
        )

        self.assertEqual(3, evidence.static_links_found)
        self.assertEqual(2, evidence.download_links_found)
        self.assertEqual({"pdf", "xlsx"}, set(evidence.file_types_found))
        self.assertIn("portfolio_disclosure", evidence.document_type_hints)
        self.assertIn("factsheet", evidence.document_type_hints)
        self.assertIn("https://example.test/api/disclosures/search", evidence.api_hints)
        self.assertIn("https://example.test/api/v1/documents?category=portfolio", evidence.api_hints)

    def test_safe_name_is_deterministic(self):
        self.assertEqual("360_one_mutual_fund", safe_name("360 ONE Mutual Fund"))


class FakeResponse:
    status_code = 200
    text = (FIXTURES / "provider_static.html").read_text()
    url = "https://example.test/downloads"

    def raise_for_status(self):
        return None


class FakeSession:
    def get(self, *args, **kwargs):
        return FakeResponse()


class FailingSession:
    def get(self, *args, **kwargs):
        raise RuntimeError("blocked")


class ProfilerTests(unittest.TestCase):
    def test_static_api_hint_without_candidate_links_returns_partial_network_profile(self):
        class ApiOnlyResponse(FakeResponse):
            text = '<script>window.endpoint = "/api/v1/disclosures";</script>'

        class ApiOnlySession:
            def get(self, *args, **kwargs):
                return ApiOnlyResponse()

        context = ProfileContext(
            run_id="run1",
            created_at="2026-06-06T12:00:00Z",
            debug_root=Path("unused"),
            session=ApiOnlySession(),
            options=ProfileOptions(browser_enabled=False, persist_debug=False),
        )

        profile = profile_source(make_source(), context)

        self.assertEqual("partial_success", profile.status)
        self.assertEqual("network_api", profile.detected_strategy)

    def test_static_profile_saves_evidence_and_returns_success(self):
        with tempfile.TemporaryDirectory() as directory:
            context = ProfileContext(
                run_id="run1",
                created_at="2026-06-06T12:00:00Z",
                debug_root=Path(directory),
                session=FakeSession(),
                options=ProfileOptions(browser_enabled=False),
            )
            profile = profile_source(make_source(), context)

            self.assertEqual("success", profile.status)
            self.assertEqual("static_html", profile.detected_strategy)
            self.assertTrue(Path(profile.debug_artifacts["static_html"]).exists())

    def test_failed_static_and_unavailable_browser_returns_explicit_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            context = ProfileContext(
                run_id="run1",
                created_at="2026-06-06T12:00:00Z",
                debug_root=Path(directory),
                session=FailingSession(),
                options=ProfileOptions(browser_enabled=True),
            )
            with patch(
                "mutual_fund_ingestion.profiler.inspect_with_browser",
                side_effect=RuntimeError("browser unavailable"),
            ):
                profile = profile_source(make_source(), context)

            self.assertEqual("failed", profile.status)
            self.assertEqual("failed_blocked", profile.detected_strategy)
            self.assertIn("blocked", profile.failure_reason)
            self.assertTrue(Path(profile.debug_artifacts["profiler_error"]).exists())

    def test_profile_sources_reuses_latest_unless_force(self):
        source = make_source()
        existing = make_profile()
        context = ProfileContext(
            run_id="run2",
            created_at="2026-06-06T13:00:00Z",
            debug_root=Path("unused"),
            session=FakeSession(),
            options=ProfileOptions(browser_enabled=False, force=False),
            latest_profiles={source.amc_name: existing},
        )

        reused = profile_sources([source], context)
        forced = profile_sources(
            [source],
            ProfileContext(
                **(
                    context.__dict__
                    | {"options": ProfileOptions(browser_enabled=False, force=True, persist_debug=False)}
                )
            ),
        )

        self.assertEqual([existing], reused)
        self.assertEqual("run2", forced[0].run_id)


class ArtifactAndReportTests(unittest.TestCase):
    def test_artifacts_append_history_write_latest_and_generate_reports(self):
        profiles = [make_profile(), make_profile("Other Mutual Fund", "failed", "manual_review")]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = ArtifactPaths.from_roots(
                root / "raw",
                root / "reports",
                root / "debug",
            )
            write_profile_artifacts(profiles, paths)
            write_profile_artifacts([make_profile()], paths)
            generate_profile_reports(profiles, paths)

            history = paths.history.read_text().strip().splitlines()
            latest = json.loads(paths.latest.read_text())
            csv_text = paths.summary_csv.read_text()
            html_text = paths.report_html.read_text()

        self.assertEqual(2, len(history))
        self.assertEqual(2, len(latest))
        self.assertIn("Other Mutual Fund", csv_text)
        self.assertIn("total_amcs", html_text)
        self.assertIn("source_provenance", csv_text)
        self.assertIn("failed_blocked_count", html_text)

    def test_dry_run_writes_nothing_and_metrics_include_required_counts(self):
        profiles = [make_profile(), make_profile("Other Mutual Fund", "failed", "manual_review")]
        metrics = calculate_metrics(profiles)
        with tempfile.TemporaryDirectory() as directory:
            paths = ArtifactPaths.from_roots(Path(directory) / "raw", Path(directory) / "reports", Path(directory) / "debug")
            write_profile_artifacts(profiles, paths, dry_run=True)
            self.assertFalse(paths.history.exists())

        self.assertEqual(2, metrics["total_amcs"])
        self.assertEqual(1, metrics["profiled_successfully"])
        self.assertEqual(1, metrics["failed"])

    def test_latest_profiles_loads_pre_revision_records(self):
        profile = make_profile().to_dict()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.json"
            path.write_text(json.dumps([profile]))
            loaded = load_latest_profiles(path)

        self.assertEqual("primary_provider", loaded["Example Mutual Fund"].source_role)

    def test_source_registry_artifacts_are_valid_and_report_unresolved_sources(self):
        entries = [
            SourceRegistryEntry(
                amc_name="Example Mutual Fund",
                seed_url="https://example.test/",
                enabled=True,
                source_role="primary_provider",
                source_type="provider_homepage",
                discovered_from=("existing_config", "amfi_reference"),
                confidence="high",
                priority="primary",
            ),
            SourceRegistryEntry(
                amc_name="Unresolved Mutual Fund",
                seed_url=None,
                enabled=True,
                source_role="primary_provider",
                source_type="provider_homepage",
                discovered_from=("amfi_reference",),
                confidence="low",
                priority="primary",
                unresolved_reasons=("missing_provider_url",),
            ),
        ]
        candidates = candidates_from_registry(entries)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = SourceRegistryPaths.from_roots(
                root / "registry.yaml",
                root / "raw",
                root / "reports",
            )
            write_source_registry_artifacts(candidates, entries, paths)
            generate_source_registry_report(entries, [{"normalized_key": "example", "candidate_count": 2}], [], paths)
            loaded = load_registry(paths.config)
            jsonl_records = [json.loads(line) for line in paths.candidates.read_text().splitlines()]
            metrics = calculate_source_registry_metrics(entries, merge_count=1)
            report_html = paths.report_html.read_text()

        self.assertEqual(2, len(loaded))
        self.assertEqual(3, len(jsonl_records))
        self.assertEqual(1, metrics["sources_missing_seed_urls"])
        self.assertIn("Unresolved Mutual Fund", report_html)


class CliTests(unittest.TestCase):
    def test_cli_exposes_phase_1_commands_and_compatibility_aliases(self):
        parser = build_parser()

        self.assertEqual("bootstrap-sources", parser.parse_args(["bootstrap-sources", "--dry-run"]).command)
        self.assertEqual("profile-providers", parser.parse_args(["profile-providers", "--dry-run"]).command)
        self.assertEqual("phase-1", parser.parse_args(["phase-1", "--dry-run"]).command)
        self.assertEqual("profile-sites", parser.parse_args(["profile-sites", "--dry-run"]).command)

    def test_cli_dry_run_does_not_write_profiles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = root / "sources.yaml"
            registry.write_text(
                "sources:\n"
                "  - amc_name: Example Mutual Fund\n"
                "    seed_url: https://example.test/downloads\n"
                "    enabled: true\n"
                "    source_type: provider_download_page\n"
                "    expected_document_types: [portfolio_disclosure]\n"
                "    notes: ''\n"
            )
            with patch("mutual_fund_ingestion.cli.build_session", return_value=FakeSession()):
                result = main(
                    [
                        "profile-sites",
                        "--registry",
                        str(registry),
                        "--output-dir",
                        str(root / "raw"),
                        "--report-dir",
                        str(root / "reports"),
                        "--debug-dir",
                        str(root / "debug"),
                        "--dry-run",
                        "--no-browser",
                    ]
                )

            self.assertEqual(0, result)
            self.assertFalse((root / "raw" / "provider_profiles.jsonl").exists())
            self.assertFalse((root / "debug").exists())

    def test_bootstrap_sources_dry_run_preserves_config_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = root / "sources.yaml"
            registry.write_text(
                "sources:\n"
                "  - amc_name: Example Mutual Fund\n"
                "    seed_url: https://example.test/downloads\n"
                "    enabled: true\n"
                "    source_type: provider_download_page\n"
                "    expected_document_types: [portfolio_disclosure]\n"
            )
            original = registry.read_text()
            result = main(
                [
                    "bootstrap-sources",
                    "--config",
                    str(registry),
                    "--source-registry-dir",
                    str(root / "raw"),
                    "--report-dir",
                    str(root / "reports"),
                    "--no-reference-network",
                    "--no-browser",
                    "--dry-run",
                ]
            )

            self.assertEqual(0, result)
            self.assertEqual(original, registry.read_text())
            self.assertFalse((root / "raw").exists())
            self.assertFalse((root / "reports").exists())

    def test_phase_1_dry_run_bootstraps_then_profiles_primary_provider_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = root / "sources.yaml"
            registry.write_text(
                "sources:\n"
                "  - amc_name: Example Mutual Fund\n"
                "    seed_url: https://example.test/downloads\n"
                "    enabled: true\n"
                "    source_type: provider_download_page\n"
                "    expected_document_types: [portfolio_disclosure]\n"
            )
            with patch("mutual_fund_ingestion.cli.build_session", return_value=FakeSession()):
                result = main(
                    [
                        "phase-1",
                        "--config",
                        str(registry),
                        "--source-registry-dir",
                        str(root / "source-raw"),
                        "--output-dir",
                        str(root / "profile-raw"),
                        "--report-dir",
                        str(root / "reports"),
                        "--debug-dir",
                        str(root / "debug"),
                        "--no-reference-network",
                        "--no-browser",
                        "--dry-run",
                    ]
                )

            self.assertEqual(0, result)
            self.assertFalse((root / "source-raw").exists())
            self.assertFalse((root / "profile-raw").exists())


if __name__ == "__main__":
    unittest.main()
