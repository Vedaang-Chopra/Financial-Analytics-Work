"""
Playwright + VLM Navigator for AMC Portfolio Disclosure Extraction

Primary technique: Playwright browser + VLM-guided navigation
Fallback technique: static_html (existing discovery engine)

This module provides intelligent navigation for AMC websites that require
JavaScript rendering, tab clicking, form filling, or complex UI interaction.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from utils.url_utils import canonical_url, file_type_from_url

LOGGER = logging.getLogger(__name__)


class NavigationError(RuntimeError):
    """Raised when navigation fails."""
    pass


class VLMUnavailable(RuntimeError):
    """Raised when VLM service is unavailable."""
    pass


@dataclass(frozen=True)
class PageState:
    """Captured state of a page during navigation."""
    url: str
    title: str
    html: str
    screenshot_path: str | None
    links: list[dict[str, str]]
    buttons: list[dict[str, str]]
    forms: list[dict[str, str]]
    visible_text: str
    network_calls: list[dict[str, Any]]
    file_downloads: list[dict[str, Any]]


@dataclass(frozen=True)
class NavigationAction:
    """Action recommended by VLM."""
    action_type: str  # click, select, fill, wait, download, navigate, skip
    target_selector: str | None
    target_text: str | None
    form_values: dict[str, str]
    reason: str
    confidence: float


@dataclass
class NavigationResult:
    """Result of a navigation attempt."""
    success: bool
    final_url: str
    file_urls_found: list[str]
    pages_visited: list[PageState]
    error: str | None = None


class PlaywrightVLMNavigator:
    """
    Uses Playwright for browser automation + VLM for intelligent navigation decisions.
    
    Workflow:
    1. Load page with Playwright
    2. Capture page state (HTML, links, buttons, forms, screenshot)
    3. Send to VLM with objective
    4. Execute VLM-recommended action
    5. Repeat until portfolio disclosure files found or max steps reached
    """
    
    def __init__(
        self,
        vlm_endpoint: str = "http://192.168.1.10:9000/v1",
        vlm_model: str = "google/gemma-4-26b-a4b-qat",
        vlm_timeout: float = 60.0,
        max_navigation_steps: int = 10,
        step_timeout: float = 30.0,
        headless: bool = True,
        debug_dir: Path | None = None,
    ):
        self.vlm_endpoint = vlm_endpoint.rstrip("/")
        self.vlm_model = vlm_model
        self.vlm_timeout = vlm_timeout
        self.max_navigation_steps = max_navigation_steps
        self.step_timeout = step_timeout
        self.headless = headless
        self.debug_dir = debug_dir or Path("/tmp/nav_debug")
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        
        self._page_states: list[PageState] = []
        self._file_urls_found: set[str] = set()
    
    def navigate_to_portfolio(self, start_url: str, amc_name: str) -> NavigationResult:
        """
        Navigate from start_url to find portfolio disclosure files.
        
        Args:
            start_url: Starting URL (e.g., AMC downloads page)
            amc_name: AMC name for context
            
        Returns:
            NavigationResult with found file URLs
        """
        self._page_states = []
        self._file_urls_found = set()
        
        try:
            return self._run_navigation(start_url, amc_name)
        except Exception as e:
            LOGGER.error("Navigation failed for %s: %s", amc_name, e)
            return NavigationResult(
                success=False,
                final_url=start_url,
                file_urls_found=list(self._file_urls_found),
                pages_visited=self._page_states,
                error=str(e)
            )
    
    def _run_navigation(self, start_url: str, amc_name: str) -> NavigationResult:
        """Main navigation loop."""
        import asyncio
        from playwright.async_api import async_playwright
        
        async def _navigate():
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=self.headless)
                page = await browser.new_page()
                
                # Set viewport for consistent rendering
                await page.set_viewport_size({"width": 1280, "height": 720})
                
                # Capture network responses for file URLs
                network_calls: list[dict[str, Any]] = []
                file_downloads: list[dict[str, Any]] = []
                
                page.on("response", lambda response: network_calls.append({
                    "url": response.url,
                    "status": response.status,
                    "content_type": response.headers.get("content-type", ""),
                }))
                
                # Navigate to start URL
                try:
                    await page.goto(start_url, wait_until="domcontentloaded", timeout=int(self.step_timeout * 1000))
                    await page.wait_for_timeout(2000)  # Wait for dynamic content
                except Exception as e:
                    raise NavigationError(f"Failed to load {start_url}: {e}")
                
                # Main navigation loop
                for step in range(self.max_navigation_steps):
                    LOGGER.info("Navigation step %d/%d for %s", step + 1, self.max_navigation_steps, amc_name)
                    
                    # Capture page state
                    page_state = await self._capture_page_state(page, network_calls, file_downloads)
                    self._page_states.append(page_state)
                    
                    # Check for file downloads in network calls
                    self._extract_file_urls_from_network(network_calls)
                    
                    # If we found portfolio files, we're done
                    portfolio_files = [u for u in self._file_urls_found if self._is_portfolio_file(u)]
                    if portfolio_files:
                        LOGGER.info("Found %d portfolio files for %s", len(portfolio_files), amc_name)
                        return NavigationResult(
                            success=True,
                            final_url=page.url,
                            file_urls_found=list(portfolio_files),
                            pages_visited=self._page_states
                        )
                    
                    # Get VLM recommendation for next action
                    action = await self._get_vlm_action(page_state, amc_name)
                    
                    if action.action_type == "skip" or action.confidence < 0.3:
                        LOGGER.info("VLM recommends skipping (confidence=%.2f): %s", action.confidence, action.reason)
                        break
                    
                    # Execute the recommended action
                    try:
                        await self._execute_action(page, action)
                        await page.wait_for_timeout(1500)
                    except Exception as e:
                        LOGGER.warning("Action failed: %s", e)
                        # Try to continue
                        pass
                    
                    # Clear network calls for next iteration (keep only new ones)
                    network_calls.clear()
                
                # Max steps reached
                portfolio_files = [u for u in self._file_urls_found if self._is_portfolio_file(u)]
                return NavigationResult(
                    success=len(portfolio_files) > 0,
                    final_url=page.url,
                    file_urls_found=list(portfolio_files),
                    pages_visited=self._page_states
                )
        
        return asyncio.run(_navigate())
    
    async def _capture_page_state(
        self,
        page,
        network_calls: list[dict[str, Any]],
        file_downloads: list[dict[str, Any]]
    ) -> PageState:
        """Capture current page state for VLM analysis."""
        
        # Get page content
        html = await page.content()
        title = await page.title()
        url = page.url
        
        # Extract links
        links = []
        for elem in await page.locator("a").all():
            try:
                href = await elem.get_attribute("href")
                text = await elem.inner_text()
                if href:
                    absolute_url = urljoin(url, href)
                    links.append({"url": canonical_url(absolute_url), "text": text.strip()[:200], "title": ""})
            except Exception:
                pass
        
        # Extract buttons
        buttons = []
        for elem in await page.locator("button, [role='button'], input[type='button'], input[type='submit']").all():
            try:
                text = await elem.inner_text()
                selector = await self._get_element_selector(elem)
                if text:
                    buttons.append({"text": text.strip()[:200], "selector": selector})
            except Exception:
                pass
        
        # Extract forms
        forms = []
        for elem in await page.locator("form").all():
            try:
                form_data = await elem.evaluate("""form => {
                    const inputs = Array.from(form.querySelectorAll('input, select, textarea'));
                    return inputs.map(i => ({
                        name: i.name,
                        type: i.type,
                        placeholder: i.placeholder,
                        value: i.value
                    }));
                }""")
                forms.append({"fields": form_data})
            except Exception:
                pass
        
        # Get visible text (first 5000 chars)
        visible_text = await page.evaluate("document.body.innerText")
        visible_text = visible_text[:5000]
        
        # Screenshot
        screenshot_path = None
        try:
            screenshot_file = self.debug_dir / f"step_{len(self._page_states)}_screenshot.png"
            await page.screenshot(path=str(screenshot_file), full_page=True, timeout=10000)
            screenshot_path = str(screenshot_file)
        except Exception:
            pass
        
        # Collect file downloads from network
        self._extract_file_urls_from_network(network_calls)
        
        return PageState(
            url=url,
            title=title,
            html=html,
            screenshot_path=screenshot_path,
            links=links,
            buttons=buttons,
            forms=forms,
            visible_text=visible_text,
            network_calls=network_calls[-20:],  # Keep last 20
            file_downloads=[{"url": u} for u in self._file_urls_found]
        )
    
    async def _get_element_selector(self, elem) -> str:
        """Generate a CSS selector for an element."""
        try:
            return await elem.evaluate("""el => {
                if (el.id) return '#' + el.id;
                if (el.className) return '.' + el.className.split(' ')[0];
                return el.tagName.toLowerCase();
            }""")
        except Exception:
            return "unknown"
    
    def _extract_file_urls_from_network(self, network_calls: list[dict[str, Any]]) -> None:
        """Extract portfolio file URLs from network calls."""
        for call in network_calls:
            ft = file_type_from_url(call["url"])
            if ft in ("xlsx", "xls", "csv", "pdf") and "portfolio" in call["url"].lower():
                self._file_urls_found.add(call["url"])
    
    def _is_portfolio_file(self, url: str) -> bool:
        """Check if URL is likely a portfolio disclosure file."""
        url_lower = url.lower()
        return (
            file_type_from_url(url) in ("xlsx", "xls", "csv") and
            any(kw in url_lower for kw in ["portfolio", "disclosure", "holding", "monthly"])
        )
    
    async def _get_vlm_action(self, page_state: PageState, amc_name: str) -> NavigationAction:
        """Get next action recommendation from VLM."""
        
        import requests
        
        prompt = self._build_vlm_prompt(page_state, amc_name)
        
        try:
            response = requests.post(
                f"{self.vlm_endpoint}/chat/completions",
                json={
                    "model": self.vlm_model,
                    "messages": [
                        {"role": "system", "content": "You are a web navigation assistant for financial data extraction. Return only valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 800,
                    "stream": False,
                },
                timeout=self.vlm_timeout,
            )
            response.raise_for_status()
            data = response.json()
            raw = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            return self._parse_vlm_response(raw, page_state)
            
        except Exception as e:
            LOGGER.warning("VLM request failed: %s", e)
            # Fallback: simple heuristic
            return self._fallback_action(page_state)
    
    def _build_vlm_prompt(self, page_state: PageState, amc_name: str) -> str:
        """Build prompt for VLM page analysis."""
        
        # Filter links to relevant ones
        relevant_links = [
            l for l in page_state.links 
            if any(kw in l["text"].lower() for kw in [
                "portfolio", "disclosure", "holding", "monthly", "fortnightly",
                "download", "factsheet", "nav", "statutory", "scheme"
            ]) or any(kw in l["url"].lower() for kw in ["portfolio", "disclosure", "holding"])
        ][:15]
        
        relevant_buttons = [
            b for b in page_state.buttons
            if any(kw in b["text"].lower() for kw in [
                "portfolio", "disclosure", "download", "view", "show", "load",
                "monthly", "fortnightly", "search", "filter", "submit"
            ])
        ][:10]
        
        return (
            f"You are navigating {amc_name}'s website to find monthly portfolio disclosure files (Excel/CSV).\n"
            f"Current URL: {page_state.url}\n"
            f"Page Title: {page_state.title}\n"
            f"Objective: Find links to monthly/fortnightly portfolio disclosure files (xlsx, xls, csv) for mutual fund schemes.\n\n"
            f"Relevant Links:\n{json.dumps(relevant_links, indent=2)}\n\n"
            f"Relevant Buttons:\n{json.dumps(relevant_buttons, indent=2)}\n\n"
            f"Forms:\n{json.dumps(page_state.forms[:3], indent=2)}\n\n"
            f"Visible Text (excerpt):\n{page_state.visible_text[:2000]}\n\n"
            "Return JSON with:\n"
            "  action_type: 'click' | 'select' | 'fill' | 'navigate' | 'download' | 'wait' | 'skip'\n"
            "  target_selector: CSS selector for click/select (or null)\n"
            "  target_text: text to match for click (or null)\n"
            "  form_values: dict of form field values to fill\n"
            "  reason: explanation\n"
            "  confidence: 0.0-1.0\n\n"
            "Guidelines:\n"
            "- Look for tabs, dropdowns, filters for 'Portfolio', 'Disclosure', 'Monthly', 'Fortnightly'\n"
            "- Click links/buttons that lead to portfolio disclosure pages\n"
            "- Fill forms to select scheme/month if needed\n"
            "- 'download' action if direct file URLs are visible\n"
            "- 'skip' if page is irrelevant (login, marketing, etc.)\n"
            "- Prefer high-confidence actions that progress toward portfolio files"
        )
    
    def _parse_vlm_response(self, raw: str, page_state: PageState) -> NavigationAction:
        """Parse VLM JSON response."""
        try:
            json_start = raw.find("{")
            json_end = raw.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                data = json.loads(raw[json_start:json_end])
                return NavigationAction(
                    action_type=data.get("action_type", "skip"),
                    target_selector=data.get("target_selector"),
                    target_text=data.get("target_text"),
                    form_values=data.get("form_values", {}),
                    reason=data.get("reason", ""),
                    confidence=float(data.get("confidence", 0.5)),
                )
        except Exception as e:
            LOGGER.warning("VLM response parse failed: %s", e)
        
        return self._fallback_action(page_state)
    
    def _fallback_action(self, page_state: PageState) -> NavigationAction:
        """Heuristic fallback when VLM fails."""
        # Look for portfolio-related links
        for link in page_state.links:
            text_lower = link["text"].lower()
            url_lower = link["url"].lower()
            if any(kw in text_lower for kw in ["portfolio", "disclosure", "holding"]) and "month" in (text_lower + url_lower):
                return NavigationAction(
                    action_type="click",
                    target_selector=None,
                    target_text=link["text"],
                    form_values={},
                    reason="Fallback: found portfolio+month link",
                    confidence=0.6
                )
        
        # Look for relevant buttons
        for btn in page_state.buttons:
            text_lower = btn["text"].lower()
            if any(kw in text_lower for kw in ["portfolio", "disclosure", "download", "view"]):
                return NavigationAction(
                    action_type="click",
                    target_selector=btn.get("selector"),
                    target_text=btn["text"],
                    form_values={},
                    reason="Fallback: found relevant button",
                    confidence=0.5
                )
        
        return NavigationAction(
            action_type="skip",
            target_selector=None,
            target_text=None,
            form_values={},
            reason="Fallback: no portfolio elements found",
            confidence=0.1
        )
    
    def _fallback_action_from_text(self, text: str) -> NavigationAction:
        """Simple text-based fallback."""
        text_lower = text.lower()
        if "portfolio" in text_lower and ("disclosure" in text_lower or "monthly" in text_lower):
            return NavigationAction(
                action_type="navigate",
                target_selector=None,
                target_text=None,
                form_values={},
                reason="Fallback: page mentions portfolio disclosure",
                confidence=0.4
            )
        return NavigationAction(
            action_type="skip",
            target_selector=None,
            target_text=None,
            form_values={},
            reason="Fallback: no portfolio keywords",
            confidence=0.1
        )
    
    async def _execute_action(self, page, action: NavigationAction) -> None:
        """Execute VLM-recommended action on page."""
        
        if action.action_type == "click":
            if action.target_selector:
                await page.click(action.target_selector, timeout=5000)
            elif action.target_text:
                # Click by text
                await page.get_by_text(action.target_text, exact=False).first.click(timeout=5000)
            else:
                LOGGER.warning("Click action has no selector or text")
        
        elif action.action_type == "select":
            if action.target_selector and action.form_values:
                for field, value in action.form_values.items():
                    await page.select_option(action.target_selector, value=value, timeout=5000)
        
        elif action.action_type == "fill":
            for field, value in action.form_values.items():
                await page.fill(f"input[name='{field}'], select[name='{field}'], textarea[name='{field}']", value, timeout=5000)
        
        elif action.action_type == "navigate":
            if action.target_text:
                # Try to find and click link by text
                await page.get_by_text(action.target_text, exact=False).first.click(timeout=5000)
        
        elif action.action_type == "wait":
            await page.wait_for_timeout(3000)
        
        elif action.action_type == "download":
            # Files are captured via network monitoring
            pass
        
        elif action.action_type == "skip":
            pass
        
        else:
            LOGGER.warning("Unknown action type: %s", action.action_type)


def discover_portfolio_files_playwright_vlm(
    start_url: str,
    amc_name: str,
    vlm_endpoint: str = "http://192.168.1.10:9000/v1",
    vlm_model: str = "google/gemma-4-26b-a4b-qat",
    max_steps: int = 10,
    headless: bool = True,
    debug_dir: Path | None = None,
) -> list[str]:
    """
    High-level function to discover portfolio disclosure file URLs using Playwright + VLM.
    
    Args:
        start_url: AMC downloads/disclosure page URL
        amc_name: AMC name for context
        vlm_endpoint: OpenAI-compatible VLM endpoint
        vlm_model: Model name to use
        max_steps: Maximum navigation steps
        headless: Run browser headless
        debug_dir: Directory for debug screenshots
        
    Returns:
        List of portfolio disclosure file URLs
    """
    navigator = PlaywrightVLMNavigator(
        vlm_endpoint=vlm_endpoint,
        vlm_model=vlm_model,
        max_navigation_steps=max_steps,
        headless=headless,
        debug_dir=debug_dir,
    )
    
    result = navigator.navigate_to_portfolio(start_url, amc_name)
    
    if result.success:
        LOGGER.info("Successfully found %d portfolio files for %s", len(result.file_urls_found), amc_name)
        for url in result.file_urls_found:
            LOGGER.info("  %s", url)
    else:
        LOGGER.warning("Failed to find portfolio files for %s: %s", amc_name, result.error)
    
    return result.file_urls_found