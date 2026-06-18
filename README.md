# team_bench_gen

## 从论文产生课题的方法

从一篇论文读取一个大课题 (big_subject)，然后根据论文，生成5个围绕大课题的可验证小课题 (small_subject)，5个小课题的复杂度和难度缓慢提升。

https://arxiv.org/pdf/2106.06257

注意事项：
- 课题必须放在 team_bench_gen/generated_task_await_verify （因为没验证）
- 如果有材料，需要复制到对应的位置 （team_bench_gen/generated_task_await_verify/{大课题名}/{大课题名}_material），该材料必须是直接从互联网获取，未经加工的材料。
- 命名规则：
    - 课题 md: {大课题名}/{大课题名}_{编号}.md
    - 材料文件夹：{大课题名}/{大课题名}_material
    - 一个大课题的所有子课题共享material，material不嫌多
- 不得创建太过于相似的小课题
- 暂时不允许你创建新的大课题



## 拓展研究课题的方法

在一个大课题中，从一个研究小课题拓展到更多研究小课题的方法，例如：

原始：
```
team_bench_gen/generated_task_verified/muon/muon_02.md
```

拓展：
```
team_bench_gen/generated_task_verified/muon/muon_03.md
team_bench_gen/generated_task_verified/muon/muon_04.md
team_bench_gen/generated_task_verified/muon/muon_05.md
team_bench_gen/generated_task_verified/muon/muon_06.md
```

拓展课题的规范如下。

```txt
    # 通用研究课题生成规范

    ## 目标

    生成一组可直接派发给研究执行 Agent 和 Judge Agent 的可验证研究课题。

    生成者只负责拟写课题，不运行实验、不写实验结论、不替后续 Agent 做验证。

    ## 基本格式

    每个课题必须使用以下结构：

    ```text
    ## 课题 N：<课题标题>

    [Agents]

    读给定材料，做实验，写结论。

    <具体实验任务、变量、对照组、训练/分析长度、记录指标、输出文件>

    ---

    [Judge (Judge IQ Requirement: low/high)]

    Look at `<结果文件>`, check whether conclusion cover the following points (最多不超过3点，每个点都必须清晰、可验证)

    1. <结果判定点 1>
    2. <结果判定点 2>
    3. <结果判定点 3>
    ```

    ## `[Agents]` 写法

    `[Agents]` 是给执行 Agent 的任务布置。

    任务文本只显式要求三件事：

    1. 读给定材料。
    2. 做实验或分析。
    3. 写结论。

    不要在任务文本里显式要求 Agent 查找资料、补充资料、联网搜索或登记材料。
    如果 Agent 自发查资料，那是 Agent 自己的行为，不应写成任务要求。

    ## 给定材料写法

    使用“给定材料”这个统称。
    不要显式提及给定材料的具体路径、材料文件名、项目内已有说明文件、既有总结、其他研究记录或其他执行者的结论。

    允许写：
    ```text
    读给定材料
    ```

    不推荐写：
    ```text
    读某个具体材料文件
    参考项目内已有说明文件
    根据已有总结
    查看其他研究记录中的结论
    ```



    ## `[Judge]` 写法

    `[Judge]` 是研究结果判定条件，不是实验执行说明。

    如果判定需要读图、理解统计显著性、比较复杂机制解释，可以提高 IQ requirement，但必须有必要性。



    ## 输出文件写法

    每个课题应指定一个结果文件，通常是：

    ```text
    ./summary_<topic>.md
    ```

    Judge 只查看该结果文件进行判定。

    不要要求 Agent 修改已有总报告、已有说明文件、已有总结或其他已有研究记录。



    ## 课题选择原则

    课题必须可验证。




    ## 自检清单

    生成任务单后，检查以下事项：

    1. 每个课题都有 `[Agents]`。
    2. 每个课题都有 `[Judge (IQ requirement: ...)]`。
    3. `[Agents]` 中只显式要求“读给定材料，做实验，写结论”。
    4. 没有显式要求 Agent 查找、补充、登记或下载材料。
    5. 没有显式提及材料文件名、已有说明文件、既有总结或其他研究记录结论。
    6. 固定实验设置写在 `[Agents]`，没有写成 Judge 判定条件。
    7. Judge 条件只检查研究结果和结论。
    8. 每个课题都有明确输出文件。
    9. 课题编号连续。
    10. 推荐顺序与删除或新增后的编号一致。
```


注意事项：
- 拓展的课题必须放在 team_bench_gen/generated_task_await_verify （因为没验证）
- 如果有材料，需要复制到对应的位置 （team_bench_gen/generated_task_await_verify/cec/cec_material），该材料必须是直接从互联网获取，未经加工的材料。
- 命名规则：
    - 课题 md: {大课题名}/{大课题名}_{编号}.md
    - 材料文件夹：{大课题名}/{大课题名}_material
    - 一个大课题的所有子课题共享material，material不嫌多
- 不得创建太过于相似的小课题
- 暂时不允许你创建新的大课题
