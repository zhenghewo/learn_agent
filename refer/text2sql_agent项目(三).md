# Skill

> 什么是 Skill？怎么写好skill？

---

![目录](./images/Extra08-figures/toc.png)

## 一、什么是 Skill？

### 1.1 定义

Skill 是一个文件夹，里面装着指令文档、参考资料、可执行脚本等资源。AI 拿到它，就能胜任一项原本不会的特定工作。

比如一个 `pdf-editor` 技能文件夹里，可能有一份"怎么处理 PDF"的操作指令、一个旋转 PDF 的 Python 脚本、一份 API 参考文档——AI 不需要从外部再找任何东西，这个文件夹里全有了。

这个概念不限于某一个产品。无论是 Codex、Claude 还是其他 AI Agent，skill 的本质都一样。你可以把它理解为 AI 的一个**能力插件**——插上去，AI 就多了一项专长；拔掉，AI 还是原来那个通用助手。

### 1.2 最小形态

一个 skill 最少只需要一个文件：

```
my-skill/
└── SKILL.md
```

`SKILL.md` 的结构很简单——上半部分告诉 AI"什么时候用我"，下半部分告诉 AI"具体怎么做"：

```yaml
---
name: my-skill                    # ← 上半部分：元数据
description: >-                   #    AI 靠这里决定要不要激活这个技能
  当用户需要做某件事时，使用这个技能。
---

下半部分：操作指令                   # ← AI 激活技能后才会读到这里
按照以下步骤执行...
```

上半部分叫 **frontmatter**（`---` 之间的 YAML），包含 `name` 和 `description` 两个字段。AI 在每次对话开始时都会扫描所有已安装技能的 frontmatter，靠 description 来判断"这个技能和当前请求相关吗"——这是技能被触发的**唯一依据**。

下半部分叫 **body**（Markdown 正文），是技能被激活之后才加载的操作指令。如果技能没被触发，AI 永远不会读到这里。

### 1.3 完整结构

当一个技能变复杂时，单靠一个 SKILL.md 就不够了。

比如你要做一个"PDF 处理"技能：SKILL.md 里写了处理流程，但旋转 PDF 的代码每次都一样，每次让 AI 重写既浪费时间又可能出错——不如直接放一个写好的 Python 脚本。再比如"前端项目生成器"技能：每次都要一套 HTML/React 的样板文件，不如直接放一个模板目录让 AI 拷贝出来改。

所以完整的 skill 目录可以包含这些东西：

```
skill-name/
├── SKILL.md                  # [必需] 入口文件：frontmatter + body
├── agents/
│   └── openai.yaml           # [推荐] 技能的"名片"
├── scripts/                  # [可选] 可执行脚本
├── references/               # [可选] 参考文档
└── assets/                   # [可选] 产出物模板
```

逐个说明：

- **SKILL.md** — 唯一必需的文件，前面已经介绍过

