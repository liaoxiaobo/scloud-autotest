---
name: git-sync-develop
description: |
  自动将 origin/develop 同步到当前个人分支。全程自动执行：环境诊断 → stash 保护本地代码 → merge → 后处理恢复。
  仅在出现冲突时停止，逐文件展示冲突标记并等待用户决策（本地/远程/编辑/跳过）。
  适合不懂 Git 的团队成员通过 AI 完成代码同步。
model: opus
allowed-tools: [Read, Edit, Write, Bash, Grep, Glob]
user-invocable: true
---

# Git 同步 Develop 到个人分支 Skill

## 1. 触发条件

### 1.1 完整同步流程（阶段一到六）

当用户表达以下意图时，执行完整的 develop 同步 + commit/push 流程：
- "拉取 develop 最新代码"
- "把 develop 合并到我当前分支"
- "同步 develop"
- "更新一下主分支代码"
- 任何涉及将 `origin/develop` 内容合并到当前个人分支的请求

### 1.2 仅 commit / push（阶段六快速入口）

当用户表达以下意图时，**跳过同步阶段，直接进入阶段六**：
- "提交当前修改" / "commit"
- "push 代码" / "推送代码" / "push 到远程"
- "提交并推送" / "commit push" / "commit 并 push"

> **阶段六快速入口执行逻辑**：
> 1. 快速诊断当前分支状态（当前分支、领先远程提交数、未提交文件数）
> 2. **直接进入阶段六**，询问用户 commit / push / commit-push / 跳过
> 3. 不走阶段一到五的同步流程

## 2. 核心原则

1. **全程自动执行，仅冲突时询问**：环境诊断、stash、merge、后处理全部自动完成，只有遇到冲突才停止并等待用户逐文件决策
2. **本地代码绝对优先**：任何可能覆盖本地未提交修改的操作前，自动 stash 保护，禁止直接丢弃
3. **冲突必须逐文件处理**：禁止批量自动解决冲突，必须逐文件展示冲突内容、等待用户决策、按决策执行
4. **默认 merge 策略**：除非用户明确要求 rebase，否则使用 merge。rebase 的 ours/theirs 概念容易混淆，不适合非技术用户
5. **命令执行环境**：本文档中的 Shell 命令面向 **Git Bash（Windows）或 Unix Shell（Linux/macOS）**。若用户环境为 Windows CMD / PowerShell，AI 必须自动转换为等效命令

## 3. 执行阶段

### 阶段一：环境诊断（自动执行）

执行以下命令，将结果汇总后一次性汇报给用户：

```bash
# 当前分支
CURRENT_BRANCH=$(git branch --show-current)

# 未提交修改（跨平台）
git status --short

# 检测工作区是否已存在未解决的合并冲突（来自之前的 merge）
# --diff-filter=U 捕获所有未合并状态（UU/AA/AU/UA/DU/UD/DD），比 grep '^UU' 更完整
UNMERGED_COUNT=$(git diff --name-only --diff-filter=U | wc -l | tr -d ' ')

# 获取远程最新状态（带重试，最多 3 次）
FETCH_RETRY=0
FETCH_MAX_RETRY=3
FETCH_SUCCESS=0
FETCH_OUTPUT=""

while [ $FETCH_RETRY -lt $FETCH_MAX_RETRY ] && [ $FETCH_SUCCESS -eq 0 ]; do
    FETCH_OUTPUT=$(git fetch origin develop 2>&1)
    FETCH_EXIT=$?
    if [ $FETCH_EXIT -eq 0 ]; then
        FETCH_SUCCESS=1
    else
        FETCH_RETRY=$((FETCH_RETRY + 1))
        if [ $FETCH_RETRY -lt $FETCH_MAX_RETRY ]; then
            sleep 2
        fi
    fi
done

# fetch 成功后计算与 origin/develop 的差异
if [ $FETCH_SUCCESS -eq 1 ]; then
    # 清除可能存在的本地 develop 模式旧标志（防止上次"本地"模式残留影响本次正常执行）
    rm -f "$(git rev-parse --git-dir)/sync-develop-use-local"

    # 先确认 origin/develop 引用存在，防止 rev-list 报错（如从未 fetch 成功过的新仓库）
    if git rev-parse --verify origin/develop >/dev/null 2>&1; then
        LOCAL_AHEAD=$(git rev-list --count origin/develop..HEAD)
        REMOTE_AHEAD=$(git rev-list --count HEAD..origin/develop)
    else
        LOCAL_AHEAD="0"
        REMOTE_AHEAD="0"
        echo "⚠️ origin/develop 引用不存在，视为无差异"
    fi
fi

# 保存阶段一工作区状态，用于阶段五前后对比（stash pop 后检测本地文件是否丢失）
MODIFIED_COUNT=$(git status --short | grep -c '^ M' || echo "0")
STAGED_COUNT=$(git status --short | grep -c '^[MA]' || echo "0")
UNTRACKED_COUNT=$(git status --short | grep -c '^??' || echo "0")
cat > "$(git rev-parse --git-dir)/sync-develop-pre-status" <<EOF
MODIFIED_COUNT=$MODIFIED_COUNT
STAGED_COUNT=$STAGED_COUNT
UNTRACKED_COUNT=$UNTRACKED_COUNT
EOF
```

