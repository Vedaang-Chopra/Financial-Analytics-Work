"""Debug: Franklin document-by-uuid endpoint variants."""
import requests

H = {"User-Agent": "Mozilla/5.0"}
base = "https://www.franklintempletonindia.com/api/literature/v1"
uid = "02b37620-f8be-4a77-aa6f-fa28e65107ec"
for u in [
    f"{base}/documents/{uid}",
    f"{base}/documents?documentId={uid}",
    f"{base}/documents?id={uid}",
    f"{base}/document/{uid}",
]:
    rr = requests.get(u, headers=H, timeout=60, allow_redirects=False)
    print(rr.status_code, rr.headers.get("content-type", "")[:30], len(rr.content), u[:90])
    if rr.is_redirect or rr.status_code in (301, 302, 303, 307):
        print("   ->", rr.headers.get("location"))