- **scripts/** — 写好的程序，AI 不需要读懂它，直接调用 shell 执行就行。比如 `scripts/rotate_pdf.py`，AI 只要跑 `python rotate_pdf.py input.pdf 90` 就能旋转 PDF，不用每次重新写旋转逻辑。适合那些**结果必须精确、不能让 AI 自由发挥**的操作

- **references/** — AI 在工作过程中需要查阅的参考资料。比如一个"BigQuery 查询"技能，AI 要知道公司有哪些表、每个表有什么字段，这些信息放在 `references/schema.md` 里，AI 需要时再读取。和 scripts 的区别是：references 是给 AI **读**的，scripts 是给 AI **执行**的

- **assets/** — 不是给 AI 看的，而是直接用在最终产出里的文件。比如一个"前端项目生成器"技能，`assets/frontend-template/` 里放着一套 HTML/React 样板代码，AI 直接把这套模板拷贝出来，在上面修改。再比如 `assets/logo.png` 是公司 logo，AI 生成网页时直接引用它。AI 不需要"读懂"一张 logo 图片，只需要知道它在哪、什么时候放进去

- **agents/openai.yaml** — 技能的"名片"。很多 AI 产品会在界面上展示一个技能列表，让用户选择或搜索。这个文件里存的就是列表中显示的名称、简介、图标等信息。它不影响 AI 的行为，纯粹是给产品界面用的

---

## 二、你是在给人写指令，还是在给 AI 写指令？

知道了 skill 是什么，下一步就是写一个。但大多数人第一次写出来的 skill 都有同一个问题。

看一个例子。假设你要做一个"代码审查"技能，你可能会这样写：

```markdown
---
name: code-review
description: 代码审查技能
---

# Code Review Skill

## 背景
本技能基于团队多年的代码审查经验总结而成，旨在提升代码质量和团队协作效率。

## 审查原则
- 保持专业、建设性的语气
- 关注代码质量而非个人风格
- 平衡严格性和灵活性

## 使用方式
当用户提交代码时，对代码进行全面审查，给出改进建议。注意保持友好和鼓励的态度。

## 版本记录
- v1.0: 初始版本
- v1.1: 增加了对 Python 的支持
```

如果这是一份给人看的团队文档，它写得不错——有背景、有原则、有使用方式，甚至还有版本记录。

但 skill 的读者是 AI。用这个视角重新审视：

- **"基于团队多年经验总结"** — AI 不关心这个技能是怎么来的，它只需要知道**现在该怎么做**
- **"保持专业、建设性的语气"** — 人类读了能 get 到一个大致的感觉，但 AI 会把"专业"和"建设性"展开成无数种组合，每次输出都不一样
- **"平衡严格性和灵活性"** — 人类经验丰富的审查者知道什么时候严格什么时候灵活，但 AI 没有这个直觉，这句话等于没说
- **"全面审查，给出改进建议"** — 这是对人类审查者的期望，但 AI 需要的是：先检查什么？再检查什么？什么问题必须指出？什么问题可以忽略？
- **"版本记录"** — AI 每次被唤醒都是全新的，v1.0 还是 v1.1 对它没有意义
- **description 只写了"代码审查技能"** — AI 靠 description 判断是否触发，"代码审查技能"五个字太模糊：用户说"帮我看看这段代码"要触发吗？"这个函数性能怎么样"要触发吗？

每一条单独看都不是"错"，但它们都是写给人看的。**问题不在于写得不够多，而在于写错了对象。**

那正确的写法是什么样的？我们来看一个现成的答案——codex的skill-creator。它是一个"创建 skill 的 skill"，它自己的 SKILL.md 就是一份关于"如何给 AI 写指令"的最佳实践。

---

## 三、skill-creator 的整体框架

打开 skill-creator 的 SKILL.md（约 370 行），在深入任何细节之前，我们先建立对它的整体认知。

skill-creator 要解决的问题只有一个：**怎么在有限的上下文窗口里，给 AI 最有效的指令？**

围绕这个问题，它给出了一套完整的设计体系，可以用三个层次来理解。

### 第一层：根本约束——简洁

AI 的上下文窗口是有限的，而且是共享的（系统提示、对话历史、所有已安装技能的元数据都在里面）。你的 skill 占得越多，留给其他用途的就越少。所以 skill-creator 的第一原则就是：**每一句话都要值得它占用的 token**。

### 第二层：两个设计维度

在"简洁"这个约束下，写 skill 时面临两个核心决策：

**维度一：信息放在哪里？**

不是所有信息都需要一开始就加载。skill-creator 设计了一个三级分层架构，让不同的信息在不同的时机进入上下文：

![Skill 标准结构与三级加载](./images/Extra08-figures/skill-structure.png)

- **L1（元数据）**：始终在上下文中，约 100 词——AI 靠它判断要不要激活这个技能
- **L2（SKILL.md body）**：触发后才加载，控制在 5k 词以内——操作指令
- **L3（scripts/references/assets）**：按需使用，无上限——其中 scripts 执行而不读入，零 token 成本

这解决了"怎么用最少的 token 承载最多的信息"。

**维度二：给 AI 多大自由度？**

不是所有任务都适合让 AI 自由发挥。

举个例子：让 AI 写一篇技术博客，十个人写出十种风格都可以——你只需要给方向，具体怎么写让 AI 自己决定。这就是**高自由度**。

但让 AI 生成一个 YAML 配置文件就不一样了。比如 skill-creator 要生成的 `openai.yaml`，里面有个 `short_description` 字段，要求 25-64 个字符、首字母大写、不能有引号。AI 写成 65 个字符？不行，产品界面会截断。写成 24 个字符？不行，校验不通过。漏了首字母大写？界面显示不一致。这种任务差一个字符就出问题，你不能让 AI 自由发挥，必须用脚本来锁死格式——这就是**低自由度**。这类任务叫"脆弱操作"：不是说它复杂，而是说它**做对只有一种方式，做错有一百种方式**。

![自由度光谱](./images/Extra08-figures/freedom-spectrum.png)

这解决了"怎么在 AI 的灵活性和输出的可靠性之间取得平衡"。

### 第三层：落地流程

有了原则和架构，skill-creator 最后给出了一个六步创建流程，把设计思想变成可执行的操作步骤：

![六步创建流程](./images/Extra08-figures/creation-flow.png)

理解→规划→初始化→编辑→校验→迭代。其中脚本贯穿流程，形成确定性的质量保障链：

![文件交互关系](./images/Extra08-figures/file-interaction.png)

### 框架总览

三个层次的关系：

```
简洁（根本约束）                         → 第四章
 ├── 信息放在哪里？ → 三级分层架构        → 第五章
 ├── 给 AI 多大自由度？ → 自由度光谱与脚本  → 第六章
 └── 怎么落地？ → 六步创建流程            → 第七章
```

接下来的每一章都在这个框架内展开。

---

## 四、根本约束：简洁
> 框架位置：第一层

### 4.1 核心约束

AI 的上下文窗口就像一张工作台——它同一时间能摊开的资料是有限的。而这张工作台上已经放着不少东西了：系统自己的规则、用户之前说过的话、所有已安装技能的简介。你的 skill 一旦被激活，它的内容也要摊上去。工作台就这么大，你占得越多，留给其他东西的空间就越少。

所以 skill-creator 把这一点写成了第一条原则：

> The context window is a public good. Skills share the context window with everything else Codex needs: system prompt, conversation history, other Skills' metadata, and the actual user request.

既然工作台空间有限，那写 skill 时怎么判断一段内容该不该放进去？skill-creator 给了一个前提假设：**AI 本身已经很聪明了，你只需要补充它不知道的东西。**

> Default assumption: Codex is already very smart. Only add context Codex doesn't already have.

基于这个假设，每写一段内容之前问自己两个问题：

- "AI 是不是已经知道这个了？" — 比如"Python 的 for 循环怎么写"，AI 当然知道，不用教
- "这段内容值不值得占用工作台上的空间？" — 一段 200 字的解释，能不能用一个 10 行的代码示例替代？

**实操推论**：用简洁的示例代替冗长的解释。一个好的代码示例胜过三段文字描述。

### 4.2 什么不该放进 Skill？

Skill-creator 明确列出了**禁止清单**：

> A skill should only contain essential files that directly support its functionality. Do NOT create extraneous documentation or auxiliary files.

不该有的文件：
- README.md
- INSTALLATION_GUIDE.md
- QUICK_REFERENCE.md
- CHANGELOG.md

> The skill should only contain the information needed for an AI agent to do the job at hand. It should not contain auxiliary context about the process that went into creating it, setup and testing procedures, user-facing documentation, etc. Creating additional documentation files just adds clutter and confusion.

原因很简单：skill 的读者是 AI，不是人类开发者。AI 不需要安装指南、更新日志、快速参考这些"人类辅助文档"。每一个多余的文件都是噪音。

### 4.3 写约束时，"不做什么"比"做什么"更精确

简洁不只是"少写"，还包括"写对"。看一个例子。

当 skill-creator 创建 `laotou-thought-style`（一种写作风格技能）时，它**没有**写：

```
请用温暖、克制、有洞察力的语气写作。
```

这种正面描述看起来清晰，但对 AI 来说，"温暖"的程度、"克制"和"有洞察力"之间的平衡——全是模糊空间。

它做的是写了一份**反模式清单**（`references/anti-patterns.md`）：

| 不要这样做 | 症状 | 怎么改 |
|-----------|------|--------|
| 角色堆砌 | 连续出现多个名字和对白 | 保留一个冲突场景，补抽象提炼 |
| 只有鸡汤没有动作 | 全文"要坚持、要努力" | 改为今天可做的一小步 |
| 直接大道理 | 开头就讲规律 | 先铺生活场景 |
| 收尾太猛 | 结尾"必须改变！" | 换成"慢慢来""就好" |
| 过度绝对化 | "永远""一定" | 加限定词"多数时候""往往" |

**每一条都是具体的、可检测的、有明确修正方案的。**

背后的原理：

```
"做什么" → 描述一个无限大的可行域 → AI 在里面随机游走
"不做什么" → 在可行域上画边界 → AI 的行为空间被收窄到你想要的范围
```

skill-creator 自身也遵循了这个原则——它的 SKILL.md 用了很大篇幅说"什么不该写"（What to Not Include in a Skill），而不是泛泛地说"写好内容"。

当你写完 SKILL.md，做一次"反转测试"：每一条正面指导，能不能改写成"不要做X"的形式？如果可以，改写后通常更精确。

### 4.4 统一使用祈使语气

skill-creator 要求 SKILL.md 的正文统一使用**祈使语气/不定式**（Always use imperative/infinitive form）。这不是美学偏好，而是为了减少歧义——祈使句天然就是指令。

---

## 五、设计维度一：信息放在哪里？
> 框架位置：第二层 — 维度一

在第三章的框架总览中，我们已经看到了三级分层架构的全貌。这一章展开讲它的细节。

### 5.1 三级渐进式加载

skill-creator 原文对三个层级的定义：

> 1. **Metadata (name + description)** - Always in context (~100 words)
> 2. **SKILL.md body** - When skill triggers (<5k words)
> 3. **Bundled resources** - As needed by Codex (Unlimited because scripts can be executed without reading into context window)

| 层级 | 内容 | 何时在上下文中 | token 成本 |
|------|------|--------------|-----------|
| **L1** | frontmatter（name + description） | **始终** | ~100 词 |
| **L2** | SKILL.md body | 触发后加载 | <5k 词 |
| **L3** | scripts/ references/ assets/ | 按需加载 | 无上限 |

**这本质上是一个信息熵管理系统**：

- **L1 是过滤器** — 从几十个已安装技能中筛选出当前需要的那一个。description 不精确 → 误触发或漏触发
- **L2 是操作手册** — 触发后告诉 AI 该怎么做。太长 → 注意力被稀释。body 控制在 500 行以内
- **L3 是工具箱** — 只在需要时打开。其中 scripts/ 最高效——**执行而不读入**，零 token 成本

### 5.2 Frontmatter：触发机制的全部来源

Frontmatter 只有两个必需字段：`name` 和 `description`。但 description 的写法至关重要：

> This is the primary triggering mechanism for your skill, and helps Codex understand when to use the skill.

skill-creator 自己的 description 是这样写的：

```yaml
description: Guide for creating effective skills. This skill should be used when
  users want to create a new skill (or update an existing skill) that extends
  Codex's capabilities with specialized knowledge, workflows, or tool integrations.
```

它不只说"做什么"（creating effective skills），还说"什么时候用"（when users want to create a new skill or update an existing skill）。

**关键规则**：
- 把所有"when to use"信息放在 description 里，**不要放在 body 里**。body 是触发后才加载的，那时候 Codex 已经决定用了，"什么时候用"的信息已经迟了
- 不要在 frontmatter 中放 `name` 和 `description` 以外的字段（`license`、`allowed-tools`、`metadata` 除外）

一个好的 description 示例（docx 技能）：

> "Comprehensive document creation, editing, and analysis with support for tracked changes, comments, formatting preservation, and text extraction. Use when Codex needs to work with professional documents (.docx files) for: (1) Creating new documents, (2) Modifying or editing content, (3) Working with tracked changes, (4) Adding comments, or any other document tasks"

### 5.3 四种捆绑资源的本质区别

理解这四种资源的区别，是理解整个 skill 系统的关键：

#### Scripts（`scripts/`）

可执行代码（Python/Bash 等），用于需要**确定性可靠性**或反复重写的任务。

- **什么时候需要**：同样的代码每次都要重新写，或者需要确定性的可靠输出
- **举例**：`scripts/rotate_pdf.py` 用于 PDF 旋转任务
- **核心优势**：token 高效、确定性、可以执行而不读入上下文窗口
- **注意**：脚本有时仍需要被 Codex 读取，用于修补或环境适配

#### References（`references/`）

文档和参考材料，在需要时加载到上下文中，辅助 Codex 的思考过程。

- **什么时候需要**：Codex 在工作时需要参考的详细文档
- **举例**：`references/finance.md`（财务 schema）、`references/api_docs.md`（API 规范）、`references/policies.md`（公司政策）
- **用途**：数据库 schema、API 文档、领域知识、公司政策、详细工作流指南
- **核心优势**：保持 SKILL.md 精炼，只在 Codex 判断需要时才加载
- **最佳实践**：如果文件很大（>10k 词），在 SKILL.md 中包含 grep 搜索模式
- **避免重复**：信息应该只存在于 SKILL.md **或** references 文件中，不能两边都有。详细信息优先放 references，SKILL.md 只保留核心流程指令和工作流指导

#### Assets（`assets/`）

不是用来加载到上下文中的文件，而是直接用在 Codex 产出物中的资源。

- **什么时候需要**：技能需要在最终输出中使用的文件
- **举例**：`assets/logo.png`（品牌素材）、`assets/slides.pptx`（PPT 模板）、`assets/frontend-template/`（HTML/React 样板）、`assets/font.ttf`（字体）
- **用途**：模板、图片、图标、样板代码、字体、示例文档——这些会被复制或修改
- **核心优势**：将输出资源与文档分离，Codex 可以使用它们而无需读入上下文

#### Agents 元数据（`agents/openai.yaml`）（推荐）

面向 UI 的元数据，不给 AI 读，给产品前端读：

- 包含 `display_name`、`short_description`、`default_prompt` 等字段
- 通过脚本 `generate_openai_yaml.py` 确定性生成，而不是手写
- 更新 SKILL.md 后要检查 `agents/openai.yaml` 是否还匹配，过期了就重新生成
- 详细字段定义见 `references/openai_yaml.md`

### 5.4 渐进式披露的三种实战模式

Skill-creator 给出了三种把内容拆分到 references 的具体模式：

**Pattern 1：高层指南 + 参考文件**

```markdown
# PDF Processing

## Quick start
Extract text with pdfplumber:
[code example]

## Advanced features
- **Form filling**: See [FORMS.md](FORMS.md) for complete guide
- **API reference**: See [REFERENCE.md](REFERENCE.md) for all methods
- **Examples**: See [EXAMPLES.md](EXAMPLES.md) for common patterns
```

Codex 只在需要时才加载 FORMS.md、REFERENCE.md 或 EXAMPLES.md。

**Pattern 2：按领域组织**

多领域/多变体技能，按领域拆分避免加载无关内容：

```
bigquery-skill/
├── SKILL.md (overview and navigation)
└── reference/
    ├── finance.md (revenue, billing metrics)
    ├── sales.md (opportunities, pipeline)
    ├── product.md (API usage, features)
    └── marketing.md (campaigns, attribution)
```

用户问销售指标时，Codex 只读 `sales.md`。

同样适用于多框架/多变体场景：

```
cloud-deploy/
├── SKILL.md (workflow + provider selection)
└── references/
    ├── aws.md (AWS deployment patterns)
    ├── gcp.md (GCP deployment patterns)
    └── azure.md (Azure deployment patterns)
```

**Pattern 3：条件性细节**

基础功能直接展示，高级功能按需链接：

```markdown
# DOCX Processing

## Creating documents
Use docx-js for new documents. See [DOCX-JS.md](DOCX-JS.md).

## Editing documents
For simple edits, modify the XML directly.

**For tracked changes**: See [REDLINING.md](REDLINING.md)
**For OOXML details**: See [OOXML.md](OOXML.md)
```

### 5.5 两条重要的避坑指南

1. **避免深层嵌套引用** — 所有 reference 文件应该从 SKILL.md 直接链接，不要 A → B → C 式嵌套
2. **长文件加目录** — 超过 100 行的 reference 文件要在顶部加 TOC，方便 Codex 预览全貌

### 5.6 常见的层错位

| 错误 | 后果 | 修正 |
|------|------|------|
| 触发条件放在 body 里 | body 是触发后才加载的，晚了 | 放 frontmatter description |
| "When to Use This Skill" 写在 body | 同上，Codex 已经决定用了才看到 | 移到 description |
| 参考细节塞进 SKILL.md | body 膨胀，信息密度下降 | 拆到 references/，body 只放引用链接 |
| 确定性操作写成文字指令 | AI 每次重新理解，可能出错 | 封装成 scripts/，执行不读入 |
| references 互相引用 | AI 需要多跳获取信息 | 所有 references 从 SKILL.md 直接链接 |
| SKILL.md 和 references 内容重复 | 浪费 token，更新时可能不一致 | 信息只在一处存在 |

---

## 六、设计维度二：给 AI 多大自由度？
> 框架位置：第二层 — 维度二

知道了信息该放在哪里、该怎么约束，下一个问题是：**AI 做什么，脚本做什么？**

AI 非常擅长理解语义、生成文本、做创造性工作。但它不擅长精确格式控制、长度约束、命名规范——这些"脆弱操作"。

### 6.1 三个自由度档位

Skill-creator 用一个**自由度光谱**来处理这种不均匀性（见第三章框架图）：

> Think of Codex as exploring a path: a narrow bridge with cliffs needs specific guardrails (low freedom), while an open field allows many routes (high freedom).

**高自由度**（文字指令）：多种方法都可行时，决策依赖上下文，用启发式引导。

**中自由度**（伪代码/带参数的脚本）：有最佳实践但允许变通，配置影响行为。

**低自由度**（具体脚本，少量参数）：操作脆弱容易出错，一致性至关重要，必须遵循特定序列。

核心逻辑：

```
任务越脆弱（容易出错） → 自由度越低 → 用脚本锁死
任务越灵活（多种方案都对） → 自由度越高 → 用文字引导
```

### 6.2 skill-creator 自身的自由度分配

| 任务 | 自由度 | 实现方式 |
|------|--------|---------|
| 理解用户需求并提问 | 高 | SKILL.md 文字指导 |
| 规划技能内容结构 | 中 | 模板 + 选择题式模式推荐 |
| 初始化目录结构 | **低** | `init_skill.py` 脚本 |
| 生成 openai.yaml | **低** | `generate_openai_yaml.py` 脚本 |
| 编写 SKILL.md 内容 | 高 | 原则指导 + 写作建议 |
| 校验最终结果 | **低** | `quick_validate.py` 脚本 |

### 6.3 两个方向的错误

**错误 1：给脆弱任务太多自由度**

```markdown
# 错误
请生成一个 openai.yaml 文件，包含 display_name 和 short_description。

# 后果：short_description 可能超过 64 字符限制，大小写可能不一致
```

Skill-creator 的做法：用 `generate_openai_yaml.py` 脚本锁死格式。AI 只提供参数值，脚本保证输出合规。

**错误 2：给创造性任务太多约束**

```markdown
# 错误
第一段必须以"昨天"开头，第二段必须包含"本质上"，最后一段以"慢慢来"结尾。

# 后果：生成的文本像填词游戏
```

Skill-creator 的做法：给结构比例（场景层 ≤30%，原理层 30-40%），但不锁定具体用词。

### 6.4 判断标准

两个问题：
1. **做错了后果多严重？** — 越严重 → 越低自由度
2. **有多少种"正确"的做法？** — 越多 → 越高自由度

### 6.5 低自由度的实现：skill-creator 的三个脚本

理解了自由度光谱，就能理解 skill-creator 为什么有三个脚本——它们就是"低自由度"的具体实现（脚本间的交互关系见第三章框架图）。

**`init_skill.py`（输入保障，398 行）**

初始化新技能目录的脚手架工具，类似 `create-react-app` 之于 React 项目：

```bash
scripts/init_skill.py <skill-name> --path <output-directory> \
  [--resources scripts,references,assets] [--examples] \
  [--interface key=value]
```

核心功能：
- 创建技能目录
- 生成带 TODO 占位符的 SKILL.md 模板（TODO 是给 Codex 看的"填空题"）
- 调用 `generate_openai_yaml.py` 生成 `agents/openai.yaml`（通过 `--interface key=value` 传入 AI 生成的 display_name、short_description、default_prompt）
- 可选创建 `scripts/`、`references/`、`assets/` 子目录
- 可选添加示例文件（`--examples`）
- 内置 `normalize_skill_name()` 自动把任意用户输入标准化为 hyphen-case

使用示例：
```bash
scripts/init_skill.py my-skill --path skills/public
scripts/init_skill.py my-skill --path skills/public --resources scripts,references
scripts/init_skill.py my-skill --path skills/public --resources scripts --examples
```

**`generate_openai_yaml.py`（格式保障，226 行）**

专门负责生成和更新 `agents/openai.yaml`：

- 从 SKILL.md 的 frontmatter 读取技能名
- 自动将 hyphen-case 转为 Title Case（`my-cool-skill` → `My Cool Skill`）
- 内置缩写词典（GH、MCP、API 等保持大写）和品牌词典（openai → OpenAI）
- 自动生成 25-64 字符的 `short_description`
- 支持 `--interface key=value` 覆盖任意字段

```bash
scripts/generate_openai_yaml.py <path/to/skill-folder> --interface key=value
```

**`quick_validate.py`（输出保障，102 行）**

技能创建后的"质检员"：

```bash
scripts/quick_validate.py <path/to/skill-folder>
```

校验内容：
- SKILL.md 是否存在
- YAML frontmatter 格式是否合法
- `name`：是否为 hyphen-case，≤ 64 字符，无连续/首尾连字符
- `description`：是否存在，无尖括号，≤ 1024 字符
- 只允许 `name`、`description`、`license`、`allowed-tools`、`metadata` 这 5 个 frontmatter 键

### 6.6 质量保障链

三个脚本形成了一条**确定性保障链**，夹住中间的创造性步骤：

```
init_skill.py（输入保障）
  命名标准化 + 目录结构创建 + 模板生成
  → 确保起点正确
       ↓
  AI 创造性编写（高自由度）
  → SKILL.md 内容、references、自定义 scripts
       ↓
quick_validate.py（输出保障）
  frontmatter 格式 + 命名规范 + 长度约束校验
  → 确保终点合规
```

关键洞察：脚本是"执行而不读入"的——**零 token 成本**。你可以把任意复杂的确定性逻辑封装进脚本，而不用担心它占用上下文。这就是为什么 skill-creator 把命名转换（缩写词典、品牌词典）、长度约束（25-64 字符）、格式校验这些细碎但脆弱的操作全部交给了脚本。

### 6.7 什么该封装成脚本？

```
每次执行结果必须一样      → 脚本
涉及精确格式/长度约束     → 脚本
涉及命名规范转换          → 脚本
需要校验规则匹配          → 脚本
同样的代码每次都要重新写   → 脚本

需要理解上下文            → 文字指令
有多种合理做法            → 文字指令
需要创造性判断            → 文字指令
```

脚本有时仍需要被 Codex 读取（用于修补或环境适配），但大多数时候它们是"执行而不读入"的。

---

## 七、落地：六步创建流程
> 框架位置：第三层

有了前面的原则和架构，skill-creator 最后给出了一个六步创建流程，把设计思想变成可执行的操作步骤（见第三章框架图）。

### 7.0 命名规范

在开始之前，先确定命名：

- 只用小写字母、数字和连字符；把用户提供的名称标准化为 hyphen-case（如 "Plan Mode" → `plan-mode`）
- 名称 ≤ 64 字符
- 优先用简短的、动词开头的短语来描述动作
- 需要时用工具名做命名空间（如 `gh-address-comments`、`linear-address-issue`）
- 技能文件夹名与技能名完全一致

### 7.1 Step 1：理解技能——用具体例子建立共识

> Skip this step only when the skill's usage patterns are already clearly understood.

要创建一个有效的 skill，必须先清楚理解**具体的使用例子**。这些理解可以来自用户提供的例子，也可以来自生成的、经用户验证的例子。

以构建 image-editor 技能为例，可以问用户：

- "image-editor 技能应该支持什么功能？编辑、旋转，还有其他吗？"
- "能给一些使用这个技能的例子吗？"
- "我能想到用户会说'去掉这张照片的红眼'或'旋转这张图片'。还有其他使用方式吗？"
- "用户会说什么话来触发这个技能？"

**注意**：不要一次问太多问题。先问最重要的，然后根据需要跟进。

**完成标志**：对技能应该支持的功能有了清晰的认识。

### 7.2 Step 2：规划可复用的技能内容

对每个具体例子做两个分析：
1. 如果从零开始做这件事，需要什么？
2. 其中哪些会被反复使用？

反复使用的东西 → 封装成 scripts/references/assets。

skill-creator 给了三个典型分析案例：

**案例 1：`pdf-editor` 技能**（用户问"帮我旋转这个 PDF"）
- 旋转 PDF 每次都要重写同样的代码
- → 封装为 `scripts/rotate_pdf.py`

**案例 2：`frontend-webapp-builder` 技能**（用户问"帮我做一个 todo app"或"做一个步数追踪仪表盘"）
- 写前端 webapp 每次都需要同样的 HTML/React 样板代码
- → 封装为 `assets/hello-world/` 模板目录

**案例 3：`big-query` 技能**（用户问"今天有多少用户登录了？"）
- 查询 BigQuery 每次都要重新发现表的 schema 和关系
- → 封装为 `references/schema.md`

**完成标志**：列出了所有要包含的可复用资源清单（scripts、references、assets）。

### 7.3 Step 3：初始化技能

> When creating a new skill from scratch, always run the `init_skill.py` script.

这里用的是"always"——不是"建议"，是"总是"。原因：
- 脚本生成的目录结构保证符合规范
- 模板中的 TODO 提醒确保不遗漏必需字段
- `agents/openai.yaml` 的格式约束（字段长度、引号规则）靠手写容易出错

这是**低自由度原则的直接应用**：初始化是一个脆弱操作，用脚本消除出错可能。

初始化后：
- 定制 SKILL.md 并根据需要添加资源
- 如果用了 `--examples`，替换或删除占位符文件

### 7.4 Step 4：编辑技能

这是最核心的步骤，分两阶段：

#### 阶段一：先实现可复用资源

从 Step 2 规划的资源开始：实现 `scripts/`、`references/`、`assets/` 文件。

注意：
- 这一步可能需要用户输入（比如 `brand-guidelines` 技能需要用户提供品牌素材）
- 新增的脚本**必须通过实际运行来测试**，确保无 bug 且输出符合预期
- 如果有很多类似的脚本，只需测试代表性样本来建立信心
- 如果用了 `--examples`，删除不需要的占位符文件。只创建真正需要的资源目录

#### 阶段二：更新 SKILL.md

**Frontmatter 写法**：

```yaml
---
name: skill-name
description: >-
  描述技能做什么 + 具体什么时候用。
  把所有 "when to use" 信息放这里，不要放在 body 里。
---
```

**Body 写法**：

写给另一个 Codex 实例的操作指令。包含对 Codex 有帮助但不显而易见的信息：程序性知识、领域细节、可复用资源的使用方式。

统一使用**祈使语气/不定式**。

### 7.5 Step 5：校验技能

```bash
scripts/quick_validate.py <path/to/skill-folder>
```

校验 YAML frontmatter 格式、必需字段、命名规则。不通过就修复后重新运行。

### 7.6 Step 6：迭代

> After testing the skill, users may request improvements. Often this happens right after using the skill, with fresh context of how the skill performed.

迭代工作流：
1. 在真实任务上使用技能
2. 发现吃力或低效的地方
3. 找出 SKILL.md 或捆绑资源该如何更新
4. 实施变更并重新测试

好的 skill 不是一次写成的。skill-creator 创建的 laotou-thought-style 技能，在第一次生成后就迭代了 `openai.yaml` 的 `short_description` 和 `default_prompt`——从泛泛的描述变为更精确的操作指令。

---

## 八、总结

回到最初的问题：怎么写出好的 skill？

回顾整个框架：

```
根本约束：简洁（第四章）
 ├── 信息放在哪里？ → 三级分层，按需加载（第五章）
 ├── 给 AI 多大自由度？ → 脆弱操作脚本锁死，创造性工作文字引导（第六章）
 └── 怎么落地？ → 六步流程：理解→规划→初始化→编辑→校验→迭代（第七章）
```

**Skill是给 AI 写指令，而不是给人。用最少的 token，在正确的层级，给 AI 最精准的约束，让它在边界内自由发挥。**


## 九、结构模版

---
name: [技能标识名]
description: [一句话描述功能 + 触发场景 + 核心价值]
version: 1.0.0
---

# [技能名称]

## 角色定义
你是一名 [具体角色]，擅长 [核心能力]。

## 核心指令
请严格按照以下步骤执行任务：
1. **分析意图**：[步骤说明]
2. **查阅资料**：如果需要，读取 `references/[文件名]` 获取详细信息。
3. **执行操作**：运行 `scripts/[脚本名]` 处理数据。
4. **输出结果**：按照下方的输出格式要求生成回答。

## 输出格式
- 必须包含：[要素 A]、[要素 B]
- 风格：[专业/幽默/简洁]

## 示例
**用户输入**：[示例提问]
**你的回答**：[示例回答]

## 错误处理
如果遇到 [某种错误]，请 [执行某种操作]。


# 例子
psql -U postgres -d text2sql_demo -h 127.0.0.1 -f init_postgres.sql
## init_postgres.sql
```
-- PostgreSQL initialization script for Text2SQL/RAG demos
-- Target: medium complexity schema with 5 related tables
-- Usage:
--   psql -h <host> -p <port> -U <user> -d <database> -f pg_init/01_init_postgres.sql

SET client_encoding = 'UTF8';
SET timezone = 'Asia/Shanghai';

BEGIN;

-- Rebuild objects to avoid old incompatible schemas (for repeatable init).
DROP VIEW IF EXISTS v_order_summary;
DROP VIEW IF EXISTS v_product_profitability;
DROP TABLE IF EXISTS sales_order_items CASCADE;
DROP TABLE IF EXISTS sales_orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS sales_reps CASCADE;

CREATE TABLE IF NOT EXISTS sales_reps (
    id BIGSERIAL PRIMARY KEY,
    rep_code VARCHAR(20) NOT NULL UNIQUE,
    rep_name VARCHAR(80) NOT NULL,
    region VARCHAR(50) NOT NULL,
    level VARCHAR(20) NOT NULL CHECK (level IN ('junior', 'mid', 'senior')),
    hire_date DATE NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS customers (
    id BIGSERIAL PRIMARY KEY,
    customer_code VARCHAR(20) NOT NULL UNIQUE,
    customer_name VARCHAR(120) NOT NULL,
    industry VARCHAR(60) NOT NULL,
    province VARCHAR(30) NOT NULL,
    city VARCHAR(30) NOT NULL,
    customer_tier VARCHAR(10) NOT NULL CHECK (customer_tier IN ('A', 'B', 'C')),
    annual_budget NUMERIC(14, 2) NOT NULL DEFAULT 0,
    account_manager_id BIGINT REFERENCES sales_reps(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS products (
    id BIGSERIAL PRIMARY KEY,
    sku VARCHAR(30) NOT NULL UNIQUE,
    product_name VARCHAR(120) NOT NULL,
    category VARCHAR(50) NOT NULL,
    unit_price NUMERIC(12, 2) NOT NULL CHECK (unit_price > 0),
    unit_cost NUMERIC(12, 2) NOT NULL CHECK (unit_cost >= 0),
    launch_date DATE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sales_orders (
    id BIGSERIAL PRIMARY KEY,
    order_no VARCHAR(30) NOT NULL UNIQUE,
    customer_id BIGINT NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    sales_rep_id BIGINT NOT NULL REFERENCES sales_reps(id) ON DELETE RESTRICT,
    order_date DATE NOT NULL,
    payment_status VARCHAR(20) NOT NULL CHECK (payment_status IN ('pending', 'paid', 'partial')),
    shipping_status VARCHAR(20) NOT NULL CHECK (shipping_status IN ('new', 'packing', 'shipped', 'delivered')),
    discount_rate NUMERIC(5, 2) NOT NULL DEFAULT 0 CHECK (discount_rate >= 0 AND discount_rate <= 100),
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sales_order_items (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES sales_orders(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(12, 2) NOT NULL CHECK (unit_price > 0),
    item_discount_rate NUMERIC(5, 2) NOT NULL DEFAULT 0 CHECK (item_discount_rate >= 0 AND item_discount_rate <= 100),
    line_total NUMERIC(14, 2) GENERATED ALWAYS AS (
        ROUND(quantity * unit_price * (100 - item_discount_rate) / 100.0, 2)
    ) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (order_id, product_id)
);

CREATE INDEX IF NOT EXISTS idx_customers_manager ON customers(account_manager_id);
CREATE INDEX IF NOT EXISTS idx_customers_region ON customers(province, city);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_sales_orders_date ON sales_orders(order_date);
CREATE INDEX IF NOT EXISTS idx_sales_orders_customer ON sales_orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_sales_orders_rep ON sales_orders(sales_rep_id);
CREATE INDEX IF NOT EXISTS idx_sales_order_items_order ON sales_order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_sales_order_items_product ON sales_order_items(product_id);

INSERT INTO sales_reps (rep_code, rep_name, region, level, hire_date, active) VALUES
('REP001', '王晨', '华东', 'senior', '2020-03-15', TRUE),
('REP002', '李珊', '华南', 'mid', '2021-07-10', TRUE),
('REP003', '周宁', '华北', 'junior', '2023-01-06', TRUE),
('REP004', '张磊', '西南', 'mid', '2022-09-20', TRUE),
('REP005', '赵阳', '华中', 'senior', '2019-11-03', TRUE)
ON CONFLICT (rep_code) DO NOTHING;

INSERT INTO customers (customer_code, customer_name, industry, province, city, customer_tier, annual_budget, account_manager_id) VALUES
('CUS001', '星辰医疗科技', '医疗', '广东', '深圳', 'A', 5200000, 2),
('CUS002', '远见教育集团', '教育', '北京', '北京', 'B', 1800000, 3),
('CUS003', '澜海零售连锁', '零售', '浙江', '杭州', 'A', 4300000, 1),
('CUS004', '拓新制造股份', '制造', '江苏', '苏州', 'B', 2600000, 5),
('CUS005', '云桥信息服务', '互联网', '四川', '成都', 'C', 900000, 4),
('CUS006', '华岳物流网络', '物流', '湖北', '武汉', 'B', 2100000, 5)
ON CONFLICT (customer_code) DO NOTHING;

INSERT INTO products (sku, product_name, category, unit_price, unit_cost, launch_date, is_active) VALUES
('SKU-AI-1001', '智能客服引擎', 'SaaS', 68000, 35000, '2023-03-01', TRUE),
('SKU-DW-2001', '企业数据仓库包', '数据平台', 128000, 76000, '2022-06-18', TRUE),
('SKU-ETL-3001', '实时ETL连接器', '数据集成', 42000, 22000, '2024-01-12', TRUE),
('SKU-BI-4001', '可视化分析套件', 'BI', 56000, 29000, '2021-10-08', TRUE),
('SKU-SEC-5001', '数据权限审计模块', '安全', 39000, 18000, '2024-05-20', TRUE),
('SKU-API-6001', '开放API网关', '平台组件', 47000, 21000, '2023-08-26', TRUE)
ON CONFLICT (sku) DO NOTHING;

INSERT INTO sales_orders (order_no, customer_id, sales_rep_id, order_date, payment_status, shipping_status, discount_rate, note) VALUES
('SO202501001', 1, 2, '2025-01-08', 'paid', 'delivered', 3.00, '年度续费加购'),
('SO202501002', 3, 1, '2025-01-12', 'partial', 'shipped', 5.00, '升级数据平台'),
('SO202501003', 2, 3, '2025-01-19', 'pending', 'packing', 0.00, '试点项目'),
('SO202502001', 4, 5, '2025-02-05', 'paid', 'delivered', 2.50, '新增业务线'),
('SO202502002', 6, 5, '2025-02-16', 'partial', 'shipped', 4.00, '区域仓储系统升级'),
('SO202503001', 5, 4, '2025-03-02', 'paid', 'new', 1.50, '接口能力补充'),
('SO202503002', 1, 2, '2025-03-10', 'pending', 'new', 6.00, '跨部门扩容')
ON CONFLICT (order_no) DO NOTHING;

INSERT INTO sales_order_items (order_id, product_id, quantity, unit_price, item_discount_rate) VALUES
(1, 1, 1, 68000, 3.00),
(1, 6, 2, 47000, 0.00),
(2, 2, 1, 128000, 5.00),
(2, 4, 2, 56000, 2.00),
(3, 3, 3, 42000, 0.00),
(4, 2, 1, 128000, 2.50),
(4, 5, 2, 39000, 0.00),
(5, 3, 2, 42000, 4.00),
(5, 6, 1, 47000, 0.00),
(6, 6, 2, 47000, 1.50),
(6, 4, 1, 56000, 0.00),
(7, 1, 1, 68000, 6.00),
(7, 3, 1, 42000, 0.00)
ON CONFLICT (order_id, product_id) DO NOTHING;

CREATE OR REPLACE VIEW v_order_summary AS
SELECT
    o.order_no,
    o.order_date,
    c.customer_name,
    r.rep_name AS sales_rep_name,
    o.payment_status,
    o.shipping_status,
    ROUND(SUM(i.line_total) * (100 - o.discount_rate) / 100.0, 2) AS order_amount_after_discount
FROM sales_orders o
JOIN customers c ON c.id = o.customer_id
JOIN sales_reps r ON r.id = o.sales_rep_id
JOIN sales_order_items i ON i.order_id = o.id
GROUP BY o.order_no, o.order_date, c.customer_name, r.rep_name, o.payment_status, o.shipping_status, o.discount_rate;

CREATE OR REPLACE VIEW v_product_profitability AS
SELECT
    p.sku,
    p.product_name,
    p.category,
    SUM(i.quantity) AS total_quantity,
    ROUND(SUM(i.quantity * i.unit_price), 2) AS gross_sales,
    ROUND(SUM(i.quantity * p.unit_cost), 2) AS total_cost,
    ROUND(SUM(i.quantity * (i.unit_price - p.unit_cost)), 2) AS estimated_profit
FROM sales_order_items i
JOIN products p ON p.id = i.product_id
GROUP BY p.sku, p.product_name, p.category;

COMMIT;
```

### analyzer_agent
```python
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage

from text2sql.config import get_settings
from text2sql.llm_client import build_chat_model
from text2sql.skill_runtime import find_skill_tool, invoke_skill_tool, load_skill_tools


class AnalyzerAgent:
    """对查询结果生成中文分析报告，并按需调用 skill 外部导出工具。"""

    SYSTEM = """你是数据分析助手。根据用户问题、执行的 SQL 与查询结果，写一份**专业、简洁**的中文分析报告。

要求：
- 用 Markdown 小标题与列表，先给结论再给依据。
- 若结果为空，说明可能原因与下一步建议。
- 不要编造数据中不存在的数字；统计量请基于给定结果。
- 篇幅适中，避免空话。"""

    _TOOL_ROUTER_SYSTEM = """你是导出工具路由器。请根据用户需求，判断是否需要调用数据导出技能。

你将收到可用技能列表（intent/name/description/triggers）与用户问题。
你的任务：
1) 只从可用 intent 中选择需要执行的项；
2) 如果不需要导出，返回空列表；
3) 输出必须是 JSON，格式：{"intents":["pdf","table"]}。

注意：
- 不要编造不存在的 intent；
- 若用户明确需要下载/导出文件，优先选择对应 intent；
- 若仅是普通分析问答，返回空列表。"""

    def __init__(self, model: Any | None = None, *, report_dir: str | Path | None = None):
        self._llm = model or build_chat_model()
        self._report_dir = self._resolve_report_dir(report_dir)
        settings = get_settings()
        self._enable_skill_tools = settings.analyzer_enable_skill_tools
        configured_root = Path(settings.analyzer_skills_dir).expanduser()
        if not configured_root.is_absolute():
            configured_root = Path(__file__).resolve().parents[1] / configured_root
        self._skills_root = configured_root.resolve()
        self._skill_tools = (
            load_skill_tools(self._skills_root) if self._enable_skill_tools else []
        )

    @staticmethod
    def _resolve_report_dir(report_dir: str | Path | None) -> Path:
        if report_dir is not None:
            p = Path(report_dir)
        else:
            # 默认路径：项目根目录下 outputs/reports
            p = Path(__file__).resolve().parents[1] / "outputs" / "reports"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _save_report_file(
        self,
        *,
        report_text: str,
        user_question: str,
        sql: str,
        columns: list[str],
        rows: list[tuple[Any, ...]],
    ) -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = uuid4().hex[:8]
        filename = f"analysis_{ts}_{suffix}.md"
        path = self._report_dir / filename
        content = (
            "# 分析报告\n\n"
            f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}\n"
            f"- 用户问题：{user_question}\n"
            f"- SQL：`{sql}`\n"
            f"- 返回列：{columns}\n"
            f"- 返回行数：{len(rows)}\n\n"
            "## 报告正文\n\n"
            f"{report_text}\n"
        )
        path.write_text(content, encoding="utf-8")
        return path

    def _detect_export_intents(self, user_question: str) -> list[str]:
        if not self._skill_tools:
            return []

        # 去重并保序，避免同一 intent 被重复执行。
        available_intents: list[str] = []
        for tool in self._skill_tools:
            if tool.intent not in available_intents:
                available_intents.append(tool.intent)

        tool_lines = []
        for tool in self._skill_tools:
            tool_lines.append(
                (
                    f"- intent={tool.intent}; name={tool.name}; "
                    f"description={tool.description}; triggers={','.join(tool.triggers)}"
                )
            )
        tool_summary = "\n".join(tool_lines)
        router_input = (
            f"用户问题：{user_question}\n\n"
            f"可用 intents：{available_intents}\n"
            f"可用技能明细：\n{tool_summary}\n\n"
            '请仅输出 JSON，例如：{"intents":["pdf"]} 或 {"intents":[]}'
        )
        resp = self._llm.invoke(
            [
                SystemMessage(content=self._TOOL_ROUTER_SYSTEM),
                HumanMessage(content=router_input),
            ]
        )
        raw = str(resp.content if hasattr(resp, "content") else resp).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # 兼容模型返回包裹说明文字的情况，尽量提取 JSON 主体。
            start = raw.find("{")
            end = raw.rfind("}")
            if start == -1 or end == -1 or end <= start:
                return []
            try:
                data = json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                return []

        intents_raw = data.get("intents") if isinstance(data, dict) else None
        if not isinstance(intents_raw, list):
            return []
        selected: list[str] = []
        for item in intents_raw:
            intent = str(item).strip().lower()
            if intent in available_intents and intent not in selected:
                selected.append(intent)
        return selected

    def _run_export_tools(
        self,
        *,
        user_question: str,
        sql: str,
        columns: list[str],
        rows: list[tuple[Any, ...]],
        report_text: str,
    ) -> list[str]:
        if not self._enable_skill_tools:
            return []
        intents = self._detect_export_intents(user_question)
        if not intents:
            return []

        outputs: list[str] = []
        payload = {
            "user_question": user_question,
            "sql": sql,
            "columns": columns,
            "rows": rows,
            "report_text": report_text,
            "report_dir": str(self._report_dir),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        }
        for intent in intents:
            tool = find_skill_tool(user_question, self._skill_tools, intent)
            if not tool:
                outputs.append(f"- 未找到可用的 `{intent}` 导出 skill。")
                continue
            result = invoke_skill_tool(tool, payload=payload)
            if not result.get("ok"):
                outputs.append(
                    f"- `{intent}` 导出失败（skill: {tool.name}）：{result.get('error') or '未知错误'}"
                )
                continue
            data = result.get("result") or {}
            artifact = data.get("artifact_path")
            message = data.get("message") or "导出完成"
            if artifact:
                outputs.append(
                    f"- `{intent}` 导出成功（skill: {tool.name}）：{message}，文件：`{artifact}`"
                )
            else:
                outputs.append(f"- `{intent}` 导出成功（skill: {tool.name}）：{message}")
        return outputs

    def analyze(
        self,
        *,
        user_question: str,
        sql: str,
        columns: list[str],
        rows: list[tuple[Any, ...]],
        max_rows_in_prompt: int = 50,
    ) -> str:
        preview = rows[:max_rows_in_prompt]
        body = (
            f"用户问题：{user_question}\n\n"
            f"执行的 SQL：\n{sql}\n\n"
            f"列：{columns}\n"
            f"行（最多展示 {max_rows_in_prompt} 行）：\n{preview}"
        )
        if len(rows) > max_rows_in_prompt:
            body += f"\n… 共 {len(rows)} 行，其余已省略。"
        msgs = [
            SystemMessage(content=self.SYSTEM),
            HumanMessage(content=body),
        ]
        resp = self._llm.invoke(msgs)
        report_text = str(resp.content if hasattr(resp, "content") else resp).strip()

        tool_outputs = self._run_export_tools(
            user_question=user_question,
            sql=sql,
            columns=columns,
            rows=rows,
            report_text=report_text,
        )
        if tool_outputs:
            report_text = (
                f"{report_text}\n\n## 导出结果\n\n" + "\n".join(tool_outputs)
            )

        self._save_report_file(
            report_text=report_text,
            user_question=user_question,
            sql=sql,
            columns=columns,
            rows=rows,
        )
        return report_text
```

### skill_runtime
```python
from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_FRONTMATTER_RE = re.compile(r"^\s*---\s*\n([\s\S]*?)\n---\s*", re.MULTILINE)
_TOOL_INTENT_RE = re.compile(r"^\s*-\s*intent:\s*(.+?)\s*$")
_TOOL_SCRIPT_RE = re.compile(r"^\s*script:\s*(.+?)\s*$")
_TOOL_TRIGGERS_RE = re.compile(r"^\s*triggers:\s*(.+?)\s*$")


@dataclass(frozen=True)
class SkillToolSpec:
    intent: str
    script_path: Path
    triggers: tuple[str, ...]
    name: str
    description: str


def _normalize_text(value: str) -> str:
    return value.strip().lower()


def _extract_frontmatter(skill_md_text: str) -> dict[str, str]:
    match = _FRONTMATTER_RE.search(skill_md_text)
    if not match:
        return {}
    body = match.group(1)
    out: dict[str, str] = {}
    for line in body.splitlines():
        item = line.strip()
        if not item or ":" not in item:
            continue
        key, val = item.split(":", 1)
        out[key.strip()] = val.strip()
    return out


def _extract_tool_defs(skill_md_text: str) -> list[dict[str, Any]]:
    tool_defs: list[dict[str, Any]] = []
    lines = skill_md_text.splitlines()
    i = 0
    while i < len(lines):
        intent_m = _TOOL_INTENT_RE.match(lines[i])
        if not intent_m:
            i += 1
            continue
        item: dict[str, Any] = {"intent": intent_m.group(1).strip()}
        i += 1
        while i < len(lines):
            if _TOOL_INTENT_RE.match(lines[i]):
                break
            script_m = _TOOL_SCRIPT_RE.match(lines[i])
            if script_m:
                item["script"] = script_m.group(1).strip()
            triggers_m = _TOOL_TRIGGERS_RE.match(lines[i])
            if triggers_m:
                raw = triggers_m.group(1).strip()
                item["triggers"] = [v.strip() for v in raw.split(",") if v.strip()]
            i += 1
        tool_defs.append(item)
    return tool_defs


def load_skill_tools(skills_root: str | Path) -> list[SkillToolSpec]:
    root = Path(skills_root)
    if not root.exists() or not root.is_dir():
        return []

    tools: list[SkillToolSpec] = []
    for skill_md in root.glob("*/SKILL.md"):
        skill_dir = skill_md.parent
        text = skill_md.read_text(encoding="utf-8")
        meta = _extract_frontmatter(text)
        skill_name = str(meta.get("name") or skill_dir.name)
        skill_desc = str(meta.get("description") or "")
        tool_defs = _extract_tool_defs(text)
        if not tool_defs:
            continue
        for item in tool_defs:
            if not isinstance(item, dict):
                continue
            intent = _normalize_text(str(item.get("intent") or ""))
            script = str(item.get("script") or "").strip()
            if not intent or not script:
                continue
            script_path = (skill_dir / script).resolve()
            if not script_path.exists():
                continue
            triggers_raw = item.get("triggers") or []
            triggers: list[str] = []
            if isinstance(triggers_raw, list):
                triggers.extend(str(t).strip() for t in triggers_raw if str(t).strip())
            triggers.append(intent)
            tools.append(
                SkillToolSpec(
                    intent=intent,
                    script_path=script_path,
                    triggers=tuple(_normalize_text(t) for t in triggers),
                    name=skill_name,
                    description=skill_desc,
                )
            )
    return tools


