from enum import Enum

class Challenge(str, Enum):
    NONE = "none"
    CF_JS = "cf_js"
    CF_TURNSTILE = "cf_turnstile"
    DATADOME = "datadome"
    PERIMETERX = "perimeterx"
    AKAMAI = "akamai"
    RECAPTCHA = "recaptcha"
    RATE_LIMIT = "rate_limit"
    UNKNOWN = "unknown"

_CF = ("just a moment", "__cf_chl_opt", "/cdn-cgi/challenge-platform/", "cf_chl_prog", "cf-browser-verification")
_TURNSTILE = ("challenges.cloudflare.com", "cf-turnstile", "turnstile")
_PX = ("_pxcaptcha", "px-captcha", "perimeterx")
_DD = ("captcha-delivery.com", "datadome", "x-dd-b")
_AK = ("reference #", "akamai", "_abck")

def _hit(body: str, needles) -> bool:
    return any(n in body for n in needles)

def detect(status: int, headers: dict, body: str, url: str) -> Challenge:
    h = {k.lower(): v for k, v in headers.items()}
    b = (body or "")[:200_000].lower()

    if status == 429:
        return Challenge.RATE_LIMIT
    if "cf-mitigated" in h:
        return Challenge.CF_TURNSTILE if _hit(b, _TURNSTILE) else Challenge.CF_JS
    if status in (403, 503):
        if _hit(b, _TURNSTILE):
            return Challenge.CF_TURNSTILE
        if _hit(b, _DD):
            return Challenge.DATADOME
        if _hit(b, _PX):
            return Challenge.PERIMETERX
        if _hit(b, _AK):
            return Challenge.AKAMAI
        if _hit(b, _CF):
            return Challenge.CF_JS
        return Challenge.UNKNOWN
    if status == 200 and _hit(b, ("g-recaptcha", "hcaptcha.com")):
        return Challenge.RECAPTCHA
    if status == 200 and _hit(b, _CF):
        return Challenge.CF_JS
    return Challenge.NONE