# Custom message for device status
# Fields:
# - device_id: Custom device ID
# - local_mac: Local machine MAC address
# - status: Device status (0, 1, or 2)
# - timestamp: Message timestamp (seconds since epoch)
# - mac_address_a: Reserved MAC address A
# - mac_address_b: Reserved MAC address B

uint32 device_id
string local_mac
uint8 status
uint64 timestamp
string mac_address_a
string mac_address_b
