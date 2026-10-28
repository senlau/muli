# 目力

摄影文章站，四个栏目：摄影师、视觉语言、28mm 专题、摄影与人生。

站点：<https://senlau.github.io/muli/>

Settings → Pages 的 Source 是 **GitHub Actions**。推到 `main` 后，工作流会从 `content/` 重新生成全部页面并部署。

## 页面与标签

| 页面 | 内容 |
| --- | --- |
| `index.html` 首页 | 本期精选（最新一天的主图和选题）→ 近期文章（四个栏目切换，每栏三篇，不重复本期精选里已有的）→ 关于 `#about` |
| `learn.html` 审美学习 | 两个标签：摄影师 `#photographer`、视觉语言 `#aesthetic` |
| `practice.html` 摄影实践 | 28mm 专题，按课的顺序排，不设标签 |
| `life.html` 摄影与人生 | 全部故事，新的在前 |
| `archive.html` 归档 | 三个标签：按主题 `#topics`、按作者 `#people`、按时间 `#timeline` |
| `photographer/` `aesthetic/` `28mm/` `meaning/` | 每篇一页，如 `photographer/2026-10-28.html`、`meaning/2026-10-28-mannell.html` |

分法：要专门去的地方做成页面；同一类内容换个角度看，做成标签。每篇文章都是独立页面，可以直接分享。

- 标签状态记在 hash 里，`learn.html#aesthetic`、`archive.html#people` 可以直接打开对应标签。首页的栏目切换不改地址。
- 归档里的单个主题、作者也能直接链接：`archive.html#topic-contour`、`archive.html#person-fan-ho`。主题的名字和 slug 写在 `content/topics.json`。
- 关闭 JavaScript 时，所有标签内容按顺序展开，页面照常可读。

## 旧链接

改版前全站是一页。`index.html` 里有一小段脚本，把旧深链转到新地址：

| 旧地址 | 现在 |
| --- | --- |
| `index.html#photographer-2026-10-27`、`#meaning-2026-10-27-goldrei` | 对应的文章页 |
| `#photographer`、`#aesthetic` | `learn.html` 的对应标签 |
| `#28mm` | `practice.html` |
| `#meaning` | `life.html` |
| `?tab=aesthetic&entry=2026-10-27`（含 `tab=mm28`） | 同上规则 |

## 本地打开

不需要构建，生成的页面都提交在仓库里。在仓库根目录：

```bash
python3 -m http.server 8765
```

浏览器打开 `http://127.0.0.1:8765/`。

## 每天怎么更新

掌印 / 目力确认当日推送之后，按 [SYNC.md](SYNC.md) 跑 `scripts/ingest.py`，用 `git add -A` 提交 `content/`、生成的页面和 `data/catalog.json`，推到 `main`。

## 图片

图都在 jsDelivr CDN 上（`https://fastly.jsdelivr.net/gh/senlau/picx-images-hosting@master/muli/`），本仓库不放原片。卡片缩略图、文中大图和灯箱用的是同一个地址，按原比例显示，不裁切。图片版权归原作者，每篇文末列出作品出处和延伸阅读。

## 字体

正文用阿里巴巴普惠体 3.0 的 Regular（400）和 Medium（500），放在 `fonts/AlibabaPuHuiTi-3/`，是官方下载的 woff2 原文件。官方法律声明全文和文件校验值见同目录的 `LEGAL.txt`。

- 声明允许免费商用，但未经书面授权不得转换、拆分或修改字体，所以不做子集化，两份文件原样放，合计约 10.7 MB。浏览器只在用到时下载，之后走缓存。
- `font-display: swap`：字体到之前先用系统字体显示，不会等字。
- 普惠体的破折号 U+2014 偏窄，中文「——」会断成两截。`css/site.css` 只把这个字符交给系统中文字体。

## 目录

| 路径 | 作用 |
| --- | --- |
| `index.html` `learn.html` `practice.html` `life.html` `archive.html` | 生成的栏目页，不要手改 |
| `photographer/` `aesthetic/` `28mm/` `meaning/` | 生成的文章页，不要手改 |
| `css/site.css` | 版式；颜色变量沿用原来的配色 |
| `js/app.js` | 标签切换、灯箱、坏图占位 |
| `fonts/` | 阿里巴巴普惠体 3.0 与法律声明 |
| `content/photographer/` | 摄影师 |
| `content/aesthetic/` | 视觉语言 |
| `content/28mm/` | 28mm 专题 |
| `content/meaning/` | 摄影与人生 |
| `content/topics.json` | 主题表，用于归档「按主题」和文末「同一主题」 |
| `data/catalog.json` | 给同步脚本和检索用的结构化目录 |
| `scripts/ingest.py` | 写入内容并重写全部页面 |
| `scripts/render_site.py` | 页面模板 |

栏目分工：视觉语言只谈风格和类型，不收构图技法；站位、换位这类练习放在 28mm 专题；摄影与人生不定期更新，和另外三个栏目互不依赖。
