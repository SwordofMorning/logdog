[![English](https://img.shields.io/badge/English-README-blue)](docs/README.en.md)

# MaaFramework Watchdog

一个为 MaaFramework 设计的基于日志的监控系统。

Logdog 通过实时分析日志文件来监控 MaaFramework Pipeline 的执行流程。它利用可配置的状态机来跟踪任务节点切换、检测超时，并在操作未在预期时间内完成时，通过外部通知发送警报。

## 一、功能特性

* 非侵入式监控: 通过 `debug/maa.log` 文件监控代理，无需注入进程内存。
* 复杂状态机: 支持多步状态转移，例如: `开始 -> 步骤 1 -> 步骤 2 -> 结束`。
* 超时检测: 如果特定节点或转移步骤超过了定义的阈值，自动发送警报。
* 入口节点检测: 当新的任务周期开始(入口节点)时，自动重置当前活动的状态。
* 多平台通知: 
    * Telegram Bot
    * 企业微信
* 自定义警报: 筛选触发通知的事件类型，例如: 仅在超时发生时报警。

## 二、使用源码

Python 版本要求3.8及以上。

1.  克隆仓库: 

```bash
git clone git@github.com:MaaGF1/logdog.git
# 或者
git clone https://github.com/MaaGF1/logdog.git
# 进入目录
cd logdog
```

2.  安装依赖: 

唯一的外部依赖是用于发送通知的 `requests` 库: 
```bash
pip install requests
```

## 三、配置说明

系统完全通过 `watchdog.conf` 文件进行控制。

### 3.1 通知设置

配置外部通知参数，以及设置通知过滤选项。

```ini
[Notification]
# Telegram 配置
Bot_Token=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
Chat_ID=123456789

# 企业微信配置
Webhook_Key=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# 默认平台，可用选项: 
    # telegram
    # wechat
Default_ExtNotify=wechat

# 通知过滤，定义哪些事件会触发消息发送，可用选项: 
    # StateActivated (状态激活), 
    # StateCompleted (状态完成), 
    # Timeout (超时), 
    # StateInterrupted (状态中断), 
    # EntryDetected (检测到入口)
# 如果注释掉此行，将发送所有事件。
NotifyWhen={Timeout, StateInterrupted}
```

### 3.2 监控设置

将 Watchdog 指向你的 MaaFramework 日志文件。

```ini
[Monitoring]
# MaaFramework 生成的日志文件路径
Log_File_Path=../debug/maa.log

# 轮询间隔(秒)
Monitor_Interval=1.0
```

### 3.3 状态机规则

#### 状态规则 (`[States]`)
格式: `规则名称={开始节点, 超时毫秒数, 下一节点, [超时毫秒数, 下一节点...], 描述}`

*   StartNode (开始节点): 日志中出现的、用于启动计时器的节点名称。
*   TimeoutMS (超时毫秒数): 允许到达下一个节点的时间(毫秒)。
*   NextNode (下一节点): 用于停止计时器或进入下一步的预期节点。

```ini
[States]
# 简单规则: 如果出现 'StartTask'，则 'EndTask' 必须在 30秒内出现
Simple_Task={StartTask, 30000, EndTask, "基础任务监控"}

# 复杂链条: StartNode -> (5s) -> SwitchNode1
#               (or) -> (10s) -> SwitchNode2
Complex_Flow={StartNode, 5000, SwitchNode1, 10000, SwitchNode2, "复杂流程链"}
```

#### 入口节点 (`[Entries]`)

标志着主要工作流开始的节点。当检测到此类节点时，所有 当前活动的状态/计时器都会被重置(视为被中断)。

```ini
[Entries]
# 格式: 名称={节点名, 描述}
Main_Entry={Task_Start_Node, "主任务入口点"}
```

#### 完成节点 (`[Completed]`)

明确标记规则已成功完成的节点。

```ini
[Completed]
# 格式: 名称={节点名, 描述}
Task_Done={Task_Success_Node, "任务成功完成"}
```

## 四、使用方法

### 4.1 启动 Watchdog

运行主脚本。它将阻塞并无限期地监控日志文件。

```bash
python main.py
```

### 4.2 命令行参数

* `--config <path>`: 指定自定义配置文件路径。
* `--status`: 打印状态机的当前状态并退出。
* `--detailed-status`: 打印关于活动状态、转移和计时器的详细信息。
* `--daemon`: (Linux) 在后台模式运行。

示例:

```bash
python main.py --config ./my_configs/watchdog.conf
```

## 五、How it works

1. 日志解析: `LogMonitor` 读取 `maa.log` 中的新行。它寻找类似 `[pipeline_data.name=NodeName] | enter` 的模式。
2. 状态激活: 如果检测到的节点匹配 `[States]` 中的 `StartNode`(开始节点)，则激活一个新的 `WatchdogState` 并开始计时。
3. 转移/完成: 
    * 如果目标节点在时限内出现，规则被标记为 Completed(完成)(或是移动到下一步)。
    * 如果时间限制已过，触发 Timeout(超时)事件。
4. 通知: 根据 `NotifyWhen` 的设置，`WatchdogNotifier` 向配置的平台发送警报。