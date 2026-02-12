import { http } from '@/utils/axio.ts';
import type {
  ApiResponse,
  User,
  LoginRequest,
  Host,
  VM,
  CreateVMRequest,
  VMPowerAction,
  NATRule,
  ProxyConfig,
  SystemStats,
  PaginationParams,
} from '@/types';

// ============================================================================
// 认证相关API
// ============================================================================

/**
 * 用户登录
 */
export const login = (data: LoginRequest): Promise<ApiResponse<{ token: string; user_info: User }>> => {
  return http.post('/api/login', data);
};

/**
 * 用户登出
 */
export const logout = (): Promise<ApiResponse> => {
  return http.get('/api/logout');
};

/**
 * 获取当前用户信息
 */
export const getCurrentUser = (): Promise<ApiResponse<User>> => {
  return http.get('/api/users/current');
};

/**
 * 找回密码
 */
export const forgotPassword = (email: string): Promise<ApiResponse> => {
  return http.post('/api/system/forgot-password', { email });
};

/**
 * 重置密码
 */
export const resetPassword = (data: { token: string; new_password: string; confirm_password: string }): Promise<ApiResponse> => {
  return http.post('/api/system/reset-password', data);
};

// ============================================================================
// 系统管理API
// ============================================================================

/**
 * 获取系统统计信息
 */
export const getSystemStats = (): Promise<ApiResponse<SystemStats>> => {
  return http.get('/api/system/stats');
};

/**
 * 获取支持的引擎类型
 */
export const getEngineTypes = (): Promise<ApiResponse<any[]>> => {
  return http.get('/api/system/engine');
};

/**
 * 获取当前Token
 */
export const getCurrentToken = (): Promise<ApiResponse<{ token: string }>> => {
  return http.get('/api/token/current');
};

/**
 * 设置新Token
 */
export const setToken = (token: string): Promise<ApiResponse<{ token: string }>> => {
  return http.post('/api/token/set', { token });
};

/**
 * 重置Token
 */
export const resetToken = (): Promise<ApiResponse<{ token: string }>> => {
  return http.post('/api/token/reset');
};

// ============================================================================
// 主机管理API
// ============================================================================

/**
 * 获取主机列表
 */
export const getHosts = (): Promise<ApiResponse<Record<string, Host>>> => {
  return http.get('/api/server/detail');
};

/**
 * 获取单个主机详情
 */
export const getHostDetail = (hsName: string): Promise<ApiResponse<Host>> => {
  return http.get(`/api/server/detail/${hsName}`);
};

/**
 * 添加主机
 */
export const createHost = (data: Partial<Host> & { server_pass: string }): Promise<ApiResponse> => {
  return http.post('/api/server/create', data);
};

/**
 * 更新主机配置
 */
export const updateHost = (hsName: string, data: Partial<Host>): Promise<ApiResponse> => {
  return http.put(`/api/server/update/${hsName}`, data);
};

/**
 * 删除主机
 */
export const deleteHost = (hsName: string): Promise<ApiResponse> => {
  return http.delete(`/api/server/delete/${hsName}`);
};

/**
 * 主机电源控制
 */
export const hostPower = (hsName: string, action: string): Promise<ApiResponse> => {
  return http.post(`/api/server/powers/${hsName}`, { action });
};

/**
 * 启用/禁用主机
 */
export const setHostEnabled = (hsName: string, enable: boolean): Promise<ApiResponse> => {
  return http.post(`/api/server/powers/${hsName}`, { enable });
};

/**
 * 获取主机状态
 */
export const getHostStatus = (hsName: string): Promise<ApiResponse> => {
  return http.get(`/api/server/status/${hsName}`);
};

/**
 * 获取主机的操作系统镜像列表
 */
export const getOSImages = (hsName: string): Promise<ApiResponse<Record<string, any[]>>> => {
  return http.get(`/api/client/os-images/${hsName}`);
};

