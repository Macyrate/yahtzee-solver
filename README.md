# yahtzee-solver

快艇骰子（Yahtzee）命令行决策助手：输入骰面和记分卡，获得**以整局期望总分最大化为目标**的保留、重投和记分建议。

通过动态规划穷举游戏状态并预计算价值表；另提供蒙特卡洛模拟，估计双方按期望分策略行动时的胜、平、负概率。

[English README](README.en.md) · [快速开始](#快速开始) · [使用指南](#使用指南) · [规则与限制](#规则与限制) · [开发与验证](#开发与验证)

## 功能一览

- **逐掷建议**：比较保留方案，显示期望总分和次选方案的差距。
- **记分卡管理**：自动计算栏位得分、上区进度及奖励。
- **胜率估计**：根据双方已填栏位模拟剩余比赛。
- **JSON 规则配置**：内置两套预设，可调整各栏计分。

| 预设 | 计分模型 | 栏数 | 开局期望总分¹ |
| --- | --- | --- | --- |
| `clubhouse` | 《世界游戏大全 51》快艇骰子 | 12 | 191.774 |
| `standard` | 基于标准 Yahtzee 的简化模型 | 13 | 245.905 |

¹ 对应仓库记录的预设模型；`standard` 未实现追加 Yahtzee 奖励和 Joker 规则，不能视为完整官方规则的最优值。

## 快速开始

需要 **Python 3.9+** 和 **NumPy >= 1.24**。在 macOS / Linux 终端运行：

```bash
git clone https://github.com/Macyrate/yahtzee-solver.git
cd yahtzee-solver
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python advise.py rules
```

Windows PowerShell 可用 `py -3 -m venv .venv` 创建环境，再用 `.\.venv\Scripts\Activate.ps1` 激活。

仓库附带 `tables.npz`，与当前配置匹配时无需建表。仓库也附带已有记分卡；**开始新局会清空 `state.json`，如需保留请先备份**：

```bash
python advise.py reset
python advise.py adv "1 3 3 3 4" 2
```

`2` 表示还可重投两次。每次实际掷骰后，重新输入骰面和剩余次数；用完重投机会后选栏记分。

## 使用指南

以下命令在已激活虚拟环境的项目目录执行。

### 查看规则与记分卡

```bash
python advise.py rules
python advise.py show
```

当前 `clubhouse` 预设的 `rules` 输出包含：

```text
开局最优期望 (全部 12 栏): 191.774
上区单练                     : 71.952
下区单练                     : 88.660
```

### 获取建议与记分

```bash
python advise.py adv "1 3 3 3 4" 2
python advise.py adv "1 2 3 3 3" 0
python advise.py take 3点 "1 2 3 3 3"
python advise.py show
```

| 输入 | 含义 |
| --- | --- |
| `"1 3 3 3 4"` | 五颗骰子，各为 1–6；用空格分隔并加引号 |
| `2` / `1` / `0` | 剩余重投次数；`0` 时比较记分选择 |
| `3点` | 当前规则中的栏位名称；以 `rules` 输出为准 |

`adv` 读取当前记分卡，`take` 将计算出的分数写入 `state.json`。**重复 `take` 同一栏会覆盖原分数**，不会自动阻止重复记分。

### 估计胜率

```bash
python pwin.py 8 6000 "1点=2,2点=8,3点=12,机会=22"
```

| 参数 | 含义 |
| --- | --- |
| `8` | 预期剩余回合数，用于与双方未填栏数核对 |
| `6000` | 每方模拟样本数；省略时为 3000 |
| `"栏位=分,…"` | 对手所有已填栏位，包括填零的栏；空卡传 `""` |

我方记分卡从 `state.json` 读取。省略的对手栏位视为未填。如果双方剩余栏数与首个参数不一致，程序会提示，并按**各自实际未填栏数**计算。输出包含终局均分、P10 / P90 分位数及胜平负比例。

这是有限样本估计，程序不输出置信区间；增加样本数通常能减小采样误差，也会增加耗时。

### 切换规则或重建表

```bash
python use.py                 # 列出预设
python use.py standard        # 覆盖 config.json 并重建 tables.npz
python use.py clubhouse       # 切回默认预设并重建
python solve.py --check       # 只显示当前规则，不建表
python solve.py               # 根据当前 config.json 重建表
```

切换前保存自定义配置和当前记分卡。`use.py` 不会重置 `state.json`；切换后开始新局请执行 `python advise.py reset`。建表耗时取决于规则规模、硬件及 NumPy / BLAS 环境。

## 规则与限制

求解器假设使用五颗公平、独立的六面骰，每回合最多掷三次，每次可以保留任意子集。

- 决策优化的是**期望总分**，不保证最大化当前对局的胜率。
- 胜率模拟假设双方都采用上述策略；对手采用不同策略时，估计可能偏离实际，方向不作保证。
- `standard` 不含追加 Yahtzee 的 +100 奖励，也没有依赖记分卡状态的 Joker 计分；当前 `full_house` 在两套预设中都接受五颗相同。因此它是简化变体。
- 动态规划枚举状态，但计算采用浮点数；“精确求解”指算法不依赖策略启发式，不代表没有浮点误差。
- 自定义上区奖励阈值目前应保持为 **63**：建表逻辑将上区小计封顶为 63，不能仅改 JSON 就宣称支持任意阈值。

### 自定义计分

从 `presets/` 的现有配置复制修改，每栏指定 `kind`、`rule` 和相应参数。例如：

```json
{
  "name": "四条",
  "kind": "lower",
  "rule": "n_kind",
  "params": { "n": 4, "score": "sum" }
}
```

| `rule` | 得分条件 | 参数 |
| --- | --- | --- |
| `upper` | 指定点数的总和 | 栏位属性 `face`：1–6 |
| `n_kind` | 至少 n 颗相同 | `n`、`score`：`"sum"` 或固定分 |
| `full_house` | 3+2 或五颗相同 | `score`：`"sum"` 或固定分 |
| `straight` | 至少 `length` 个连续点数 | `length`、`score` |
| `all_same` | 五颗相同 | `score` |
| `sum` | 五颗骰子总和 | 无 |

上区栏位必须排在所有下区栏位之前，栏位名称应唯一，栏位顺序决定掩码位序。修改 `config.json` 后执行 `python solve.py`；建议工具会检查配置指纹，拒绝使用不匹配的表。

## 工作原理

跨回合状态为 `(未填上区掩码, 上区小计, 未填下区掩码)`，通过后向归纳计算未来最优期望。回合内枚举 252 种无序骰面组合和 462 种保留组合，用保留到重投结果的概率转移比较行动价值。

`solve.py` 预计算价值表，`advise.py` 加载表后结合当前记分卡给出建议；`pwin.py` 用该策略模拟双方剩余比赛。

## 开发与验证

| 文件 | 职责 |
| --- | --- |
| [rules.py](rules.py) | 配置加载、计分矩阵、骰子空间与掩码工具 |
| [solve.py](solve.py) | 动态规划建表 |
| [advise.py](advise.py) | 决策建议、记分卡及全局模拟 |
| [pwin.py](pwin.py) | 双方终局分数和胜平负模拟 |
| [use.py](use.py) | 预设切换 |
| [verify.py](verify.py) | 独立掷骰、计分路径的统计校验 |
| [config.json](config.json) / [presets/](presets/) | 当前配置 / 内置预设 |
| `tables.npz` | 与配置指纹匹配的预计算数据 |
| [state.json](state.json) / [results/](results/) | 当前记分卡 / 历史对局记录 |
| [AGENTS.md](AGENTS.md) | 中文仓库协作指南 |

轻量检查：

```bash
python -m py_compile rules.py solve.py advise.py pwin.py use.py verify.py
python solve.py --check
python advise.py rules
```

修改求解或计分逻辑后，可重建表并运行统计验证：

```bash
python solve.py
python verify.py                # 每项默认 8000 局
python verify.py 32 56 20 1000   # 指定局面 (ru, s, rl) 与样本数
python advise.py sim 20000      # 全局模拟
```

完整模拟可能耗时较长。`verify.py` 的掷骰和计分路径独立，但行动策略仍依赖 DP 表；它检查模拟均分与 DP 期望是否相符，不是最优性的独立证明。统计检查存在采样波动，报告结果时应附规则、样本数和运行环境。

### 参与贡献

欢迎通过 [Issues](https://github.com/Macyrate/yahtzee-solver/issues) 报告问题，或提交 Pull Request。复现决策问题时请提供规则配置、已填记分卡、骰面、剩余重投次数、实际输出和预期行为。

提交前按改动范围运行检查；计分或求解改动应覆盖边界骰面并核对两套预设。不要在无关改动中提交个人记分卡、历史记录或重新生成的表。CLI 或规则行为变化时同步维护中英文说明。

## 许可

[MIT License](LICENSE)，Copyright © 2026 Macyrate。
