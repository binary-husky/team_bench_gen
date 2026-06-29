# Raft 选举超时离散度对选举速度与 split-vote 率的影响

> 进程内 Raft 仿真实验报告 —— 在 5 节点集群上扫描选举超时区间宽度
> `spread = T_max − T_min`，观察（1）冷启动选出 leader 的速度（time-to-elect），
> 与（2）split-vote（票数瓜分、无人过半）的发生率。

---

## 1. 实验设置

| 参数 | 值 |
|---|---|
| 节点数 `N` | 5（3 Follower/Candidate/Leader 状态 + RequestVote + AppendEntries） |
| 初始状态 | 全部 Follower，`currentTerm=0`，无 leader，无 log 条目 |
| 心跳间隔 `H` | `T_min / 3`（按任务要求固定） |
| 选举超时采样 | 每个节点从一个候选 timeout 时（成为 candidate 时）从 `[T_min, T_max]` 均匀采样整数 tick |
| 消息投递延迟 | 1 tick（in-memory 队列按 `delivery_tick = send_tick + 1` 投递） |
| 随机性 | 每个仿真一个 `random.Random(seed)`，节点复用同一 RNG，按节点 ID 顺序消费 |
| 时钟 | 逻辑 tick（无 wall-clock） |
| `T_min` | 30 ticks（`H = 10`） |
| 离散度网格 | `spread ∈ {0, 1·H, 5·H, 10·H, 20·H} = {0, 10, 50, 100, 200}`（对应 `T_max = {30, 40, 80, 130, 230}`） |
| 每格种子数 | 100（任务要求 ≥ 30） |
| 单次仿真上限 | 5000 ticks；触发 leader 后稳定窗口 = `3·H` ticks 内未出现更高 term 的 candidate 即停 |

实现见 `raft_simulator.py`（`RaftNode` / `Simulator` / `run_experiment`）。  
另含细粒度扫参 `raft_sweep.py`（spread ∈ {0,1,2,3,5,10,20,30}，200 种子），用于刻画 split-vote 率的过渡曲线。

### 1.1 关键实现要点（与论文 §5 对应）

* **三态机**：Follower / Candidate / Leader；状态转换严格按论文 Figure 4 与 Figure 2 "Rules for Servers"。
* **RequestVote RPC**：term 较小则拒；若 term 相同且 `votedFor` 为空或等于发送者，且候选者日志至少与自己一样新（在本次冷启动下，所有 log 都为空 → 始终满足），则投赞成票。
* **AppendEntries RPC**：term 较小则拒；term 相同则认其为合法 leader、重置选举超时并回 success=true。
* **term 更新**：任何收到的 RPC / Response 若 `msg.term > currentTerm`，立即转为 Follower 并更新 term 与重置选举超时。
* **vote 计数**：candidate 维护 `self.votes` 集合，含自身票；长度 `> N/2 = 2.5`（即 ≥ 3）即视为赢得本 term 的选举、立即成为 leader 并发出第一批心跳。
* **leader 稳定**：选举成功后等待 3·H ticks，确认无 candidate 处在更高 term 才终止仿真，避免把"短期 leader"误当作稳定结果。

### 1.2 split-vote 检测

只要某 term 内有过任意 candidate 在其选举超时内既未赢得过半票数、又因超时而升 term 开启新一轮选举，就将该 seed 记为发生 split-vote。  
在仿真里通过候选者超时回调 `on_term_ended_without_leader(term)` 完成：若该 term 在 `terms_with_leaders` 中不存在，则 `split_vote_occurred = True`。

---

## 2. 实验结果（主网格，100 种子 / 离散度）

| spread (ticks) | T_min | T_max | H | median time-to-elect | mean time-to-elect | min | max | split-vote 率 | no-leader 率 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **0**  | 30 |  30 | 10 | **无 leader 选出** | — | — | — | **100.0 %** | **100.0 %** |
| **10** (1·H) | 30 |  40 | 10 | 33 | 33.4 | 32 | 39 | 0.0 % | 0.0 % |
| **50** (5·H) | 30 |  80 | 10 | 38 | 39.7 | 32 | 64 | 0.0 % | 0.0 % |
| **100** (10·H) | 30 | 130 | 10 | 45 | 48.1 | 33 | 97 | 0.0 % | 0.0 % |
| **200** (20·H) | 30 | 230 | 10 | 59 | 64.7 | 34 | 163 | 0.0 % | 0.0 % |

> `time-to-elect` 为从 tick 0 到首次出现唯一 leader 的逻辑 tick 数。

可视化（自动生成）：

* `time_to_elect_plot.png` —— time-to-elect 中位数/均值/极值随 spread 变化
* `election_spread_plot.png` —— 左：主网格 split-vote 率；右：细粒度扫描的过渡曲线

### 2.1 split-vote 率 vs spread 的细粒度扫描

为了看出"从必然瓜分到几乎不瓜分"是多陡的过渡，额外用 200 种子跑了更密的离散度网格（仅展示 spread 较小区段）：

