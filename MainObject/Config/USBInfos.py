class USBInfos:
    def __init__(self, **kwargs):
        self.vid_uuid: str = ""
        self.pid_uuid: str = ""
        self.usb_hint: str = ""
        self.__load__(**kwargs)

    def __save__(self):
        return {
            "vid_uuid": self.vid_uuid,
            "pid_uuid": self.pid_uuid,
            "usb_hint": self.usb_hint,
        }

    # 加载数据 ===============================
    def __load__(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
