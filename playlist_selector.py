#!/usr/bin/env python3
"""
playlist_selector.py

- Supports HTTP and local M3U
- Reloads saved config (local only)
- Clean prompts
- No crashes
"""

import json
import re
import subprocess
import shutil
import urllib.request
from collections import defaultdict
from pathlib import Path

# ----------------------------------------------------------------------
# Constants & configuration
# ----------------------------------------------------------------------
print("Script started") #####--------------debug start

HOME = Path("/home/jerry")
EDITOR_PATH = HOME / "m3u-epg-editor" / "m3u-epg-editor-py3.py"
CONFIG_PATH = Path("m3u-editor-config.json")
TEMP_DIR = Path("temp_m3u_editor_output")
TRIMMED_DIR = HOME / "m3u-epg-editor" / "trimlist" / "trimmed"

GROUP_PAGE_SIZE = 150
CHANNEL_PAGE_SIZE = 25
COLUMNS = 3
COL_WIDTH = 50

# ----------------------------------------------------------------------
# Blocked channel keywords (case‑insensitive)
# ----------------------------------------------------------------------
BLOCKED_KEYWORDS = [
    "sports", "adult", "nfl", "nba", "nhl", "mlb", "football", "baseball",
    "soccer", "espn", "fox sports", "bein", "sky sports", "ncaa", "wwe", "ufc",
    "boxing", "tennis", "golf", "cricket", "rugby", "f1", "motogp", "nascar"
]
BLOCKED_PATTERN = re.compile("|".join(map(re.escape, BLOCKED_KEYWORDS)),
                             re.IGNORECASE)


def is_blocked(name: str) -> bool:
    """Return True if the channel name matches any blocked keyword."""
    return bool(BLOCKED_PATTERN.search(name))


# ----------------------------------------------------------------------
# Input helpers
# ----------------------------------------------------------------------
def input_with_retry(prompt: str, default=None, validator=None):
    """Prompt repeatedly until a non‑empty, valid value is entered."""
    while True:
        value = input(prompt).strip()
        if not value and default is not None:
            value = default
        if not value:
            print("Empty input not allowed.")
            continue
        if validator and not validator(value):
            print("Invalid input. Try again.")
            continue
        return value


def validate_file_path(path_str: str) -> bool:
    """Return True if the path exists and is a regular file."""
    p = Path(path_str).expanduser().resolve()
    return p.is_file()


def validate_url(url: str) -> bool:
    """Very light URL validation – must start with http/https/file."""
    if not url.startswith(("http://", "https://", "file://")):
        return False
    if url.startswith("file://"):
        return validate_file_path(url[7:])
    # HEAD request – quick check that the resource exists
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=5):
            return True
    except Exception:
        return False


# ----------------------------------------------------------------------
# M3U handling
# ----------------------------------------------------------------------
def download_http_m3u(url: str) -> Path | None:
    """Download an M3U file from HTTP(S) and store it under TEMP_DIR."""
    print(f"Downloading from {url} …")
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        dest = TEMP_DIR / "downloaded.m3u"
        dest.write_text(content, encoding="utf-8")
        print(f"Saved to {dest}")
        return dest
    except Exception as exc:
        print(f"Failed to download: {exc}")
        return None