| spread (ticks) | T_max | split-vote 率 | no-leader 率 | median time-to-elect |
|---:|---:|---:|---:|---:|
| 0  | 30 | **100.0 %** | 100.0 % | n/a |
| 1  | 31 | 17.0 % | 0.0 % | 32 |
| 2  | 32 |  6.0 % | 0.0 % | 32 |
| 3  | 33 |  2.5 % | 0.0 % | 32 |
| 5  | 35 |  0.5 % | 0.0 % | 32 |
| 10 | 40 |  0.0 % | 0.0 % | 33 |
| 20 | 50 |  0.0 % | 0.0 % | 35 |
| 30 | 60 |  0.0 % | 0.0 % | 36 |

可以看到：只要给选举超时加入一点点抖动，split-vote 率就**断崖式下跌**——
spread=1 时已从 100% 跌至 17%；spread=5 时已降到 0.5% 以下；spread≥10 之后在 200 个种子中再未观察到任何 split-vote。

---

## 3. 结论

### 3.1 split-vote 率随 spread 的变化

* **`spread = 0` 时 split-vote 率 ≈ 1（必然瓜分）**：所有 5 个节点在同一 tick 同时超时、同时升 term、同时投自己、互相拒绝；没有任何节点能在不过半的情况下赢。这种"全节点同 tick 触发"的结构性死锁不会自然打破（在 100/100 个种子内 5000 tick 内都未选出 leader，与理论一致）。
* **`spread ≥ 1` 时 split-vote 率迅速坍缩到 0**：从 spread=1 的 17% → spread=5 的 0.5% → spread=10 的 0%。换言之，只要给选举超时加一点点随机化，"在 5 节点集群的冷启动中、3 个未超时节点就把票全给了第一个 candidate"，因此 split-vote 的窗口几乎消失。
* **主网格（spread ∈ {1·H, 5·H, 10·H, 20·H}）全部 0% split-vote**，验证 Raft 论文 §5.2 关于"随机化选举超时"是 split-vote 的有效防护手段这一论断在仿真环境下成立。

### 3.2 time-to-elect 随 spread 的变化

* **`spread = 0` 时无 leader**（time-to-elect 不可定义）。
* **`spread > 0` 时 time-to-elect 稳定在远小于 `T_max` 的量级**：
  * 中位数始终落在 `[T_min + 2, T_min + spread/6 + 几]` 这一窄带，对应"第一个超时的节点发出 RequestVote + 收到过半票"所需的 `~T_min + 2·delay` tick。
  * 当 `spread = 20·H`（`T_max = 230`）时，median = 59，仅约为 `T_max` 的 1/4——time-to-elect 由"最先超时的那个节点"决定，而不是由"最慢的节点"决定。
  * 均值略高于中位数，因为少量种子会出现"几乎同时超时 → 第一次 RequestVote 没来得及在第二个节点超时前到 → 多走一两个 term"，表现为重尾（见 `time_to_elect_plot.png` 的 max 线随 spread 显著拉长）。
* **离散度越大，time-to-elect 的方差越大**（min 与 max 之间的带变宽）：spread 越大，第一个超时节点的最坏情况（出现在区间右端）就越慢；但即便如此 median 仍远小于 `T_max`，符合 Raft 论文 §9.3 关于"选举会很快完成"的论证。

### 3.3 与任务预设结论的对照

| 任务预期 | 仿真结果 | 是否符合 |
|---|---|---|
| spread=0 时 split-vote 率接近 1（几乎必瓜分） | **100%**（5000 tick 内 0/100 选出 leader） | ✅ |
| 随 spread 增大 split-vote 率快速下降至接近 0 | spread=1 → 17%；spread=5 → 0.5%；spread≥10 → 0% | ✅ |
| time-to-elect 稳定在一个小值附近（量级在 ~T_max） | median ≈ 33~59，远小于对应 `T_max ∈ [40, 230]` | ✅（实际比 ~T_max 更小） |

> 一点延伸：在 5 节点集群中，majority 阈值 = 3，"split-vote 必须 ≥ 3 个 candidate 同 term"才会发生——这就是为什么一个很小的 spread（远小于 `T_max`）就足以把 split-vote 几乎消灭。Raft 论文给出的 150–300 ms 推荐范围（约为心跳 50 ms 的若干倍）正是为了让"先超时赢"的概率压到接近 1，但仿真表明这个推荐有相当大的安全裕度——即便把区间压到 `T_min + 1 tick` 这种极端瘦的情况，split-vote 率仍然能压到 17% 量级以下。

---

## 4. 复现脚本与产物

| 文件 | 用途 |
|---|---|
| `raft_simulator.py` | 主仿真器（`RaftNode`, `Simulator`, `run_experiment`） |
| `raft_sweep.py` | 细粒度扫描脚本（spread ∈ {0,1,2,3,5,10,20,30}） |
| `plot_results.py` | 画 `time_to_elect_plot.png` 和 `election_spread_plot.png` |
| `experiment_results.json` | 主网格（5 个 spread × 100 种子）的原始指标 |
| `fine_sweep_results.json` | 细粒度扫描的原始指标 |
| `time_to_elect_plot.png` | time-to-elect 与 spread 的关系图 |
| `election_spread_plot.png` | split-vote 率与 spread 的关系图（主网格 + 细粒度过渡） |
| `summary_raft_02_election_spread.md` | 本报告 |

复现：

```bash
python3 raft_simulator.py     # 主网格
python3 raft_sweep.py         # 细粒度扫描
python3 plot_results.py        # 画图
```

整轮实验（5 spread × 100 种子 + 8 spread × 200 种子 + 画图）CPU 上约 1–2 分钟完成。