**汇报格式**（分两种情况）：

**情况 A：fetch 成功**

```markdown
🔍 环境诊断结果：
- 当前分支：`$CURRENT_BRANCH`
- fetch 状态：✅ 成功
- 未提交修改：`N` 个文件
- 新增未跟踪：`N` 个文件
- 暂存区变更：`N` 个文件
- 未解决冲突：`$UNMERGED_COUNT` 个文件
- 本地领先 origin/develop：`$LOCAL_AHEAD` 个提交
- 远程领先本地：`$REMOTE_AHEAD` 个提交
```

**情况 B：fetch 失败（3 次重试后仍失败）**

```bash
# 分析失败根因
if echo "$FETCH_OUTPUT" | grep -qiE "(Could not resolve host|Failed to connect|Connection refused|timed out|Network is unreachable)"; then
    FETCH_REASON="网络不可达：无法连接到远程仓库服务器"
    FETCH_SUGGEST="请检查网络连接、VPN 状态，或确认远程仓库地址是否正确（git remote -v）"
elif echo "$FETCH_OUTPUT" | grep -qiE "(Authentication failed|401|403|could not read Username|fatal: unable to access)"; then
    FETCH_REASON="认证失败：无法通过身份验证访问远程仓库"
    FETCH_SUGGEST="请检查 Git 凭据（git credential fill），或确认 SSH 密钥已配置且已添加到 ssh-agent"
elif echo "$FETCH_OUTPUT" | grep -qiE "(Permission denied.*publickey|Could not read from remote repository.*ssh)"; then
    FETCH_REASON="SSH 密钥问题：无法通过 SSH 认证"
    FETCH_SUGGEST="请检查 SSH 密钥是否已配置（~/.ssh/id_rsa 或 ~/.ssh/id_ed25519），并确认公钥已添加到远程仓库"
elif echo "$FETCH_OUTPUT" | grep -qiE "(Could not resolve hostname|Name or service not known)"; then
    FETCH_REASON="DNS 解析失败：无法解析远程仓库域名"
    FETCH_SUGGEST="请检查 DNS 设置，或尝试用 IP 地址替代域名"
elif echo "$FETCH_OUTPUT" | grep -qiE "(does not appear to be a git repository|no such remote)"; then
    FETCH_REASON="远程仓库配置错误：origin 指向的地址无效"
    FETCH_SUGGEST="请检查 remote 配置（git remote -v），确认 origin URL 正确"
elif echo "$FETCH_OUTPUT" | grep -qiE "(Couldn't find remote ref|remote ref develop)"; then
    FETCH_REASON="develop 分支不存在：远程仓库中没有 develop 分支"
    FETCH_SUGGEST="请确认远程仓库中确实存在 develop 分支，或修改 skill 使用正确的分支名"
else
    FETCH_REASON="未知错误：$FETCH_OUTPUT"
    FETCH_SUGGEST="请根据上述错误信息排查，或联系管理员"
fi
```

```markdown
🔍 环境诊断结果：
- 当前分支：`$CURRENT_BRANCH`
- fetch 状态：⚠️ 失败（已重试 3 次）
- 失败根因：$FETCH_REASON
- 未提交修改：`N` 个文件
- 新增未跟踪：`N` 个文件
- 暂存区变更：`N` 个文件
- 未解决冲突：`$UNMERGED_COUNT` 个文件

💡 建议：$FETCH_SUGGEST

请选择：
- "重试" → 重新执行 fetch（再尝试 3 次）
- "本地" → 使用本地 develop 分支继续同步（⚠️ 可能不是最新代码，存在冲突风险）
- "停止" → 结束同步，手动修复后重新执行本 skill
```

