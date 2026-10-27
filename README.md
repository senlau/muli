# 目力

摄影策展站。三条线分开看：每日摄影师（按作者）、每日审美一课（按风格）、28mm 专题（按焦段）。

站点：<https://senlau.github.io/muli/>

仓库里还没有开过 GitHub Pages。有仓库管理权限的人需要在 Settings → Pages 里把 Source 选成 **GitHub Actions**，点一次即可。之后推到 `main` 会自动部署。当前令牌不能代开这个开关。

图都在 CDN 上（`https://fastly.jsdelivr.net/gh/senlau/picx-images-hosting@master/muli/`），本仓库不放原片。

## 本地打开

不需要构建。在仓库根目录：

```bash
python3 -m http.server 8765
```

浏览器打开 `http://127.0.0.1:8765/`。深链用 `#photographer`、`#aesthetic`、`#28mm`，单则是 `#photographer-2026-10-27` 这种形式。也可以用 `?tab=aesthetic&entry=2026-10-27`，页面会改写成对应的 hash。

## 每天怎么更新

掌印 / 目力确认当日三条推送之后，按 [SYNC.md](SYNC.md) 跑 `scripts/ingest.py`，提交 `content/`、`index.html`、`data/catalog.json`，推到 `main`。GitHub Actions 会把站点部署到上面的地址。

## 目录

| 路径 | 作用 |
| --- | --- |
| `index.html` | 生成的页面，不要手改 |
| `css/site.css` `js/app.js` | 版式和少量交互（筛选、焦点、灯箱） |
| `content/photographer/` | 每日摄影师 |
| `content/aesthetic/` | 每日审美一课 |
| `content/28mm/` | 28mm 专题 |
| `data/catalog.json` | 给同步脚本和检索用的结构化目录 |
| `scripts/ingest.py` | 从简报或 `content.json` 写入内容并重写页面 |

审美课不收 28mm 的站位清单。两条学审美（作者 / 风格），一条练焦段。
