class VFConfig:
    def __init__(self, **kwargs):
        self.gpu_uuid: str = ""
        self.gpu_mdev: str = ""
        self.gpu_hint: str = ""
        self.__load__(**kwargs)

    def __save__(self):
        return {
            "gpu_uuid": self.gpu_uuid,
            "gpu_mdev": self.gpu_mdev,
            "gpu_hint": self.gpu_hint,
        }

    # 加载数据 ===============================
    def __load__(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
