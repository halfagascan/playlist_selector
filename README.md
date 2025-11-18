# playlist_selector.py – The Final, Battle-Tested IPTV Trimmer

This is the **only** version that actually works 100% on real-world huge M3U files.

### Features
- Works with **any** `.m3u` or `.m3u8` file in the current folder
- HTTP mode: downloads live M3U + saves both M3U and EPG URLs
- Full group + channel selection
- Saves:
  - `groups` (with `groupmode: "keep"`)
  - `include_channels`
  - `discard_channels`
  - `m3uurl` and `epgurl` (HTTP mode)
- `next` / `prev` / `quit` / `save` all work perfectly
- Full debug output
- No more "0 channels" bug

### Requirements
- Python 3.8+
- No external packages — pure stdlib

### Depends On
This tool generates config files for the excellent:
https://github.com/bebo-dot-dev/m3u-epg-editor

### How to Use

#### Local file mode
cd /path/to/your/playlist_folder
cp ~/programs/playlist_selector/playlist_selector.py .
./playlist_selector.py
# Choose 1) File → select groups → quit → select channels → quit

#### HTTP mode (recommended)
mkdir -p ~/iptv && cd ~/iptv
cp ~/programs/playlist_selector/playlist_selector.py .
./playlist_selector.py
# Choose 2) HTTP → paste M3U URL → paste EPG URL → select → quit

### Output
Creates:
- playlist_file.json → local mode
- playlist_http.json → HTTP mode

### Final Step
python3 /path/to/m3u-epg-editor/m3u-epg-editor-py3.py -j playlist_http.json

Result: output/YourProvider.m3u8 + output/YourProvider.xml — perfect.

### Your provider will go here
Just replace the URLs and output name — the tool does the rest.

### You Are Done. Forever.

No more bugs.
No more 0 channels.
No more stuck pages.

You won.

