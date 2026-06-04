#!/usr/bin/env python3
"""
设备状态消息的订阅节点

此节点订阅来自“device_status”主题的设备状态消息。
它包含一个回调函数，该函数可通过自定义逻辑进行扩展
"""

import rclpy
from rclpy.node import Node
from custom_interfaces.msg import DeviceStatus


class DeviceStatusSubscriber(Node):
    """
    一个订阅设备状态消息的ROS2节点。

    此订阅者监听“device_status”主题并进行处理
    接收到的设备状态消息，包含设备信息、状态，
    以及MAC地址。
    """

    def __init__(self):
        """初始化订阅者节点"""
        super().__init__('device_status_subscriber')
        
        # 创建订阅
        self.subscription = self.create_subscription(
            DeviceStatus,
            'device_status_service',
            self.listener_callback,
            10
        )
        
        # 消息计数器用于统计接收到的消息数量
        self.message_count = 0
        self.last_device_id = None
        self.status_history = {}
        
        self.get_logger().info('Device设备状态订阅者已初始化，正在等待消息...')

    def listener_callback(self, msg: DeviceStatus):
        """
        当收到新消息时调用的回调函数。

        每当接收到DeviceStatus消息时，就会调用此函数
        在“device_status”主题上。它处理消息并调用
        自定义回调函数。
        
        参数：
            msg (DeviceStatus)：收到的DeviceStatus消息
        """
        self.message_count += 1
        self.last_device_id = msg.device_id
        
        # 跟踪状态历史
        if msg.device_id not in self.status_history:
            self.status_history[msg.device_id] = []
        self.status_history[msg.device_id].append(msg.status)
        
        # 记录接收到的消息
        self.get_logger().info(
            f'设备信息 #{self.message_count}:\n'
            f'  设备id={msg.device_id}\n'
            f'  本地mac={msg.local_mac}\n'
            f'  状态={msg.status}\n'
            f'  时间={msg.timestamp}\n'
            f'  A主机mac={msg.mac_address_a}\n'
            f'  B主机mac={msg.mac_address_b}'
        )
        
        # 调用自定义回调
        self.on_message_received_callback(msg)

    def on_message_received_callback(self, msg: DeviceStatus):
        """
        在接收到消息后调用的自定义回调函数。
        此函数专为自定义逻辑预留，可进行扩展
        在收到消息时执行其他操作。
        参数：
            msg (DeviceStatus)：接收到的消息
        """
        # TODO: 在此处添加自定义回调逻辑
        # 示例实现：

        #1. 基于状态的动作
        if msg.status == 0:
            self.get_logger().info(f'Device {msg.device_id} 处于探查状态')
        elif msg.status == 1:
            self.get_logger().info(f'Device {msg.device_id} 处于协商状态')
        elif msg.status == 2:
            self.get_logger().info(f'Device {msg.device_id} 处于维护状态')
        
        # 2. MAC地址验证
        self._validate_mac_addresses(msg)
        
        # 3. 时间戳处理
        # self._process_timestamp(msg)

    def _validate_mac_addresses(self, msg: DeviceStatus):
        """
        验证并处理来自消息的MAC地址。
        参数：
            msg (DeviceStatus)：包含MAC地址的消息
        """
        # TODO: 在此处添加MAC地址验证逻辑
        # 示例：检查MAC地址是否为有效格式
        mac_addresses = [msg.local_mac, msg.mac_address_a, msg.mac_address_b]
        for mac in mac_addresses:
            if not self._is_valid_mac(mac):
                self.get_logger().warn(f'Invalid MAC address format: {mac}')

    def _is_valid_mac(self, mac: str) -> bool:
        """
        检查MAC地址是否为有效格式。
        
        参数:
            mac (str): MAC地址字符串
            
        返回:
            bool:如果有效，则为True；否则为False
        """
        import re
        pattern = r'^([0-9A-Fa-f]{2}:){5}([0-9A-Fa-f]{2})$'
        return re.match(pattern, mac) is not None

    # def _process_timestamp(self, msg: DeviceStatus):
    #     """
    #     处理来自消息的时间戳信息。
    #     参数：
    #         msg (DeviceStatus)：包含时间戳的消息
    #     """
        
    #     # TODO：在此处添加时间戳处理逻辑
    #     # 示例：转换为人类可读的格式，计算延迟等。
    #     from datetime import datetime
    #     timestamp_sec = msg.timestamp / 1000.0  # 从毫秒转换为秒
    #     dt = datetime.fromtimestamp(timestamp_sec)
    #     self.get_logger().debug(f'消息时间戳:{dt.isoformat()}')

    def get_statistics(self):
        """
        获取订阅用户统计数据。
        
        返回：
            dict：包含订阅者统计信息的字典
        """
        return {
            'total_messages': self.message_count,
            'last_device_id': self.last_device_id,
            'tracked_devices': len(self.status_history),
            'status_history': self.status_history
        }


def main(args=None):
    """订阅者节点的主入口点"""
    rclpy.init(args=args)
    node = DeviceStatusSubscriber()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # 打印最终统计信息
        stats = node.get_statistics()
        node.get_logger().info(
            f'订阅者统计:\n'
            f'  接收到的消息总数: {stats["total_messages"]}\n'
            f'  跟踪的设备数: {stats["tracked_devices"]}'
        )
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
