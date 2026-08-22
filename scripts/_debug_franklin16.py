"""Debug: Franklin - deep-link filters + capture real download URLs."""
import asyncio

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
            viewport={"width": 1366, "height": 900},
            accept_downloads=True,
        )
        page = await ctx.new_page()
        hits = []
        page.on("response", lambda r: hits.append((r.status, r.url[:150], r.headers.get("content-type", "")[:40]))
                if ("xlsx" in r.url.lower() or "xls" in r.url.lower()) else None)
        for f in (12, 13):
            url = f"https://www.franklintempletonindia.com/investor/reports?firstFilter-{f}"
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(8000)
            except Exception as e:
                print(f"filter {f} EXC:", str(e)[:120])
                continue
            title_sel = await page.title()
            links = await page.eval_on_selector_all(
                "a[href]",
                "els => els.map(e => ({h: e.getAttribute('href'), t: e.innerText.slice(0,60)})).filter(x => /portfol/i.test(x.h || '') || /portfol/i.test(x.t || ''))",
            )
            print(f"### filter {f}: title={title_sel!r} portfolio-ish links={len(links)}")
            for l in links[:5]:
                print("   ", l)
        print("captured xls responses:", hits[:10])
        await browser.close()


asyncio.run(main())
