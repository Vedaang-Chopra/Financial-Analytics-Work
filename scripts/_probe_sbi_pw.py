"""One-off probe: SBI portfolios page via Playwright + network capture."""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        reqs = []

        def on_response(resp):
            if "sbimf.com" in resp.url and resp.request.method == "POST":
                reqs.append((resp.request.method, resp.request.post_data, resp.url))

        page.on("response", lambda r: reqs.append((r.request.method, r.request.post_data, r.url)))
        await page.goto("https://www.sbimf.com/portfolios", wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(6000)
        print("--- POST/XHR requests seen:")
        for m, d, u in reqs:
            if m == "POST":
                print("  ", u[:150], "| data:", str(d)[:200])
        # table content
        html = await page.inner_html("#tblPortfoliosheets")
        print("--- tblPortfoliosheets len:", len(html))
        print(html[:3000])
        await browser.close()


asyncio.run(main())
