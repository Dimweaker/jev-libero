<div align="center">

<img src="docs/media/banner.svg" alt="Jev × LIBERO" width="960" />

**Jev 分层选择原子动作，物理前视提供可验证的候选。**

[English](README.md) · [任务配置](docs/tasks.md) · [结果与复现](docs/results.md) · [MIT](LICENSE)

</div>

## 演示

<table>
<tr><th>关闭微波炉</th><th>关闭顶层抽屉</th></tr>
<tr><td><a href="docs/media/microwave.mp4"><img src="docs/media/microwave.gif" width="360" alt="微波炉实际仿真轨迹" /></a></td><td><a href="docs/media/top-drawer.mp4"><img src="docs/media/top-drawer.gif" width="360" alt="抽屉实际仿真轨迹" /></a></td></tr>
<tr><td>14 次原子决策 · 111 环境步</td><td>20 次原子决策 · 155 环境步</td></tr>
</table>

两条轨迹均通过 LIBERO 原始成功判定。动画播放的是**仿真时间**，不包含推理与物理前视等待，不代表实时控制。抽屉任务只更换了 JSON 配置，没有手写关抽屉技能。

## 核心设计

- **27 个原子输入**：世界坐标平移、旋转、开爪、合爪和保持。
- **真正串行的分层选择**：意图 → 接触/运动方式 → 一个原子输入；下层接收上层的选择。
- **可逆物理前视**：保存完整物理与控制器快照，模拟候选输入，再恢复原状态。
- **任务配置化**：对象、进展公式、接触规则、局部目标、提示、信息投影和评价条件均由 JSON 加载。
- **可检查的证据**：提供请求、响应、费用、预测、实际控制、状态数组，也保留失败记录。

物理计算和筛选由代码、FCL 与 MuJoCo 完成，Jev 在可行候选中选择。不能把求解器的计算全部归功于 Jev。两步前视只提供后续可行输入的见证，**不会自动执行两步序列**。

## 快速开始

推荐 Linux x86-64、Python 3.10。

```bash
git clone https://github.com/Dimweaker/jev-libero.git
cd jev-libero
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .

# 不需要 API Key 或仿真器即可查看记录
jev-libero tasks
jev-libero inspect examples/records/top_drawer_seed1
```

安装仿真依赖和固定版本 LIBERO：

```bash
pip install torch==2.2.0 --index-url https://download.pytorch.org/whl/cpu
pip install -e '.[robot]'
git clone https://github.com/Lifelong-Robot-Learning/LIBERO.git ../LIBERO
git -C ../LIBERO checkout 8f1084e3132a39270c3a13ebe37270a43ece2a01
export LIBERO_ROOT="$(cd ../LIBERO && pwd)"
export MUJOCO_GL=egl

# 独立回放保存的控制指令，不调用模型
jev-libero replay examples/records/top_drawer_seed1
```

无需下载示范数据集，也不修改 LIBERO 源码或 `~/.libero`。渲染需要可用的 EGL；更多依赖说明见 [安装文档](docs/setup.md)。

运行新的付费模型闭环：

```bash
export OPENROUTER_API_KEY_FILE=/path/to/private/openrouter.key
# 也可设置 OPENROUTER_API_KEY 环境变量，不要把密钥提交到 Git。

jev-libero run --task microwave --seed 1 --init-state 0 \
  --out runs/microwave-s1 --max-decisions 100 --budget-usd 0.10

jev-libero run --task top_drawer --seed 1 --init-state 0 \
  --out runs/drawer-s1 --max-decisions 100 --budget-usd 0.10
```

需要 OpenRouter 上 `typesafe/jev-1.13` Decisions API 的访问权限。费用保护依据返回的实际费用在下次调用前检查，不是服务商侧的硬账单上限。输出目录必须是新目录。`--no-render` 可禁用图像输出，但仍保存控制与状态。

## 已记录结果

|任务|种子|结果|原子决策|环境步|
|---|---:|---|---:|---:|
|微波炉|1|成功|14|111|
|微波炉|2|失败|75|600|
|微波炉|3|成功|53|417|
|顶层抽屉|1|成功|20|155|

这四轮均使用初态索引 0；种子仍可能改变固定物体的布局，也不控制远端 Jev 的随机性。**微波炉 2/3、抽屉 1/1 只是少量试验结果，不是稳定成功率。** 失败轮最终停在约 28.33°，当前短时目标条件无法找到合格的恢复动作。

公开记录的 API 费用合计约 **$0.012707**，不含计算成本。软件整理后，对全部 **311 次历史请求与选择** 做了等价性检查；控制轨迹也可在固定仿真栈中逐步回放验证。

## 当前边界

使用完整仿真状态，不是纯视觉策略，不适用于直接部署到真实机器人。只支持单个活动目标；一般抓放、多物体长流程、开关等模型状态变更尚未实现。接触筛选也不是连续时间或全机械臂安全保证。

仿真会在前视和 API 调用期间暂停。抽屉演示为 7.75 秒仿真时间，原运行壁钟约 131 秒。

## 开发

```bash
pip install -e '.[dev]'
ruff check src tests tools
ruff format --check src tests tools
pytest
pytest --simulation  # 需 robot 依赖与 LIBERO_ROOT，不调用付费 API
```

详见 [贡献指南](CONTRIBUTING.md)、[任务配置](docs/tasks.md) 和 [第三方致谢](THIRD_PARTY.md)。