def find_skill_tool(user_question: str, tools: list[SkillToolSpec], intent: str) -> SkillToolSpec | None:
    wanted = _normalize_text(intent)
    q = _normalize_text(user_question)
    candidates = [t for t in tools if t.intent == wanted]
    if not candidates:
        return None
    for tool in candidates:
        if any(trigger and trigger in q for trigger in tool.triggers):
            return tool
    return candidates[0]


def invoke_skill_tool(
    tool: SkillToolSpec,
    *,
    payload: dict[str, Any],
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(tool.script_path)],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if proc.returncode != 0:
        return {
            "ok": False,
            "error": f"脚本退出码={proc.returncode}",
            "stderr": stderr,
            "stdout": stdout,
        }
    if not stdout:
        return {"ok": True, "result": {"message": "工具执行成功，但未返回内容"}}
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return {"ok": True, "result": {"message": stdout}}
    return {"ok": True, "result": data}

```


### text2sql_agent
```python
import re
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from text2sql.llm_client import build_chat_model


_SQL_BLOCK = re.compile(r"```(?:sql)?\s*([\s\S]*?)```", re.IGNORECASE)

# ReAct 续轮：模型未给出 Final 时注入，促使其继续或收尾为 Final SQL
_REACT_OBSERVATION = (
    "Observation（系统）：上一轮未出现以 `Final:` 开头的最终 SQL。"
    "请继续 ReAct：输出 Thought / Action / Observation，"
    "若已确定查询则下一则回复必须以 `Final:` 开头并紧跟一条可执行的 SELECT（PostgreSQL），"
    "在此之前不要结束。"
)


