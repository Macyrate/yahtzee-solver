# 仓库协作指南

## 沟通与范围

- 默认使用简体中文沟通、撰写项目说明和提交信息；保留现有英文符号命名。
- 开始工作先检查 `git status --short`，保留用户已有改动。只修改任务所需文件，不顺手重构或增加依赖。
- 以实际代码和配置为准；README 中的历史性能、模拟结果不能替代本次验证。

## 项目结构

本项目是 Python + NumPy 命令行工具，没有 Web 服务或前端构建流程。

- `rules.py`：规则加载、计分矩阵、骰子组合、掩码与配置指纹。
- `solve.py`：后向归纳求解，输出 `tables.npz`。
- `advise.py`：加载预计算表、提供期望分建议、读写记分卡和模拟。
- `pwin.py`：按双方期望分策略模拟胜平负。
- `use.py`：复制预设到 `config.json`，默认重建表。
- `verify.py`：以独立掷骰和计分路径做统计校验，策略仍使用 DP 表。
- `presets/`：内置规则；`state.json`：当前对局；`results/`：历史对局。

先读 `README.md` 建立使用上下文，修改前亲自阅读相关实现。

## 环境与常用命令

使用项目已有 `.venv`；不存在时创建虚拟环境并安装 `requirements.txt`。不要向系统 Python 安装依赖。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python solve.py --check
python advise.py rules
```

最低文档环境为 Python 3.9+、NumPy >= 1.24。新增语法或依赖时保持兼容，并同步说明。

## 修改约束

- 沿用现有函数式脚本结构、四空格缩进和 `snake_case` 命名；避免为小改动引入新框架。
- 上区栏位必须位于下区之前；栏位顺序对应掩码位序，改动时检查状态和表的兼容性。
- 计分配置、状态维度或求解逻辑变化后，按需重建表并核对配置指纹。指纹只反映配置，不能检测算法代码变化。
- 当前上区小计维度固定为 0–63，不要将 JSON 可编辑误写成支持任意奖励阈值。
- 区分期望分最优决策与蒙特卡洛胜率估计；`standard` 是不含追加 Yahtzee 奖励及 Joker 规则的简化模型。
- 修改 CLI、规则或输出语义时，同步核对 `README.md` 与 `README.en.md`。不要捏造基准、兼容性或测试结果。

## 数据与副作用

- `advise.py reset` 清空 `state.json`；`take` 写入分数，同栏重复调用会覆盖。
- `use.py <预设>` 覆盖 `config.json` 并默认重建 `tables.npz`，但不重置记分卡。
- `solve.py` 覆盖 `tables.npz`。这些文件及 `results/` 含仓库数据，不要在文档检查中顺手覆盖。
- 需要运行有写入副作用的示例时，优先在临时目录复制必要文件后验证；任务明确需要修改这些数据时再在工作区执行。
- 不将个人对局、无关配置变化或生成数据混入代码提交。

## 验证与交付

按改动选择最小有效检查，不为纯文档改动重跑完整模拟：

```bash
python -m py_compile rules.py solve.py advise.py pwin.py use.py verify.py
python solve.py --check
python advise.py rules
git diff --check
```

计分或求解改动还需检查边界骰面（五颗相同、3+2、重复点数顺子、不满足条件）、转移概率以及两套预设。需要统计验证时运行：

```bash
python solve.py
python verify.py
python verify.py 32 56 20 1000
python advise.py sim 20000
```

这些模拟可能耗时较长；低样本试跑不能当作完整验证。报告实际运行的命令、规则、样本数及未验证范围，区分语法检查、统计一致性和最优性证明。提交前检查差异，提交信息必须使用简体中文。

## 本地检索与子代理

- 本地读文件、搜索和定位优先使用 FastCtx 的 `inspect_local_file`、`grep`、`glob`，传入绝对路径；多文件读取使用 `files` 批量调用。工具不可用时再使用 shell。
- 机械批量替换优先使用 FastCtx `replace`；语义修改及新增内容使用 `apply_patch`。
- 已知的小文件、即将修改的代码和架构、设计等奠基性文档由主代理亲自阅读。
- 对可独立回答、会产生大量中间材料的跨文件检索，优先委派只读子代理；多个值得委派的独立问题可并行，最多 10 个。不能清晰拆分或委派成本更高时直接处理。
- 子代理只负责探索、检索和独立核验；主代理负责关键判断、全部修改和最终验收。默认使用 `default` 的 Luna Medium、`fork_turns="none"`，复杂追踪按需选择更强模型。
- 委派任务须自包含，明确范围、问题和交付格式，要求返回 `file:line`、符号及关键原文。根据出处抽查重要结论，不重复通读其全部材料。
- 派发后继续独立工作；需要结果时等待，收齐所依赖任务的终态再下结论。子代理核验期间不要修改其证据文件。