/**
 * 获取主机GPU列表（兼容旧接口）
 */
export const getGPUList = (hsName: string): Promise<ApiResponse<Record<string, any>>> => {
  return http.get(`/api/client/gpu-list/${hsName}`);
};

/**
 * 获取主机可直通PCI设备列表
 */
export const getPCIList = (hsName: string): Promise<ApiResponse<Record<string, { gpu_uuid: string; gpu_mdev: string; gpu_hint: string }>>> => {
  return http.get(`/api/client/pci-list/${hsName}`, { timeout: 300000 });
};

/**
 * PCI设备直通操作（需要关机）
 */
export const setupPCI = (hsName: string, vmUuid: string, data: {
  pci_key: string; gpu_uuid: string; gpu_mdev: string; gpu_hint: string; action: 'add' | 'remove';
}): Promise<ApiResponse> => {
  return http.post(`/api/client/pci/setup/${hsName}/${vmUuid}`, data);
};

/**
 * 获取主机可用USB设备列表
 */
export const getUSBList = (hsName: string): Promise<ApiResponse<Record<string, { vid_uuid: string; pid_uuid: string; usb_hint: string }>>> => {
  return http.get(`/api/client/usb-list/${hsName}`);
};

/**
 * USB设备直通操作（无需关机）
 */
export const setupUSB = (hsName: string, vmUuid: string, data: {
  usb_key: string; vid_uuid: string; pid_uuid: string; usb_hint: string; action: 'add' | 'remove';
}): Promise<ApiResponse> => {
  return http.post(`/api/client/usb/setup/${hsName}/${vmUuid}`, data);
};

// ============================================================================
// 虚拟机管理API
// ============================================================================

/**
 * 获取虚拟机列表
 */
export const getVMs = (hsName: string): Promise<ApiResponse<VM[]>> => {
  return http.get(`/api/client/detail/${hsName}`);
};

/**
 * 获取虚拟机详情
 */
export const getVMDetail = (hsName: string, vmUuid: string): Promise<ApiResponse<VM>> => {
  return http.get(`/api/client/detail/${hsName}/${vmUuid}`);
};

/**
 * 创建虚拟机
 */
export const createVM = (hsName: string, data: CreateVMRequest): Promise<ApiResponse> => {
  return http.post(`/api/client/create/${hsName}`, data);
};

/**
 * 更新虚拟机配置
 */
export const updateVM = (hsName: string, vmUuid: string, data: Partial<CreateVMRequest>): Promise<ApiResponse> => {
  return http.put(`/api/client/update/${hsName}/${vmUuid}`, data);
};

/**
 * 删除虚拟机
 */
export const deleteVM = (hsName: string, vmUuid: string, force = false): Promise<ApiResponse> => {
  return http.delete(`/api/client/delete/${hsName}/${vmUuid}?force=${force}`);
};

/**
 * 虚拟机电源控制
 */
export const vmPower = (hsName: string, vmUuid: string, action: VMPowerAction): Promise<ApiResponse> => {
  return http.post(`/api/client/powers/${hsName}/${vmUuid}`, { action });
};

/**
 * 获取虚拟机状态
 */
export const getVMStatus = (hsName: string, vmUuid: string): Promise<ApiResponse> => {
  return http.get(`/api/client/status/${hsName}/${vmUuid}`);
};

/**
 * 扫描主机虚拟机
 */
export const scanVMs = (hsName: string): Promise<ApiResponse> => {
  return http.post(`/api/client/scaner/${hsName}`);
};

/**
 * 获取控制台访问地址
 */
export const getVMConsole = (hsName: string, vmUuid: string): Promise<ApiResponse<{ console_url: string; terminal_url: string }>> => {
  return http.get(`/api/client/remote/${hsName}/${vmUuid}`);
};

/**
 * 修改虚拟机密码
 */
export const changeVMPassword = (hsName: string, vmUuid: string, data: { password?: string; vnc_password?: string }): Promise<ApiResponse> => {
  return http.post(`/api/client/reset/${hsName}/${vmUuid}`, data);
};

