# ROS2 自定义消息包项目

## 项目概述

本项目为ROS2提供了一个完整的自定义消息系统，用于设备状态通信。项目包含两个主要包：

1. **custom_interfaces**：定义自定义消息类型（CMake构建）
2. **custom_nodes**：包含Python发布者和订阅者节点

## 项目结构

```
ros2_ws/
├── src/
│   ├── custom_interfaces/          # 自定义消息接口包
│   │   ├── msg/
│   │   │   └── DeviceStatus.msg    # 自定义消息定义
│   │   ├── CMakeLists.txt
│   │   └── package.xml
│   │
│   └── custom_nodes/               # Python节点包
│       ├── custom_nodes/
│       │   ├── __init__.py
|       |   ├── device_data_service.py #伪服务
│       │   ├── publisher_node.py   # 发布者节点
│       │   └── subscriber_node.py  # 订阅者节点
│       ├── resource/
│       ├── setup.py
│       ├── setup.cfg
│       └── package.xml
│
└── README.md                        # 本文件
```

## 消息定义

### DeviceStatus 消息

自定义消息 `DeviceStatus` 包含以下字段：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `device_id` | uint32 | 自定义设备ID |
| `local_mac` | string | 本机MAC地址 |
| `status` | uint8 | 设备状态（0=启动, 1=探测,2=协商, 3=维护） |
| `timestamp` | uint64 | 消息时间戳（毫秒） |
| `mac_address_a` | string | 主节点MAC地址 |
| `mac_address_b` | string | 副节点MAC地址 |

## 安装和编译

### 前置要求

- ROS2（Humble或更新版本）
- Python 3.8+
- colcon构建工具

### 编译步骤

1. **进入工作空间**

```bash
cd ros2_ws
```

2. **编译所有包**

```bash
colcon build
```

3. **设置环境变量**

```bash
source install/setup.bash
```

## 使用方法

### 测试：运行发布者节点

在第一个终端中运行发布者节点：

```bash
source install/setup.bash
ros2 run custom_nodes publisher_node
```

**预期输出：**

```
[INFO] [1780575178.482887310] [device_status_publisher]: 设备状态发布器已使用device_id初始化=[1002, 1003, 1004], 本机mac=2c:cf:67:81:0c:d9
[INFO] [1780575178.483537213] [device_status_publisher]: 设备状态发布器已使用device_id初始化=1002, mac=66:77:88:99:aa:bb
[INFO] [1780575178.484113542] [device_status_publisher]: 设备状态发布器已使用device_id初始化=1003, mac=cc:dd:ee:ff:00:11
[INFO] [1780575178.484610020] [device_status_publisher]: 设备状态发布器已使用device_id初始化=1004, mac=22:33:44:55:66:77
...
```

### 测试：运行订阅者节点

在第二个终端中运行订阅者节点：

```bash
source install/setup.bash
ros2 run custom_nodes subscriber_node
```

**预期输出：**

```
[INFO] [subscriber_node]: Device Status Subscriber initialized and waiting for messages...
[INFO] [subscriber_node]: Received message #1:
  device_id=1001
  local_mac=xx:xx:xx:xx:xx:xx
  status=0
  timestamp=1234567890000
  mac_address_a=aa:bb:cc:dd:ee:ff
  mac_address_b=11:22:33:44:55:66
[INFO] [subscriber_node]: Device 1001 is in IDLE state
...
```

## 代码说明

### 发布者节点 (publisher_node.py)

**主要功能：**

- 定期发布 `DeviceStatus` 消息
- 获取本机MAC地址
- 发送不同状态值（0, 1, 2, 3）
- 提供 `on_publish_callback()` 回调函数

**关键方法：**

| 方法名 | 说明 |
|--------|------|
| `__init__()` | 初始化发布者，创建定时器 |
| `_get_local_mac()` | 获取本机MAC地址 |
| `timer_callback()` | 定时发布消息 |
| `on_publish_callback()` | 回调函数 |
| `timer_callback()` | 定时函数 |


### 订阅者节点 (subscriber_node.py)

**主要功能：**

- 订阅 `device_status` 主题
- 接收并处理 `DeviceStatus` 消息
- 验证MAC地址格式
- 处理时间戳信息
- 跟踪消息统计信息
- 提供 `on_message_received_callback()` 回调函数

**关键方法：**

| 方法名 | 说明 |
|--------|------|
| `listener_callback()` | 消息接收回调 |
| `on_message_received_callback()` | 回调函数 |
| `_validate_mac_addresses()` | 验证MAC地址 |
| `_is_valid_mac()` | 检查MAC地址格式 |
| `_process_timestamp()` | 处理时间戳 |
| `get_statistics()` | 获取统计信息 |

## 一些告知

### 如何修改发布频率？

修改 `timer_period`：

```python
timer_period = 0.5  # 改为0.5秒发布一次
self.timer = self.create_timer(timer_period, self.timer_callback)
```

### 修改设备ID-》后续应该做入yaml文件

修改 `device_id`：

```python
self.device_id = 2001  # 改为其他ID
```

### 添加新的消息字段

1. 修改 `custom_interfaces/msg/DeviceStatus.msg`，添加新字段
2. 重新编译：`colcon build --packages-select custom_interfaces`
3. 在代码中使用新字段

### 关于调试节点

使用ROS2的日志系统(所有debug输出均在此模式才能看到)：

```bash
# 设置日志级别为DEBUG
export RCL_LOG_LEVEL=DEBUG
ros2 run custom_nodes publisher_node

# 或在运行时设置
ros2 run custom_nodes publisher_node --ros-args --log-level DEBUG
```

## 许可证

Apache License 2.0

## 联系方式

如有问题或建议，请联系项目维护者。

---

**最后更新：** 2026年6月4日
