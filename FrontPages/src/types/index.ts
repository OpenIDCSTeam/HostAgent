// API响应基础类型
export interface ApiResponse<T = any> {
  code: number; // 状态码
  msg: string; // 响应消息
  data?: T; // 响应数据
  timestamp?: string; // 时间戳
}

// 用户相关类型
export interface User {
  id: number;
  username: string;
  email: string;
  is_admin: boolean;
  is_active: boolean;
  email_verified: boolean;
  created_at: string;
  last_login?: string;
  assigned_hosts: string[];
  gpu_ids?: string;
  // 权限
  can_create_vm: boolean;
  can_modify_vm: boolean;
  can_delete_vm: boolean;
  // 配额信息
  quota_cpu: number;
  quota_ram: number;
  quota_ssd: number;
  quota_gpu: number;
  quota_nat_ports: number;
  quota_nat_ips: number;
  quota_web_proxy: number;
  quota_pub_ips: number;
  quota_bandwidth_up: number;
  quota_bandwidth_down: number;
  quota_traffic: number;
  // 已使用资源
  used_cpu: number;
  used_ram: number;
  used_ssd: number;
  used_gpu: number;
  used_nat_ports: number;
  used_nat_ips: number;
  used_web_proxy: number;
  used_pub_ips: number;
  used_bandwidth_up: number;
  used_bandwidth_down: number;
  used_traffic: number;
}

// 登录请求
export interface LoginRequest {
  login_type?: 'token' | 'user';
  token?: string;
  username?: string;
  password?: string;
}

// 主机相关类型
export interface Host {
  server_name: string;
  server_type: string;
  server_addr: string;
  server_user: string;
  status: 'online' | 'offline' | 'error';
  enabled?: boolean; // 主机是否启用（对应后端的enable_host字段）
  enable_host?: boolean; // 后端返回的原始字段
  vms_count: number;
  running_vms?: number;
  stopped_vms?: number;
  cpu_usage?: number;
  memory_usage?: number;
  disk_usage?: number;
  last_check?: string;
  version?: string;
  uptime_seconds?: number;
  error_message?: string;
}

// 虚拟机相关类型
export interface VM {
  vm_uuid: string;
  vm_name: string;
  display_name?: string;
  os_name: string;
  os_version?: string;
  cpu_num: number;
  mem_num: number;
  hdd_num: number;
  gpu_num?: number;
  status: 'running' | 'stopped' | 'suspended' | 'error';
  power_state?: string;
  ip_address?: string;
  mac_address?: string;
  created_time?: string;
  modified_time?: string;
  last_boot?: string;
  tools_status?: string;
  snapshot_count?: number;
  is_template?: boolean;
  owner?: string;
  tags?: string[];
}

// 虚拟机创建请求
export interface CreateVMRequest {
  vm_uuid: string;
  vm_name: string;
  display_name?: string;
  os_name: string;
  os_version?: string;
  cpu_num: number;
  mem_num: number;
  hdd_num: number;
  gpu_num?: number;
  vm_path?: string;
  iso_path?: string;
  network_type?: 'bridged' | 'nat' | 'hostonly';
  description?: string;
  template_uuid?: string;
}

// 虚拟机电源操作
export type VMPowerAction = 'S_START' | 'H_CLOSE' | 'S_RESET' | 'S_PAUSE' | 'S_RESUME';

// NAT规则
export interface NATRule {
  rule_index: number;
  host_port: number;
  vm_port: number;
  protocol: 'tcp' | 'udp';
  description?: string;
  enabled: boolean;
  created_time?: string;
  // 老前端字段名兼容
  id?: number;
  public_port?: number;
  private_port?: number;
  internal_ip?: string;
  wan_port?: number | string;
  lan_port?: number | string;
  lan_addr?: string;
  nat_tips?: string;
}

// 反向代理配置
export interface ProxyConfig {
  proxy_index: number;
  domain: string;
  backend_ip?: string;
  backend_port: number;
  proxy_type?: 'http' | 'https';
  ssl_enabled: boolean;
  ssl_cert_path?: string;
  ssl_key_path?: string;
  description?: string;
  enabled: boolean;
}

// 系统统计信息
export interface SystemStats {
  hosts_count: number;
  vms_count: number;
  users_count?: number;
  running_vms: number;
  stopped_vms: number;
  total_cpu_cores?: number;
  total_memory_gb?: number;
  total_storage_gb?: number;
  cpu_usage_percent?: number;
  memory_usage_percent?: number;
  storage_usage_percent?: number;
}

