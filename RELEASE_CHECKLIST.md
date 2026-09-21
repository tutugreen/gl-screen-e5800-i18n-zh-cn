# Pre-release checklist

Use this before the first public push. **Git root is this directory** (`gl-screen-e5800-i18n-zh-cn/`), not the parent workspace folder.

## Legal & repo hygiene

- [ ] Read [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [LICENSE](LICENSE)
- [ ] No files under `local/` or `assets/` committed (see [.gitignore](.gitignore))
- [ ] No personal notes (`@tutugreen` timestamps, private URLs) in tracked sources
- [ ] `overlay/` generated TTFs and `license.txt` are **not** in git (built in CI)
- [ ] ipk installs on device and includes `ttf/license.txt` (IBM OFL)

## Build & QA

- [ ] `python scripts/validate_zh_cn.py` — keys match `sources/en`
- [ ] GitHub Actions **Build IPK** (`workflow_dispatch`) succeeds
- [ ] Device has `gl-sdk4-screen-large` at `git-2026.237.10575-dd8a031-1` (`opkg list-installed | grep screen`)
- [ ] `opkg install` on GL-E5800 — no `Malformed package file`; wrong firmware should be **rejected by Depends**
- [ ] UI Chinese text and fonts look correct
- [ ] `opkg remove` restores English `text/default`

## Metrics (optional refresh)

```sh
# Copy stock *.ttf from router into assets/device-original-ttf/ (local only)
python scripts/extract_device_metrics.py assets/device-original-ttf
```

## Enable CI on push (optional)

Uncomment `push:` in [.github/workflows/build-ipk.yml](.github/workflows/build-ipk.yml).

## First push (when ready)

```sh
cd gl-screen-e5800-i18n-zh-cn
git init
git remote add origin git@github.com:<user>/gl-screen-e5800-i18n-zh-cn.git
git add .
git commit -m "Initial release: GL-E5800 screen zh-CN ipk"
git push -u origin main
```
