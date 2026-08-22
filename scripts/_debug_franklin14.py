"""Debug: Franklin - load file URL via Playwright, check response."""
import asyncio

from playwright.async_api import async_playwright

URL = ("https://www.franklintempletonindia.com/en-in/monthly-portfolio-dsclr/"
       "02b37620-f8be-4a77-aa6f-fa28e65107ec/Monthly-Portfolio-ISIN-31-Jul-2026.xlsx")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
        )
        page = await ctx.new_page()
        resp_info = {}

        async def with_page():
            await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(4000)

        try:
            resp = await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            if resp:
                print("status:", resp.status, "ct:", resp.headers.get("content-type"), "len:", len(await resp.body() if resp.status == 200 else b""))
        except Exception as e:
            print("goto EXC:", str(e)[:200])

        # capture any subsequent request to same url
        reqs = []
        page.on("response", lambda r: reqs.append((r.status, r.url[:120], r.headers.get("content-type", ""))))
        await page.wait_for_timeout(2000)
        print(reqs[:5])
        print("title:", await page.title())
        await browser.close()


asyncio.run(main())