> **文件列表超过 5 个时，前 5 个完整列出，其余用 "...等 N 个文件" 概括。**
>
> **分流逻辑**：
> - 如果 `FETCH_SUCCESS -eq 0`：**停止自动流程**，汇报 fetch 失败根因，等待用户选择"重试"/"本地"/"停止"
>   - 用户选"重试" → 回到阶段一重新执行 fetch
>   - 用户选"本地" → 将 `FETCH_SUCCESS` 视为成功，使用本地 develop 分支继续后续阶段：
>     1. 设置标志文件：`echo "1" > "$(git rev-parse --git-dir)/sync-develop-use-local"`
>     2. AI 执行以下命令计算差异（基于本地 develop 分支）：
>        ```bash
>        LOCAL_AHEAD=$(git rev-list --count develop..HEAD)
>        REMOTE_AHEAD=$(git rev-list --count HEAD..develop)
>        ```
>     3. 阶段三检测到该标志后使用 `git merge develop` 而非 `git merge origin/develop`
>   - 用户选"停止" → 结束 skill，不执行任何后续操作
> - 如果 `UNMERGED_COUNT > 0`：⚠️ 汇报"工作区存在未解决冲突，需先处理"，**跳过阶段二、三、五，直接进入阶段四处理冲突**
> - 如果 `REMOTE_AHEAD > 0`：继续阶段二
> - 如果 `REMOTE_AHEAD = 0`：汇报"✅ 当前分支已是最新，无需同步"，**跳过阶段二至五，直接进入阶段六**
>
> 汇报完成后自动按分流逻辑进入下一阶段，**fetch 失败时等待用户回复，其他情况无需等待**。

---

### 阶段二：保护本地未提交修改（自动执行）

如果阶段一检测到未提交修改，**自动执行 stash**，避免 merge 时冲突或覆盖：

```bash
git stash push -u -m "sync-develop-$(git rev-parse --short HEAD)-$(date +%m%d-%H%M)"
```

**汇报格式**：

```markdown
🛡️ 本地代码保护：
检测到 $N 个未提交文件，已自动暂存（stash）。
同步完成后将自动恢复，无需担心丢失。
```

如果没有未提交修改，直接汇报"工作区干净，无需暂存"，继续下一阶段。

> **此阶段全程自动，不询问用户。**

---

### 阶段三：执行同步（自动执行）

**3.1 保存当前 HEAD 并执行同步**

```bash
# 保存当前 HEAD 到临时文件，用于后续依赖变更检测
#（用文件替代环境变量，因 Claude Code 各 Bash 调用为独立进程，export 无法跨调用持久化）
git rev-parse HEAD > "$(git rev-parse --git-dir)/sync-develop-pre-merge-head"

# 判断是否使用本地 develop 模式（阶段一 fetch 失败时用户选择"本地"）
USE_LOCAL=$(cat "$(git rev-parse --git-dir)/sync-develop-use-local" 2>/dev/null || echo "0")

# 判断当前分支
CURRENT_BRANCH=$(git branch --show-current)

if [ "$CURRENT_BRANCH" = "develop" ]; then
    # 用户已在 develop 分支，执行 pull 而非 merge
    if [ "$USE_LOCAL" = "1" ]; then
        echo "⚠️ 当前在 develop 分支且使用本地模式，无需 merge"
    else
        echo "⚠️ 当前在 develop 分支，执行 git pull origin develop"
        git pull origin develop
    fi
else
    # 在个人分支上，执行 merge
    if [ "$USE_LOCAL" = "1" ]; then
        echo "⚠️ 使用本地 develop 分支执行 merge：git merge develop"
        git merge develop
    else
        git merge origin/develop
    fi
fi
```

**3.2 检查冲突并分流**

```bash
CONFLICT_FILES=$(git diff --name-only --diff-filter=U)
```

- 如果 `CONFLICT_FILES` 为空：汇报"✅ 合并完成，无冲突"，**自动进入阶段五**
- 如果 `CONFLICT_FILES` 非空：汇报"⚠️ 发现冲突，进入冲突处理"，**进入阶段四（询问用户）**

> **此阶段全程自动，不询问用户。**

---

### 阶段四：冲突处理（核心交互环节，必须等待用户决策）

#### 4.1 冲突概览

```bash
CONFLICT_FILES=$(git diff --name-only --diff-filter=U)
CONFLICT_COUNT=$(echo "$CONFLICT_FILES" | grep -c .)
```

**汇报格式**：

```
⚠️ 发现 $CONFLICT_COUNT 个文件存在冲突，已停止自动操作。

冲突文件列表：
1. path/to/file1.py
2. path/to/file2.py
...

处理规则说明：
- "本地" → 保留你当前分支上的版本（`--ours`）
- "远程" → 保留 develop 分支上的版本（`--theirs`）
- "编辑" → AI 检测并打开环境中的 IDE（VS Code / JetBrains）编辑该文件，完成后回复"已解决"
- "编辑：<内容>" → 无 IDE 时的 fallback：你提供完整文件内容，AI 直接写入替换
- "跳过" → 暂不处理这个文件，继续下一个

注意：`--ours` = 你当前分支（本地），`--theirs` = develop（远程）。此对应关系仅适用于 merge 场景。
```

#### 4.2 逐文件冲突处理循环

**对每个冲突文件执行以下流程，每步必须等待用户明确指令：**

