#!/usr/bin/env python3
"""
设备数据服务节点
此服务节点：
1. 订阅device_status主题并记录设备数据
2. 提供发布设备状态消息的功能
3. 包含用于自定义处理的回调钩子
4. 将设备数据存储在内存中，并附带时间戳跟踪功能
5. 向外部URL发送HTTP POST请求
"""

import rclpy
from rclpy.node import Node
from custom_interfaces.msg import DeviceStatus
import time
from datetime import datetime
import json
import os
import uuid
import requests
from threading import Thread
import random

class DeviceDataService(Node):
    """
    一个管理设备状态数据的ROS2服务节点。
    特点：
    - 订阅device_status主题
    - 记录并存储设备数据
    - 发布设备状态消息
    - 数据处理的自定义回调钩子
    - 数据持久化到JSON文件
    - 向外部URL发送HTTP POST请求
    """

    def __init__(self):
        """初始化设备数据服务节点"""
        super().__init__('device_data_service')
        
        # 声明HTTP配置参数
        self.declare_parameter('post_url', '')
        self.declare_parameter('enable_http_post', False)
        self.declare_parameter('post_timeout', 5)
        
        # 获取参数
        self.post_url = self.get_parameter('post_url').value
        self.enable_http_post = self.get_parameter('enable_http_post').value
        self.post_timeout = self.get_parameter('post_timeout').value

        # 数据存储
        self.device_records = {}  # {device_id: [records]}
        self.total_records = 0
        self.data_file = 'device_data.json'
        self.restart_file = "device_restart.json" # 记录上次信息的文件路径

        if os.path.exists(self.restart_file):
            self.get_logger().info("restart文件存在")
            with open(self.restart_file, 'r') as f:
                self.device_id = json.load(f)  # 从文件中加载设备ID
                self.get_logger().info(f'从文件加载设备ID: {self.device_id}')
        else:
            self.get_logger().info("restart文件不存在")
            self.device_id = random.randint(1000, 9999)  # 设备ID
            self.save_data_to_file(filename='device_restart.json', data=self.device_id) # 初始化时保存id到文件

        # self.device_id = random.randint(1000, 9999)  # 设备ID
        self.status = 0  # 设备状态（0、1、2、3）
        self.local_mac = self._get_local_mac()
        self.mac_address_a = '00:00:00:00:00:00'  #MAC A
        self.mac_address_b = '00:00:00:00:00:00'  #MAC B
        self.device_death = {}  # 记录死亡设备的字典


        #为device_status主题创建发布器（用于重新发布）
        self.publisher = self.create_publisher(
            DeviceStatus,
            'device_status',
            10
        )
        

        # 订阅device_status主题
        self.subscription = self.create_subscription(
            DeviceStatus,
            'device_status',
            self.device_status_callback,
            10
        )
        
        # 发布初始启动状态 status=0
        self.publish_device_status()
        self.get_logger().info('设备正在初始化...')

        
        # 统计
        self.status_count = {0: 0, 1: 0, 2: 0, 3: 0}  # 状态分布
        # HTTP请求统计
        self.http_post_count = 0
        self.http_error_count = 0

        # 输出HTTP POST配置状态
        if self.enable_http_post and self.post_url:
            self.get_logger().info(f'启用HTTP POST: {self.post_url}')
        else:
            self.get_logger().info('HTTP POST已禁用或URL未配置')
        
        self.get_logger().info('设备数据服务已初始化')
        self.get_logger().info(f'订阅device_status主题')
        self.get_logger().info(f'发布到device_status_service主题')

        #完成初始化
        # self.status = 1
        #发布消息以进行状态更新
        # self.publish_device_status()
        # self.get_logger().info('探测通告已发出，等待设备响应...')

        

    def device_status_callback(self, msg: DeviceStatus):
        """
        device_status消息的回调函数。
        这个函数：
        1. 记录设备数据
        2. 更新统计数据
        3. 发送HTTP POST请求(如果已启用)
        4. 调用自定义回调钩子
        参数：
            msg (DeviceStatus)：收到的设备状态消息
        """

        device_id = msg.device_id
        #关于冲突双方的调整
        if device_id == self.device_id and msg.local_mac != self.local_mac and self.status != 3:
            self.get_logger().warn(
                f'设备ID冲突: 收到的消息device_id={msg.device_id} '
                f'与本机device_id={self.device_id}相同，但MAC地址不同!'
            )
            self.reset() # 重置ID以避免冲突
            return  # 不记录冲突消息
        elif msg.status == -1 and msg.device_id == self.device_id and self.status == 3:
            self.get_logger().info('已忽略重置信息')
            return  # 忽略来自重置设备的重置记录消息
        
        #关于非冲突双方的调整
        if msg.status == -1 and self.status != 3:
            self.get_logger().warn(
                f'设备 {msg.device_id} 请求重置，正在清除相关记录...'
            )
            if msg.device_id in self.device_records:
                del self.device_records[msg.device_id]  # 删除相关记录
            # if msg.loacl_mac in self.device_death:
                # del self.device_death[msg.local_mac]  # 从死亡列表中移除设备ID
            return  # 不记录重置请求
            
        # 记录消息
        self._record_device_data(msg)
        
        # 更新统计信息
        self._update_statistics(msg)

        # 记录接收到的数据
        self.get_logger().info(
            f'记录设备 {msg.device_id}: 状态={msg.status}, '
            f'mac={msg.local_mac}, 时间戳={msg.timestamp}'
        )
        
        # 调用自定义回调
        self.on_device_data_received(msg)


    def _send_http_post(self):
        """
        向配置的URL发送包含设备数据的HTTP POST请求。
        此函数在后台线程中运行，以避免阻塞
        ROS2回调。

        参数：
            msg (DeviceStatus)：要发送的设备状态消息
        """
        try:
            device_id_mac = {}
            device_id_status = {}
            # 准备要发送的数据
            for i in self.device_records.keys():
                device_id_mac[i] = self.device_records[i][-1]['设备mac']  # 获取每个设备的最新MAC地址
                device_id_status[i] = self.device_records[i][-1]['设备状态']  # 获取每个设备的最新状态

            data = {
                'device_id': self.device_id,
                'local_mac': self.local_mac,
                'status': self.status,
                'timestamp': int(time.time() * 1000),
                'mac_address_a': self.mac_address_a,
                'mac_address_b': self.mac_address_b,
                'device_records': list(self.device_records.keys()),  # 发送当前记录的设备列表
                'device_id:mac': device_id_mac,  # 发送当前记录的设备id与MAC地址对照表
                'device_id_status': device_id_status,  # 发送当前记录的设备id与状态对照表
                'received_at': datetime.now().isoformat(),
                'device_death': list(self.device_death.keys()),  # 发送当前记录的死亡设备列表
            }
            
            # 发送POST请求
            response = requests.post(
                self.post_url,
                json=data,
                timeout=self.post_timeout,
                headers={'Content-Type': 'application/json'}
            )
            
            # 检查响应状态
            if response.status_code == 200:
                self.http_post_count += 1
                self.get_logger().debug(
                    f'HTTP POST 成功: {self.post_url} '
                    f'(device_id={self.device_id})'
                )
            else:
                self.http_error_count += 1
                self.get_logger().warn(
                    f'HTTP POST 请求失败，返回状态码 {response.status_code}: '
                    f'{self.post_url}'
                )
                
        except requests.exceptions.Timeout:
            self.http_error_count += 1
            self.get_logger().error(
                f'HTTP POST 超时: {self.post_url} '
                f'(timeout={self.post_timeout}s)'
            )
        except requests.exceptions.ConnectionError as e:
            self.http_error_count += 1
            self.get_logger().error(
                f'HTTP POST 连接错误: {self.post_url} - {str(e)}'
            )
        except Exception as e:
            self.http_error_count += 1
            self.get_logger().error(
                f'HTTP POST 错误: {self.post_url} - {str(e)}'
            )

    def set_post_url(self, url: str, enable: bool = True):
        """
        设置HTTP POST URL并启用/禁用发布功能。
        参数：
            url (str): 用于发送POST请求的URL
            enable (bool): 是否启用HTTP发布
        """
        self.post_url = url
        self.enable_http_post = enable
        
        if enable:
            self.get_logger().info(f'HTTP POST enabled: {url}')
        else:
            self.get_logger().info(f'HTTP POST disabled')

        
    def reset(self):
        """
        重置设备数据服务的状态和记录。
        此函数可用于处理设备ID冲突或其他需要重置服务状态的情况。
        """
        self.status = -1  # 设置为-1表示重置状态
        self.publish_device_status()  # 发布重置状态以通知其他设备

        del self.device_records[self.device_id] #清除当前设备ID的记录

        self.get_logger().warn('正在重置设备数据服务状态...')
        self.device_id = random.randint(1000, 9999)  # 生成新的随机设备ID

        self.save_data_to_file(filename='device_restart.json', data=self.device_id) # 初始化时保存id到文件

        self.publish_device_status()  # 发布重置后的状态以通知其他设备，以进行-1状态的记录
        self.status = 0  # 重置状态
        self.publish_device_status()  # 发布重置后的状态以通知其他设备
        self.get_logger().info(f'设备数据服务已重置，新的设备ID: {self.device_id}')

    def _record_device_data(self, msg: DeviceStatus):
        """
        将设备数据记录到内存中(这里是记录数据，然后调用保存函数最开始是在关机时)
        
        参数：
            msg (DeviceStatus)：要记录的设备状态消息
        """
        device_id = msg.device_id

        # 若设备记录列表不存在，则初始化该列表
        if device_id not in self.device_records:
            self.device_records[device_id] = []
        
        # 创建记录字典
        record = {
            '设备id': msg.device_id,
            '设备mac': msg.local_mac,
            '设备状态': msg.status,
            '时间戳': msg.timestamp,
            'mac_address_a': msg.mac_address_a,
            'mac_address_b': msg.mac_address_b,
            '记录时间': datetime.now().isoformat(),
        }

        if msg.local_mac in self.device_death:
            self.get_logger().info(f'设备 {device_id} 已重新上线，移除死亡字典中的记录')
            # self.device_death.remove(device_id)  # 从死亡列表中移除设备ID
            del self.device_death[msg.local_mac]  # 删除相关记录
        

        if msg.status == 0 and msg.local_mac != self.local_mac: #0是给新设备发，1是给reset过的设备发
            self.get_logger().info(f'发现新设备,给予信息供应,设备mac: {msg.local_mac}, 本机mac: {self.local_mac}')
            self.publish_device_status() # 发布当前状态通告给新入机器(如果发现)
        
        # 添加记录
        self.device_records[device_id].append(record)
        self.total_records += 1

        #检索某设备信息，超过五条清除最后一条
        if len(self.device_records[device_id]) > 5:
            self.device_records[device_id].pop(0)

        self.save_data_to_file() # 每次记录后保存数据到文件

    def _update_statistics(self, msg: DeviceStatus):
        """
        根据收到的消息更新统计数据。
        参数：
            msg (DeviceStatus)：设备状态消息
        """
        if msg.status in self.status_count:
            self.status_count[msg.status] += 1

    def on_device_data_received(self, msg: DeviceStatus):
        """
        自定义回调函数，当收到设备数据时调用。

        此函数保留用于自定义处理逻辑。

        参数:
            msg (DeviceStatus): 收到的设备状态消息
        """
        # TODO：在此处添加自定义回调逻辑
        # 示例：
        # - 对特定状态值进行警报
        # - 触发外部操作
        # - 进行数据验证
        # - 发送通知
        
        # 示例：错误状态时发出警报
        if msg.status >= 4:
            self.get_logger().warn(
                f'设备 {msg.device_id} 状态错误!'
            )
        
        # case msg.status:
        #     case 0:
        #         self.get_logger().info(f'设备 {msg.device_id} 处于启动状态')
        #     case 1:
        #         self.get_logger().info(f'设备 {msg.device_id} 处于探查状态')
        #     case 2:
        #         self.get_logger().info(f'设备 {msg.device_id} 处于协商状态')
        #     case 3:
        #         self.get_logger().info(f'设备 {msg.device_id} 处于维护状态')
        
        self.status_choose(self.status,msg)


    def status_choose(self, status: int, msg: DeviceStatus):
        """
        根据状态处理订阅的信息(满足构建条件后(设备数量大于4))
        """
        match status:
            case 0:
                self.status = 1  # 更新状态为1，表示已完成启动阶段
                self.publish_device_status()
                self.get_logger().info('探测通告已发出，等待设备响应...')
                return '启动'
            case 1:
                #状态设置
                if msg.status == 3:
                    self.get_logger().info(f'设备 {msg.device_id} 已进入维护状态，记录协商结果...')
                    self.status = 3  # 更新状态为3，表示已完成协商阶段
                    self.mac_address_a = msg.mac_address_a  # 更新MAC A
                    self.mac_address_b = msg.mac_address_b  # 更新MAC B
                    self.publish_device_status() # 发布已完成协商通告
                    timer_period = 10.0
                    self.timer = self.create_timer(timer_period, self.timer_callback) #10s检测一次状态
                elif len(self.device_records) >= 4:
                    self.status = 2
                else:
                    self.get_logger().info('等待设备触发协商...')
                # self.publish_device_status() # 发布已经完成探测通告
                # self.get_logger().info('探测通告已发出，等待设备响应...')
                return '探查'
            case 2:
                
                self.get_logger().info('已记录4台设备，触发协商')
                device_list = list(self.device_records.keys())
                self.get_logger().info(f'当前设备列表: {device_list}')
                self.get_logger().debug(f'cs: {list(self.device_records.values())}')

                device_mac = list(sorted(list(self.device_records.values()), key=lambda x: x[-1]['设备mac'], reverse=True))
                self.get_logger().debug(f'当前设备mac地址列表(排序完成): {device_mac}')

                self.mac_address_a = device_mac[0][-1]['设备mac']  # 选择第一个设备的MAC地址作为MAC A
                self.mac_address_b = device_mac[1][-1]['设备mac']  # 选择第二个设备的MAC地址作为MAC B

                self.status = 3
                self.publish_device_status() # 发布已完成协商通告
                timer_period = 10.0
                self.timer = self.create_timer(timer_period, self.timer_callback) #10s检测一次状态
                
                return '协商'
            case 3:
                if msg.status == 0:
                    self.publish_device_status() # 发布当前状态通告给新入机器
                if self.local_mac == self.mac_address_a:
                    self.get_logger().info('本机被选为主服务器，进入维护状态,开启服务端口...')
                elif self.local_mac == self.mac_address_b:
                    self.get_logger().info('本机被选为备服务器，进入维护状态')
                else:
                    self.get_logger().info('本机未被选中，进入维护状态')
                return '维护'
            case _:
                return '未知状态'

            
    def timer_callback(self):
        """
        定时器回调函数，用于定期检查设备状态。
        目前预留用于维护状态的定期检查。
        """



        self.get_logger().info('定时器触发: 检查设备状态...')
        self.publish_device_status()
        for i in self.device_records:
            # self.get_logger().info(f'设备 {i} 的最新记录: {self.device_records[i][-1]}')
            timestamp = int(time.time() * 1000)
            if timestamp - self.device_records[i][-1]['时间戳'] > 15000 and self.device_records[i][-1]['设备mac'] not in self.device_death:  # 15秒未更新
                self.get_logger().warn(f'设备 {i} 已超过15秒未更新状态!')
                # self.device_death.append(i)  # 将设备ID添加到死亡设备列表
                self.device_death[self.device_records[i][-1]['设备mac']] = i
        #注意异常处理顺序(设备不足处理>副服务器挂起处理>主服务器挂起处理)(不能先处理主，以防副服务器挂起而被设为主服务器从而延长处理时间)
        if len(self.device_records) - len(self.device_death) > 1 and self.status == 3:  # 如果剩余设备少于2台且处于维护状态

            if self.mac_address_b in self.device_death:
                self.get_logger().warn(f'副服务器挂起，正在进行恢复处理...')
                mac_b = list(sorted(list(self.device_records.values()), key=lambda x: x[-1]['设备mac'], reverse=True))  # 选择最大的设备MAC地址作为新的备服务器
                for i in mac_b:
                    if i[-1]['设备mac'] != self.mac_address_a and i[-1]['设备mac'] not in self.device_death:
                        self.mac_address_b = i[-1]['设备mac']
                        break

            if self.mac_address_a in self.device_death:
                self.get_logger().warn(f'主服务器挂起，正在进行恢复处理...')
                self.mac_address_a = self.mac_address_b  # 将备服务器提升为主服务器
                mac_b = list(sorted(list(self.device_records.values()), key=lambda x: x[-1]['设备mac'], reverse=True))  # 选择最大的设备MAC地址作为新的备服务器
                for i in mac_b:
                    if i[-1]['设备mac'] != self.mac_address_a and i[-1]['设备mac'] not in self.device_death:
                        self.mac_address_b = i[-1]['设备mac']
                        break
            
            if self.mac_address_a == self.mac_address_b:
                self.get_logger().warn(f'设备数量恢复充足，重新搭建网络...')
                mac_b = list(sorted(list(self.device_records.values()), key=lambda x: x[-1]['设备mac'], reverse=True))  # 选择最大的设备MAC地址作为新的备服务器
                for i in mac_b:
                    if i[-1]['设备mac'] != self.mac_address_a and i[-1]['设备mac'] not in self.device_death:
                        self.mac_address_b = i[-1]['设备mac']
                        break
        else:
            self.get_logger().warn('设备数量不足，正在进行恢复处理...')
            self.mac_address_a = self.local_mac  # 将本机提升为主服务器
            self.mac_address_b = self.local_mac  #设为副服务器，用于后续设备足够时检测是否为恢复
            #TODO其他处理

        self.get_logger().warn('------------------------------')

        # 发送HTTP POST请求（在后台线程中执行以避免阻塞）
        if self.enable_http_post and self.post_url and self.local_mac == self.mac_address_a:  # 仅主服务器发送HTTP POST
            thread = Thread(target=self._send_http_post)
            thread.daemon = True
            thread.start()

    def publish_device_status(self):
        """
        发布设备状态消息。
        此功能允许服务发布设备状态消息
        发送到device_status_service主题。
        参数：
            device_id (int): 设备ID
            status (int): 设备状态（0、1、2、3）
            local_mac (str): 本地MAC地址
            mac_a (str): MAC地址A
            mac_b (str): MAC地址B
        """
        msg = DeviceStatus()
        msg.device_id = self.device_id
        msg.status = self.status
        msg.local_mac = self.local_mac
        msg.timestamp = int(time.time() * 1000)
        msg.mac_address_a = self.mac_address_a
        msg.mac_address_b = self.mac_address_b
        
        self.publisher.publish(msg)
        
        self.get_logger().info(
            f'发布设备状态: 设备id={self.device_id}, 状态={self.status}'
        )
        
        # 调用发布回调
        # self.on_device_status_published(msg)

    def on_device_status_published(self, msg: DeviceStatus):
        """
        消息发布时调用的自定义回调函数。
        此函数专为发布后的自定义处理逻辑预留。
        参数：
            msg (DeviceStatus)：已发布的设备状态消息
        """
        # TODO：在此处添加自定义回调逻辑
        # 示例：
        # - 记录到数据库
        # - 更新用户界面
        # - 触发工作流
        pass

    #关机后调用，用于保存数据，每次获得数据也调用
    def save_data_to_file(self, filename: str = None, data=None):
        """
        将记录的设备数据保存到JSON文件中。

        参数：
            filename (str): 输出文件名（默认值：device_data.json）
        """
        if filename is None:
            filename = self.data_file
        
        if data is None:
            data = self.device_records

        try:
            device_records_save = data.copy()  # 创建记录的浅复制以避免修改原始数据
        except AttributeError:
            device_records_save = data

        try:
            with open(filename, 'w') as f:
                json.dump(device_records_save, f, indent=2)

            self.get_logger().info(
                f'设备数据保存到:{filename} '
                f'({self.total_records} 记录)'
            )
        except Exception as e:
            self.get_logger().error(f'无法保存数据: {e}')

    #预留功能：从文件加载数据
    def load_data_from_file(self, filename: str = None):
        """
        从JSON文件中加载设备数据。
        参数：
            filename (str): 输入文件名（默认值：device_data.json
        """
        if filename is None:
            filename = self.data_file
        
        if not os.path.exists(filename):
            self.get_logger().warn(f'Data file {filename} not found')
            return
        
        try:
            with open(filename, 'r') as f:
                self.device_records = json.load(f)
            
            # Recalculate total records
            self.total_records = sum(
                len(records) for records in self.device_records.values()
            )
            
            self.get_logger().info(
                f'Device data loaded from {filename} '
                f'({self.total_records} records)'
            )
        except Exception as e:
            self.get_logger().error(f'Failed to load data: {e}')

    #预留功能：获取某个设备记录
    def get_device_records(self, device_id: int = None):
        """
        获取已记录的设备数据。
        参数：
            device_id (int): 特定设备ID（所有设备均为None）
        返回：
            字典：设备记录
        """
        if device_id is None:
            return self.device_records
        else:
            return self.device_records.get(device_id, [])

    #目前只在关机时调用,获取统计数据
    def get_statistics(self):
        """
        获取服务统计数据。
        返回：
            dict: 统计词典
        """
        return {
            '总记录数': self.total_records,
            '总设备数': len(self.device_records),
            '状态分布': self.status_count,
            '设备列表': list(self.device_records.keys()),
            'http_post_count': self.http_post_count,
            'http_error_count': self.http_error_count,
        }
    
    #关机时调用,将服务统计信息打印到控制台
    def print_statistics(self):
        """将服务统计信息打印到控制台"""
        stats = self.get_statistics()
        
        self.get_logger().info('=' * 50)
        self.get_logger().info('设备数据服务统计')
        self.get_logger().info('=' * 50)
        self.get_logger().info(f'总记录数: {stats["总记录数"]}')
        self.get_logger().info(f'总设备数: {stats["总设备数"]}')
        self.get_logger().info(f'状态分布: {stats["状态分布"]}')
        self.get_logger().info(f'设备列表: {stats["设备列表"]}')
        self.get_logger().info(f'HTTP POST Successful: {stats["http_post_count"]}')
        self.get_logger().info(f'HTTP POST Errors: {stats["http_error_count"]}')
        self.get_logger().info('=' * 50)

    #预留功能：清除记录
    def clear_records(self):
        """清除所有已记录的数据"""
        self.device_records.clear()
        self.total_records = 0
        self.status_count = {0: 0, 1: 0, 2: 0}
        self.get_logger().info('所有记录已清除')

    #获取本机mac地址
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


def main(args=None):
    """设备数据服务节点的主入口点"""
    rclpy.init(args=args)
    node = DeviceDataService()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # 打印最终统计信息
        node.print_statistics()
        
        # 关机前保存数据
        node.save_data_to_file()
        
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
