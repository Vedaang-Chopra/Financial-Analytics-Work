"""One-off probe: find SBI DataBindUrls endpoint definitions."""
import requests, time

H = {"User-Agent": "Mozilla/5.0"}
candidates = [
    "/Content/Service/DataBindUrls.js",
    "/Content/Service/APIURLS.js",
    "/Content/Service/Urls.js",
    "/Content/Service/TokenService.js",
    "/Content/Service/EncryptionService.js",
    "/Content/Service/StoreKeys.js",
]
for c in candidates:
    try:
        r = requests.get("https://www.sbimf.com" + c, headers=H, timeout=20)
        hit = r.status_code == 200 and len(r.text) > 100
        print(("HIT " if hit else "miss"), c, r.status_code, len(r.text))
        if hit:
            up = r.text.upper()
            if "SCHEME_PORTFOLIO" in up or "DATABINDURLS" in up:
                print(r.text[:3000])
    except Exception as e:
        print("EXC", c, e)
    time.sleep(1)
