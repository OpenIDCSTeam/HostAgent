import React, { useEffect, useState } from 'react';
import { Card, Row, Col, Progress, Spin, message, Tag, Button, Empty, Tooltip } from 'antd';
import { useNavigate } from 'react-router-dom';
import { useUserStore } from '@/utils/data.ts';
import api, { getHosts } from '@/utils/apis.ts';
import PageHeader from '@/components/PageHeader';
import { VM_STATUS_MAP } from '@/constants/status';
import { 
  CpuChipIcon, 
  CircleStackIcon, 
  ServerIcon,
  GlobeAltIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  CubeIcon
} from '@heroicons/react/24/outline';
import {
  DesktopOutlined,
  PoweroffOutlined,
  EyeOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
  LoadingOutlined,
  QuestionCircleOutlined,
  CloudServerOutlined,
  RightOutlined
} from '@ant-design/icons';

const UserPanels: React.FC = () => {
  const navigate = useNavigate();
  const { user, setUser } = useUserStore();
  const [loading, setLoading] = useState(false);
  const [vmsLoading, setVmsLoading] = useState(false);
  const [vms, setVMs] = useState<Record<string, any>>({});

  useEffect(() => {
    fetchUserData();
    loadAllVMs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchUserData = async () => {
    setLoading(true);
    try {
      const res = await api.getCurrentUser();
      if (res.code === 200) {
        setUser(res.data || null);
      }
    } catch (error) {
      console.error('获取用户信息失败', error);
      message.error('获取用户信息失败');
    } finally {
      setLoading(false);
    }
  };

  const loadAllVMs = async () => {
    try {
      setVmsLoading(true);
      let allVMs: Record<string, any> = {};
      const hostsRes = await getHosts();
      if (hostsRes.code === 200 && hostsRes.data) {
        // 过滤掉未启用的主机，不请求其虚拟机列表
        const hostsData = hostsRes.data;
        const hosts = Object.keys(hostsData).filter(
          (host) => hostsData[host].enable_host !== false
        );
        await Promise.all(hosts.map(async (host) => {
          try {
            const vmsRes = await api.getVMs(host);
            if (vmsRes.code === 200 && vmsRes.data) {
              Object.entries(vmsRes.data).forEach(([uuid, vm]) => {
                allVMs[`${host}-${uuid}`] = { ...vm, _host: host, _realUuid: uuid };
              });
            }
          } catch (err) {
            console.error(`获取主机 ${host} 的虚拟机失败`, err);
          }
        }));
      }
      setVMs(allVMs);
    } catch (error) {
      message.error('加载虚拟机列表失败');
    } finally {
      setVmsLoading(false);
    }
  };

  if (!user) return <Spin />;

  // 智能单位换算（MB -> GB -> TB），超过0.95则进位
  const formatStorage = (mb: number): string => {
    if (mb === 0) return '0';
    if (mb < 1024 * 0.95) return `${Math.round(mb)} MB`;
    const gb = mb / 1024;
    if (gb < 1024 * 0.95) {
      if (gb >= 0.95 && gb < 1) return '1 GB';
      return `${gb >= 10 ? Math.round(gb) : (Math.round(gb * 10) / 10)} GB`;
    }
    const tb = gb / 1024;
    if (tb >= 0.95 && tb < 1) return '1 TB';
    return `${tb >= 10 ? Math.round(tb) : (Math.round(tb * 10) / 10)} TB`;
  };

  // 智能单位换算（带宽 Mbps -> Gbps -> Tbps），超过0.95则进位
  const formatBandwidth = (mbps: number): string => {
    if (mbps === 0) return '0';
    if (mbps < 1000 * 0.95) return `${Math.round(mbps)} M`;
    const gbps = mbps / 1000;
    if (gbps < 1000 * 0.95) {
      if (gbps >= 0.95 && gbps < 1) return '1 G';
      return `${gbps >= 10 ? Math.round(gbps) : (Math.round(gbps * 10) / 10)} G`;
    }
    const tbps = gbps / 1000;
    if (tbps >= 0.95 && tbps < 1) return '1 T';
    return `${tbps >= 10 ? Math.round(tbps) : (Math.round(tbps * 10) / 10)} T`;
  };

  // 智能数量换算，超过0.95则进位
  const formatCount = (count: number, unit: string): string => {
    if (count === 0) return '0';
    if (count >= 10000 * 0.95) {
      const wan = count / 10000;
      if (wan >= 0.95 && wan < 1) return `1万${unit}`;
      return `${wan >= 10 ? Math.round(wan) : (Math.round(wan * 10) / 10)}万${unit}`;
    }
    if (count >= 1000 * 0.95) {
      const k = count / 1000;
      if (k >= 0.95 && k < 1) return `1k${unit}`;
      return `${k >= 10 ? Math.round(k) : (Math.round(k * 10) / 10)}k${unit}`;
    }
    return `${Math.round(count)} ${unit}`;
  };

  // CPU核心数量换算（支持万核），超过0.95则进位
  const formatCpuCores = (cores: number): string => {
    if (cores === 0) return '0';
    if (cores >= 10000 * 0.95) {
      const wan = cores / 10000;
      if (wan >= 0.95 && wan < 1) return '1万核';
      return `${wan >= 10 ? Math.round(wan) : (Math.round(wan * 10) / 10)}万核`;
    }
    if (cores >= 1000 * 0.95) {
      const k = cores / 1000;
      if (k >= 0.95 && k < 1) return '1k核';
      return `${k >= 10 ? Math.round(k) : (Math.round(k * 10) / 10)}k核`;
    }
    return `${Math.round(cores)} 核`;
  };

  // 资源项数据
  const computeResources = [
    {
      title: 'CPU',
      used: user.used_cpu || 0,
      quota: user.quota_cpu || 0,
      unit: '核',
      icon: <CpuChipIcon style={{ width: '18px', height: '18px', color: '#3b82f6' }} />,
      color: '#3b82f6',
      formatter: formatCpuCores
    },
    {
      title: '内存',
      used: user.used_ram || 0,
      quota: user.quota_ram || 0,
      icon: <CircleStackIcon style={{ width: '18px', height: '18px', color: '#10b981' }} />,
      color: '#10b981',
      formatter: formatStorage
    },
    {
      title: '磁盘',
      used: user.used_ssd || 0,
      quota: user.quota_ssd || 0,
      icon: <ServerIcon style={{ width: '18px', height: '18px', color: '#8b5cf6' }} />,
      color: '#8b5cf6',
      formatter: formatStorage
    },
    ...(user.quota_gpu > 0 ? [{
      title: 'GPU',
      used: user.used_gpu || 0,
      quota: user.quota_gpu || 0,
      icon: <CubeIcon style={{ width: '18px', height: '18px', color: '#ec4899' }} />,
      color: '#ec4899',
      formatter: formatStorage
    }] : [])
  ];

  const networkResources = [
    {
      title: 'NAT',
      used: user.used_nat_ports || 0,
      quota: user.quota_nat_ports || 0,
      icon: <GlobeAltIcon style={{ width: '18px', height: '18px', color: '#6366f1' }} />,
      color: '#6366f1',
      formatter: (val: number) => formatCount(val, '')
    },
    {
      title: 'Web',
      used: user.used_web_proxy || 0,
      quota: user.quota_web_proxy || 0,
      icon: <GlobeAltIcon style={{ width: '18px', height: '18px', color: '#14b8a6' }} />,
      color: '#14b8a6',
      formatter: (val: number) => formatCount(val, '')
    },
    {
      title: '上行',
      used: user.used_bandwidth_up || 0,
      quota: user.quota_bandwidth_up || 0,
      icon: <ArrowUpIcon style={{ width: '18px', height: '18px', color: '#ef4444' }} />,
      color: '#ef4444',
      formatter: formatBandwidth
    },
    {
      title: '下行',
      used: user.used_bandwidth_down || 0,
      quota: user.quota_bandwidth_down || 0,
      icon: <ArrowDownIcon style={{ width: '18px', height: '18px', color: '#06b6d4' }} />,
      color: '#06b6d4',
      formatter: formatBandwidth
    }
  ];

  // 渲染资源项（卡片样式）
  const renderResourceItem = (item: any) => {
    const percent = item.quota > 0 ? Math.min(Math.round((item.used / item.quota) * 100), 100) : 0;
    const isUnlimited = item.quota > 1000000;
    
    const usedDisplay = item.formatter ? item.formatter(item.used) : `${item.used}`;
    const quotaDisplay = isUnlimited ? '∞' : (item.formatter ? item.formatter(item.quota) : `${item.quota}`);

    return (
      <Card 
        key={item.title}
        hoverable
        size="small"
        className="ant-card-bordered glass-effect"
        styles={{ body: { padding: '12px' } }}
        style={{ flex: '1 1 0', minWidth: '120px' }}
      >
        <div className="flex items-center gap-2">
          <div className="flex-shrink-0">{item.icon}</div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-gray-500 dark:text-gray-400">{item.title}</span>
              <span className="text-xs font-semibold" style={{ color: item.color }}>
                {usedDisplay} / {quotaDisplay}
              </span>
            </div>
            <Progress
              percent={isUnlimited ? 0 : percent}
              size="small"
              strokeColor={item.color}
              showInfo={false}
              style={{ margin: 0 }}
            />
          </div>
        </div>
      </Card>
    );
  };

  // 收集所有NAT端口和Web代理
  const allNatPorts: Array<{host: string, uuid: string, port: any, portKey: string}> = [];
  const allWebProxies: Array<{host: string, uuid: string, proxy: any, proxyKey: string}> = [];
  
  Object.entries(vms).forEach(([key, vm]: [string, any]) => {
    const config = vm.config || {};
    const vmHost = vm._host;
    const vmUuid = vm._realUuid || key;
    
    // 收集NAT端口 - nat_all 是对象，key为端口索引
    const natAll = config.nat_all || {};
    if (typeof natAll === 'object' && !Array.isArray(natAll)) {
      Object.entries(natAll).forEach(([portKey, nat]: [string, any]) => {
        allNatPorts.push({ host: vmHost, uuid: vmUuid, port: nat, portKey });
      });
    } else if (Array.isArray(natAll)) {
      natAll.forEach((nat: any, index: number) => {
        allNatPorts.push({ host: vmHost, uuid: vmUuid, port: nat, portKey: String(index) });
      });
    }
    
    // 收集Web代理 - web_all 是对象，key为代理索引
    const webAll = config.web_all || {};
    if (typeof webAll === 'object' && !Array.isArray(webAll)) {
      Object.entries(webAll).forEach(([proxyKey, web]: [string, any]) => {
        allWebProxies.push({ host: vmHost, uuid: vmUuid, proxy: web, proxyKey });
      });
    } else if (Array.isArray(webAll)) {
      webAll.forEach((web: any, index: number) => {
        allWebProxies.push({ host: vmHost, uuid: vmUuid, proxy: web, proxyKey: String(index) });
      });
    }
  });

  // 渲染端口卡片
  const renderPortCard = (item: {host: string, uuid: string, port: any, portKey: string}, index: number) => {
    const port = item.port;
    // 兼容不同字段名：wan_port/outer_port, lan_port/inner_port
    const outerPort = port.wan_port || port.outer_port || '-';
    const innerPort = port.lan_port || port.inner_port || '-';
    const portName = port.nat_tips || port.name || `端口${outerPort}`;
    const protocol = port.nat_type || port.protocol || 'TCP';
    
    return (
      <Card 
        key={`nat-${index}`}
        hoverable
        size="small"
        className="ant-card-bordered glass-effect cursor-pointer"
        styles={{ body: { padding: '12px' } }}
        onClick={() => navigate(`/hosts/${item.host}/vms/${item.uuid}`)}
      >
        <div className="flex items-center justify-between mb-1">
          <Tooltip title={portName}>
            <span className="text-xs font-semibold text-blue-600 dark:text-blue-400 truncate" style={{maxWidth: '100px'}}>
              {portName}
            </span>
          </Tooltip>
          <Tag color="blue" className="m-0 text-xs">{protocol}</Tag>
        </div>
        <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
          外:{outerPort} → 内:{innerPort}
        </div>
        <Tooltip title={item.uuid}>
          <div className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            {item.uuid}
          </div>
        </Tooltip>
      </Card>
    );
  };

  // 渲染Web代理卡片
  const renderProxyCard = (item: {host: string, uuid: string, proxy: any, proxyKey: string}, index: number) => {
    const proxy = item.proxy;
    // 兼容不同字段名
    const domain = proxy.domain || proxy.web_domain || '未配置域名';
    const backendPort = proxy.backend_port || proxy.inner_port || 80;
    const sslEnabled = proxy.ssl_enabled || proxy.https || false;
    const fullUrl = `${sslEnabled ? 'https' : 'http'}://${domain}`;
    
    return (
      <Card 
        key={`web-${index}`}
        hoverable
        size="small"
        className="ant-card-bordered glass-effect"
        styles={{ body: { padding: '12px' } }}
      >
        <div className="flex items-center justify-between mb-1">
          <Tooltip title={domain}>
            <span className="text-xs font-semibold text-purple-600 dark:text-purple-400 truncate" style={{maxWidth: '100px'}}>
              {domain}
            </span>
          </Tooltip>
          <div className="flex items-center gap-1">
            <Tag color={sslEnabled ? 'green' : 'orange'} className="m-0 text-xs">
              {sslEnabled ? 'HTTPS' : 'HTTP'}
            </Tag>
            <Tooltip title={`访问 ${fullUrl}`}>
              <Button
                type="link"
                size="small"
                className="p-0 h-auto text-xs"
                onClick={(e) => {
                  e.stopPropagation();
                  window.open(fullUrl, '_blank');
                }}
              >
                访问
              </Button>
            </Tooltip>
          </div>
        </div>
        <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
          → :{backendPort}
        </div>
        <Tooltip title={item.uuid}>
          <div 
            className="text-xs text-gray-400 dark:text-gray-500 mt-1 cursor-pointer hover:text-blue-500"
            onClick={() => navigate(`/hosts/${item.host}/vms/${item.uuid}`)}
          >
            {item.uuid}
          </div>
        </Tooltip>
      </Card>
    );
  };

  // 获取虚拟机状态图标
  const getStatusIcon = (powerStatus: string) => {
    switch (powerStatus) {
      case 'STARTED':
        return <PlayCircleOutlined className="text-green-600 dark:text-green-400" />;
      case 'STOPPED':
        return <PoweroffOutlined className="text-red-600 dark:text-red-400" />;
      case 'SUSPEND':
        return <PauseCircleOutlined className="text-yellow-600 dark:text-yellow-400" />;
      case 'ON_STOP':
      case 'ON_OPEN':
      case 'ON_SAVE':
      case 'ON_WAKE':
        return <LoadingOutlined className="text-blue-600 dark:text-blue-400" spin />;
      default:
        return <QuestionCircleOutlined />;
    }
  };

  // 渲染虚拟机概要卡片
  const renderVMCard = (key: string, vm: any) => {
    const config = vm.config || {};
    const statusList = vm.status || [];
    const firstStatus = statusList.length > 0 ? statusList[0] : { ac_status: 'UNKNOWN' };
    const powerStatus = firstStatus.ac_status || 'UNKNOWN';
    const statusInfo = VM_STATUS_MAP[powerStatus] || VM_STATUS_MAP.UNKNOWN;
    const vmHost = vm._host;
    const vmUuid = vm._realUuid || key;

    const cpuTotal = firstStatus.cpu_total || config.cpu_num || 0;
    const cpuUsage = firstStatus.cpu_usage || 0;
    const cpuPercent = cpuTotal > 0 ? Math.round((cpuUsage / cpuTotal) * 100) : 0;

    const memTotal = firstStatus.mem_total || config.mem_num || 0;
    const memUsage = firstStatus.mem_usage || 0;
    const memPercent = memTotal > 0 ? Math.round((memUsage / memTotal) * 100) : 0;

    const nicAll = config.nic_all || {};
    const firstNic = Object.values(nicAll)[0] || {};
    // @ts-ignore
    const ipv4 = firstNic.ip4_addr || '-';

    const handleDetail = () => {
      navigate(`/hosts/${vmHost}/vms/${vmUuid}`);
    };

    return (
      <Col key={key} xs={24} sm={12} lg={8} xl={6}>
        <Card
          hoverable
          className="glass-effect"
          styles={{ body: { padding: '16px' } }}
          onClick={handleDetail}
        >
          {/* 头部：名称和状态 */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <div className="w-10 h-10 rounded-lg flex items-center justify-center border border-purple-600/30 dark:border-purple-400/30 flex-shrink-0">
                <DesktopOutlined className="text-xl text-purple-600 dark:text-purple-400" />
              </div>
              <div className="min-w-0 flex-1">
                <Tooltip title={vmUuid}>
                  <h4 className="m-0 text-sm font-bold truncate">{vmUuid}</h4>
                </Tooltip>
                <span className="text-xs text-gray-500">{config.os_name || '未知系统'}</span>
              </div>
            </div>
            <Tag color={statusInfo.color} icon={getStatusIcon(powerStatus)} className="m-0 flex-shrink-0">
              {statusInfo.text}
            </Tag>
          </div>

          {/* 资源使用 */}
          <div className="grid grid-cols-2 gap-2 mb-3">
            <div className="p-2 rounded-lg ">
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-gray-500">CPU</span>
                <span className="font-semibold">{cpuPercent}%</span>
              </div>
              <Progress percent={cpuPercent} size="small" strokeColor="#3b82f6" showInfo={false} />
            </div>
            <div className="p-2 rounded-lg ">
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-gray-500">内存</span>
                <span className="font-semibold">{memPercent}%</span>
              </div>
              <Progress percent={memPercent} size="small" strokeColor="#10b981" showInfo={false} />
            </div>
          </div>

          {/* 底部信息 */}
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              {vmHost && (
                <Tag icon={<CloudServerOutlined />} color="blue" className="m-0 text-xs">
                  {vmHost}
                </Tag>
              )}
              <span className="text-gray-500">{ipv4}</span>
            </div>
            <div className="flex items-center gap-1">
              <Tooltip title="VNC控制台">
                <Button 
                  type="text" 
                  size="small"
                  icon={<DesktopOutlined />}
                  disabled={powerStatus !== 'STARTED'}
                  className="hover:bg-purple-50 dark:hover:bg-purple-900/30"
                  onClick={(e) => {
                    e.stopPropagation();
                    window.open(`/hosts/${vmHost}/vms/${vmUuid}/vnc`, '_blank');
                  }}
                />
              </Tooltip>
              <Tooltip title="电源操作">
                <Button 
                  type="text" 
                  size="small"
                  icon={<PoweroffOutlined className={powerStatus === 'STARTED' ? 'text-green-500' : ''} />}
                  className="hover:bg-green-50 dark:hover:bg-green-900/30"
                  onClick={(e) => {
                    e.stopPropagation();
                    // 跳转到详情页的电源控制
                    handleDetail();
                  }}
                />
              </Tooltip>
              <Button 
                type="link" 
                size="small" 
                icon={<EyeOutlined />}
                className="p-0 h-auto"
                onClick={(e) => {
                  e.stopPropagation();
                  handleDetail();
                }}
              >
                详情
              </Button>
            </div>
          </div>
        </Card>
      </Col>
    );
  };

  const vmCount = Object.keys(vms).length;
  const runningCount = Object.values(vms).filter((vm: any) => {
    const statusList = vm.status || [];
    const firstStatus = statusList.length > 0 ? statusList[0] : { ac_status: 'UNKNOWN' };
    return firstStatus.ac_status === 'STARTED';
  }).length;

  return (
    <div className="p-6 min-h-screen">
      {/* 页面标题 */}
      <PageHeader
        icon={<CubeIcon style={{ width: '24px', height: '24px' }} />}
        title="资源概览"
        subtitle="查看您的资源使用情况和虚拟机状态"
      />
      
      <Spin spinning={loading}>
        {/* 资源概况 */}
        <div className="mb-6">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-lg font-semibold text-gray-800 dark:text-gray-200">📊 资源概况</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {computeResources.map(renderResourceItem)}
            {networkResources.map(renderResourceItem)}
          </div>
        </div>

        {/* 端口转发概要 */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <span className="text-lg font-semibold text-gray-800 dark:text-gray-200">🔗 端口转发</span>
              <Tag color="blue">{allNatPorts.length} 个</Tag>
            </div>
          </div>
          {allNatPorts.length === 0 ? (
            <div className="text-center py-6 text-gray-400 border border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
              暂无端口转发
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              {allNatPorts.slice(0, allNatPorts.length > 5 ? 4 : 5).map((item, index) => renderPortCard(item, index))}
              {allNatPorts.length > 5 && (
                <div 
                  className="p-3 rounded-lg border-2 border-dashed border-blue-300 dark:border-blue-600 bg-blue-50/50 dark:bg-blue-900/20 hover:border-blue-500 transition-colors cursor-pointer flex flex-col items-center justify-center"
                  onClick={() => navigate('/user/vms')}
                >
                  <RightOutlined className="text-2xl text-blue-500 mb-1" />
                  <span className="text-xs text-blue-600 dark:text-blue-400 font-semibold">查看全部</span>
                  <span className="text-xs text-blue-500">{allNatPorts.length} 个</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* 反向代理概要 */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <span className="text-lg font-semibold text-gray-800 dark:text-gray-200">🌐 反向代理</span>
              <Tag color="purple">{allWebProxies.length} 个</Tag>
            </div>
          </div>
          {allWebProxies.length === 0 ? (
            <div className="text-center py-6 text-gray-400 border border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
              暂无反向代理
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              {allWebProxies.slice(0, allWebProxies.length > 5 ? 4 : 5).map((item, index) => renderProxyCard(item, index))}
              {allWebProxies.length > 5 && (
                <div 
                  className="p-3 rounded-lg border-2 border-dashed border-purple-300 dark:border-purple-600 bg-purple-50/50 dark:bg-purple-900/20 hover:border-purple-500 transition-colors cursor-pointer flex flex-col items-center justify-center"
                  onClick={() => navigate('/user/vms')}
                >
                  <RightOutlined className="text-2xl text-purple-500 mb-1" />
                  <span className="text-xs text-purple-600 dark:text-purple-400 font-semibold">查看全部</span>
                  <span className="text-xs text-purple-500">{allWebProxies.length} 个</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* 虚拟机概要 */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <span className="text-lg font-semibold text-gray-800 dark:text-gray-200">🖥️ 实例概要</span>
              <Tag color="blue">{vmCount} 台</Tag>
              <Tag color="green">{runningCount} 运行中</Tag>
            </div>
            <Button 
              type="link" 
              onClick={() => navigate('/user/vms')}
              className="flex items-center gap-1"
            >
              管理全部虚拟机 <RightOutlined />
            </Button>
          </div>

          <Spin spinning={vmsLoading}>
            {vmCount === 0 ? (
              <Empty 
                description="暂无虚拟机" 
                className="py-12 glass-card-enhanced rounded-2xl"
                style={{
                  background: 'var(--card-bg)',
                  border: '1px solid var(--border-color)',
                }}
              >
                <Button type="primary" onClick={() => navigate('/user/vms')}>
                  创建虚拟机
                </Button>
              </Empty>
            ) : (
              <Row gutter={[16, 16]}>
                {Object.entries(vms).slice(0, vmCount > 12 ? 11 : 12).map(([key, vm]) => renderVMCard(key, vm))}
                {vmCount > 12 && (
                  <Col xs={24} sm={12} lg={8} xl={6}>
                    <Card
                      hoverable
                      className="glass-effect h-full flex flex-col items-center justify-center cursor-pointer border-2 border-dashed border-blue-300 dark:border-blue-600 bg-blue-50/30 dark:bg-blue-900/20 hover:border-blue-500 transition-colors"
                      styles={{ body: { padding: '24px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: '180px' } }}
                      onClick={() => navigate('/user/vms')}
                    >
                      <div className="text-4xl text-blue-400 dark:text-blue-500 mb-3">···</div>
                      <div className="text-lg font-semibold text-blue-600 dark:text-blue-400 mb-1">管理更多实例</div>
                      <div className="text-sm text-blue-500">还有 {vmCount - 11} 台虚拟机</div>
                      <Button 
                        type="primary" 
                        icon={<RightOutlined />}
                        className="mt-3"
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate('/user/vms');
                        }}
                      >
                        查看全部
                      </Button>
                    </Card>
                  </Col>
                )}
              </Row>
            )}
          </Spin>
        </div>
      </Spin>
    </div>
  );
};

export default UserPanels;