/**
 * 重装系统
 */
export const reinstallVM = (hsName: string, vmUuid: string, data: { os_name: string; password?: string }): Promise<ApiResponse> => {
  return http.post(`/api/client/reinstall/${hsName}/${vmUuid}`, data);
};

/**
 * 获取虚拟机IP地址列表
 */
export const getVMIPAddresses = (hsName: string, vmUuid: string): Promise<ApiResponse<any[]>> => {
  return http.get(`/api/hosts/${hsName}/vms/${vmUuid}/ip_addresses`);
};

/**
 * 添加IP地址
 */
export const addIPAddress = (hsName: string, vmUuid: string, data: any): Promise<ApiResponse> => {
  return http.post(`/api/hosts/${hsName}/vms/${vmUuid}/ip_addresses`, data);
};

/**
 * 删除IP地址
 */
export const deleteIPAddress = (hsName: string, vmUuid: string, nicName: string): Promise<ApiResponse> => {
  return http.delete(`/api/hosts/${hsName}/vms/${vmUuid}/ip_addresses/${nicName}`);
};

/**
 * 获取虚拟机监控数据
 */
export const getVMMonitorData = (hsName: string, vmUuid: string, range: number): Promise<ApiResponse<any>> => {
  return http.get(`/api/client/status/${hsName}/${vmUuid}?limit=${range}`);
};

/**
 * 获取虚拟机截图
 */
export const getVMScreenshot = (hsName: string, vmUuid: string): Promise<ApiResponse<{ screenshot: string }>> => {
  return http.get(`/api/client/screenshot/${hsName}/${vmUuid}`, { silent: true });
};

/**
 * 获取虚拟机备份列表
 */
export const getVMBackups = (hsName: string, vmUuid: string): Promise<ApiResponse<any[]>> => {
  return http.get(`/api/client/detail/${hsName}/${vmUuid}`);
};

/**
 * 创建虚拟机备份
 */
export const createVMBackup = (hsName: string, vmUuid: string, data: { vm_tips: string }): Promise<ApiResponse> => {
  return http.post(`/api/client/backup/create/${hsName}/${vmUuid}`, data);
};

/**
 * 还原虚拟机备份
 */
export const restoreVMBackup = (hsName: string, vmUuid: string, backupName: string): Promise<ApiResponse> => {
  return http.post(`/api/client/backup/restore/${hsName}/${vmUuid}`, { vm_back: backupName });
};

/**
 * 删除虚拟机备份
 */
export const deleteVMBackup = (hsName: string, vmUuid: string, backupName: string): Promise<ApiResponse> => {
  return http.delete(`/api/client/backup/delete/${hsName}/${vmUuid}`, { data: { vm_back: backupName } });
};

// ============================================================================
// ISO管理API
// ============================================================================

/**
 * 获取虚拟机ISO挂载列表
 */
export const getVMISOs = (hsName: string, vmUuid: string): Promise<ApiResponse<any[]>> => {
  return http.get(`/api/client/detail/${hsName}/${vmUuid}`);
};

/**
 * 挂载ISO
 */
export const addISO = (hsName: string, vmUuid: string, data: { iso_name: string; iso_file: string; iso_hint?: string }): Promise<ApiResponse> => {
  return http.post(`/api/client/iso/mount/${hsName}/${vmUuid}`, data);
};

/**
 * 卸载ISO
 */
export const deleteISO = (hsName: string, vmUuid: string, isoName: string): Promise<ApiResponse> => {
  return http.delete(`/api/client/iso/unmount/${hsName}/${vmUuid}/${isoName}`);
};

// ============================================================================
// USB管理API
// ============================================================================

/**
 * 添加USB设备
 */
export const addUSB = (hsName: string, vmUuid: string, data: { usb_vid: string; usb_pid: string; usb_remark?: string }): Promise<ApiResponse> => {
  return http.post(`/api/client/usb/mount/${hsName}/${vmUuid}`, data);
};