// 分页参数
export interface PaginationParams {
  page?: number;
  page_size?: number;
}

// 分页响应
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// 虚拟机细分权限掩码位定义
export const VM_PERMISSION = {
  PWR_EDITS: 1,       // 是否允许编辑电源
  PWD_EDITS: 2,       // 是否允许编辑密码
  SYS_EDITS: 4,       // 是否允许编辑系统
  NIC_EDITS: 8,       // 是否允许编辑网卡
  ISO_EDITS: 16,      // 是否允许编辑光盘
  HDD_EDITS: 32,      // 是否允许编辑硬盘
  NET_EDITS: 64,      // 是否允许编辑网络
  WEB_EDITS: 128,     // 是否允许编辑网页
  VNC_EDITS: 256,     // 是否允许控制桌面
  PCI_EDITS: 512,     // 是否允许编辑PCIe
  USB_EDITS: 1024,    // 是否允许编辑USBs
  VM_BACKUP: 2048,    // 是否允许备份还原
  EFI_EDITS: 4096,    // 是否允许管理启动顺序
  VM_MODIFY: 8192,    // 是否允许修改配置
  VM_DELETE: 16384,   // 是否允许删除实例
  FIREWALLS: 32768,   // 是否可编辑防火墙
  FULL_MASK: 65535,   // 全权限
} as const;

// 权限名称映射（用于UI展示）
export const VM_PERMISSION_LABELS: Record<string, string> = {
  pwr_edits: '编辑电源',
  pwd_edits: '编辑密码',
  sys_edits: '编辑系统',
  nic_edits: '编辑网卡',
  iso_edits: '编辑光盘',
  hdd_edits: '编辑硬盘',
  net_edits: '编辑网络',
  web_edits: '编辑网页',
  vnc_edits: '控制桌面',
  pci_edits: '编辑PCIe',
  usb_edits: '编辑USBs',
  vm_backup: '备份还原',
  efi_edits: '启动顺序',
  vm_modify: '修改配置',
  vm_delete: '删除实例',
  firewalls: '编辑防火墙',
};

// 权限字段到掩码位的映射
export const PERMISSION_FIELD_MASK: Record<string, number> = {
  pwr_edits: VM_PERMISSION.PWR_EDITS,
  pwd_edits: VM_PERMISSION.PWD_EDITS,
  sys_edits: VM_PERMISSION.SYS_EDITS,
  nic_edits: VM_PERMISSION.NIC_EDITS,
  iso_edits: VM_PERMISSION.ISO_EDITS,
  hdd_edits: VM_PERMISSION.HDD_EDITS,
  net_edits: VM_PERMISSION.NET_EDITS,
  web_edits: VM_PERMISSION.WEB_EDITS,
  vnc_edits: VM_PERMISSION.VNC_EDITS,
  pci_edits: VM_PERMISSION.PCI_EDITS,
  usb_edits: VM_PERMISSION.USB_EDITS,
  vm_backup: VM_PERMISSION.VM_BACKUP,
  efi_edits: VM_PERMISSION.EFI_EDITS,
  vm_modify: VM_PERMISSION.VM_MODIFY,
  vm_delete: VM_PERMISSION.VM_DELETE,
  firewalls: VM_PERMISSION.FIREWALLS,
};

// 检查权限掩码是否拥有指定权限
export function hasPermission(mask: number, permBit: number): boolean {
  return (mask & permBit) !== 0;
}

// Tab key 到所需权限的映射
export const TAB_PERMISSION_MAP: Record<string, number> = {
  ip: VM_PERMISSION.NIC_EDITS,
  hdd: VM_PERMISSION.HDD_EDITS,
  iso: VM_PERMISSION.ISO_EDITS,
  nat: VM_PERMISSION.NET_EDITS,
  proxy: VM_PERMISSION.WEB_EDITS,
  pci: VM_PERMISSION.PCI_EDITS,
  usb: VM_PERMISSION.USB_EDITS,
  backup: VM_PERMISSION.VM_BACKUP,
  efi: VM_PERMISSION.EFI_EDITS,
};

// 权限不足时直接隐藏的Tab（平台不支持此功能）
export const HIDDEN_TABS: Set<string> = new Set(['usb', 'pci', 'efi', 'owners']);

// 权限不足时仅只读的Tab（可查看但禁止操作）
export const READONLY_TABS: Set<string> = new Set(['ip', 'hdd', 'iso', 'nat', 'proxy', 'backup']);

// owners tab 仅管理员/主所有者可见（不受普通权限控制）
export const OWNER_ONLY_TABS: Set<string> = new Set(['owners']);