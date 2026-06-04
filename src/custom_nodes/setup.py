from setuptools import find_packages, setup
from glob import glob
import os

package_name = 'custom_nodes'

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'),
            glob(os.path.join('launch', '*.launch.py'))),
    ],
    install_requires=['setuptools', 'rclpy'],
    zip_safe=True,
    maintainer='User',
    maintainer_email='user@example.com',
    description='Python nodes for custom device status messaging',
    license='Apache License 2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'publisher_node = custom_nodes.publisher_node:main',
            'subscriber_node = custom_nodes.subscriber_node:main',
            'device_data_service = custom_nodes.device_data_service:main',
        ],
    },
)
