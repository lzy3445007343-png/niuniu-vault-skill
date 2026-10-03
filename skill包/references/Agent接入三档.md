# 让 Agent 吃进知识库：从直接读到 RAG 三档

> 回答：怎么让 Agent（WorkBuddy / Claude / Copilot 这类）真正读懂、用上你这套 vault。

## 一、先放一张「地图」：vault 根 AGENTS.md

不管用哪种方案，先在 vault 根放一个 `AGENTS.md`（也有叫 `CLAUDE.md`，作用一样）——写给 Agent 看的「结构地图 + 纪律」。直接复制 `assets/AGENTS.md` 改成你的库结构即可。

这张地图让 Agent 不迷路、不乱翻、知道「入口在哪、哪些碰不得」。零成本、立刻生效，是所有方案的第 0 步。

## 二、档位一：直接读文件（零配置）

最省事：Agent 直接 Read 你的 `.md` 文件。
- 适合：库小（<200 篇）、临时问答、Agent 自带文件读取能力时。
- 前提：vault 是纯文本 .md，路径 Agent 能访问。
- ⚠️ 缺点：库一大全读会爆上下文也慢；且是字面匹配，难跨多篇联想。小库够用。

### 加一道：热缓存 hot.md（零配置，强烈推荐）

每次会话结尾，让 Agent 把「当前状态」写进库根一个 `hot.md`（**500 字以内**）：最近在推进什么、推进到哪一步、有没有结论刚变了、上轮关键要点。

给 AI 的指令直接可用：
> 「读完这轮对话，把要点更新进库根 hot.md，500 字以内；只留最新状态，旧状态直接覆盖。」

下次开新对话（**哪怕换了另一个 Agent**），Agent 先读 `hot.md` + `00_总目录.md` 两份就能接上进度，不用重读全库、不用你重新交代背景。

**为什么**：Agent 每次开新对话都是「失忆」的——热缓存等于替它存了一份进度条，省掉重新翻库的开销，也省掉你每次交代背景的时间。它和「每层 00_目录」是绝配：目录管「库里有什么」，hot.md 管「现在干到哪了」。

## 三、档位二：MCP 结构化调用

让 Agent 像调工具一样「操作」vault，能列、读、搜、写。
1. Obsidian 装社区插件 **Local REST API**，启用后复制 API Key，记下 Host/Port（默认 `127.0.0.1:27124`）。
2. 接一个 MCP server（如 `mcp-obsidian` / `@hu14/obsidian-mcp`），Key 通过环境变量传（**绝不写进代码或仓库**）。
3. 配好 Agent 能调：`vault_list` / `vault_get`（读）/ `search_simple`（全文搜）/ `vault_create` / `vault_update` 等。
- ⚠️ 前提：Obsidian 程序得在跑（REST API 是本地服务）。Key 走环境变量，别提交 git。

## 四、档位三：RAG 语义检索（大库专用）

库到 1000+ 篇，字面搜不够，让 Agent 按「意思」找。
- 思路：本地把笔记切块 → embedding 模型转向量 → 存 ChromaDB → 包一层 MCP server 暴露 `search_notes`，Agent 提问时先做语义检索再答。
- embedding 模型（本地、离线、无 key）：Smart Connections 用 `BGE-micro-v2`（快）或 `nomic-embed-text-v1.5`（质优）；也可 Ollama 跑 `nomic-embed-text`。
- 向量库：ChromaDB，本地进程、数据落盘、无云无账号。
- ⚠️ 防幻觉纪律：RAG 检索 prompt 写死「只用 vault 上下文回答，不够就直说，别用训练知识补全」。

## 五、怎么选

| 库规模 / 需求 | 推荐档位 |
|---|---|
| <200 篇，临时问答 | 档位一（直接读）+ vault 根 AGENTS.md |
| 要 Agent 帮你写 / 改笔记 | 档位二（MCP） |
| 1000+ 篇，要语义联想 | 档位三（RAG） |

三档**可叠加**：AGENTS.md 永远先放；小库用档位一，长大接档位二，超大再上 RAG。别一上来就搭 RAG——前期纯文本直接读最省事。

## 诚实标注
档位二 / 三依赖 Obsidian 在跑或本地服务在跑，不是纯云端；关了程序 Agent 就够不着。embedding 模型质量影响命中率，以实测为准。MCP server 具体命令随版本变，落地前以对应仓库文档为准。「vault 根 AGENTS.md」是约定俗成的入口名，部分平台认 `CLAUDE.md`，内容一样，按你用的 Agent 叫法放一份即可。
