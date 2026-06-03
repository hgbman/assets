#!/usr/bin/env python3
import json
import urllib.request
import urllib.error
import os
import sys

EMULATORS_JSON = "emulators.json"
TIMEOUT        = 20
BROKEN         = []
OK             = []

with open(EMULATORS_JSON, encoding="utf-8") as f:
    data = json.load(f)

token = os.environ.get("GH_TOKEN", "")
headers_base = {"User-Agent": "HGB-URLChecker/1.0"}
if token:
    headers_base["Authorization"] = "Bearer " + token

GH_RELEASE_PREFIX = "github-release:"

def resolve_github_release(name, url):
    path  = url[len(GH_RELEASE_PREFIX):]
    parts = path.split("/", 2)
    if len(parts) < 3:
        raise ValueError("Formato invalido: " + url)
    owner, repo, tag = parts
    api_url = "https://api.github.com/repos/" + owner + "/" + repo + "/releases/tags/" + tag
    req = urllib.request.Request(api_url, headers=dict(
        list(headers_base.items()) + [
            ("Accept", "application/vnd.github+json"),
            ("X-GitHub-Api-Version", "2022-11-28"),
        ]
    ))
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        release = json.loads(resp.read())
    assets = release.get("assets", [])
    if not assets:
        raise ValueError("Release '" + tag + "' no tiene assets")
    exts = (".7z", ".zip", ".exe")
    for asset in assets:
        dl = asset.get("browser_download_url", "")
        if any(asset["name"].lower().endswith(e) for e in exts) and dl:
            return dl, asset["name"]
    raise ValueError("Ningun asset descargable en release '" + tag + "'")

entries_with_url = [(e["name"], e["url"]) for e in data if e.get("url", "")]
print("Verificando " + str(len(entries_with_url)) + " URLs...\n")

for name, url in entries_with_url:
    try:
        if url.startswith(GH_RELEASE_PREFIX):
            dl_url, asset_name = resolve_github_release(name, url)
            print("  OK  [gh-release] " + name + "  ->  " + asset_name)
            OK.append((name, url, "gh-release"))
        else:
            req = urllib.request.Request(url, method="HEAD", headers=headers_base)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                code = resp.status
                if code < 400:
                    print("  OK  [" + str(code) + "] " + name)
                    OK.append((name, url, code))
                else:
                    print("  ERR [" + str(code) + "] " + name + "  ->  " + url)
                    BROKEN.append((name, url, code))
    except urllib.error.HTTPError as e:
        print("  ERR [" + str(e.code) + "] " + name + "  ->  " + url)
        BROKEN.append((name, url, e.code))
    except Exception as e:
        print("  ERR [---] " + name + "  ->  " + url + "  (" + str(e) + ")")
        BROKEN.append((name, url, str(e)))

print("\nResultado: " + str(len(OK)) + " OK, " + str(len(BROKEN)) + " con problemas")

with open("/tmp/broken_urls.txt", "w") as f:
    if BROKEN:
        for name, url, code in BROKEN:
            f.write("- " + name + ": [" + str(code) + "] " + url + "\n")
    else:
        f.write("")

github_output = os.environ.get("GITHUB_OUTPUT", "")
if github_output:
    with open(github_output, "a") as out:
        out.write("broken_count=" + str(len(BROKEN)) + "\n")
        out.write("ok_count=" + str(len(OK)) + "\n")

if BROKEN:
    sys.exit(1)
