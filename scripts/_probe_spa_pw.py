"""One-off probe: UTI / Kotak / Franklin pages via Playwright (links + XHR capture)."""
import asyncio

from playwright.async_api import async_playwright

PAGES = [
    ("UTI", "https://www.utimf.com/downloads/consolidate-debt-portfolio-disclosure"),
    ("KOTAK", "https://www.kotakmf.com/Information/statutory-disclosure/information"),
    ("FRANKLIN", "https://www.franklintempletonindia.com/investor/reports?firstFilter-10"),
]


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1366, "height": 900},
        )
        for label, url in PAGES:
            page = await ctx.new_page()
            xhrs = []

            def on_response(resp, _label=label):
                u = resp.url
                ct = resp.headers.get("content-type", "")
                if resp.request.resource_type in ("xhr", "fetch") or "json" in ct:
                    xhrs.append((resp.status, resp.request.method, u[:170]))

            page.on("response", on_response)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(8000)
            except Exception as e:
                print(f"### {label} goto EXC: {e}")
                continue
            links = await page.eval_on_selector_all(
                "a[href]",
                "els => els.map(e => e.getAttribute('href')).filter(h => /\\.(xlsx?|zip)(\\?|$)/i.test(h || ''))",
            )
            print(f"### {label}: {len(set(links))} unique file links")
            for l in sorted(set(links))[:10]:
                print("   ", l[:160])
            print(f"   XHR/fetch calls ({len(xhrs)}):")
            seen = set()
            for st, m, u in xhrs:
                if u not in seen:
                    seen.add(u)
                    print(f"    {st} {m} {u}")
            await page.close()
        await browser.close()


asyncio.run(main())
