# 经方多医家文献研习 Skill

**简体中文** | [繁體中文](README.zh-TW.md)

`jingfang-research` · `0.2.0-public-preview` · Python 3.9+

一个统一入口，自动选择倪海厦、李可或多医家视角，检索用户的本地文献，并追溯来源。支持常见中文问题路由、会话内切换、SQLite 中文检索和证据展开。

**公开版仅附带两条合成演示数据，不附带经典原文、倪海厦/李可语料、医案或课程。**未导入有权使用的文献时，医学问题会明确提示资料不足。演示数据不能作为医学证据。本项目是文献研习工具，不是个体诊疗系统。

## 直接使用整个仓库

下载或克隆本仓库后进入目录，运行：

```bash
python3 .agents/skills/jingfang-research/scripts/build_index.py
python3 .agents/skills/jingfang-research/scripts/research.py '桂枝汤和麻黄汤有什么区别？'
python3 .agents/skills/jingfang-research/scripts/research.py '展开证据 DEMO001'
```

然后在 Codex 中打开本仓库，启动新聊天，直接说：

- “倪师怎么看桂枝汤？”
- “切换李可视角。”
- “比较倪海厦和李可的观点；缺失资料明确说明。”

本仓库的 AGENTS.md 引导统一入口；也可用 `$jingfang-research` 明确调用。Skill 发生变化而未显示时，重开项目或新聊天。官方加载规则见 [Codex Skills](https://learn.chatgpt.com/docs/build-skills)。

## 安装到另一个项目

在本仓库运行，明确指定一个已经存在的目标项目：

```bash
python3 scripts/install_skill.py --project /path/to/your-project
```

安装器只复制公开清单中的自包含 Skill，并为目标独立建立演示索引。不写全局 Codex 配置，不改目标 AGENTS.md；遇到同名 Skill 会拒绝覆盖。目标项目若已有同名本地研习版，请继续保留该版本，在新的测试项目试用公开版。

在目标项目启动新聊天。自然语言选择取决于 Codex 实际交互；必要时用 `$jingfang-research`。可以自行将“涉及经方文献研究优先使用 jingfang-research，工程任务正常处理”加入目标项目说明，但安装器不会擅自修改它。

卸载时只移除目标项目的 `.agents/skills/jingfang-research`；先备份其中自行导入的资料和会话。没有后台进程、服务或端口需要停止。

## 导入自己的文献

按 [授权资料导入说明](docs/DATA_IMPORT.md) 准备资料包，在实际安装位置执行：

```bash
python3 .agents/skills/jingfang-research/scripts/import_evidence.py /path/to/authorized-bundle --name my-source
```

导入器只读取本地 JSONL 和必要来源文件，不下载资料、不执行包内脚本。用户资料进入 `modules/private-*`，不会加入公开文件清单，Git 默认忽略。RIGHTS.md 与 rights_basis 只是使用权声明，工具不独立核实授权。

经典、倪海厦和李可的资料分别标 perspective。没有相应记录时不生成其观点。真实证据 ID 由导入资料决定；公开版不包含 N003，演示 ID 是 DEMO001/DEMO002。

## 模式与会话

当前明确多医家/比较指令优先，否则当前选择 > 本聊天最近明确模式 > 提到医家 > 默认多医家。新聊天默认 comparison。代码词法路由覆盖常见表达，复杂问题仍需要 Codex 正确理解。

CLI 可用 `--mode nihaixia` / `like` / `comparison` 表示前一模式；当前指令可覆盖。使用 `--interactive` 时生成独立会话，输入 `exit` 退出。只有显式 `--session` 或交互模式会保存最近问题和模式；请勿录入患者身份信息，不同聊天不要共用 ID。

## 依赖和检索边界

Python 3.9+ 标准库，无 pip、付费 API、Docker、向量库或 Web 服务。SQLite 支持 FTS5 trigram 时使用三字检索，否则回退字面扫描；两字查询回退字面匹配。繁简映射有限，不是完整中文分词或语义检索。

运行路径从脚本自身定位，不依赖固定用户名或工作目录；整个 Skill 可以搬迁。CLI 输出证据包，中文分析由 Codex 组织。脚本离线可用不等于 Codex 模型离线可用。

A/B/C/D 是原件核验、待核定位、第三方整理、AI 推论/演示等来源状态，不是临床有效性等级。即便找到原话，也不等于相关疗效和安全性已证实。

## 测试和生成发布包

```bash
python3 -B -m unittest discover -s tests -v
python3 scripts/package_release.py --output ../jingfang-research-public.zip
```

打包器核对 PUBLIC_FILES.json 中的文件和哈希，只打包这些文本文件。未知文件、内容改动或疑似个人信息会使检查失败；不会自动把新资料加入清单。生成索引、会话与缓存不进入 ZIP；存在未列入清单的私人资料时会拒绝打包。不要直接压缩整个本地研习目录。

修改公开代码后，维护者须审查变更和隐私，再更新清单中的哈希。尚未上传或自动配置 GitHub。测试范围与待验项目见 [测试报告](docs/TEST_REPORT.md)。

## 许可证

本公开包的原创代码、文档和合成演示数据采用 [MIT](LICENSE)。不包含第三方医学语料或上游代码；使用者导入的资料不自动获得 MIT 授权。[公开包范围与许可说明](docs/DISTRIBUTION.md)。
