"""
ICICI Prudential AMC Navigator - Playwright-based extraction for portfolio disclosures.

This module provides a specialized navigator for ICICI Prudential's React-based website
that requires clicking through filters (Financial Year) to reveal portfolio disclosure files.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .playwright_vlm_navigator import PlaywrightVLMNavigator, NavigationResult

LOGGER = logging.getLogger(__name__)


class ICICIPrudentialNavigator:
    """
    Specialized navigator for ICICI Prudential AMC.
    
    The ICICI Prudential site (www.icicipruamc.com) is a React application with:
    - Tabbed interface for document types (NFO Material, Forms, SID, Other Scheme Disclosures, etc.)
    - Filter dropdowns (Document Type, Financial Year)
    - Portfolio disclosure files are ZIP files under "Fortnightly Debt Scheme Portfolio"
    - Files are downloaded via blob storage URLs
    
    Navigation strategy:
    1. Load the downloads page with "Other Scheme Disclosures" tab and "FortnightlyPortfolioDisclosures" sub-tab
    2. Click "Financial Year" filter dropdown
    2. Select desired financial year (e.g., "2026-2027")
    3. Wait for file list to load
    4. Click all "DOWNLOAD" buttons to get ZIP files
    """
    
    def __init__(
        self,
        vlm_endpoint: str = "http://192.168.1.10:9000/v1",
        vlm_model: str = "google/gemma-4-26b-a4b-qat",
        headless: bool = True,
        debug_dir: Path | None = None,
    ):
        self.navigator = PlaywrightVLMNavigator(
            vlm_endpoint=vlm_endpoint,
            vlm_model=vlm_model,
            max_navigation_steps=10,
            headless=headless,
            debug_dir=debug_dir,
        )
    
    def extract_portfolio_urls(
        self,
        start_url: str = "https://www.icicipruamc.com/media-center/downloads?currentTabFilter=OtherSchemeDisclosures&&subCatTabFilter=FortnightlyPortfolioDisclosures",
        financial_year: str = "2026-2027",
    ) -> list[str]:
        """
        Extract all portfolio disclosure ZIP file URLs for a given financial year.
        
        Args:
            start_url: The ICICI Prudential downloads page URL with correct tab filters
            financial_year: Financial year to select (e.g., "2026-2027", "2025-2026")
            
        Returns:
            List of direct download URLs for portfolio disclosure ZIP files
        """
        return self.extract_multiple_years(start_url, [financial_year]).get(financial_year, [])
    
    def _extract_all_years(
        self,
        start_url: str,
        financial_years: list[str],
    ) -> dict[str, list[str]]:
        """Internal method to extract URLs for multiple financial years in one browser session."""
        
        import asyncio
        from playwright.async_api import async_playwright
        
        async def _extract():
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                
                try:
                    results = {}
                    for year in financial_years:
                        LOGGER.info("Processing financial year: %s", year)
                        
                        page = await browser.new_page()
                        await page.set_viewport_size({"width": 1280, "height": 720})
                        
                        try:
                            # Navigate to start URL fresh for each year
                            await page.goto(start_url, wait_until="domcontentloaded", timeout=30000)
                            await page.wait_for_timeout(3000)
                            
                            # Click Financial Year dropdown
                            await page.click('button:has-text("Financial Year")', timeout=5000)
                            await page.wait_for_timeout(1500)
                            
                            # Click the specified financial year
                            await page.click(f'div:has-text("{year}"):visible', force=True, timeout=5000)
                            await page.wait_for_timeout(3000)
                            
                            # Find all DOWNLOAD buttons and download files
                            buttons = await page.locator('button:has-text("DOWNLOAD")').all()
                            LOGGER.info("Found %d DOWNLOAD buttons for %s", len(buttons), year)
                            
                            file_urls = []
                            for i, btn in enumerate(buttons):
                                try:
                                    async with page.expect_download(timeout=15000) as download_info:
                                        await btn.click(force=True, timeout=5000)
                                    download = await download_info.value
                                    file_urls.append(download.url)
                                    LOGGER.info("Downloaded %d for %s: %s", i + 1, year, download.suggested_filename)
                                    await page.wait_for_timeout(500)
                                except Exception as e:
                                    LOGGER.warning("Error downloading file %d for %s: %s", i, year, e)
                            
                            results[year] = file_urls
                            
                        finally:
                            await page.close()
                    
                    return results
                    
                finally:
                    await browser.close()
        
        return asyncio.run(_extract())
    
    def extract_multiple_years(
        self,
        start_url: str = "https://www.icicipruamc.com/media-center/downloads?currentTabFilter=OtherSchemeDisclosures&&subCatTabFilter=FortnightlyPortfolioDisclosures",
        financial_years: list[str] | None = None,
    ) -> dict[str, list[str]]:
        """
        Extract portfolio URLs for multiple financial years.
        
        Args:
            start_url: Base URL
            financial_years: List of financial years to extract (default: 2025-2026, 2026-2027)
            
        Returns:
            Dict mapping financial year to list of file URLs
        """
        if financial_years is None:
            financial_years = ["2026-2027", "2025-2026", "2024-2025", "2023-2024"]
        
        results = self._extract_all_years(start_url, financial_years)
        
        for year in financial_years:
            if year not in results:
                results[year] = []
                LOGGER.warning("No results for %s", year)
            else:
                LOGGER.info("Extracted %d files for %s", len(results[year]), year)
        
        return results


def extract_icici_portfolio_urls(
    financial_years: list[str] | None = None,
    headless: bool = True,
    debug_dir: Path | None = None,
) -> dict[str, list[str]]:
    """
    High-level function to extract ICICI Prudential portfolio URLs.
    
    Args:
        financial_years: List of financial years (default: 2025-2026, 2026-2027)
        headless: Run browser headless
        debug_dir: Directory for debug screenshots
        
    Returns:
        Dict mapping financial year to list of file URLs
    """
    navigator = ICICIPrudentialNavigator(
        headless=headless,
        debug_dir=debug_dir,
    )
    return navigator.extract_multiple_years(financial_years=financial_years)