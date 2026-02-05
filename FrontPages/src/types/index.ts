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