```
========== 文件 X/$CONFLICT_COUNT: <file_path> ==========

[完整冲突标记内容]
<<<<<<< HEAD
...你当前分支的版本内容...
=======
...develop 分支的版本内容...
>>>>>>> origin/develop

请选择：
- 输入 **"本地"** → 保留你当前分支版本
- 输入 **"远程"** → 保留 develop 版本
- 输入 **"编辑"** → AI 检测并打开 IDE（VS Code / JetBrains）编辑该文件
- 输入 **"编辑："+完整内容** → 无 IDE 时 fallback，AI 按你提供的内容完整替换文件
- 输入 **"跳过"** → 暂不处理，继续下一个文件
```

**按决策执行的命令**：

| 用户决策 | AI 执行 |
|:---|:---|
| 本地 | `git checkout --ours "<file_path>" && git add "<file_path>"` |
| 远程 | `git checkout --theirs "<file_path>" && git add "<file_path>"` |
| 编辑 | **IDE 模式**：检测 IDE → 打开文件 → 等待用户回复"已解决" → `git add "<file_path>"` |
| 编辑：... | **Fallback 模式**：使用 `Write` 工具将用户提供的内容完整写入 `<file_path>`，然后 `git add "<file_path>"` |
| 跳过 | 无操作，继续下一个文件 |
| 已解决 | 用户通过 IDE 解决后回复，执行 `git add "<file_path>"` 后继续 |

#### 编辑模式详细流程（IDE 自动检测）

当用户输入 **"编辑"**（无冒号及后续内容）时，按以下流程处理：

**1. 检测可用 IDE**

```bash
# 检测 VS Code（优先）
if command -v code >/dev/null 2>&1 || [ -n "$(which code 2>/dev/null)" ]; then
    IDE="vscode"
    IDE_CMD="code"
elif command -v idea >/dev/null 2>&1 || [ -n "$(which idea 2>/dev/null)" ]; then
    IDE="jetbrains"
    IDE_CMD="idea"
else
    IDE="none"
fi
```

**2. 按检测结果分流**

- **检测到 VS Code 或 JetBrains**：
  ```bash
  $IDE_CMD "<file_path>"
  ```
  汇报格式：
  ```markdown
  🖥️ 已在 $IDE 中打开 `<file_path>`。

  VS Code 提示：点击编辑器中的 "Accept Current Change" / "Accept Incoming Change" / "Accept Both Changes" 按钮，或手动编辑冲突标记区域。

  编辑完成后，请回复 **"已解决"**，AI 将自动执行 `git add` 并继续下一个文件。
  ```
  AI **等待用户回复"已解决"**，收到后执行 `git add "<file_path>"` 并继续下一文件。

- **未检测到 IDE**：
  汇报格式：
  ```markdown
  ⚠️ 未检测到 VS Code 或 JetBrains IDE。

  请使用 fallback 编辑模式：输入 **"编辑："+完整文件内容**（会完整替换整个文件），或选择：
  - "本地" → 保留当前分支版本
  - "远程" → 保留 develop 版本
  - "跳过" → 暂不处理
  ```
  AI **等待用户重新选择**，不自动处理下一文件。

> **重要**：用户发送"编辑："后的内容时，AI 必须用 `Write` 工具完整写入文件，不要尝试合并或拼接，直接替换整个文件内容。

#### 4.3 冲突解决完成

所有文件处理完毕后，检查是否还有未解决冲突：

```bash
REMAINING=$(git diff --name-only --diff-filter=U)

if [ -z "$REMAINING" ]; then
    # 区分 merge 冲突（需要创建合并提交）和 stash pop 冲突（只需恢复工作区，不自动 commit）
    if [ -f "$(git rev-parse --git-dir)/MERGE_HEAD" ]; then
        git commit -m "Merge origin/develop into $(git branch --show-current)"
        echo "✅ 冲突已全部解决，合并提交已创建。"
    else
        echo "✅ 冲突已全部解决，本地修改已恢复为未提交状态。"
    fi
else
    echo "⚠️ 以下文件仍被跳过未解决："
    echo "$REMAINING"
    echo "可稍后手动处理，或重新执行本流程。"
fi
```

> **汇报结果后，自动进入阶段五。**

---

### 阶段五：后处理与恢复（自动执行）

**5.1 检查工作区状态**

```bash
git status --short
```

**5.2 恢复 stash（如果阶段二使用了 stash）**

