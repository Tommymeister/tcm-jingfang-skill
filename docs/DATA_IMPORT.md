# 授权资料导入

只有在有权使用资料时才导入；不要把导入成功理解为授权或医学有效性已核实。导入器不联网，也不会执行包内脚本。当前仅支持 classics、nihaixia、like 三种资料视角。

资料包结构：

```text
authorized-bundle/
  RIGHTS.md
  evidence.jsonl
  sources/
    excerpt.txt
```

RIGHTS.md 记录作者/权利人、资料来源、版本、许可或授权依据、使用范围和限制。不要为无授权资料虚填许可。sources/excerpt.txt 保存有权使用的必要短引及定位，避免完整搬运受保护著作。

evidence.jsonl 每行一条 JSON，字段如下：

| 字段 | 要求 |
|---|---|
| source_id | 稳定且全库唯一；常用 N900001 / L900001 / C900001，可通过聊天展开 |
| perspective | classics / nihaixia / like |
| author、title、edition | 如实记录作者、标题、版本；未知就明确未知 |
| chapter_or_lesson、page_or_timestamp | 实际章节、页码或时间；未知留空，不编造 |
| original_excerpt | 实际短引，不能把摘要当作原话 |
| interpretation | 解释或摘要，与短引分开 |
| source_url | 原件或真实转录链接，没有则空字符串 |
| local_source_path | 资料包内 sources/ 下的相对文件路径 |
| verification_status | A / B / C / D；A 必须另附 verification_log |
| verification_note | 核对了什么、还缺什么 |
| primary_locator_status | 原件定位状态，没有则 null |
| origin_family | 同源转载使用相同来源族，不能冒充独立印证 |
| record_kind | excerpt / locator_only / demo；demo 必须 D |
| rights_basis、license_scope | 使用权依据与范围，不是自动授权 |
| original_excerpt_sha256 | 对 original_excerpt 的 UTF-8 字节计算 SHA-256 |

计算短引哈希的方法：

```python
import hashlib
excerpt = input("输入与记录完全相同的短引：")
print(hashlib.sha256(excerpt.encode("utf-8")).hexdigest())
```

运行 README 的导入命令，名称只允许小写字母、数字和连字符。源路径不允许绝对路径、父目录跳转或越界链接。导入器只复制记录实际引用的来源文件和 RIGHTS.md；不会把整份来源目录或可执行脚本带入。

导入后存入 Skill 自己的 modules/private-名称。重复名称不覆盖；重复证据编号、短引哈希错误等导致索引构建失败时，会移除本次新模块，保留旧索引。索引采用原子替换。不要并发导入或重建同一个 Skill。

数据源字段仍是用户提供的内容；哈希和存在性检查不能核实原件内容、授权或医学事实。Skill 把检索内容作为不可信资料，不执行其指令。生成回答还需逐条审查引用。

删除某次导入：先备份，再删除对应 private-模块，重建索引。演示数据可移除 modules/demo/evidence.jsonl 后重建，空库仍可运行并诚实提示缺失。

用户资料和索引不属于公开包。不要为通过发布检查而把 private-模块加入 PUBLIC_FILES.json。若确实计划公开某项数据，应另做权利/隐私审查，并单独说明数据许可证。
