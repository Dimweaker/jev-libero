# How to contribute / 如何参与开发

This page is for people who want to report bugs or change the project. **You do not need these steps just to run the demos.**

本页面向想报告问题或改进项目的人；**只是使用项目，不需要执行这些步骤。**

## Report a problem / 报告问题

Open a [GitHub issue](https://github.com/Dimweaker/jev-libero/issues) with your command, dependency versions, expected result, and the error you saw. Remove API keys and private information from any attached logs.

在 Issue 中写明运行命令、依赖版本、预期结果和实际报错。上传日志前删除密钥和私人信息。

## Change the code / 修改代码

1. Fork the repository and create a branch for your change. / Fork 仓库，为修改创建分支。
2. Make your change. Task definitions are in `src/jev_libero/tasks/`; API access is in `client.py`; simulation is in `world.py`. / 根据改动选择对应文件。
3. Run the relevant local checks below. They do not make paid API calls. / 运行与修改相关的本地检查，不调用付费 API。
4. Open a pull request (PR) explaining what changed and why. / 提交 PR，说明改了什么、解决什么问题。

```bash
pip install -e '.[dev]'
ruff check src tests tools
ruff format --check src tests tools
pytest
```

Only changes to physics/control need the additional simulator checks (`pytest --simulation`, with the robot dependencies and `LIBERO_ROOT` configured). API/documentation-only changes do not require rerunning robot episodes.

只有涉及物理或控制逻辑的修改才需要额外的仿真检查；只修改 API 接入或文档，无需重跑机器人任务。
