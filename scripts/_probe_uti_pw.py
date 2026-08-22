"""One-off probe 5: UTI scheme-wise portfolio pages via Playwright."""
import asyncio

from playwright.async_api import async_playwright

PAGES = [
    ("UTI scheme-wise", "https://www.utimf.com/downloads/scheme-wise-portfolio-disclosure"),
    ("UTI consolidate-debt", "https://www.utimf.com/downloads/consolidate-debt-portfolio-disclosure"),
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
            apis = []
            page.on("response", lambda r: apis.append((r.status, r.url)) if "/api/" in r.url else None)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(7000)
            except Exception as e:
                print(f"### {label} EXC: {e}")
                continue
            links = await page.eval_on_selector_all(
                "a[href]",
                "els => els.map(e => e.getAttribute('href')).filter(h => /\\.(xlsx?|zip)(\\?|$)/i.test(h || ''))",
            )
            print(f"### {label}: {len(set(links))} unique file links")
            for l in sorted(set(links))[:8]:
                print("   ", l[:160])
            seen = set()
            print("   APIs:")
            for st, u in apis:
                if u not in seen:
                    seen.add(u)
                    print(f"    {st} {u[:150]}")
            await page.close()
        await browser.close()


asyncio.run(main())
