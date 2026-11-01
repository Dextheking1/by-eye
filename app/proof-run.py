#!/usr/bin/env python3
"""By Eye app web proof: home, analyzing, result on the sample plate."""
import json
import os
import time

from playwright.sync_api import sync_playwright

OUT = "/home/hatch/workspace/by-eye/app/proof"
os.makedirs(OUT, exist_ok=True)
URL = "http://127.0.0.1:18761/"


def log(**kw):
    print(json.dumps(kw), flush=True)


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.goto(URL, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(1500)
    text = page.inner_text("body")
    log(step="home", has_sample=("sample plate" in text.lower()),
        text_snip=text[:200].replace("\n", " | "))
    page.screenshot(path=os.path.join(OUT, "home.png"))

    page.get_by_text("Try a sample plate").click()
    page.wait_for_timeout(3000)
    text = page.inner_text("body")
    log(step="analyzing", text_snip=text[:200].replace("\n", " | "))
    page.screenshot(path=os.path.join(OUT, "analyzing.png"))

    t0 = time.time()
    ok = False
    while time.time() - t0 < 300:
        text = page.inner_text("body")
        if "grilled chicken" in text.lower() or "measured by sam" in text.lower():
            ok = True
            break
        page.wait_for_timeout(3000)
    log(step="result", reached=ok, secs=round(time.time() - t0),
        text_snip=text[:400].replace("\n", " | "))
    page.wait_for_timeout(2500)
    page.screenshot(path=os.path.join(OUT, "result.png"))
    browser.close()
log(done=True)
