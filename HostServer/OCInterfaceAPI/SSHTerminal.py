import os
import random
import string
import subprocess
import platform
from loguru import logger

from MainObject.Config.HSConfig import HSConfig


class SSHTerminal:
    """Web Terminal (ttyd) 管理API - 修改为直接启动ttyd进程"""

    def __init__(self, hs_config: HSConfig):
        self.hs_config = hs_config
        self.ttyd_processes = {}  # 存储ttyd进程 {port: process}
        self.ttyd_tokens = {}  # 存储token映射 {port: token}
        # 根据系统获取ttyd可执行文件路径
        self.ttyd_path = self.path_tty()

    # 获取ttyd可执行文件路径 #############################################
    def path_tty(self) -> str:
        # 获取脚本所在目录的父目录（项目根目录）
        # current_dir = os.path.dirname(os.path.abspath(__file__))
        # project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        ttyd_dir = os.path.join(os.getcwd(), "HostConfig", "ttydserver")

        system = platform.system().lower()
        machine = platform.machine().lower()

        # 根据系统选择合适的ttyd可执行文件
        if system == "windows":
            ttyd_file = "ttyd.win32.exe"
        elif system == "linux":
            if "aarch64" in machine or "arm64" in machine:
                ttyd_file = "ttyd.aarch64"
            else:
                ttyd_file = "ttyd.x86_64"
        else:
            logger.warning(f"不支持的平台: {system} {machine}")
            return ""

        ttyd_path = os.path.join(ttyd_dir, ttyd_file)

        # 检查文件是否存在
        if os.path.exists(ttyd_path):
            logger.info(f"找到ttyd: {ttyd_path}")
            return ttyd_path
        else:
            logger.warning(f"ttyd未找到: {ttyd_path}")
            return ""

    # 启动 ttyd SSH会话 #################################################################
    # :param hs_conf: 主机配置信息
    # :param vm_port: 远程SSHD端口
    # :param vm_uuid: 虚拟机的UUID
    # :return: (port, token)
    # ###################################################################################
    def open_tty(self,
                 hs_conf: HSConfig,
                 vm_port: str,
                 vm_uuid: str,
                 vm_type: str = "docker") -> tuple[int, str]:
        # 检查ttyd可执行文件是否存在 ====================================================
        if not self.ttyd_path:
            logger.error("ttyd可执行文件未找到")
            return -1, ""
        # 生成随机端口和token ===========================================================
        rand_port = random.randint(7000, 8000)
        rand_pass = ''.join(random.sample(string.ascii_letters + string.digits, 32))
        # 启动ttyd进程 ==================================================================
        try:
            # 自动输入密码支持：检测 sshpass ============================================
            ssh_port = 22  # 固定为22，如需动态可在hs_conf增加字段
            password = hs_conf.server_pass
            auto_cmd = ""
            if platform.system().lower() == "windows":
                sshpass_path = os.path.join(
                    os.getcwd(), "HostConfig",
                    "winptyexec", "sshpass.exe")
                if os.path.exists(sshpass_path):
                    auto_cmd = f'"{sshpass_path}" -p "{password}"'
            else:  # linux / macos
                # 检查系统是否有 sshpass 命令
                which_result = subprocess.run(
                    ["which", "sshpass"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL)
                if which_result.returncode == 0:
                    auto_cmd = "sshpass -p '{}'".format(password)
            # 构造 ssh 命令 ===============================================================
            ssh_cmd = f"ssh -tt -o StrictHostKeyChecking=no root@{hs_conf.server_addr}"
            # 检查是否需要自动输入密码 ====================================================
            if (hs_conf.server_addr == "" or
                hs_conf.server_pass == "") \
                    and auto_cmd != "":
                ssh_cmd += f" -p {vm_port}"
            else:  # 直接使用docker exec进入虚拟机内部 ------------------------------------
                if vm_type == "docker":
                    ssh_cmd += f" -p {ssh_port} docker exec -it {vm_uuid} bash"
                else:
                    ssh_cmd += f" -p {ssh_port} lxc exec {vm_uuid} bash"
                if auto_cmd:
                    ssh_cmd = f"{auto_cmd} {ssh_cmd}"
            # 启动ttyd进程 ================================================================
            tty_cmd = [self.ttyd_path, "--writable", "-w",
                       "C:\\" if platform.system().lower() == "windows" else "/",
                       "-t", "titleFixed=Terminal-"+vm_uuid,
                       "-p", str(rand_port), ssh_cmd]
            tty_cmd = " ".join(tty_cmd)  # 重要！！否则无法正常启动
            logger.info(f"TTY-启动命令: {' '.join(tty_cmd)}")
            # 启动ttyd进程 ================================================================
            process = subprocess.Popen(
                tty_cmd,
                # shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding='gbk',  # Windows中文系统常用编码
                errors='replace',  # 替换无法解码的字符
                text=True,
            )
            # 存储进程信息
            self.ttyd_processes[rand_port] = process
            self.ttyd_tokens[rand_port] = rand_pass
            logger.info(
                f"TTY-启动成功 " +
                f"{rand_port} -> {hs_conf.server_addr}:{vm_port}/{vm_uuid}")
            return rand_port, rand_pass
        except Exception as e:
            logger.error(f"TTY-启动失败: {str(e)}")
            return -1, ""

    # 停止 ttyd 会话 #####################################################
    def stop_tty(self, port: int):
        """
        停止指定端口的ttyd进程
        :param port: ttyd进程监听的端口
        """
        if port in self.ttyd_processes:
            process = None
            try:
                process = self.ttyd_processes[port]
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if process:
                    process.kill()
            finally:
                del self.ttyd_processes[port]
                if port in self.ttyd_tokens:
                    del self.ttyd_tokens[port]
                logger.info(f"已停止端口{port}上ttyd会话")
