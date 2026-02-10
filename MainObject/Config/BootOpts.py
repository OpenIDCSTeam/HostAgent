class BootOpts:
    def __init__(self, **kwargs):
        self.efi_type: bool = False  # False = HDD，True = ISO
        self.efi_name: str = ""  # 启动项名称->对应的HDD/ISO名
        self.__load__(**kwargs)

    def __save__(self):
        return {
            "efi_type": self.efi_type,
            "efi_name": self.efi_name
        }

    # 加载数据 ===============================
    def __load__(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