```bash
# 以下命令需在 Git Bash / Unix Shell 中执行

# 先检查是否存在阶段二创建的 stash（通过命名前缀匹配）
STASH_EXISTS=$(git stash list | grep -c "sync-develop-" || echo "0")

if [ "$STASH_EXISTS" -eq 0 ]; then
    echo "阶段二未创建 stash，无需恢复。"
else
    if [ -z "$(git status --short)" ]; then
        STASH_POP_OUTPUT=$(git stash pop 2>&1)
        STASH_POP_EXIT=$?
        if [ $STASH_POP_EXIT -eq 0 ]; then
            echo "✅ 之前暂存的本地修改已恢复，且无冲突。"
        else
            # 检查是否是"同名 untracked 文件已存在"导致的失败
            DUPLICATE_FILES=$(echo "$STASH_POP_OUTPUT" | grep "already exists, no checkout" | sed 's/ already exists, no checkout//')
            if [ -n "$DUPLICATE_FILES" ]; then
                echo "⚠️ stash 恢复时以下 untracked 文件已存在于工作区中（develop 也新增了同名文件）："
                echo "$DUPLICATE_FILES"
                echo "正在比较 stash 版本与工作区版本的内容差异..."
                # 进入 5.2.1 同名 untracked 文件处理流程
            else
                # 其他失败：检查是否产生合并冲突
                NEW_CONFLICTS=$(git diff --name-only --diff-filter=U)
                if [ -z "$NEW_CONFLICTS" ]; then
                    echo "⚠️ stash pop 失败，但未检测到冲突。错误信息："
                    echo "$STASH_POP_OUTPUT"
                else
                    echo "⚠️ 恢复暂存代码时以下文件产生新冲突，需逐文件处理："
                    echo "$NEW_CONFLICTS"
                    # stash 恢复冲突也进入阶段四处理
                fi
            fi
        fi
    else
        echo "工作区不干净，跳过自动恢复 stash。"
        echo "请稍后手动执行：git stash pop"
    fi
fi
```

> **如果 stash pop 产生新冲突，回到阶段四逐文件处理。**
> **如果 stash pop 因"同名 untracked 文件已存在"而失败，进入 5.2.1 处理。**

**5.2.1 同名 untracked 文件处理（循环逐文件处理，严禁中途 stash drop）**

当 stash 中的 untracked 文件与 merge 后的工作区文件同名时，按以下流程处理。

> ⚠️ **安全红线**：`git stash drop` 会删除整个 stash（含所有未恢复文件）。**严禁在处理单个文件后执行 `git stash drop`。** 必须等所有冲突文件处理完毕后，通过 `git stash pop` 恢复剩余内容。

1. **提取所有冲突的 untracked 文件列表**：
   ```bash
   DUPLICATE_FILES=$(echo "$STASH_POP_OUTPUT" | grep "already exists, no checkout" | sed 's/ already exists, no checkout//')
   ```

2. **逐个循环处理每个冲突文件**：

   对 `DUPLICATE_FILES` 中的每个 `<file_path>` 执行：

   a. **提取 stash 中的版本**：untracked 文件存储在 `stash@{0}^3` 中
      ```bash
      git show stash@{0}^3:<file_path> > "$(git rev-parse --git-dir)/stash-compare-<filename>"
      ```

   b. **比较内容差异**：
      ```bash
      # 方法 A：比较 hash（Git 自带，跨平台）
      HASH_STASH=$(git hash-object "$(git rev-parse --git-dir)/stash-compare-<filename>")
      HASH_WORK=$(git hash-object <file_path>)

      # 方法 B：diff（查看具体差异）
      diff -u "$(git rev-parse --git-dir)/stash-compare-<filename>" <file_path>
      ```

   c. **统一移动工作区文件到临时位置**（⚠️ **用 `mv` 替代 `rm`，保留恢复可能**）：

      无论 hash 是否相同，**首先将工作区中的冲突文件移动到 `.git` 目录的临时位置**，避免直接删除导致丢失风险：
      ```bash
      mv <file_path> "$(git rev-parse --git-dir)/stash-temp-$(echo '<file_path>' | tr '/' '_')"
      ```
      > 临时文件名使用原始路径（将 `/` 替换为 `_` 避免子目录），确保唯一可追踪。例如 `sugon_web/test.py` → `.git/stash-temp-sugon_web_test.py`。

      同时记录该文件的决策到决策清单文件：
      ```bash
      echo "<file_path>|<决策>" >> "$(git rev-parse --git-dir)/stash-decisions"
      ```

   d. **按结果决策**：
      - **如果 hash 相同**：两个版本完全一致。决策标记为 **"stash"**。汇报"内容一致，已临时移走工作区同名文件"，继续下一个文件。
      - **如果 hash 不同但 diff 仅显示 `^M` 或换行符差异**（Windows CRLF vs Unix LF）：内容本质相同。决策标记为 **"stash"**。汇报"差异仅为换行符（LF ↔ CRLF），已临时移走工作区同名文件"，继续下一个文件。
      - **如果内容确实不同**：停止自动操作，向用户汇报：
        ```
        ⚠️ 文件 <file_path>（第 X/Y 个冲突文件）在 stash 和工作区中的内容不同，请决定保留哪个版本：
        - 输入"stash" → 保留 stash 版本（pop 后自动恢复）
        - 输入"工作区" → 保留当前工作区版本（pop 后用原文件覆盖）
        - 输入"编辑：..." → pop 后写入你提供的内容
        ```
        用户决策后，AI 标记决策：
        - "stash" → 决策为 **"stash"**
        - "工作区" → 决策为 **"work"**
        - "编辑：..." → 决策为 **"edit"**
        **然后标记该文件已处理，继续下一个文件。**