/**
 * 删除USB设备
 */
export const deleteUSB = (hsName: string, vmUuid: string, usbKey: string): Promise<ApiResponse> => {
  return http.delete(`/api/client/usb/delete/${hsName}/${vmUuid}/${usbKey}`);
};

// ============================================================================
// EFI启动项管理API
// ============================================================================

/**
 * 获取虚拟机启动项列表
 */
export const getEFIList = (hsName: string, vmUuid: string): Promise<ApiResponse<{ efi_type: boolean; efi_name: string }[]>> => {
  return http.get(`/api/client/efi-list/${hsName}/${vmUuid}`);
};

/**
 * 设置虚拟机启动项顺序
 */
export const setupEFI = (hsName: string, vmUuid: string, efiList: { efi_type: boolean; efi_name: string }[]): Promise<ApiResponse> => {
  return http.post(`/api/client/efi/setup/${hsName}/${vmUuid}`, { efi_list: efiList });
};

// ============================================================================
// 硬盘管理API
// ============================================================================

/**
 * 获取虚拟机硬盘列表
 */
export const getVMHDDs = (hsName: string, vmUuid: string): Promise<ApiResponse<any[]>> => {
  return http.get(`/api/client/detail/${hsName}/${vmUuid}`);
};

/**
 * 添加硬盘
 */
export const addHDD = (hsName: string, vmUuid: string, data: { hdd_size: number; hdd_name: string; hdd_type?: number }): Promise<ApiResponse> => {
  return http.post(`/api/client/hdd/mount/${hsName}/${vmUuid}`, data);
};

/**
 * 删除硬盘
 */
export const deleteHDD = (hsName: string, vmUuid: string, hddIndex: number): Promise<ApiResponse> => {
  return http.delete(`/api/client/hdd/delete/${hsName}/${vmUuid}/${hddIndex}`);
};

/**
 * 获取虚拟机分享用户
 */
export const getVMOwners = (hsName: string, vmUuid: string): Promise<ApiResponse<any[]>> => {
  return http.get(`/api/client/owners/${hsName}/${vmUuid}`);
};

/**
 * 添加虚拟机分享用户
 */
export const addVMOwner = (hsName: string, vmUuid: string, data: { username: string }): Promise<ApiResponse> => {
  return http.post(`/api/client/owners/${hsName}/${vmUuid}`, data);
};

/**
 * 删除虚拟机分享用户
 */
export const deleteVMOwner = (hsName: string, vmUuid: string, username: string): Promise<ApiResponse> => {
  return http.delete(`/api/client/owners/${hsName}/${vmUuid}`, { data: { username } });
};

/**
 * 更新虚拟机所有者权限
 */
export const updateVMOwnerPermission = (hsName: string, vmUuid: string, username: string, permission: number): Promise<ApiResponse> => {
  return http.put(`/api/client/owners/${hsName}/${vmUuid}/permission`, { username, permission });
};

// ============================================================================
// 网络管理API
// ============================================================================

/**
 * 获取NAT规则
 */
export const getNATRules = (hsName: string, vmUuid: string): Promise<ApiResponse<NATRule[]>> => {
  return http.get(`/api/client/natget/${hsName}/${vmUuid}`);
};

/**
 * 添加NAT规则
 */
export const addNATRule = (hsName: string, vmUuid: string, data: Omit<NATRule, 'rule_index' | 'enabled' | 'created_time'>): Promise<ApiResponse> => {
  return http.post(`/api/client/natadd/${hsName}/${vmUuid}`, data);
};

/**
 * 删除NAT规则
 */
export const deleteNATRule = (hsName: string, vmUuid: string, ruleIndex: number): Promise<ApiResponse> => {
  return http.delete(`/api/client/natdel/${hsName}/${vmUuid}/${ruleIndex}`);
};

