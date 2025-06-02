import netifaces

def get_internal_ip():
    # Список приватных сетей (RFC 1918)
    private_ranges = [
        ("10.", 8),          # 10.0.0.0/8
        ("172.16.", 12),      # 172.16.0.0/12
        ("192.168.", 16)      # 192.168.0.0/16
    ]

    for interface in netifaces.interfaces():
        addrs = netifaces.ifaddresses(interface)
        if netifaces.AF_INET in addrs:
            for addr_info in addrs[netifaces.AF_INET]:
                ip = addr_info['addr']
                # Игнорируем loopback и публичные IP
                if ip == "127.0.0.1":
                    continue
                # Проверяем, принадлежит ли IP к приватным диапазонам
                for (prefix, mask) in private_ranges:
                    if ip.startswith(prefix):
                        return ip
    
    print("No private IP found" | "внутренний ip не найден") 