3. **所有冲突文件处理完毕后**：
   - 汇报："所有冲突文件已处理，正在恢复 stash 中的剩余内容..."
   - 执行 `git stash pop`
   - **如果成功**：
     - 遍历决策清单文件 `$(git rev-parse --git-dir)/stash-decisions`，逐行读取 `<file_path>|<决策>`：
       - 决策为 **"stash"** → `rm "$(git rev-parse --git-dir)/stash-temp-$(echo '<file_path>' | tr '/' '_')"`（删除临时文件，stash 版本已恢复）
       - 决策为 **"work"** → `mv "$(git rev-parse --git-dir)/stash-temp-$(echo '<file_path>' | tr '/' '_')" <file_path>`（用原工作区版本覆盖 stash 恢复的版本）
       - 决策为 **"edit"** → `rm "$(git rev-parse --git-dir)/stash-temp-$(echo '<file_path>' | tr '/' '_')"`（删除临时文件），然后用 `Write` 工具写入用户提供的内容
     - 删除决策清单文件：`rm "$(git rev-parse --git-dir)/stash-decisions"`
     - ✅ stash 自动删除，所有 tracked/untracked 文件完整恢复
   - **如果仍失败**：
     - ⚠️ 汇报"stash pop 失败，正在恢复工作区原始文件..."
     - 遍历所有临时文件，`mv` 回原始路径（恢复合并后的工作区状态）
     - 删除决策清单文件
     - ⚠️ 汇报具体错误，**保留 stash**（`git stash list` 可查），建议手动处理

4. **绝对禁止**：
   - ❌ 在处理单个文件后执行 `git stash drop`
   - ❌ 在循环中途丢弃 stash
   - ❌ 使用 `rm` 直接删除工作区冲突文件（必须用 `mv` 保留恢复可能）

**5.3 检查依赖文件变更**

```bash
# 使用阶段三保存的 pre-merge HEAD 文件（存储在 .git 目录内，跨平台兼容）
PRE_MERGE_HEAD=$(cat "$(git rev-parse --git-dir)/sync-develop-pre-merge-head" 2>/dev/null || echo "HEAD@{1}")
git diff --name-only ${PRE_MERGE_HEAD} HEAD | grep -E "(requirements.*\.txt|package\.json|pyproject\.toml|poetry\.lock|yarn\.lock|Dockerfile)" || true
```

**如检测到依赖配置文件变更**：

> "检测到依赖配置文件有变更，建议执行 `pip install -r requirements.txt`（或对应环境的安装命令）更新依赖。"

**5.4 完成汇报（含同步前后对比）**

执行以下对比脚本，检测阶段一 stash 的本地文件是否在同步后丢失或被误删：

```bash
# 读取阶段一保存的状态
PRE_STATUS_FILE="$(git rev-parse --git-dir)/sync-develop-pre-status"
POST_MODIFIED=$(git status --short | grep -c '^ M' || echo "0")
POST_STAGED=$(git status --short | grep -c '^[MA]' || echo "0")
POST_UNTRACKED=$(git status --short | grep -c '^??' || echo "0")

if [ -f "$PRE_STATUS_FILE" ]; then
    source "$PRE_STATUS_FILE"
    echo "PRE_MODIFIED=$MODIFIED_COUNT"
    echo "PRE_STAGED=$STAGED_COUNT"
    echo "PRE_UNTRACKED=$UNTRACKED_COUNT"
    echo "POST_MODIFIED=$POST_MODIFIED"
    echo "POST_STAGED=$POST_STAGED"
    echo "POST_UNTRACKED=$POST_UNTRACKED"
fi
```

**汇报格式**：

```markdown
📋 同步完成：
- [x] 合并完成：当前分支已与 origin/develop 同步
- [x] 冲突文件：X 个已解决 / Y 个已跳过
- [x] stash 状态：已恢复 / 未恢复 / 无 stash
- [x] 依赖变更：有 / 无

📊 同步前后对比（本地代码保护检查）：
| 项目 | 同步前 | 同步后 | 状态 |
|:---|:---|:---|:---|
| 已跟踪修改 | `$PRE_MODIFIED` | `$POST_MODIFIED` | ✅ 一致 / ⚠️ 变化 |
| 暂存区文件 | `$PRE_STAGED` | `$POST_STAGED` | ✅ 一致 / ⚠️ 变化 |
| 未跟踪文件 | `$PRE_UNTRACKED` | `$POST_UNTRACKED` | ✅ 一致 / ⚠️ 变化 |
```