/**
 * 获取反向代理配置
 */
export const getProxyConfigs = (hsName: string, vmUuid: string): Promise<ApiResponse<ProxyConfig[]>> => {
  return http.get(`/api/client/proxys/detail/${hsName}/${vmUuid}`);
};

/**
 * 添加反向代理配置
 */
export const addProxyConfig = (hsName: string, vmUuid: string, data: Omit<ProxyConfig, 'proxy_index' | 'enabled'>): Promise<ApiResponse> => {
  return http.post(`/api/client/proxys/create/${hsName}/${vmUuid}`, data);
};

/**
 * 删除反向代理配置
 */
export const deleteProxyConfig = (hsName: string, vmUuid: string, proxyIndex: number): Promise<ApiResponse> => {
  return http.delete(`/api/client/proxys/delete/${hsName}/${vmUuid}/${proxyIndex}`);
};

// ============================================================================
// Web反向代理管理API
// ============================================================================

/**
 * 获取所有Web反向代理列表
 */
export const getWebProxys = (): Promise<ApiResponse<{ list: any[] }>> => {
  return http.get('/api/client/proxys/list');
};

/**
 * 创建Web反向代理
 */
export const createWebProxy = (
  hsName: string,
  vmUuid: string,
  data: {
    domain: string;
    backend_ip?: string;
    backend_port: number;
    ssl_enabled?: boolean;
    description?: string;
  }
): Promise<ApiResponse> => {
  return http.post(`/api/client/proxys/create/${hsName}/${vmUuid}`, data);
};

/**
 * 更新Web反向代理
 */
export const updateWebProxy = (
  hsName: string,
  vmUuid: string,
  proxyIndex: number,
  data: {
    domain: string;
    backend_ip?: string;
    backend_port: number;
    ssl_enabled?: boolean;
    description?: string;
  }
): Promise<ApiResponse> => {
  return http.put(`/api/client/proxys/update/${hsName}/${vmUuid}/${proxyIndex}`, data);
};

/**
 * 删除Web反向代理
 */
export const deleteWebProxy = (
  hsName: string,
  vmUuid: string,
  proxyIndex: number
): Promise<ApiResponse> => {
  return http.delete(`/api/client/proxys/delete/${hsName}/${vmUuid}/${proxyIndex}`);
};

// ============================================================================
// 用户管理API
// ============================================================================

/**
 * 获取用户列表
 */
export const getUsers = (params?: PaginationParams): Promise<ApiResponse<User[]>> => {
  return http.get('/api/users', { params });
};

/**
 * 创建用户
 */
export const createUser = (data: Partial<User> & { password: string }): Promise<ApiResponse> => {
  return http.post('/api/users', data);
};

/**
 * 更新用户信息
 */
export const updateUser = (userId: number, data: Partial<User>): Promise<ApiResponse> => {
  return http.put(`/api/users/${userId}`, data);
};

/**
 * 删除用户
 */
export const deleteUser = (userId: number): Promise<ApiResponse> => {
  return http.delete(`/api/users/${userId}`);
};

/**
 * 修改用户邮箱
 */
export const changeEmail = (newEmail: string): Promise<ApiResponse> => {
  return http.post('/api/users/change-email', { new_email: newEmail });
};

/**
 * 修改用户密码
 */
export const changePassword = (newPassword: string, confirmPassword: string): Promise<ApiResponse> => {
  return http.post('/api/users/change-password', { new_password: newPassword, confirm_password: confirmPassword });
};

// ============================================================================
// 任务管理API
// ============================================================================

/**
 * 获取任务列表
 */
export const getTasks = (hsName: string, limit?: number): Promise<ApiResponse<any[]>> => {
  const params = limit ? { limit } : {};
  return http.get(`/api/tasks/${hsName}`, { params });
};

// ============================================================================
// 备份管理API
// ============================================================================

/**
 * 获取系统日志详情
 */