def _extract_sql(text: str) -> str:
    text = text.strip()
    m = _SQL_BLOCK.search(text)
    if m:
        return m.group(1).strip()
    return text


def _extract_final_sql(text: str) -> str | None:
    """从 `Final:` 行（或段）解析最终 SQL；无则返回 None。"""
    lower = text.lower()
    key = "final:"
    idx = lower.rfind(key)
    if idx == -1:
        return None
    rest = text[idx + len(key) :].strip()
    if not rest:
        return None
    # 去掉可选的 markdown 围栏
    rest = re.sub(r"^```(?:sql)?\s*", "", rest, flags=re.IGNORECASE)
    rest = re.sub(r"\s*```\s*$", "", rest)
    rest = rest.strip()
    return rest or None


def _resolve_sql_output(text: str) -> str:
    """优先 Final:，否则兼容旧版 ```sql``` 或整段文本。"""
    final = _extract_final_sql(text)
    if final:
        return final
    return _extract_sql(text).strip()


class Text2sqlAgent:
    """根据自然语言与上下文生成只读 SQL，并在失败时结合错误信息修正。"""

    SYSTEM = """你是一个 PostgreSQL Text2SQL Agent，使用 ReAct（Thought / Action / Observation）模式工作。
你的目标：根据「数据库 schema」「对话历史」「用户问题」，生成最终可执行的**只读 SQL**。

你必须遵循以下硬性约束：
- 只能输出一条 SQL（最终答案必须是 SQL）。
- SQL 必须以 SELECT 开头。
- 禁止 INSERT/UPDATE/DELETE/DDL/ALTER/DROP/TRUNCATE/CREATE/事务控制/多语句/存储过程。
- 禁止输出 Markdown、解释文字、注释。
- 若信息不足，生成保守但可执行的查询（例如加 LIMIT、使用 ILIKE 模糊匹配）。
- 必须使用 PostgreSQL 语法。
- 优先使用 schema 中存在的表与字段，禁止臆造字段。
- 若用户追问指代前文，必须结合对话历史消歧后再思考。
- 若给出错误反馈（Observation），Thought 必须解释修正依据，再输出新 Action。

格式要求：
Thought: <分析需求、参照 schema 与对话历史、消歧、判断可行性、错误修正思路>
Action: 选择操作（如：识别表、识别字段、构建 join、添加过滤条件、添加聚合、加 limit、修复错误）
Observation: 检查 SQL 合法性、字段是否存在、语法是否正确、是否只读

重要输出格式规则：
- 你的最终输出必须是：
Final: <SQL>"""

    def __init__(self, model: Any | None = None, *, max_react_steps: int = 8):
        self._llm = model or build_chat_model()
        self._max_react_steps = max(1, max_react_steps)

    def generate(
        self,
        *,
        messages: list[BaseMessage],
        schema_text: str,
        previous_sql: str = "",
        last_error: str | None = None,
    ) -> str:
        extra: list[BaseMessage] = []
        if last_error:
            extra.append(
                HumanMessage(
                    content=(
                        f"上一次生成的 SQL 执行失败。\n错误信息：{last_error}\n"
                        f"上次 SQL：\n{previous_sql}\n\n"
                        "请按 Thought / Action / Observation 分析失败原因并修正；"
                        "最终必须以 `Final:` 开头输出一条可执行的 SELECT（PostgreSQL）。"
                    )
                )
            )
        trail: list[BaseMessage] = [
            SystemMessage(
                content=f"{self.SYSTEM}\n\n当前数据库 schema 摘要：\n{schema_text}"
            ),
            *messages,
            *extra,
        ]
        last_raw = ""
        for step in range(self._max_react_steps):
            resp = self._llm.invoke(trail)
            last_raw = (
                resp.content if hasattr(resp, "content") else str(resp)
            )
            last_raw = str(last_raw)
            sql = _extract_final_sql(last_raw)
            if sql:
                return sql.strip()
            # 未出现 Final:：继续 ReAct 轮次（最后一轮仍无 Final 则走兼容解析）
            if step < self._max_react_steps - 1:
                trail.append(AIMessage(content=last_raw))
                trail.append(HumanMessage(content=_REACT_OBSERVATION))
        return _resolve_sql_output(last_raw).strip()


