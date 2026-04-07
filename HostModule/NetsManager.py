import requests
import json
import hashlib
from typing import Optional, Dict, Any
from loguru import logger


class NetsManager:
    """爱快路由器管理类"""

    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.sess_key = None
        self.session = requests.Session()

    # 登录WEB调用方法 ########################################################################
    def login(self) -> bool:
        try:
            # 构造登录数据
            passwd_md5 = hashlib.md5(self.password.encode()).hexdigest()
            # 根据要求，pass字段为salt_11+密码
            pass_str = "salt_11" + self.password

            login_data = {
                "username": self.username,
                "passwd": passwd_md5,
                "pass": pass_str,
                "remember_password": ""
            }
            # 发送登录请求
            response = self.session.post(
                f"{self.base_url}/Action/login",
                json=login_data,
                headers={'Content-Type': 'application/json'}
            )
            if response.status_code == 200:
                # 解析响应JSON
                try:
                    response_data = response.json()

                    # 检查登录结果
                    if response_data.get("Result") == 10000:
                        # 提取session_key
                        cookies = response.headers.get('Set-Cookie', '')

                        if 'sess_key=' in cookies:
                            import re
                            match = re.search(r'sess_key=([^;]+)', cookies)
                            if match:
                                self.sess_key = match.group(1)

                                # 设置正确的cookie格式
                                cookie_header = f"sess_key={self.sess_key}; username={self.username}; login=1"
                                self.session.headers.update({'Cookie': cookie_header})

                                # 同时设置到cookies对象中
                                self.session.cookies.set('sess_key', self.sess_key)
                                self.session.cookies.set('username', self.username)
                                self.session.cookies.set('login', '1')

                                return True
                    else:
                        error_msg = response_data.get("ErrMsg", "未知错误")
                        logger.error(f"登录失败: {error_msg}")

                except json.JSONDecodeError:
                    logger.error("响应不是有效的JSON格式")
            else:
                logger.error(f"登录失败，状态码: {response.status_code}")

            return False

        except Exception as e:
            logger.error(f"登录异常: {e}")
            return False

    # 内部API调用方法 ########################################################################
    def posts(self, func_name: str, action: str, param: Dict[str, Any]) -> Optional[Dict]:
        """
        内部API调用方法
        
        Args:
            func_name: 功能名称
            action: 操作类型
            param: 参数字典
            
        Returns:
            Optional[Dict]: API响应结果
        """
        if not self.sess_key:
            logger.warning("请先登录")
            return None

        try:
            api_data = {
                "func_name": func_name,
                "action": action,
                "param": param
            }

            response = self.session.post(
                f"{self.base_url}/Action/call",
                json=api_data,
                headers={'Content-Type': 'application/json'}
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"API调用失败: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"API调用异常: {e}")
            return None

    # 获取静态IP4列表 ########################################################################
    def get_dhcp(self) -> Optional[Dict]:
        param = {
            "TYPE": "static_total,static_data",
            "ORDER_BY": "",
            "ORDER": ""
        }

        result = self.posts("dhcp_static", "show", param)
        if result and result.get("ErrMsg") == "Success":
            logger.info(f"✅ 获取静态IP列表成功，共{result['Data'].get('static_total', 0)}条")
            return result
        else:
            logger.error("❌ 获取静态IP列表失败")
            return None

    # 获取端口映射列表 #######################################################################
    def get_port(self) -> Optional[Dict]:
        param = {
            "TYPE": "total,data",
            "ORDER_BY": "",
            "ORDER": ""
        }

        result = self.posts("dnat", "show", param)
        if result and result.get("ErrMsg") == "Success":
            logger.info(f"✅ 获取端口映射列表成功，共{result['Data'].get('total', 0)}条")
            return result
        else:
            logger.error("❌ 获取端口映射列表失败")
            return None

    # 获取ARP列表 ############################################################################
    def get_arps(self) -> Optional[Dict]:
        param = {
            "TYPE": "total,data",
            "ORDER_BY": "ip_addr_int",
            "orderType": "IP",
            "ORDER": "asc",
        }

        result = self.posts("arp", "show", param)
        if result and result.get("ErrMsg") == "Success":
            logger.info(f"✅ 获取ARP列表成功，共{result['Data'].get('total', 0)}条")
            return result
        else:
            logger.error("❌ 获取ARP列表失败")
            return None

    # 静态IP4设置方法 ########################################################################
    def add_dhcp(self, lan_addr: str, mac_addr: str, comment: str = "",
                 lan_dns1: str = "119.29.29.29", lan_dns2: str = "223.5.5.5") -> bool:
        param = {
            "newRow": True,
            "hostname": "",
            "ip_addr": lan_addr,
            "mac": mac_addr,
            "gateway": "auto",
            "interface": "auto",
            "dns1": lan_dns1,
            "dns2": lan_dns2,
            "comment": comment,
            "enabled": "yes"
        }

        logger.info(f"🔍 准备添加DHCP - 提交参数: {json.dumps(param, ensure_ascii=False)}")

        result = self.posts("dhcp_static", "add", param)
        success = result is not None and result.get("ErrMsg") == "Success"
        if success:
            logger.info(f"✅ 静态IP添加成功: {lan_addr} -> {mac_addr}")
        else:
            logger.error(f"❌ 静态IP添加失败: {lan_addr} -> {mac_addr}")
            logger.error(result)

        return success

    # 静态IP4删除方法 ########################################################################
    def del_dhcp(self, lan_addr: str, mac: str = None) -> bool:
        # 通过get_dhcp查找entry_id
        if not lan_addr and not mac:
            logger.warning("必须提供ip_addr或mac中的一个")
            return False

        # 获取DHCP列表
        dhcp_list = self.get_dhcp()
        if not dhcp_list or 'Data' not in dhcp_list:
            logger.error("无法获取DHCP列表")
            return False

        # 查找匹配的条目
        entry_id = None
        for item in dhcp_list['Data'].get('static_data', []):
            if (lan_addr and item.get('ip_addr') == lan_addr) or \
                    (mac and item.get('mac') == mac):
                entry_id = item.get('id')
                logger.info(f"找到匹配的DHCP条目: ID={entry_id}, IP={item.get('ip_addr')}, MAC={item.get('mac')}")
                break

        if not entry_id:
            identifier = lan_addr or mac
            logger.error(f"未找到匹配的DHCP条目: {identifier}")
            return False

        param = {"id": entry_id}
        logger.info(f"🔍 准备删除DHCP - 提交参数: {json.dumps(param, ensure_ascii=False)}")

        result = self.posts("dhcp_static", "del", param)
        success = result is not None and result.get("ErrMsg") == "Success"
        logger.debug(result)
        if result and result.get('ErrMsg') == "Success":
            success = True
        if success:
            identifier = entry_id or lan_addr or mac
            logger.info(f"✅ 静态IP删除成功: {identifier}")
        else:
            identifier = entry_id or lan_addr or mac
            logger.error(f"❌ 静态IP删除失败: {identifier}")

        return success

    # TCP/UDP转发设置 ########################################################################
    def add_port(self, wan_port: int, lan_port: int, lan_addr: str, comment: str = "") -> bool:
        param = {
            "enabled": "yes",
            "comment": comment,
            "interface": "wan1",
            "lan_addr": lan_addr,
            "protocol": "tcp+udp",
            "wan_port": wan_port,
            "lan_port": lan_port,
            "src_addr": ""
        }

        result = self.posts("dnat", "add", param)
        success = result is not None and result.get("ErrMsg") == "Success"
        if success:
            logger.info(f"✅ 端口转发添加成功: 外部端口{wan_port} -> {lan_addr}:{lan_port}")
        else:
            logger.error(f"❌ 端口转发添加失败: 外部端口{wan_port} -> {lan_addr}:{lan_port}")
        return success

    # TCP/UDP转发删除 ########################################################################
    def del_port(self, lan_port: int, lan_addr: str = None) -> bool:

        # 通过get_port查找entry_id
        if not lan_port and not lan_addr:
            logger.warning("必须提供lan_port或lan_addr中的一个")
            return False

        # 获取端口映射列表
        port_list = self.get_port()
        if not port_list or 'Data' not in port_list:
            logger.error("无法获取端口映射列表")
            return False

        # 查找匹配的条目
        entry_id = None
        for item in port_list['Data'].get('data', []):
            if (lan_port and lan_addr and
                item.get('lan_port') == lan_port and
                item.get('lan_addr') == lan_addr) or \
                    (lan_port and not lan_addr and item.get('lan_port') == lan_port) or \
                    (lan_addr and not lan_port and item.get('lan_addr') == lan_addr):
                entry_id = item.get('id')
                logger.info(
                    f"找到匹配的端口映射条目: ID={entry_id}, WAN端口={item.get('wan_port')}, LAN地址={item.get('lan_addr')}:{item.get('lan_port')}")
                break

        if not entry_id:
            identifier = f"{lan_addr or ''}:{lan_port or ''}"
            logger.error(f"未找到匹配的端口映射条目: {identifier}")
            return False

        param = {"id": entry_id}
        logger.info(f"🔍 准备删除端口映射 - 提交参数: {json.dumps(param, ensure_ascii=False)}")

        result = self.posts("dnat", "del", param)
        success = result is not None and result.get("ErrMsg") == "Success"
        if success:
            identifier = f"{lan_addr}:{lan_port}"
            logger.info(f"✅ 端口转发删除成功: {identifier}")
        else:
            identifier = f"{lan_addr}:{lan_port}"
            logger.error(f"❌ 端口转发删除失败: {identifier}")
        return success

    # ARP绑定方法 ############################################################################
    def add_arps(self, lan_addr: str, mac_addr: str, comment: str = "") -> bool:
        param = {
            "bind_type": 0,
            "interface": "lan1",
            "ip_addr": lan_addr,
            "mac": mac_addr,
            "comment": comment,
            "old_ip_addr": ""
        }

        result = self.posts("arp", "add", param)
        success = result is not None and result.get("success", False)
        if success:
            logger.info(f"✅ ARP绑定添加成功: {lan_addr} -> {mac_addr}")
        else:
            logger.error(f"❌ ARP绑定添加失败: {lan_addr} -> {mac_addr}")
        return success

    # ARP解绑方法 ############################################################################
    def del_arps(self, lan_addr: str, mac_addr: str = None) -> bool:
        # 通过get_arp查找entry_id和ip_addr
        if not lan_addr and not mac_addr:
            logger.warning("必须提供ip_addr或mac中的一个")
            return False

        # 获取ARP列表
        arp_list = self.get_arps()
        if not arp_list or 'Data' not in arp_list:
            logger.error("无法获取ARP列表")
            return False

        # 查找匹配的条目
        target_id = None
        target_ip = None
        for item in arp_list['Data'].get('data', []):
            if (lan_addr and item.get('ip_addr') == lan_addr) or \
                    (mac_addr and item.get('mac') == mac_addr):
                target_id = item.get('id')
                target_ip = item.get('ip_addr')
                logger.info(f"找到匹配的ARP条目: ID={target_id}, IP={target_ip}, MAC={item.get('mac')}")
                break

        if not target_id or not target_ip:
            identifier = lan_addr or mac_addr
            logger.error(f"未找到匹配的ARP条目: {identifier}")
            return False

        param = {
            "id": target_id,
            "ip_addr": target_ip
        }
        logger.info(f"🔍 准备删除ARP - 提交参数: {json.dumps(param, ensure_ascii=False)}")

        result = self.posts("arp", "del", param)
        success = result is not None and result.get("ErrMsg") == "Success"
        if success:
            logger.info(f"✅ ARP绑定删除成功: ID={target_id}, IP={target_ip}")
        else:
            logger.error(f"❌ ARP绑定删除失败: ID={target_id}, IP={target_ip}")
            logger.error(result)
        return success

