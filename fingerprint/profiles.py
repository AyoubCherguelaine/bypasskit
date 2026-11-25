from dataclasses import dataclass

@dataclass(frozen=True)
class Profile:
    name: str
    impersonate: str          # curl_cffi target
    user_agent: str
    accept_language: str
    sec_ch_ua: str | None = None
    platform: str | None = None
    accept: str = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    viewport: tuple[int, int] = (1440, 900)
    timezone: str = "America/New_York"
    locale: str = "en-US"

def headers_for(p: Profile, referer: str | None = None) -> dict:
    """Insertion order matters — some WAFs hash the header sequence."""
    h = {
        "User-Agent": p.user_agent,
        "Accept": p.accept,
        "Accept-Language": p.accept_language,
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none" if not referer else "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }
    if p.sec_ch_ua:
        h["sec-ch-ua"] = p.sec_ch_ua
        h["sec-ch-ua-mobile"] = "?0"
        h["sec-ch-ua-platform"] = f'"{p.platform}"'
    if referer:
        h["Referer"] = referer
        h["Sec-Fetch-Site"] = "same-origin"
    return h

CHROME = Profile(
    name="chrome-124",
    impersonate="chrome124",
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    accept_language="en-US,en;q=0.9",
    sec_ch_ua='"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    platform="Windows",
)

SAFARI = Profile(
    name="safari-17",
    impersonate="safari17_0",
    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    accept_language="en-US,en;q=0.9",
    platform="macOS",
)

FIREFOX = Profile(
    name="firefox-133",
    impersonate="firefox133",
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    accept_language="en-US,en;q=0.5",
)