# Monoplanner 演示脚本 / Monoplanner Demo Script

## 录制准备 / Recording setup

- 目标时长：5 分 30 秒。最终录制请控制在 8 分钟以内。 / Target duration: 5 minutes 30 seconds. Keep the final recording below 8 minutes.
- 全程保持摄像头画面可见，但不要遮挡导航、提示词或结果数值。 / Keep the webcam visible throughout without covering navigation, prompts, or result values.
- 使用一个已准备好的项目，其中需求、资产和提示词包均已完成。不要等待实时模型调用。 / Use a prepared project with completed requirements, assets, and prompt packs. Do not wait for a live model call.
- 调整浏览器缩放比例，确保需求、前端提示词和后端提示词均清晰可读。 / Set browser zoom so the requirement, frontend prompt, and backend prompt are readable.
- 录制前打开以下标签页：Monoplanner 项目、`PRODUCT_DOCUMENTATION.md`、`data/README.md`、`evals/README.md` 和 `results/README.md`。 / Open these tabs before recording: Monoplanner project, `PRODUCT_DOCUMENTATION.md`, `data/README.md`, `evals/README.md`, and `results/README.md`.
- 关闭通知，并隐藏可能暴露凭据的终端或文件。 / Disable notifications and hide terminals or files that could expose credentials.

## 0:00 至 0:35 问题与贡献 / 0:00 to 0:35 Problem and contribution

**画面 / Screen：** 展示 Monoplanner 项目页面，并保持摄像头叠加画面可见。 / Show the Monoplanner project page with the webcam overlay visible.

**旁白 / Narration：**

大家好，我是李凌昊。Monoplanner 要解决 AI 辅助全栈开发中的一种特定失效模式：当需求发生变化时，团队往往分别重写前端和后端提示词。字段类型、验证限制、权限、分页和错误等共享规则因此可能出现偏差。Monoplanner 存储持续演化的项目上下文，并基于同一次变更生成带版本的前端和后端提示词包。我的最终评估直接衡量这种同步性，而不是将代码质量或构建成功作为替代指标。

Hello, I am Li Linghao. Monoplanner addresses a specific failure mode in AI-assisted full-stack development. When a requirement changes, teams often rewrite frontend and backend prompts separately. Shared rules such as field types, validation limits, permissions, pagination, and errors can then diverge. Monoplanner stores the evolving project context and generates a versioned frontend and backend prompt pack from the same change. My final evaluation measures that synchronization directly rather than using code quality or build success as a proxy.

## 0:35 至 1:15 产品架构 / 0:35 to 1:15 Product architecture

**画面 / Screen：** 打开 `PRODUCT_DOCUMENTATION.md` 中的架构图，在提到每个方框时指向它。 / Open the architecture diagram in `PRODUCT_DOCUMENTATION.md` and point to each box as it is mentioned.

**旁白 / Narration：**

Next.js 界面会向 FastAPI 服务发送请求。生成任务记录在 PostgreSQL 中，并由后台工作进程领取，因此耗时较长的模型调用不会阻塞 API。工作进程将结构化提示词发送给兼容 OpenAI 的模型，验证响应，并存储带版本的需求、变更集、设计资产和提示词包。我负责这套编排、持久化、验证、队列和评估代码；我仅租用模型推理服务。评估运行器调用相同的提示词包核心逻辑，但不进行数据库缓存查询，从而保持实验单元相互隔离。

The Next.js interface sends requests to a FastAPI service. Generation work is recorded in PostgreSQL and claimed by a background worker, so long model calls do not block the API. The worker sends structured prompts to an OpenAI-compatible model, validates the response, and stores versioned requirements, change sets, design assets, and prompt packs. I own this orchestration, persistence, validation, queue, and evaluation code. I rent only model inference. The evaluation runner calls the same prompt-pack core without database cache lookup, which keeps experimental units isolated.

## 1:15 至 3:15 从需求到提示词包 / 1:15 to 3:15 Requirement to prompt pack