def last_user_text(messages: list[BaseMessage]) -> str:
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            c = m.content
            return c if isinstance(c, str) else str(c)
    return ""

```

### config
```python
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


Provider = Literal["doubao", "deepseek", "qwen", "openai"]


# 常见 OpenAI 兼容网关默认地址（可通过环境变量覆盖）
_DEFAULT_BASE_URLS: dict[str, str] = {
    "doubao": "https://ark.cn-beijing.volces.com/api/v3",
    "deepseek": "https://api.deepseek.com/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "openai": "https://api.openai.com/v1",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql://user:pass@localhost:5432/dbname",
        description="PostgreSQL 连接串",
    )

    llm_provider: Provider = Field(default="deepseek", description="doubao | deepseek | qwen | openai")
    llm_api_key: str = Field(default="", description="LLM API Key")
    llm_base_url: str | None = Field(default=None, description="覆盖默认网关")
    llm_model: str = Field(default="deepseek-chat", description="模型名")

    max_sql_retries: int = Field(default=3, ge=1, le=10)
    sql_timeout_seconds: int = Field(default=60, ge=1)

    # 可选：限制只暴露这些表给模型（逗号分隔）；空表示从库中拉取 public 表清单
    schema_allow_tables: str = Field(default="", description="e.g. orders,users")
    analyzer_skills_dir: str = Field(
        default="skills",
        description="skills 根目录，按 <skill>/SKILL.md 组织",
    )
    analyzer_enable_skill_tools: bool = Field(
        default=True,
        description="是否启用分析阶段的 skill 外部工具调用",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def resolve_llm_base_url(settings: Settings) -> str:
    if settings.llm_base_url:
        return settings.llm_base_url
    return _DEFAULT_BASE_URLS.get(settings.llm_provider, _DEFAULT_BASE_URLS["openai"])

```