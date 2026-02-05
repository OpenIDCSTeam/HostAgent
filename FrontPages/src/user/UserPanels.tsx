import React, { useEffect, useState } from 'react';
import { Card, Typography, Row, Col, Progress, Spin, message } from 'antd';
import { useUserStore } from '@/utils/data.ts';
import api from '@/utils/apis.ts';
import { 
  CpuChipIcon, 
  CircleStackIcon, 
  ServerIcon,
  GlobeAltIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  CubeIcon
} from '@heroicons/react/24/outline';

const { Title } = Typography;

const UserPanels: React.FC = () => {
  const { user, setUser } = useUserStore();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchUserData();
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

  if (!user) return <Spin />;

  const formatStorage = (mb: number): string => {
    if (mb < 1024) return `${mb}MB`;
    const gb = mb / 1024;
    if (gb < 1024) return `${gb.toFixed(1)}GB`;
    const tb = gb / 1024;
    return `${tb.toFixed(1)}TB`;
  }

  const renderResourceCard = (
    title: string, 
    used: number, 
    quota: number, 
    unit: string = '', 
    isStorage: boolean = false,
    icon: React.ReactNode,
    gradientFrom: string,
    gradientTo: string,
    strokeColor: string
  ) => {
    const percent = quota > 0 ? Math.min(Math.round((used / quota) * 100), 100) : 0;
    const status = percent > 90 ? 'exception' : percent > 70 ? 'active' : 'normal';
    
    // 如果配额非常大（比如99999），显示为无限制
    const isUnlimited = quota > 1000000;
    
    let usedDisplay = `${used}${unit}`;
    let quotaDisplay = isUnlimited ? '无限制' : `${quota}${unit}`;

    if (isStorage) {
        usedDisplay = formatStorage(used);
        quotaDisplay = isUnlimited ? '无限制' : formatStorage(quota);
    }
    
    return (
      <Col xs={24} sm={12} md={8} lg={6} style={{ marginBottom: 24 }}>
        <Card 
          className="glass-card-enhanced hover:shadow-xl transition-all duration-300 hover:-translate-y-1"
          style={{
            background: `linear-gradient(135deg, ${gradientFrom} 0%, ${gradientTo} 100%)`,
            border: `1px solid ${gradientFrom.replace('0.1', '0.2')}`,
            borderRadius: '16px',
            overflow: 'hidden'
          }}
          bodyStyle={{ padding: '24px' }}
        >
          {/* 图标容器 */}
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between',
            marginBottom: '16px'
          }}>
            <div style={{
              width: '48px',
              height: '48px',
              borderRadius: '12px',
              background: `linear-gradient(135deg, ${gradientFrom.replace('0.1', '0.3')} 0%, ${gradientTo.replace('0.1', '0.4')} 100%)`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              {icon}
            </div>
            <div style={{ 
              fontSize: '14px', 
              fontWeight: 500,
              color: 'var(--text-primary)'
            }}>
              {title}
            </div>
          </div>

          {/* 进度环 */}
          <div style={{ textAlign: 'center', marginBottom: '16px' }}>
            <Progress 
              type="dashboard" 
              percent={isUnlimited ? 0 : percent} 
              status={status}
              strokeColor={strokeColor}
              format={() => (
                <div style={{
                  fontSize: '24px',
                  fontWeight: 700,
                  background: `linear-gradient(135deg, ${strokeColor} 0%, ${strokeColor}dd 100%)`,
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  backgroundClip: 'text'
                }}>
                  {usedDisplay}
                </div>
              )}
            />
          </div>

          {/* 配额信息 */}
          <div style={{ 
            textAlign: 'center',
            fontSize: '13px',
            color: 'var(--text-secondary)',
            fontWeight: 500
          }}>
            总配额: <span style={{ 
              color: 'var(--text-primary)',
              fontWeight: 600
            }}>{quotaDisplay}</span>
          </div>

          {/* 使用率标签 */}
          <div style={{
            marginTop: '12px',
            padding: '6px 12px',
            borderRadius: '8px',
            background: percent > 90 
              ? 'rgba(239, 68, 68, 0.1)' 
              : percent > 70 
                ? 'rgba(251, 191, 36, 0.1)' 
                : 'rgba(34, 197, 94, 0.1)',
            textAlign: 'center',
            fontSize: '12px',
            fontWeight: 600,
            color: percent > 90 
              ? '#ef4444' 
              : percent > 70 
                ? '#f59e0b' 
                : '#22c55e'
          }}>
            使用率 {isUnlimited ? '0' : percent}%
          </div>
        </Card>
      </Col>
    );
  };

  return (
    <div style={{ 
      padding: '32px',
      minHeight: '100vh'
    }}>
      {/* 页面标题 */}
      <div style={{ marginBottom: '32px' }}>
        <Title 
          level={2} 
          style={{ 
            margin: 0,
            fontSize: '32px',
            fontWeight: 700,
            color: 'var(--text-primary)',
            display: 'flex',
            alignItems: 'center',
            gap: '12px'
          }}
        >
          <CubeIcon style={{ width: '36px', height: '36px', color: 'var(--accent-primary)' }} />
          全局资源概览
        </Title>
        <div style={{ 
          marginTop: '8px',
          fontSize: '14px',
          color: 'var(--text-secondary)'
        }}>
          查看您的资源使用情况和配额信息
        </div>
      </div>
      
      <Spin spinning={loading}>
        {/* 计算资源 */}
        <div style={{ marginBottom: '32px' }}>
          <div style={{ 
            fontSize: '18px', 
            fontWeight: 600,
            marginBottom: '16px',
            color: 'var(--text-primary)'
          }}>
            💻 计算资源
          </div>
          <Row gutter={[24, 24]}>
            {renderResourceCard(
              'CPU 核心', 
              user.used_cpu || 0, 
              user.quota_cpu || 0, 
              '核',
              false,
              <CpuChipIcon style={{ width: '24px', height: '24px', color: '#3b82f6' }} />,
              'rgba(59, 130, 246, 0.1)',
              'rgba(37, 99, 235, 0.1)',
              '#3b82f6'
            )}
            {renderResourceCard(
              '内存', 
              user.used_ram || 0, 
              user.quota_ram || 0, 
              '',
              true,
              <CircleStackIcon style={{ width: '24px', height: '24px', color: '#10b981' }} />,
              'rgba(16, 185, 129, 0.1)',
              'rgba(5, 150, 105, 0.1)',
              '#10b981'
            )}
            {renderResourceCard(
              '磁盘存储', 
              user.used_ssd || 0, 
              user.quota_ssd || 0, 
              '',
              true,
              <ServerIcon style={{ width: '24px', height: '24px', color: '#8b5cf6' }} />,
              'rgba(139, 92, 246, 0.1)',
              'rgba(124, 58, 237, 0.1)',
              '#8b5cf6'
            )}
            {/* 如果有GPU配额，也显示 */}
            {(user.quota_gpu || 0) > 0 && renderResourceCard(
              'GPU 显存', 
              user.used_gpu || 0, 
              user.quota_gpu || 0, 
              '',
              true,
              <CubeIcon style={{ width: '24px', height: '24px', color: '#ec4899' }} />,
              'rgba(236, 72, 153, 0.1)',
              'rgba(219, 39, 119, 0.1)',
              '#ec4899'
            )}
          </Row>
        </div>

        {/* 网络资源 */}
        <div>
          <div style={{ 
            fontSize: '18px', 
            fontWeight: 600,
            marginBottom: '16px',
            color: 'var(--text-primary)'
          }}>
            🌐 网络资源
          </div>
          <Row gutter={[24, 24]}>
            {renderResourceCard(
              'NAT 端口', 
              user.used_nat_ports || 0, 
              user.quota_nat_ports || 0, 
              '个',
              false,
              <GlobeAltIcon style={{ width: '24px', height: '24px', color: '#6366f1' }} />,
              'rgba(99, 102, 241, 0.1)',
              'rgba(79, 70, 229, 0.1)',
              '#6366f1'
            )}
            {renderResourceCard(
              'Web 代理', 
              user.used_web_proxy || 0, 
              user.quota_web_proxy || 0, 
              '个',
              false,
              <GlobeAltIcon style={{ width: '24px', height: '24px', color: '#14b8a6' }} />,
              'rgba(20, 184, 166, 0.1)',
              'rgba(13, 148, 136, 0.1)',
              '#14b8a6'
            )}
            {renderResourceCard(
              '上行带宽', 
              user.used_bandwidth_up || 0, 
              user.quota_bandwidth_up || 0, 
              'Mbps',
              false,
              <ArrowUpIcon style={{ width: '24px', height: '24px', color: '#ef4444' }} />,
              'rgba(239, 68, 68, 0.1)',
              'rgba(220, 38, 38, 0.1)',
              '#ef4444'
            )}
            {renderResourceCard(
              '下行带宽', 
              user.used_bandwidth_down || 0, 
              user.quota_bandwidth_down || 0, 
              'Mbps',
              false,
              <ArrowDownIcon style={{ width: '24px', height: '24px', color: '#06b6d4' }} />,
              'rgba(6, 182, 212, 0.1)',
              'rgba(8, 145, 178, 0.1)',
              '#06b6d4'
            )}
          </Row>
        </div>
      </Spin>
    </div>
  );
};

export default UserPanels;
