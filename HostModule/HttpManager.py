import os
import time
import signal
import random
import traceback
import subprocess
from pathlib import Path
from HostModule.DataManager import DataManager


class HttpManager:
    # 初始化 #####################################################################################
    def __init__(self,
                 config_name="HttpManage.txt",
                 proxys_type="tty",
                 proxys_addr="127.0.0.1"):
        # 初始化二进制进程和配置文件 =======================
        self.proxys_port = 0
        self.proxys_addr = proxys_addr
        self.proxys_type = proxys_type
        self.binary_proc = None
        self.binary_path = "HostConfig/Server_x64"
        self.config_path = Path("HostConfig")
        self.config_file = Path(f"DataSaving/{config_name}")
        self.manage_port = random.randint(8000, 9000)
        # proxys_sshd格式: { ===============================
        #   port: {
        #       token:(ip,port)
        #   }
        # } ================================================
        self.proxys_sshd = {}
        # proxys_list格式: { ===============================
        # domain: {
        #   "target": (port, ip),
        #   "is_https": bool,
        #   "listen_port": int
        #   }
        # } ================================================
        self.proxys_list = {}
        # 设置二进制路径 ===================================
        if os.name == 'nt':
            self.binary_path += ".exe"
            self.binary_path = self.binary_path.replace(
                "/", "\\")
        # 初始数据库管理 ===================================
        self.config_path.mkdir(exist_ok=True)
        self.db_manager = DataManager()
        # 生成初始的配置 ===================================
        self.config_all()
        print(f"HttpManager初始化完成，"
              f"管理端口: {self.manage_port}，"
              f"配置文件: {self.config_file}")

    # 生成完整的Caddy配置文件 ####################################################################
    def config_all(self):
        # 使用实例的管理端口生成全局配置
        config = f"{{\n\tadmin localhost:{self.manage_port}\n}}\n\n"
        # 生成普通代理配置 #######################################################################
        for domain, proxy_info in self.proxys_list.items():
            port, ip = proxy_info["target"]
            is_https = proxy_info.get("is_https", True)
            listen_port = proxy_info.get("listen_port")
            should_add_port = listen_port not in (None, 0, 80, 443)
            if domain.startswith("/") or domain == "":
                url = f"*:{listen_port}"
            elif should_add_port:
                protocol = "https" if is_https else "http"
                url = f"{protocol}://{domain}:{listen_port}"
            else:
                url = domain if is_https else f"http://{domain}"
            # 后端目标协议
            backend_protocol = "https" if is_https else "http"
            if domain.find("/") > -1:  # 存在子路径
                sub_path = "/" + "/".join(domain.split("/")[1:])
                config += (
                    f"{url} "
                    f"{{\n\t@secret path {sub_path}\n"
                    f"\treverse_proxy "
                    f"{backend_protocol}://{ip}:{port}\n"
                    f"}}\n\n")
            else:
                config += (
                    f"{url} "
                    f"{{\n\treverse_proxy "
                    f"{backend_protocol}://{ip}:{port}\n"
                    f"}}\n\n")
        # 生成SSH代理配置 ########################################################################
        if self.proxys_sshd:
            for listen_port, token_dict in self.proxys_sshd.items():
                config += ":%s {\n" % listen_port
                if self.proxys_type == "vmk":
                    # 静态文件代理
                    config += f"\thandle_path /static/* {{\n"
                    config += f"\t\troot * VNCConsole/vSphere\n"
                    config += f"\t\tfile_server\n"
                    config += f"\t}}\n"
                    config += f"\t@websockets {{\n"
                    config += f"\theader Connection *Upgrade*\n"
                    config += f"\theader Upgrade websocket\n"
                    config += f"\t}}\n"
                for token, (target_ip, target_port) in token_dict.items():
                    # TTY代理 ====================================================================
                    if self.proxys_type == "tty":
                        config += f"\thandle_path /{token}* {{\n"
                        config += f"\t\treverse_proxy http://{target_ip}:{target_port} {{\n"
                        config += f"\t\theader_up Host {{http.axio.host}}\n"
                        config += f"\t\theader_up X-Real-IP {{http.axio.remote.host}}\n"
                        config += f"\t\theader_up X-Forwarded-For {{http.axio.remote.host}}\n"
                        config += f"\t\theader_up REMOTE-HOST {{http.axio.remote.host}}\n"
                        config += f"\t\theader_up Connection {{http.axio.header.Connection}}\n"
                        config += f"\t\theader_up Upgrade {{http.axio.header.Upgrade}}\n"
                        config += f"\t}}\n"
                        config += f"\t}}\n"
                    # VMK代理 ====================================================================
                    elif self.proxys_type == "vmk":
                        # 生成 ticket_path =================================
                        ticket_path = str(target_port)
                        if "/" in str(target_port):
                            ticket_path = str(target_port).split("/")[1]
                            target_port = str(target_port).split("/")[0]
                        # WebSocket 反向代理
                        config += f"\thandle_path /{token}/ws/* {{\n"
                        config += f"\t\treverse_proxy https://{target_ip}:{target_port} {{\n"
                        config += f"\t\t\theader_up Host {{http.axio.host}}\n"
                        config += f"\t\t\theader_up X-Real-IP {{http.axio.remote.host}}\n"
                        config += f"\t\t\theader_up X-Forwarded-For {{http.axio.remote.host}}\n"
                        config += f"\t\t\theader_up REMOTE-HOST {{http.axio.remote.host}}\n"
                        config += f"\t\t\theader_up Connection {{http.axio.header.Connection}}\n"
                        config += f"\t\t\theader_up Upgrade {{http.axio.header.Upgrade}}\n"
                        # config += f"\t\t\theader_up X-Target-Path /ticket/{ticket_path}\n"
                        config += f"\t\t\ttransport http {{\n"
                        config += f"\t\t\t\ttls_insecure_skip_verify\n"
                        config += f"\t\t\t}}\n"
                        config += f"\t\t}}\n"
                        config += f"\t}}\n"
                        # 返回 test.html 模板
                        html_template = f'''<!DOCTYPE html PUBLIC"-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
                        <html xmlns="http://www.w3.org/1999/xhtml">
                        <head>
                        <meta http-equiv="content-type" content="text/html; charset=utf-8" />
                        <title>Console</title>
                        </head>
                        <body>
                        <link rel="stylesheet" type="text/css" href="/static/css/wmks-all.css" />
                        <script type="text/javascript" src="http://code.jquery.com/jquery-1.8.3.min.js"></script>
                        <script type="text/javascript" src="http://code.jquery.com/ui/1.8.16/jquery-ui.min.js"></script>
                        <script type="text/javascript" src="/static/wmks.min.js"></script>
                        <div id="wmksContainer" style="position:absolute;width:100%;height:100%"></div>
                        <script>
                        var wmks = WMKS.createWMKS("wmksContainer",{{}})
                         .register(WMKS.CONST.Events.CONNECTION_STATE_CHANGE, function(event,data){{
                         if(data.state == WMKS.CONST.ConnectionState.CONNECTED){{
                          console.log("connection state change : connected");}}}});
                        wmks.connect("ws://{self.proxys_addr}:{self.proxys_port}/{token}/ws/ticket/{ticket_path}");
                        </script>
                        </body>
                        </html>'''
                        config += f"\thandle_path /{token} {{\n"
                        config += f"\t\theader Content-Type text/html;charset=utf-8\n"
                        config += f"\t\trespond `{html_template}` 200\n"
                        config += f"\t}}\n"
                config += "}\n\n"
        # 保存配置文件 ###########################################################################
        self.config_file.write_text(config)
        return True

    # 初始化VNC代理管理 ##########################################################################
    def launch_vnc(self,
                   port: int = random.randint(8000, 9000)):
        self.proxys_port = port
        if str(self.proxys_port) not in self.proxys_sshd:
            self.proxys_sshd[str(self.proxys_port)] = {}

    # 关闭SSH代理的管理 ##########################################################################
    def closed_vnc(self, port: int):
        if str(port) in self.proxys_sshd:
            del self.proxys_sshd[str(port)]

    # 添加SSH的代理配置 ##########################################################################
    def create_vnc(self, token, target_ip, target_port, path=""):
        try:
            # 检查是否已有相同token的配置 ======================
            for port, token_dict in self.proxys_sshd.items():
                if token in token_dict:
                    print(f"令牌 {token} 的SSH代理配置已存在")
                    return False
            # 如SSH未启动则启动 ================================
            if self.proxys_port == 0:
                self.launch_vnc()
            # 添加到SSH代理配置 ================================
            proxy_conf = [target_ip, str(target_port)]
            if path != "":
                proxy_conf[1] += "/" + path
            proxy_port = str(self.proxys_port)
            self.proxys_sshd[proxy_port][token] = proxy_conf
            print(f"SSH代理已添加: "
                  f"/{token} -> {target_ip}:{target_port}"
                  f" (统一端口: {str(self.proxys_port)})")
            # 重新生成配置文件 =================================
            self.config_all()
            # 重载Caddy配置 ====================================
            return self.reload_web()

        except Exception as e:
            print(f"添加SSH代理配置时发生错误: {str(e)}")
            traceback.print_exc()
            return False

    # 添加代理配置 ###############################################################################
    def create_web(self, target, domain, is_https=True, listen_port=None, persistent=True):
        """添加代理配置"""
        try:
            # 检查域名是否已存在
            if domain in self.proxys_list:
                print(f"域名 {domain} 的配置已存在")
                return False

            # 添加到内存配置
            self.proxys_list[domain] = {
                "target": target,
                "is_https": is_https,
                "listen_port": listen_port
            }

            # 重新生成配置文件
            self.config_all()

            # 保存到数据库（只有persistent为True时才写入）
            # if persistent:
            #     self.global_set(domain, self.proxys_list[domain])
            # else:
            #     print(f"代理 {domain} 为临时代理，不写入数据库")

            # 重载Caddy配置
            return self.reload_web()

        except Exception as e:
            print(f"添加代理配置时发生错误: {str(e)}")
            # 回滚
            if domain in self.proxys_list:
                del self.proxys_list[domain]
            return False

    # 删除代理配置 ###############################################################################
    def remove_web(self, domain):
        """删除代理配置"""
        try:
            # 检查域名是否存在
            if domain not in self.proxys_list:
                print(f"未找到匹配的代理配置: {domain}")
                print(f"当前已有的域名: {list(self.proxys_list.keys())}")
                return False

            # 备份配置（用于回滚）
            backup = self.proxys_list[domain]

            # 从内存配置中删除
            del self.proxys_list[domain]

            # 重新生成配置文件
            self.config_all()

            # 从数据库删除（不写入JSON文件）
            # self.global_del(domain)

            # 重载Caddy配置
            result = self.reload_web()

            if not result:
                # 回滚
                self.proxys_list[domain] = backup
                self.config_all()
                # self.global_set(domain, backup)

            return result

        except Exception as e:
            print(f"删除代理配置时发生错误: {str(e)}")
            return False

    # 启动Caddy服务 ##############################################################################
    def launch_web(self):
        """启动Caddy服务"""
        try:
            cmd = [self.binary_path, "run", "--config", str(self.config_file), "--adapter", "caddyfile"]

            print(" ".join(cmd))
            self.binary_proc = subprocess.Popen(cmd, shell=True)
            time.sleep(2)  # 等待进程启动

            if self.binary_proc.poll() is None:
                print(f"Caddy进程已启动，PID: {self.binary_proc.pid}")
                return True

            return False

        except FileNotFoundError:
            print("错误: 找不到caddy可执行文件")
            return False
        except Exception as e:
            print(f"启动Caddy时发生错误: {str(e)}")
            return False

    # 停止Caddy服务 ##############################################################################
    def closed_web(self):
        """停止Caddy服务"""
        try:
            if self.binary_proc and self.binary_proc.poll() is None:
                self.binary_proc.terminate()
                try:
                    self.binary_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.binary_proc.kill()
                    self.binary_proc.wait()
                print("Caddy进程已停止")
                return True
            return False
        except Exception as e:
            print(f"停止Caddy时发生错误: {str(e)}")
            return False

    # Caddy运行状态检查 ##########################################################################
    def is_web_running(self):
        return self.binary_proc is not None and self.binary_proc.poll() is None

    # 重载Caddy配置 ##############################################################################
    def reload_web(self):
        """重载Caddy配置"""
        try:
            # 尝试重载配置（无论binary_proc状态如何）
            if os.name == 'nt':
                # 使用实例的管理端口进行重载
                reload_cmd = [self.binary_path, "reload", "--config",
                              str(self.config_file), "--adapter", "caddyfile",
                              "--address", f"localhost:{self.manage_port}"]
                print("重载服务命令:", " ".join(reload_cmd))
                result = subprocess.run(reload_cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    print(f"Caddy配置已重载（管理端口: {self.manage_port}）")
                    return True
                else:
                    print(f"重载失败，尝试重新启动服务: {result.stderr}")
                    self.closed_web()
                    return self.launch_web()
            else:
                # Linux/Mac: 如果有进程引用则发送信号
                if self.binary_proc and self.binary_proc.poll() is None:
                    self.binary_proc.send_signal(signal.SIGUSR1)
                    print(f"Caddy配置已重载（管理端口: {self.manage_port}）")
                    return True
                else:
                    return self.launch_web()
        except Exception as e:
            print(f"重载Caddy配置时发生错误: {str(e)}")
            return False

    # # 加载代理配置 ###############################################################################
    # def global_get(self):
    #     """从虚拟机配置加载代理配置（已废弃，由HostManager.all_load统一管理）"""
    #     # 此函数已废弃，代理配置现在从虚拟机配置中加载
    #     # 在HostManager.all_load中会遍历所有虚拟机的web_all并调用create_web
    #     print("global_get已废弃，代理配置由HostManager统一管理")
    #     return True
    #
    # # 保存代理配置 ###############################################################################
    # def global_set(self, domain, proxy_info):
    #     """将代理配置保存到虚拟机配置（已废弃，由虚拟机配置统一管理）"""
    #     # 此函数已废弃，代理配置现在保存在虚拟机的web_all列表中
    #     # 通过admin_add_proxy或用户的add_proxy接口添加
    #     print(f"global_set已废弃，代理 {domain} 应通过虚拟机配置管理")
    #     return True
    #
    # # 删除代理配置 ###############################################################################
    # def global_del(self, domain):
    #     """从虚拟机配置删除代理配置（已废弃，由虚拟机配置统一管理）"""
    #     # 此函数已废弃，代理配置现在从虚拟机的web_all列表中删除
    #     # 通过admin_delete_proxy或用户的delete_proxy接口删除
    #     print(f"global_del已废弃，代理 {domain} 应通过虚拟机配置管理")
    #     return True


# 使用示例
if __name__ == "__main__":
    manager = HttpManager()

    try:
        # 启动服务
        manager.launch_web()
        time.sleep(2)

        # 添加代理（使用HTTP协议，监听8081端口避免80端口冲突）
        manager.create_web((1880, "127.0.0.1"), "local.524228.xyz", is_https=False, listen_port=1889)

        # 等待一段时间
        time.sleep(100)

        # 删除代理
        manager.remove_web("local.524228.xyz")

        # 停止服务
        manager.closed_web()
    except KeyboardInterrupt as e:
        manager.closed_web()