**异常告警规则**：
- 如果 `POST_MODIFIED < PRE_MODIFIED`：⚠️ 汇报"检测到已跟踪修改文件数量减少，可能存在 stash 恢复丢失或 merge 覆盖，请核对以下文件："，列出同步前存在但现在消失的文件（通过 `git status --short` 前后对比）。
- 如果 `POST_UNTRACKED < PRE_UNTRACKED`：⚠️ 汇报"检测到未跟踪文件数量减少，可能存在 stash 恢复时同名文件被覆盖或丢失，请核对："，列出消失的文件。
- 如果所有数字一致：✅ 汇报"本地代码保护检查通过，同步前后文件数量一致。"

> **此阶段全程自动，仅在 stash pop 产生冲突时回到阶段四询问用户。**

---

### 阶段六：后续操作 — commit / push（必须询问）

同步完成后，**必须**检测分支状态并询问用户是否 commit / push。

**快速入口**：如果用户通过 1.2 触发（直接要求 commit/push），跳过阶段一到五，直接执行本阶段。

**执行前诊断**：

```bash
CURRENT_BRANCH=$(git branch --show-current)
UPSTREAM=$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null)
AHEAD_COUNT=$(git rev-list --count @{u}..HEAD 2>/dev/null || echo "0")
MODIFIED_COUNT=$(git status --short | grep -c '^ M' || echo "0")
STAGED_COUNT=$(git status --short | grep -c '^[MA]' || echo "0")
UNTRACKED_COUNT=$(git status --short | grep -c '^??' || echo "0")
```

**状态汇报**：无论是否有内容可提交/推送，都必须汇报当前状态并询问用户。

**汇报格式**：

```markdown
📋 同步完成。

📊 当前分支状态：
- 本地领先远程：`$AHEAD_COUNT` 个提交
- 可提交的已跟踪修改：`$MODIFIED_COUNT` 个文件
- 可提交的暂存区文件：`$STAGED_COUNT` 个
- 未跟踪新文件：`$UNTRACKED_COUNT` 个

💡 后续操作（可选）：
- "push" → 推送已 commit 的提交到远程
- "commit" → 提交工作区修改（会让你选择文件并输入提交信息）
- "commit-push" → 提交并推送
- "跳过" → 不执行任何操作，继续编辑
```

> **用户必须明确输入一个选项（push / commit / commit-push / 跳过），skill 等待用户回复后才结束。**

---

#### 6.1 commit 文件选择流程

当用户输入 "commit" 或 "commit-push" 时，进入文件选择交互：

**1. 获取并分类文件列表**

```bash
# 已跟踪修改
MODIFIED_LIST=$(git status --short | grep '^ M' | sed 's/^ M //')
# 暂存区
STAGED_LIST=$(git status --short | grep '^[MA]' | sed 's/^[MA] //')
# 未跟踪
UNTRACKED_LIST=$(git status --short | grep '^??' | sed 's/^?? //')
```

**2. 展示文件列表**

```markdown
📋 请选择要提交的文件：

【A】已跟踪修改（修改现有文件）：
1. path/to/file1.py
2. path/to/file2.py
... 共 $N 个

【B】暂存区文件（已标记为新增/修改）：
5. path/to/file5.py
6. path/to/file6.py
... 共 $N 个

【C】未跟踪新文件（不会自动提交）：
8. path/to/new_file.py
9. path/to/new_dir/
... 共 $N 个

请选择：
- "A" → 仅提交已跟踪修改（默认推荐，最安全）
- "A+B" → 提交已跟踪修改 + 暂存区文件
- "全部" → 提交所有文件（A+B+C）
- "取消" → 不执行 commit
```

**3. 按选择执行**

| 用户选择 | AI 执行 |
|:---|:---|
| A | `git add -u`（仅已跟踪的修改） |
| A+B | `git add -u` + `git add <暂存区文件>` |
| 全部 | `git add -A`（包含未跟踪文件） |
| 取消 | 无操作，结束 commit 流程 |

> **注意**：`git add -u` 只添加已跟踪文件的修改，不会误添加 `.env`、临时文件等未跟踪文件。

**4. 询问提交信息**

用户确认文件后：

```markdown
请输入提交信息（或按回车使用默认）：
默认：WIP: $CURRENT_BRANCH 开发进度更新
```

**5. 执行 commit**

```bash
git commit -m "用户输入的提交信息"
```

**6. 如果用户输入的是 "commit-push"**

```bash
# 检查是否有远程分支
if git rev-parse --abbrev-ref --symbolic-full-name @{u} >/dev/null 2>&1; then
    git push origin $CURRENT_BRANCH
else
    # 首次推送，建立追踪关系
    git push -u origin $CURRENT_BRANCH
fi
```

---

#### 6.2 push 单独执行

当用户仅输入 "push" 时：

```bash
if [ "$AHEAD_COUNT" -gt 0 ]; then
    git push origin $CURRENT_BRANCH
else
    echo "本地无领先远程的提交，无需 push。"
fi
```

---

## 4. 安全红线

以下操作**未经用户明确文字确认，绝对禁止执行**：