**画面 / Screen：** 回到准备好的项目。打开需求历史记录，然后打开选定的业务故事。 / Return to the prepared project. Open the requirement history, then the selected business story.

**旁白 / Narration：**

该项目会保留原始需求及后续修订，而不是替换历史记录。我选择代表这次变更的业务故事，并在执行前检查其范围。

This project keeps the original requirement and later revisions instead of replacing the history. I select the business story that represents the change and inspect its scope before execution.

**画面 / Screen：** 打开关联的变更集，并滚动查看受影响的层。 / Open the associated change set and scroll through the affected layers.

**旁白 / Narration：**

变更集识别出哪些产品层必须发生变化。这样就将请求的变更与生成的资产版本分开，并使转换过程可供审查。

The change set identifies which product layers must change. This separates the requested change from the generated asset versions and makes the transition reviewable.

**画面 / Screen：** 打开一个 API 或数据库资产，然后打开前端和后端实现资产。简要展示当前版本标识和历史记录。 / Open one API or database asset, then the frontend and backend implementation assets. Show the current version indicator and history briefly.

**旁白 / Narration：**

每个受影响的层都会成为带版本的资产。上一版本仍然可用，而当前版本会成为下一次变更的上下文。这能防止提示词生成器只依赖用户最新的一句话。

Each affected layer becomes a versioned asset. The previous version remains available, while the current version becomes context for the next change. This prevents the prompt generator from relying only on the latest sentence from the user.

**画面 / Screen：** 打开提示词包页面。将前端和后端指令同时置于画面中，并高亮一项共享契约事实。 / Open the prompt-pack page. Place the frontend and backend instructions in view and highlight one shared contract fact.

**旁白 / Narration：**

最终提示词包包含分别面向前端和后端编码代理的实现指令。两个提示词都会获得相同的当前契约，但也可以包含各自一侧特有的职责。核心审查问题很简单：对于同一个操作和状态，这两个提示词是否陈述了无法同时成立的事实？它们是否明确覆盖了每一项必需的共享事实？

The final prompt pack contains separate implementation instructions for frontend and backend coding agents. Both prompts receive the same current contract, but each prompt can also include responsibilities specific to its side. The key review question is simple: for the same operation and state, do the two prompts state facts that cannot both be true, and have they explicitly covered every required shared fact?

## 3:15 至 4:45 数据评估与结果 / 3:15 to 4:45 Data evaluation and results

**画面 / Screen：** 打开 `data/README.md` 并展示数据集表格，然后打开 `evals/README.md` 及其指标定义。 / Open `data/README.md`, show the dataset table, then open `evals/README.md` and its metric definitions.

**旁白 / Narration：**

该仓库提交了数据、评估代码、模型请求、原始响应、审查证据和报告。数据集包含十条需求链，每条都有三次连续变更，并以一个固定版本的公开全栈仓库为基础。第一次评估使用了八条留出链、两种方法和 48 个提示词包。人工审查覆盖了 688 项事实判断。严格成功率仅为 27.08%，遗漏率为 39.68%，并观察到两处矛盾。

这一结果暴露了我在测量设计中的问题。评分器期待模型输入中并不总是存在的历史契约事实。我修订了数据模型，将当前变更的事实与活动契约分离，并为每项事实指定了适用性和覆盖要求。

The repository checks in the data, evaluation code, model requests, raw responses, review evidence, and reports. The dataset contains ten requirement chains with three consecutive changes each, grounded in a pinned public full-stack repository. The first evaluation used eight held-out chains, two methods, and 48 prompt packs. Human review covered 688 fact judgments. Strict success was only 27.08 percent, with a 39.68 percent omission rate and two observed contradictions.

That result exposed a problem in my measurement design. The scorer expected historical contract facts that were not always present in the model input. I revised the data model to separate facts changed now from the active contract, and I assigned applicability and coverage requirements to each fact.

**画面 / Screen：** 打开 `results/README.md`，先指向 v2.1 行，再指向 v2.2 行。 / Open `results/README.md` and point to the v2.1 row and then the v2.2 row.

**旁白 / Narration：**