export const getLoggerDetail = (): Promise<ApiResponse<any[]>> => {
  return http.get('/api/system/logger/detail');
};

/**
 * 清空系统日志
 */
export const clearLogs = (hsName?: string): Promise<ApiResponse> => {
  const params = hsName ? { hs_name: hsName } : {};
  return http.post('/api/system/logger/clear', null, { params });
};

/**
 * 获取系统设置
 */
export const getSystemSettings = (): Promise<ApiResponse<any>> => {
  return http.get('/api/system/settings');
};

/**
 * 保存系统设置
 */
export const saveSystemSettings = (data: any): Promise<ApiResponse> => {
  return http.post('/api/system/settings', data);
};

/**
 * 保存系统配置
 */
export const saveSystemConfig = (): Promise<ApiResponse> => {
  return http.post('/api/system/config/save');
};

/**
 * 加载系统配置
 */
export const loadSystemConfig = (): Promise<ApiResponse> => {
  return http.post('/api/system/config/load');
};

/**
 * 更新系统设置
 */
export const updateSystemSettings = (data: any): Promise<ApiResponse> => {
  return http.put('/api/system/settings', data);
};

/**
 * 发送测试邮件
 */
export const sendTestEmail = (data: { recipient: string; subject?: string; body?: string }): Promise<ApiResponse> => {
  return http.post('/api/system/test-email', data);
};



/**
 * 扫描主机备份文件
 */
export const scanBackups = (hsName: string): Promise<ApiResponse> => {
  return http.post(`/api/server/backup/scan/${hsName}`);
};

// ============================================================================
// 默认导出
// ============================================================================

/**
 * 默认导出所有API函数
 * 支持 import api from '@/services/api' 的使用方式
 */
export default {
  // 认证相关
  login,
  logout,
  getCurrentUser,
  forgotPassword,
  resetPassword,
  
  // 系统管理
  getSystemStats,
  getEngineTypes,
  getCurrentToken,
  setToken,
  resetToken,
  getLoggerDetail,
  clearLogs,
  getSystemSettings,
  saveSystemSettings,
  
  // 主机管理
  getHosts,
  getHostDetail,
  createHost,
  updateHost,
  deleteHost,
  hostPower,
  setHostEnabled,
  getHostStatus,
  getOSImages,
  getGPUList,
  getPCIList,
  setupPCI,
  getUSBList,
  setupUSB,
  
  // 虚拟机管理
  getVMs,
  getVMDetail,
  createVM,
  updateVM,
  deleteVM,
  vmPower,
  getVMStatus,
  scanVMs,
  getVMConsole,
  changeVMPassword,
  reinstallVM,
  getVMIPAddresses,
  addIPAddress,
  deleteIPAddress,
  getVMMonitorData,
  getVMScreenshot,
  getVMHDDs,
  addHDD,
  deleteHDD,
  getVMISOs,
  addISO,
  deleteISO,
  addUSB,
  deleteUSB,
  getVMBackups,
  createVMBackup,
  restoreVMBackup,
  deleteVMBackup,
  getVMOwners,
  addVMOwner,
  deleteVMOwner,
  updateVMOwnerPermission,
  
  // EFI启动项管理
  getEFIList,
  setupEFI,
  
  // 网络管理
  getNATRules,
  addNATRule,
  deleteNATRule,
  getProxyConfigs,
  addProxyConfig,
  deleteProxyConfig,
  
  // Web反向代理管理
  getWebProxys,
  createWebProxy,
  updateWebProxy,
  deleteWebProxy,
  
  // 用户管理
  getUsers,
  createUser,
  updateUser,
  deleteUser,
  changeEmail,
  changePassword,
  
  // 任务管理
  getTasks,
  
  // 备份管理
  scanBackups,
  
  // 系统配置
  saveSystemConfig,
  loadSystemConfig,
  updateSystemSettings,
  sendTestEmail,
  
  // HTTP方法（用于自定义请求）
  ...http,
};
