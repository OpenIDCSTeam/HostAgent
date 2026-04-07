import json


class PortData:
    def __init__(self, **kwargs):
        self.lan_port: int = 0
        self.wan_port: int = 0
        self.lan_addr: str = ""
        self.nat_tips: str = ""

    def __load__(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                # lan_port / wan_port 强制转为 int，防止前端传入空字符串
                if key in ("lan_port", "wan_port"):
                    try:
                        value = int(value) if value != "" else 0
                    except (TypeError, ValueError):
                        value = 0
                setattr(self, key, value)

    def __save__(self):
        return {
            "lan_port": self.lan_port,
            "wan_port": self.wan_port,
            "lan_addr": self.lan_addr,
            "nat_tips": self.nat_tips
        }

    def __str__(self):
        return json.dumps(self.__save__())
