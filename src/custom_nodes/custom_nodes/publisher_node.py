#!/usr/bin/env python3
"""
设备状态消息发布节点

此节点将自定义设备状态消息发布到“device_status”主题。
它包含一个回调函数，该函数可通过自定义逻辑进行扩展。
"""

import rclpy
from rclpy.node import Node
from custom_interfaces.msg import DeviceStatus
import time
import uuid
import socket


class DeviceStatusPublisher(Node):
    """
    一个发布设备状态消息的ROS2节点。
    此发布器发送包含以下内容的自定义设备状态消息：
    - device_id：唯一设备标识符
    - local_mac：本地机器的MAC地址
    - status：当前设备状态（0、1、2、3）
    - 时间戳：消息时间戳
    - mac_address_a：保留的MAC地址A
    - mac_address_b：保留的MAC地址
    """

    def __init__(self):
        """初始化发布者节点。"""
        super().__init__('device_status_publisher')
        
        # 创建发布者
        self.publisher_ = self.create_publisher(
            DeviceStatus,
            'device_status',
            10
        )
        
        # 设备配置
        self.device_id = [1002,1003,1004]
        self.de_mac ={1002:'11:77:88:99:aa:bb',1003:'11:dd:ee:ff:00:11',1004:'11:33:44:55:66:77'}
        self.local_mac = self._get_local_mac()
        self.status_counter = 0
        
        self.get_logger().info(
            f'设备状态发布器已使用device_id初始化={self.device_id}, '
            f'本机mac={self.local_mac}'
        )


        msg = DeviceStatus()
        
        # 设置消息字段
        for i in self.device_id:
            msg.device_id = i
            msg.local_mac = self.de_mac[i]
            msg.status = self.status_counter  #0、1、2
            msg.timestamp = int(time.time() * 1000)  # 时间戳（毫秒）
            msg.mac_address_a = 'aa:bb:cc:dd:ee:ff'  # Reserved MAC A
            msg.mac_address_b = '11:22:33:44:55:66'  # Reserved MAC B
            self.get_logger().info(
            f'设备状态发布器已使用device_id初始化={i}, '
            f'mac={self.de_mac[i]}'
            )
            # 发布消息
            self.publisher_.publish(msg)
            # 定时器用于定期发布（间隔10秒）
            # timer_period = 5.0
            # self.timer = self.create_timer(timer_period, self.timer_callback)




    def _get_local_mac(self) -> str:
        """
        获取本地计算机的MAC地址。
        返回：
            str：格式为“xx:xx:xx:xx:xx:xx”的MAC地址
        """
        try:
            mac = uuid.UUID(int=uuid.getnode()).hex[-12:]
            return ':'.join(mac[i:i+2] for i in range(0, 12, 2))
        except Exception as e:
            self.get_logger().warn(f'无法获取MAC地址: {e}')
            return '00:00:00:00:00:00'

    def timer_callback(self):
        """
        发布设备状态消息的定时器回调函数。
        此函数会定期调用，并发布一条新的DeviceStatus消息。
        状态在0、1、2和3这四个值之间循环。
        """
        msg = DeviceStatus()
        
        # 设置消息字段
        msg.device_id = self.device_id
        msg.local_mac = self.local_mac
        msg.status = self.status_counter  #0、1、2、3
        msg.timestamp = int(time.time() * 1000)  # 时间戳（毫秒）
        msg.mac_address_a = 'aa:bb:cc:dd:ee:ff'  # Reserved MAC A
        msg.mac_address_b = '11:22:33:44:55:66'  # Reserved MAC B
        
        # 发布消息
        self.publisher_.publish(msg)
        
        # 调用自定义回调
        # self.on_publish_callback(msg)
        
        # self.status_counter += 1

    # def on_publish_callback(self, msg: DeviceStatus):
    #     """
    #     发布消息后调用的自定义回调函数。
    #     此函数专为自定义逻辑预留，可进行扩展
    #     在消息发布时执行额外操作。
    #     参数：
    #         msg (DeviceStatus)：已发布的消息
    #     """
    #     self.get_logger().info(
    #         f'Published - device_id={msg.device_id}, status={msg.status}, '
    #         f'timestamp={msg.timestamp}'
    #     )
        
        #  TODO: 在此处添加自定义回调逻辑
        # 示例：记录到数据库，根据状态触发操作等。


def main(args=None):
    """发布者节点的主入口点。"""
    rclpy.init(args=args)
    node = DeviceStatusPublisher()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