def load_m3u(m3u_path: Path):
    """
    Parse an M3U file.
    Returns:
        groups: dict mapping group name → set of channel names
        channels: dict mapping channel name → {"group": str, "enabled": bool}
    """
    if not m3u_path.is_file():
        print(f"File not found: {m3u_path}")
        return {}, {}

    groups = defaultdict(set)
    channels = {}
    blocked_cnt = 0

    with m3u_path.open(encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("#EXTINF:"):
                continue

            # Extract group‑title if present
            g_match = re.search(r'group-title="([^"]*)"', line)
            group = g_match.group(1) if g_match else "No Group"

            # Channel name is the text after the last comma
            name = line.split(",", 1)[-1].strip()
            if not name:
                continue

            enabled = not is_blocked(name)
            if not enabled:
                blocked_cnt += 1

            channels[name] = {"group": group, "enabled": enabled}
            groups[group].add(name)

    print(f"Found {len(groups)} groups, {len(channels)} channels.")
    print(f"Auto‑disabled {blocked_cnt} sports/adult channels.")
    return dict(groups), channels


# ----------------------------------------------------------------------
# UI helpers (printing, pagination, toggling)
# ----------------------------------------------------------------------
def toggle_item(enabled: bool) -> str:
    """Return '[X]' if enabled else '[ ]'."""
    return "[X]" if enabled else "[ ]"


def truncate(text: str, width: int) -> str:
    """Shorten text to `width` characters, adding ellipsis if needed."""
    return text[:width - 3] + "..." if len(text) > width else text


def print_groups_3x50(items, start, enabled_dict):
    """Display groups in 3 columns, 50 rows per column."""
    end = min(start + GROUP_PAGE_SIZE, len(items))
    print("\n=== GROUPS (150 per page: 3×50) ===")
    print(f"Items {start + 1}-{end} of {len(items)}")
    print("-" * 156)

    col_size = 50
    col1 = items[start:start + col_size]
    col2 = items[start + col_size:start + col_size * 2]
    col3 = items[start + col_size * 2:end]

    for i in range(col_size):
        line = ""
        for col_idx, col_data in enumerate([col1, col2, col3], 1):
            if i < len(col_data):
                idx = start + (col_idx - 1) * col_size + i
                item = col_data[i]
                status = toggle_item(enabled_dict.get(item, False))
                entry = f"{idx + 1:3}. {status} {item}"
                entry = truncate(entry, COL_WIDTH)
                line += f"{entry:<{COL_WIDTH + 2}}"
            else:
                line += " " * (COL_WIDTH + 2)
        print(line.rstrip())
    print("-" * 156)


def paginated_groups_selector(all_items, enabled_dict, all_groups):
    """Interactive selector for groups (keep/discard)."""
    sorted_items = sorted(all_items)
    start = 0
    search_query = ""

    while True:
        # Apply search filter
        display = [
            g for g in sorted_items
            if not search_query or search_query.lower() in g.lower()
        ]

        if not display:
            print("No groups match search.")
            search_query = ""
            continue

        print_groups_3x50(display, start, enabled_dict)

        total_pages = (len(display) - 1) // GROUP_PAGE_SIZE + 1
        current_page = start // GROUP_PAGE_SIZE + 1
        print(
            "Commands: n=next, p=prev, a=all on page, A=ALL, N=DISABLE ALL, q=save"
        )
        choice = input(f"Page {current_page}/{total_pages} > ").strip()

        if choice == "q":
            break
        elif choice == "n" and start + GROUP_PAGE_SIZE < len(display):
            start += GROUP_PAGE_SIZE
        elif choice == "p" and start >= GROUP_PAGE_SIZE:
            start -= GROUP_PAGE_SIZE
        elif choice == "a":
            for g in display[start:start + GROUP_PAGE_SIZE]:
                enabled_dict[g] = True
            print("All on page selected.")
        elif choice == "A":
            for g in all_groups:
                enabled_dict[g] = True
            print(f"ALL {len(all_groups)} groups selected!")
            break
        elif choice == "N":
            for g in all_groups:
                enabled_dict[g] = False
            print(f"ALL {len(all_groups)} groups disabled!")
        elif choice.startswith("/"):
            search_query = choice[1:]
            start = 0
            print(f"Searching for: {search_query}")
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(display):
                grp = display[idx]
                enabled_dict[grp] = not enabled_dict.get(grp, False)
        else:
            print("Invalid input.")

    # Return only the groups that stayed enabled
    return {g: v for g, v in enabled_dict.items() if v}


def print_3col(items, start, enabled_dict, title, page_size):
    """Print items in 3 columns (used for channels)."""
    end = min(start + page_size, len(items))
    print(f"\n=== {title} ===")
    print(f"Items {start + 1}-{end} of {len(items)}")
    print("-" * 156)

    chunk = (page_size + COLUMNS - 1) // COLUMNS
    rows = []
    for i in range(chunk):
        row = []
        for col in range(COLUMNS):
            idx = start + i + col * chunk
            if idx < end:
                item = items[idx]
                status = toggle_item(enabled_dict.get(item, False))
                entry = f"{idx + 1:3}. {status} {item}"
                entry = truncate(entry, COL_WIDTH)
                row.append(entry)
            else:
                row.append("")
        rows.append(row)

    for row in rows:
        line = ""
        for cell in row:
            line += f"{cell:<{COL_WIDTH + 2}}"
        print(line.rstrip())
    print("-" * 156)


def paginated_channels_selector(all_items, enabled_dict, all_channels):
    """Interactive selector for channels (keep/discard)."""
    sorted_items = sorted(all_items)
    start = 0
    search_query = ""

    while True:
        display = [
            c for c in sorted_items
            if not search_query or search_query.lower() in c.lower()
        ]

        if not display:
            print("No channels match search.")
            search_query = ""
            continue

        print_3col(display, start, enabled_dict, "CHANNELS", CHANNEL_PAGE_SIZE)

        total_pages = (len(display) - 1) // CHANNEL_PAGE_SIZE + 1
        current_page = start // CHANNEL_PAGE_SIZE + 1
        print("Commands: n=next+deselect, p=prev, a=all on page, "
              "A=ALL, N=DISABLE ALL, q=save")
        choice = input(f"Page {current_page}/{total_pages} > ").strip()

        if choice == "q":
            break
        elif choice == "n":
            # Deselect everything on the current page
            for ch in display[start:start + CHANNEL_PAGE_SIZE]:
                enabled_dict[ch] = False
            print("All on page deselected.")
            if start + CHANNEL_PAGE_SIZE < len(display):
                start += CHANNEL_PAGE_SIZE
        elif choice == "p" and start >= CHANNEL_PAGE_SIZE:
            start -= CHANNEL_PAGE_SIZE
        elif choice == "a":
            for ch in display[start:start + CHANNEL_PAGE_SIZE]:
                enabled_dict[ch] = True
            print("All on page selected.")
        elif choice == "A":
            for ch in all_channels:
                enabled_dict[ch] = True
            print(f"ALL {len(all_channels)} channels selected!")
            break
        elif choice == "N":
            for ch in all_channels:
                enabled_dict[ch] = False
            print(f"ALL {len(all_channels)} channels disabled!")
        elif choice.startswith("/"):
            search_query = choice[1:]
            start = 0
            print(f"Searching for: {search_query}")
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(display):
                ch = display[idx]
                enabled_dict[ch] = not enabled_dict.get(ch, False)
        else:
            print("Invalid input.")

    return {c: v for c, v in enabled_dict.items() if v}


# ----------------------------------------------------------------------
# Main workflow
# ----------------------------------------------------------------------
def main():
    print("M3U Playlist Selector + Output → trimmed/")
    print("=" * 156)

    # Ensure temporary directories exist
    TRIMMED_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------
    # 1️⃣ Choose M3U source (file or HTTP)
    # --------------------------------------------------------------
    print("M3U SOURCE: Enter 'file' or 'http'")
    source_type = input("Source [file]: ").strip().lower() or "file"

    m3u_path = None
    m3u_url = None

    if source_type == "http":
        m3u_url = input_with_retry("HTTP M3U URL: ", validator=validate_url)
        print(f"Using HTTP URL: {m3u_url}")
        m3u_path = download_http_m3u(m3u_url)
        if not m3u_path:
            return
    elif source_type == "file":
        while not m3u_path:
            m3u_input = input_with_retry(f"Local M3U file path [{HOME}]: ",
                                         default=str(HOME),
                                         validator=validate_file_path)
            m3u_path = Path(m3u_input).expanduser().resolve()
            if not m3u_path.is_file():
                print(f"File not found: {m3u_path}")
                m3u_path = None
    else:
        print("Invalid choice. Use 'file' or 'http'")
        return

    # --------------------------------------------------------------
    # 2️⃣ Reload saved session (if any)
    # --------------------------------------------------------------
    saved_config_path = None
    saved_groups_path = None
    if m3u_path:
        saved_config_path = m3u_path.with_name(m3u_path.stem + ".config.json")
        saved_groups_path = m3u_path.with_suffix(".groups.json")

        if saved_config_path.is_file():
            print("\nFound saved session:")
            print(f"  Config: {saved_config_path.name}")
            print(
                f"  Groups: {saved_groups_path.name if saved_groups_path.is_file() else 'none'}"
            )
            reload = input("Reload saved session? (y/n) [y]: ").strip().lower()
            if reload in ("", "y", "yes"):
                try:
                    config = json.loads(saved_config_path.read_text())
                    CONFIG_PATH.write_text(json.dumps(config, indent=2))
                    print("Reloaded saved config!")

                    # Run the editor immediately with the restored config
                    print("\nRunning m3u‑epg‑editor …")
                    result = subprocess.run(
                        ["python3",
                         str(EDITOR_PATH), "-j",
                         str(CONFIG_PATH)],
                        capture_output=True,
                        text=True)
                    if result.returncode != 0:
                        print("Editor failed:")
                        print(result.stderr)
                        return

                    # Copy generated files to the trimmed folder
                    print(f"\nCopying results to: {TRIMMED_DIR}")
                    expected = [
                        "original.m3u", "original.channels.txt",
                        "original.xml", "no_epg_channels.txt", "selected.m3u8",
                        "selected.xml", "process.log"
                    ]
                    for fname in expected:
                        src = TEMP_DIR / fname
                        dst = TRIMMED_DIR / fname.replace("selected", "output")
                        if src.is_file():
                            shutil.copy2(src, dst)
                            print(f"  Copied: {dst.name}")

                    # Save the config alongside the output
                    shutil.copy2(CONFIG_PATH,
                                 TRIMMED_DIR / "m3u-editor-config.json")
                    print("  Copied: m3u-editor-config.json")

                    print("\nDone! All output →", TRIMMED_DIR)
                    shutil.rmtree(TEMP_DIR, ignore_errors=True)
                    return
                except Exception as e:
                    print(f"Failed to load config: {e}")
                    print("Starting fresh…")

    # --------------------------------------------------------------
    # 3️⃣ Fresh start – parse the M3U
    # --------------------------------------------------------------
    print("Loading M3U file...")
    groups_dict, channels_dict = load_m3u(m3u_path)
    print("M3U file loaded.")
    print(f"Groups: {groups_dict}")
    print(f"Channels: {channels_dict}")
    print("End of script") #---------------debug end
    all_groups = list(groups_dict.keys())

    # Initialise group enable‑state (all disabled)
    group_enabled = {g: False for g in all_groups}
    if saved_groups_path and saved_groups_path.is_file():
        try:
            saved = json.loads(saved_groups_path.read_text())
            for g in saved:
                if g in group_enabled:
                    group_enabled[g] = True
            print(f"Restored {len(saved)} saved groups.")
        except Exception:
            pass

    print("\nSelect GROUPS to KEEP (150 per page: 3×50)")
    enabled_groups = paginated_groups_selector(all_groups, group_enabled,
                                               all_groups)
    if saved_groups_path:
        saved_groups_path.write_text(json.dumps(list(enabled_groups.keys())),
                                     encoding="utf-8")

    # --------------------------------------------------------------
    # 4️⃣ Filter channels based on selected groups
    # --------------------------------------------------------------
    filtered_channels = [
        name for name, data in channels_dict.items()
        if data["group"] in enabled_groups
    ]
    # Build a dict of channel → enabled flag (only for the filtered channels)
    channel_enabled = {
        name: data["enabled"]
        for name, data in channels_dict.items() if name in filtered_channels
    }

    # --------------------------------------------------------------
    # 5️⃣ Channel selector (keep/discard)
    # --------------------------------------------------------------
    print(f"\nFiltered to {len(filtered_channels)} channels.")

