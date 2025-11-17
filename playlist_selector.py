#!/usr/bin/env python3
"""FINAL – next/prev fixed, quit works, full debug, saves everything"""

import json, re, sys, urllib.request
from pathlib import Path
from collections import defaultdict

FILE_JSON = Path("citrus_file.json")
HTTP_JSON = Path("citrus_http.json")

def download_m3u(url):
    print(f"DEBUG: Downloading M3U → {url}")
    try:
        with urllib.request.urlopen(url) as r:
            content = r.read().decode("utf-8", errors="ignore")
        print(f"DEBUG: M3U downloaded – {len(content):,} bytes")
        return content
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

def find_local_m3u():
    files = list(Path(".").glob("*.m3u*"))
    if not files:
        print("ERROR: No .m3u/.m3u8 found")
        sys.exit(1)
    path = files[0]
    print(f"DEBUG: Using local → {path.name}")
    return path.read_text(encoding="utf-8", errors="ignore")

def load_m3u_from_content(content):
    groups = defaultdict(set)
    channels = {}
    extinf = None
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("#EXTINF:"):
            extinf = line
        elif line.startswith("http") and extinf:
            group = re.search(r'group-title="([^"]*)"', extinf)
            group = group.group(1) if group else "Unknown"
            name = re.search(r'tvg-name="([^"]*)"', extinf)
            name = name.group(1) if name else extinf.split(",", 1)[-1].strip()
            if name:
                channels[name] = {"group": group}
                groups[group].add(name)
            extinf = None
    print(f"DEBUG: Parsed {len(channels)} channels, {len(groups)} groups")
    return dict(groups), channels

def load_config(file):
    if file.exists():
        try: return json.loads(file.read_text(encoding="utf-8"))
        except: pass
    return {}

def save_config(file, m3u_url=None, epg_url=None, groups=None, include=None, discard=None):
    cfg = load_config(file)
    if m3u_url: cfg["m3uurl"] = m3u_url
    if epg_url: cfg["epgurl"] = epg_url
    if groups is not None:
        cfg.update({
            "groups": sorted(groups),
            "groupmode": "keep",
            "include_channels": sorted(include or []),
            "discard_channels": sorted(discard or [])
        })
    file.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print(f"SAVED → {file.name}")

def selector(items, title, saved=None, all_items=None, cfg_file=None):
    items = sorted(items)
    selected = set(saved) if saved else set()
    page = 0
    while True:
        start = page * 28
        end = min(start + 28, len(items))
        print(f"\n=== {title} ({len(items)} total) === Page {page+1}/{((len(items)-1)//28)+1}")
        print("-" * 80)
        for i, item in enumerate(items[start:end], start + 1):
            print(f"{i:3}. [{'X' if item in selected else ' '}] {item}")
        print("-" * 80)
        print("next prev all none rescan quit save 1-35")
        c = input("> ").strip().lower()

        if c in ("quit", "q"):
            print(f"DEBUG: QUIT – returning {len(selected)} items")
            if title == "CHANNELS":
                discard = (all_items or set()) - selected
                return selected, discard
            return selected

        if c == "save" and cfg_file:
            if title == "GROUPS":
                save_config(cfg_file, groups=selected)
            else:
                discard = (all_items or set()) - selected
                save_config(cfg_file, groups=None, include=selected, discard=discard)
            continue

        if c == "all": selected.update(items)
        elif c == "none": selected.clear()
        elif c == "rescan": return set()
        elif c == "prev" and page > 0: page -= 1
        elif c == "next" and end < len(items): page += 1
        elif c.isdigit() or ("-" in c):
            try:
                if "-" in c:
                    s, e = map(int, c.split("-"))
                    s, e = s-1, e-1
                else:
                    s = e = int(c)-1
                if 0 <= s <= e < len(items):
                    for i in range(s, e+1):
                        selected.symmetric_difference_update([items[i]])
            except: print("bad input")

def main():
    print("1) File  2) HTTP")
    mode = input("Choose [1]: ").strip() or "1"
    cfg_file = FILE_JSON if mode == "1" else HTTP_JSON

    m3u_url = None
    epg_url = None

    if mode == "2":
        print("\nHTTP MODE")
        m3u_url = input("M3U URL: ").strip()
        epg_url = input("EPG URL (optional): ").strip()
        if not m3u_url:
            print("URL required")
            sys.exit(1)
        content = download_m3u(m3u_url)
    else:
        content = find_local_m3u()

    groups, channels = load_m3u_from_content(content)
    cfg = load_config(cfg_file)

    keep_groups = selector(list(groups.keys()), "GROUPS", cfg.get("groups"), cfg_file=cfg_file)
    if not keep_groups:
        print("No groups selected")
        sys.exit(0)

    filtered = [c for c in channels if channels[c]["group"] in keep_groups]
    print(f"DEBUG: Filtered channels → {len(filtered)}")
    keep_channels, discard_channels = selector(
        filtered, "CHANNELS",
        cfg.get("include_channels"),
        all_items=set(filtered),
        cfg_file=cfg_file
    )

    save_config(cfg_file, m3u_url=m3u_url, epg_url=epg_url,
                groups=keep_groups, include=keep_channels, discard=discard_channels)

    print("\nDONE! Run:")
    print(f"python3 ~/m3u-epg-editor/m3u-epg-editor-py3.py -j {cfg_file}")

if __name__ == "__main__":
    main()
