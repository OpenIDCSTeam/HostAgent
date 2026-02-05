import React, { useEffect, useState } from 'react';
import { Card, Typography, Button, message, Tag, Row, Col, Empty, Spin } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { 
  GlobeAltIcon, 
  ServerIcon, 
  ShieldCheckIcon,
  LinkIcon,
  ArrowTopRightOnSquareIcon
} from '@heroicons/react/24/outline';
import api from '@/utils/apis.ts';
import { ProxyConfig } from '@/types';

const { Title, Text } = Typography;

interface UserProxy extends ProxyConfig {
  hostName: string;
  vmUuid: string;
}

const UserProxys: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [proxies, setProxies] = useState<UserProxy[]>([]);

  useEffect(() => {
    fetchProxies();
  }, []);

  const fetchProxies = async () => {
    setLoading(true);
    try {
      // 1. 获取所有主机
      const hostsRes = await api.getHosts();
      if (hostsRes.code !== 200 || !hostsRes.data) {
        throw new Error('获取主机列表失败');
      }
      const hosts = Object.keys(hostsRes.data);

      const allProxies: UserProxy[] = [];

      // 2. 遍历主机获取VMs
      for (const hostName of hosts) {
        try {
          const vmsRes = await api.getVMs(hostName);
          if (vmsRes.code === 200 && vmsRes.data) {
            const vms = Array.isArray(vmsRes.data) ? vmsRes.data : Object.values(vmsRes.data);

            // 3. 遍历VMs获取Proxies
            await Promise.all(vms.map(async (vm: any) => {
              const vmUuid = vm.config?.vm_uuid || vm.uuid;
              try {
                const proxyRes = await api.getProxyConfigs(hostName, vmUuid);
                if (proxyRes.code === 200 && proxyRes.data) {
                  proxyRes.data.forEach((p: ProxyConfig) => {
                    allProxies.push({
                      ...p,
                      hostName,
                      vmUuid
                    });
                  });
                }
              } catch (e) {
                // 忽略错误
              }
            }));
          }
        } catch (e) {
          console.error(`获取主机 ${hostName} 数据失败`, e);
        }
      }

      setProxies(allProxies);
    } catch (error) {
      console.error('获取反向代理失败', error);
      message.error('获取数据失败');
    } finally {
      setLoading(false);
    }
  };

  // 统计数据
  const stats = {
    total: proxies.length,
    http: proxies.filter(p => !p.proxy_type || p.proxy_type === 'http').length,
    https: proxies.filter(p => p.proxy_type === 'https').length,
    enabled: proxies.filter(p => p.enabled).length,
    disabled: proxies.filter(p => !p.enabled).length,
  };

  // 统计卡片组件
  const StatCard = ({ 
    icon, 
    title, 
    value, 
    gradient, 
    delay 
  }: { 
    icon: React.ReactNode; 
    title: string; 
    value: number; 
    gradient: string;
    delay: number;
  }) => (
    <Card
      hoverable
      className="glass-medium"
      style={{
        height: '100%',
        animation: `fadeInUp 0.6s ease-out ${delay}s both`,
        transition: 'all 0.3s ease',
      }}
      styles={{ body: { padding: '24px' } }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-4px)';
        e.currentTarget.style.boxShadow = '0 12px 24px rgba(0, 0, 0, 0.15)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)';
        e.currentTarget.style.boxShadow = '';
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div
          style={{
            width: '56px',
            height: '56px',
            borderRadius: '12px',
            background: gradient,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          {icon}
        </div>
        <div style={{ flex: 1 }}>
          <Text type="secondary" style={{ fontSize: '14px', display: 'block', marginBottom: '4px', color: 'var(--text-secondary)' }}>
            {title}
          </Text>
          <div style={{ fontSize: '28px', fontWeight: 600, lineHeight: 1, color: 'var(--text-primary)' }}>
            {value}
          </div>
        </div>
      </div>
    </Card>
  );

  // 代理卡片组件
  const ProxyCard = ({ proxy, index }: { proxy: UserProxy; index: number }) => {
    const protocol = proxy.proxy_type === 'https' ? 'https' : 'http';
    const url = `${protocol}://${proxy.domain}`;

    return (
      <Card
        hoverable
        className="glass-light"
        style={{
          height: '100%',
          animation: `fadeInUp 0.6s ease-out ${0.1 + index * 0.05}s both`,
          transition: 'all 0.3s ease',
        }}
        styles={{ body: { padding: '20px' } }}
        onMouseEnter={(e) => {
          e.currentTarget.style.transform = 'translateY(-4px)';
          e.currentTarget.style.boxShadow = '0 12px 24px rgba(0, 0, 0, 0.15)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = 'translateY(0)';
          e.currentTarget.style.boxShadow = '';
        }}
      >
        {/* 状态标签 */}
        <div style={{ marginBottom: '16px' }}>
          <Tag color={proxy.enabled ? 'success' : 'error'} style={{ fontSize: '12px' }}>
            {proxy.enabled ? '✓ 已启用' : '✕ 已禁用'}
          </Tag>
          <Tag color={proxy.proxy_type === 'https' ? 'blue' : 'orange'} style={{ fontSize: '12px' }}>
            {proxy.proxy_type?.toUpperCase() || 'HTTP'}
          </Tag>
        </div>

        {/* 域名 */}
        <div style={{ marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <GlobeAltIcon style={{ width: '18px', height: '18px', color: 'var(--accent-primary)' }} />
            <Text strong style={{ fontSize: '16px', color: 'var(--text-primary)' }}>域名</Text>
          </div>
          <a 
            href={url} 
            target="_blank" 
            rel="noopener noreferrer"
            style={{ 
              fontSize: '14px', 
              display: 'flex', 
              alignItems: 'center', 
              gap: '6px',
              wordBreak: 'break-all'
            }}
          >
            {proxy.domain}
            <ArrowTopRightOnSquareIcon style={{ width: '14px', height: '14px', flexShrink: 0 }} />
          </a>
        </div>

        {/* 主机信息 */}
        <div style={{ marginBottom: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <ServerIcon style={{ width: '16px', height: '16px', color: 'var(--success)' }} />
            <Text type="secondary" style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>主机</Text>
          </div>
          <Text style={{ fontSize: '14px', marginLeft: '24px', color: 'var(--text-primary)' }}>{proxy.hostName}</Text>
        </div>

        {/* 虚拟机 UUID */}
        <div style={{ marginBottom: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <LinkIcon style={{ width: '16px', height: '16px', color: 'var(--accent-secondary)' }} />
            <Text type="secondary" style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>虚拟机</Text>
          </div>
          <Text 
            style={{ 
              fontSize: '13px', 
              marginLeft: '24px', 
              fontFamily: 'monospace',
              wordBreak: 'break-all',
              color: 'var(--text-primary)'
            }}
          >
            {proxy.vmUuid}
          </Text>
        </div>

        {/* 后端端口 */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <ShieldCheckIcon style={{ width: '16px', height: '16px', color: 'var(--warning)' }} />
            <Text type="secondary" style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>后端端口</Text>
          </div>
          <Text style={{ fontSize: '14px', marginLeft: '24px', fontFamily: 'monospace', color: 'var(--text-primary)' }}>
            :{proxy.backend_port}
          </Text>
        </div>
      </Card>
    );
  };

  return (
    <div style={{ padding: '24px', minHeight: '100vh' }}>
      <style>
        {`
          @keyframes fadeInUp {
            from {
              opacity: 0;
              transform: translateY(30px);
            }
            to {
              opacity: 1;
              transform: translateY(0);
            }
          }
        `}
      </style>

      {/* 页面标题 */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center', 
        marginBottom: '24px' 
      }}>
        <Title level={2} style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '12px', color: 'var(--text-primary)' }}>
          <ArrowTopRightOnSquareIcon style={{ width: '32px', height: '32px', color: 'var(--accent-primary)' }} />
          反向代理管理
        </Title>
        <Button 
          icon={<ReloadOutlined />} 
          onClick={fetchProxies} 
          loading={loading}
          size="large"
          type="primary"
        >
          刷新
        </Button>
      </div>

      {/* 统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: '24px' }}>
        <Col xs={24} sm={12} md={8} lg={6}>
          <StatCard
            icon={<GlobeAltIcon style={{ width: '28px', height: '28px', color: 'white' }} />}
            title="总代理数"
            value={stats.total}
            gradient="linear-gradient(135deg, #667eea 0%, #764ba2 100%)"
            delay={0}
          />
        </Col>
        <Col xs={24} sm={12} md={8} lg={6}>
          <StatCard
            icon={<ShieldCheckIcon style={{ width: '28px', height: '28px', color: 'white' }} />}
            title="HTTP 代理"
            value={stats.http}
            gradient="linear-gradient(135deg, #f093fb 0%, #f5576c 100%)"
            delay={0.1}
          />
        </Col>
        <Col xs={24} sm={12} md={8} lg={6}>
          <StatCard
            icon={<ShieldCheckIcon style={{ width: '28px', height: '28px', color: 'white' }} />}
            title="HTTPS 代理"
            value={stats.https}
            gradient="linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)"
            delay={0.2}
          />
        </Col>
        <Col xs={24} sm={12} md={8} lg={6}>
          <StatCard
            icon={<ServerIcon style={{ width: '28px', height: '28px', color: 'white' }} />}
            title="已启用"
            value={stats.enabled}
            gradient="linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)"
            delay={0.3}
          />
        </Col>
      </Row>

      {/* 代理列表 */}
      {loading ? (
        <Card className="glass-light" style={{ textAlign: 'center', padding: '60px 0' }}>
          <Spin size="large" />
          <div style={{ marginTop: '16px' }}>
            <Text type="secondary">加载中...</Text>
          </div>
        </Card>
      ) : proxies.length === 0 ? (
        <Card className="glass-light" style={{ textAlign: 'center', padding: '60px 0' }}>
          <Empty 
            description="暂无反向代理配置"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        </Card>
      ) : (
        <Row gutter={[16, 16]}>
          {proxies.map((proxy, index) => (
            <Col xs={24} sm={24} md={12} lg={8} xl={6} key={`${proxy.hostName}-${proxy.vmUuid}-${proxy.domain}`}>
              <ProxyCard proxy={proxy} index={index} />
            </Col>
          ))}
        </Row>
      )}
    </div>
  );
};

export default UserProxys;