经过细化的 v2.1 试点评估了 12 个提示词包和 82 项事实。结构、标记和精确陈述覆盖率均为 100%。人工语义覆盖率达到 98.78%，总体严格成功率达到 91.67%。联合模型方法仅达到 83.33%，因为一项可选的 HTML 验证建议可能会以不同于既定契约的方式计算 Unicode 文本。随后我移除了语义上不安全的可选建议。v2.2 自动回归在结构和精确覆盖检查中达到 100%，但我没有进行另一轮人工审查，因此不主张 v2.2 的语义成功率。

The refined v2.1 pilot evaluated 12 packs and 82 facts. Structural, marker, and exact-statement coverage were 100 percent. Human semantic coverage reached 98.78 percent, and overall strict success reached 91.67 percent. The joint model method reached only 83.33 percent because one optional HTML validation suggestion could count Unicode text differently from the stated contract. I then removed semantically unsafe optional suggestions. The v2.2 automatic regression reached 100 percent on structural and exact coverage checks, but I did not perform another human review, so I do not claim a v2.2 semantic success rate.

## 4:45 至 5:30 批判与未来工作 / 4:45 to 5:30 Critique and future work

**画面 / Screen：** 回到 `PRODUCT_DOCUMENTATION.md` 中的局限性和未来路径章节。 / Return to the limitations and future-path sections in `PRODUCT_DOCUMENTATION.md`.

**旁白 / Narration：**

最有价值的成果是评估纪律，而不是证明大语言模型优于规则模板的证据。在 v2.1 中，确定性规则基线通过了每个提示词包，而联合方法没有。该研究还只使用了一个源仓库、两条经过细化的开发链、一位审查者和一次模型重复。由于数据集尚不包含人工编写的资产快照和变更集，完整的数据库支持工作流尚未得到评估。

下一步是将细化后的协议扩展到八条留出链，采用抽样或两阶段审查，增加第二位审查者，并进行重复的配对试验。Monoplanner 目前提供了可用的版本化工作流和透明证据，但其更广泛的生产力价值仍是假设，有待未来验证。谢谢。

The strongest outcome is the evaluation discipline rather than evidence that an LLM beats a rule template. In v2.1, the deterministic rule baseline passed every pack, while the joint method did not. The study also uses one source repository, two refined development chains, one reviewer, and one model repetition. The complete database-backed workflow was not evaluated because the dataset does not yet contain authored asset snapshots and change sets.

The next step is to extend the refined protocol to the eight held-out chains, use sampled or two-stage review, add a second reviewer, and run repeated paired trials. Monoplanner now provides a working versioned workflow and transparent evidence, but its broader productivity value remains a hypothesis for future testing. Thank you.

## 无网络备选方案 / No network fallback

如果应用程序或模型提供方在录制期间不可用，请不要在镜头前重试。展示准备好的截图或已完成的项目页面，然后使用已提交的 `PRODUCT_DOCUMENTATION.md`、`results/README.md`、v2.1 报告 JSON 和录制的提示词包输出。说明该演示使用的是已完成运行的录制证据。

If the application or model provider is unavailable during recording, do not retry on camera. Show the prepared screenshots or completed project pages, then use the checked-in `PRODUCT_DOCUMENTATION.md`, `results/README.md`, v2.1 report JSON, and recorded prompt-pack outputs. State that the demo uses recorded evidence from the completed run.

## 最终录制检查 / Final recording check

- 人脸和屏幕均清晰可见。 / Face and screen are both visible.
- 不显示 API 密钥、`.env`、用户邮箱或数据库凭据。 / No API key, `.env`, user email, or database credential appears.
- 音频清晰，指针跟随旁白移动。 / The audio is clear and the pointer follows the narration.
- 视频演示一次需求变更以及提示词的前后端两侧。 / The video demonstrates one requirement change and both prompt sides.
- 指标声明与已提交的报告相符。 / Metric claims match the checked-in reports.
- 录制时长在 4 至 8 分钟之间。 / The recording is between 4 and 8 minutes.
