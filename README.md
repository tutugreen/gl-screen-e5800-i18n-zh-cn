# gl-screen-e5800-i18n-zh-cn

Unofficial Simplified Chinese pack for the GL.iNet **GL-E5800** screen UI (OpenWrt **ipk**).

| | |
|---|---|
| Maintainer | [tutugreen](https://tutu.green) |
| Fonts | [IBM Plex Sans SC](https://github.com/IBM/plex/releases?q=sc) — downloaded and modified in CI (metrics only); shipped as `*_tutu_zh-cn.ttf` |
| Affiliation | Not affiliated with GL.iNet |

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [LICENSE](LICENSE). Complete [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) before publishing.

## Repository layout

```
sources/          en + zh_cn (tracked; font names point to *_tutu_zh-cn)
overlay/          ipk tree — generated, gitignored except .gitkeep
config/           device-font-metrics.json
package/scripts/  opkg hooks
scripts/          download → build fonts → sync lang → ipk
```

Private notes: `local/notes.md` (gitignored); see [docs/local-notes.example.md](docs/local-notes.example.md).

## CI (GitHub Actions)

Workflow **Build IPK** (`workflow_dispatch`):

1. Download `ibm-plex-sans-sc.zip` from IBM/plex releases
2. `prepare_overlay.py` — build `*_tutu_zh-cn.ttf` + sync `text/default`
3. `validate_zh_cn.py`
4. `build_ipk.py` — version `YYYY-MM-DD-HH-MM-SS` (UTC)

No font binaries are stored in git.

## Local build

```sh
cd gl-screen-e5800-i18n-zh-cn
pip install -r requirements.txt
python scripts/prepare_overlay.py
python scripts/build_ipk.py
```

## Install

Requires the stock screen UI package (opkg will check this):

| Package | Version |
|---------|---------|
| `gl-sdk4-screen-large` | `git-2026.237.10575-dd8a031-1` |

```sh
opkg install gl-screen-e5800-i18n-zh-cn_<version>_all.ipk
```

If the dependency does not match (wrong device or firmware), `opkg` will refuse to install.

Uninstall restores English `text/default` from `default.opkg-dist`.

## Edit translations

1. Edit `sources/zh_cn` (font block must use `*_tutu_zh-cn` basenames)
2. `python scripts/sync_overlay_lang.py`
3. `python scripts/build_ipk.py`