| # | 禁止行为 | 正确做法 |
|:---:|:---|:---|
| 1 | `git reset --hard` 丢弃本地修改 | 自动 stash 保护，禁止直接丢弃 |
| 2 | `git checkout -- <file>` 强制覆盖本地修改 | 自动 stash 保护 |
| 3 | `git clean -fd` 删除未跟踪文件 | 仅列出文件提醒用户，不自动执行 |
| 4 | 自动批量解决冲突（全部 ours 或全部 theirs） | 逐文件展示、逐文件询问 |
| 5 | 在存在未提交修改的分支上直接 merge | 自动 stash 后再 merge |
| 6 | `git push --force` | 绝对禁止 |
| 7 | 自动使用 rebase 而不告知用户 | 默认 merge，rebase 需用户明确同意 |

---

## 5. 异常处理

### 5.1 图形化工具建议

如用户已安装 VS Code、JetBrains 等 IDE，在阶段四冲突处理时可建议：

```bash
# VS Code
code .
# JetBrains 系列
idea .
```

用户解决后回复"已解决"，AI 执行 `git add` 后继续。

### 5.2 二进制文件冲突
`.jpg`、`.png`、`.pdf`、`.zip` 等二进制文件冲突时：
- **不能展示 diff 内容**（二进制无文本 diff）
- 直接询问：保留本地版本还是远程版本？

### 5.3 敏感配置文件冲突
`.env`、`*config*.yaml`、`*secret*` 等文件冲突时：
- **高亮提醒**：此类文件通常包含环境配置（IP、密码、密钥）
- **建议用户手动核对**，不要自动选择任意一方

### 5.4 删除冲突（一方删除、一方修改）
- **停止并询问**：保留修改后的文件，还是接受删除？

### 5.5 合并后 stash 恢复产生新冲突
- 回到阶段四，对新冲突文件重复逐文件处理流程

### 5.6 stash pop 时"同名 untracked 文件已存在"

> **本场景的处理流程已在阶段五 5.2.1 中详细定义，此处仅为引用摘要。实际执行时必须严格遵循 5.2.1 的完整循环流程。**

当 merge 后的工作区中已存在与 stash 中同名的 untracked 文件（通常是 develop 新创建的文件）：

1. **禁止直接 `git stash drop`**：无论内容是否相同，**绝对禁止**在处理过程中执行 `git stash drop`。`drop` 会删除整个 stash（含所有未恢复的 tracked/untracked 文件），曾导致用户丢失大量本地未跟踪文件。
2. **必须循环逐文件处理**：提取 stash@{0}^3 中的每个冲突文件，与工作区版本比较 hash。
   - 处理前先 **`mv` 工作区文件到 `.git` 目录临时位置**（严禁 `rm`，保留恢复可能）。
   - 内容相同（或仅换行符差异）：决策为 "stash"，继续下一个文件。
   - 内容不同：停止并询问用户（"stash"/"工作区"/"编辑"），记录决策。
3. **所有冲突文件处理完毕后，执行 `git stash pop`**：
   - 成功 → 按决策处理临时文件（删除 stash 决策 / 恢复 work 决策 / 写入 edit 决策）
   - 失败 → 将临时文件 `mv` 回工作区，恢复原始状态

### 5.7 紧急回退
如合并后出现严重问题：

```bash
# 查看 reflog 找到合并前状态
git reflog

# 回退到合并前（保留工作区修改，优先推荐）
git reset --keep <commit-hash>

# 如 stash 被误删，尝试恢复
git fsck --unreachable | grep commit
# 找到疑似 stash 的 commit hash 后执行：
# git stash store <commit-hash>
# 然后 git stash list 确认已恢复
```

---

## 6. 交互规范（自动模式）

- **非冲突阶段全程自动**：环境诊断、stash、merge、后处理全部自动执行并汇报，不等待用户"继续"
- **仅在以下情况停止并等待用户输入**：
  1. **fetch 失败（阶段一）**：3 次重试后仍无法拉取远程 develop，等待用户选择"重试"/"本地"/"停止"
  2. 合并出现冲突（阶段四）
  3. stash pop 恢复后产生新冲突（回到阶段四）
  4. stash pop 因"同名 untracked 文件已存在"失败，且内容确实不同（进入 5.2.1）
  5. 同步完成后，用户选择 "commit" 或 "commit-push"（阶段六 6.1 文件选择）
  6. 用户主动打断或提出异议
- **冲突处理时**，每展示一个文件的冲突内容后，必须等待用户针对该文件的明确指令，禁止自动处理下一个
- **用户回复"编辑：..."时**，AI 必须使用 `Write` 工具完整写入文件，禁止拼接或合并
- **高危操作**（放弃修改、reset、force）绝对禁止在自动模式下执行
- **用户通过 IDE 解决冲突后回复"已解决"**，AI 执行 `git add` 并继续下一文件
