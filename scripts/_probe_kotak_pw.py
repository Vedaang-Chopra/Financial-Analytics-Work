"""One-off probe 17: Kotak via Playwright (single attempt)."""
import asyncio

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            viewport={"width": 1366, "height": 900},
        )
        page = await ctx.new_page()
        try:
            await page.goto(
                "https://www.kotakmf.com/Information/statutory-disclosure/information",
                wait_until="domcontentloaded",
                timeout=60000,
            )
            await page.wait_for_timeout(10000)
            title = await page.title()
            print("title:", title)
            links = await page.eval_on_selector_all(
                "a[href]",
                "els => els.map(e => e.getAttribute('href')).filter(h => /\\.(xlsx?|zip)(\\?|$)/i.test(h || ''))",
            )
            print("file links:", len(set(links)))
            for l in sorted(set(links))[:10]:
                print("   ", l[:160])
        except Exception as e:
            print("EXC:", e)
        await browser.close()


asyncio.run(main())
