import React, { useEffect, useState } from 'react';
import { Card, Table, Button, message, Tag, Modal, Form, Input, Select, InputNumber, Space, Typography } from 'antd';
import { ReloadOutlined, PlusOutlined, DeleteOutlined } from '@ant-design/icons';
import { ArrowsRightLeftIcon } from '@heroicons/react/24/outline';

const { Title } = Typography;
import api from '@/utils/apis.ts';
import { NATRule } from '@/types';

interface UserNATRule extends NATRule {
  hostName: string;
  vmUuid: string;
  rule_index: number; // 确保包含 rule_index
}

const PortManage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [rules, setRules] = useState<UserNATRule[]>([]);
  const [modalVisible, setModalVisible] = useState(false);
  const [form] = Form.useForm();
  
  // 主机和虚拟机列表，用于添加规则时的选择
  const [hosts, setHosts] = useState<string[]>([]);
  const [vms, setVms] = useState<{label: string, value: string}[]>([]);
  const [selectedHost, setSelectedHost] = useState<string>('');

  useEffect(() => {
    fetchNATRules();
    loadHosts();
  }, []);

  const loadHosts = async () => {
    try {
      const res = await api.getHosts();
      if (res.code === 200 && res.data) {
        setHosts(Object.keys(res.data));
      }
    } catch (e) {
      console.error('加载主机列表失败', e);
    }
  };

  const loadVMs = async (hostName: string) => {
    try {
      const res = await api.getVMs(hostName);
      if (res.code === 200 && res.data) {
        const vmList = Array.isArray(res.data) 
          ? res.data.map((vm: any) => ({ label: vm.config?.vm_uuid || vm.uuid, value: vm.config?.vm_uuid || vm.uuid }))
          : Object.values(res.data).map((vm: any) => ({ label: vm.config?.vm_uuid || vm.uuid, value: vm.config?.vm_uuid || vm.uuid }));
        setVms(vmList);
      }
    } catch (e) {
      console.error('加载虚拟机列表失败', e);
      setVms([]);
    }
  };

  const handleHostChange = (value: string) => {
    setSelectedHost(value);
    form.setFieldsValue({ vmUuid: undefined });
    loadVMs(value);
  };

  const fetchNATRules = async () => {
    setLoading(true);
    try {
      // 1. 获取所有主机
      const hostsRes = await api.getHosts();
      if (hostsRes.code !== 200 || !hostsRes.data) {
        throw new Error('获取主机列表失败');
      }
      const hosts = Object.keys(hostsRes.data);

      const allRules: UserNATRule[] = [];

      // 2. 遍历主机获取VMs
      for (const hostName of hosts) {
        try {
          const vmsRes = await api.getVMs(hostName);
          if (vmsRes.code === 200 && vmsRes.data) {
             const vms = Array.isArray(vmsRes.data) ? vmsRes.data : Object.values(vmsRes.data);
             
             // 3. 遍历VMs获取NAT规则
             await Promise.all(vms.map(async (vm: any) => {
                 const vmUuid = vm.config?.vm_uuid || vm.uuid;
                 try {
                    const natRes = await api.getNATRules(hostName, vmUuid);
                    if (natRes.code === 200 && natRes.data) {
                        natRes.data.forEach((r: NATRule, index: number) => {
                             allRules.push({
                                 ...r,
                                 hostName,
                                 vmUuid,
                                 rule_index: index
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

      setRules(allRules);
    } catch (error) {
      console.error('获取端口转发规则失败', error);
      message.error('获取数据失败');
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = () => {
    form.resetFields();
    setModalVisible(true);
    // 如果已经有规则数据，可以默认选中第一个主机，但为了简单，让用户选择
  };

  const handleDelete = async (record: UserNATRule) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这条端口转发规则吗？',
      mask: false,
      onOk: async () => {
        try {
          const res = await api.deleteNATRule(record.hostName, record.vmUuid, record.rule_index);
          if (res.code === 200) {
            message.success('删除成功');
            fetchNATRules();
          } else {
            message.error(res.msg || '删除失败');
          }
        } catch (e) {
          message.error('删除失败');
        }
      }
    });
  };

  const handleSubmit = async (values: any) => {
    try {
      const data = {
        lan_port: values.vm_port,
        wan_port: values.host_port,
        nat_tips: values.description || '',
        lan_addr: '' // 默认空，由后端处理
      };
      
      // @ts-expect-error - API接口类型定义与实际使用的数据结构不完全匹配
      const res = await api.addNATRule(values.hostName, values.vmUuid, data);
      if (res.code === 200) {
        message.success('添加成功');
        setModalVisible(false);
        fetchNATRules();
      } else {
        message.error(res.msg || '添加失败');
      }
    } catch (e) {
      message.error('添加失败');
    }
  };

  const columns = [
    {
      title: '主机',
      dataIndex: 'hostName',
      key: 'hostName',
      render: (text: string) => <Tag color="blue">{text}</Tag>,
    },
    {
      title: '虚拟机',
      dataIndex: 'vmUuid',
      key: 'vmUuid',
      render: (text: string) => <span className="dark:text-gray-200">{text}</span>,
    },
    {
      title: '公网端口',
      dataIndex: 'wan_port', // 后端返回的是 wan_port
      key: 'wan_port',
      render: (text: number) => <span className="dark:text-gray-200">{text || '-'}</span>,
    },
    {
        title: '虚拟机端口',
        dataIndex: 'lan_port', // 后端返回的是 lan_port
        key: 'lan_port',
        render: (text: number) => <span className="dark:text-gray-200">{text || '-'}</span>,
    },
    {
      title: '备注',
      dataIndex: 'nat_tips',
      key: 'nat_tips',
      render: (text: string) => <span className="dark:text-gray-200">{text}</span>,
    },
    {
        title: '操作',
        key: 'action',
        render: (_: any, record: UserNATRule) => (
            <Button 
                type="text" 
                danger 
                icon={<DeleteOutlined />} 
                onClick={() => handleDelete(record)}
            >
                删除
            </Button>
        )
    }
  ];

  return (
    <div style={{ padding: 24 }}>
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
          <ArrowsRightLeftIcon style={{ width: '36px', height: '36px', color: 'var(--accent-primary)' }} />
          端口转发管理
        </Title>
        <div style={{ 
          marginTop: '8px',
          fontSize: '14px',
          color: 'var(--text-secondary)'
        }}>
          管理您的NAT端口转发规则
        </div>
      </div>

      {/* 操作按钮 */}
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'flex-end' }}>
        <Space>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
            添加规则
          </Button>
          <Button icon={<ReloadOutlined />} onClick={fetchNATRules} loading={loading}>
            刷新
          </Button>
        </Space>
      </div>

      <Card className="glass-card">
        <Table
          dataSource={rules}
          columns={columns}
          rowKey={(record) => `${record.hostName}-${record.vmUuid}-${record.rule_index}`}
          loading={loading}
          locale={{ emptyText: '暂无端口转发规则' }}
        />
      </Card>

      <Modal
        title="添加端口转发规则"
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item name="hostName" label="选择主机" rules={[{ required: true }]}>
            <Select onChange={handleHostChange} placeholder="请选择主机">
              {hosts.map(h => <Select.Option key={h} value={h}>{h}</Select.Option>)}
            </Select>
          </Form.Item>
          <Form.Item name="vmUuid" label="选择虚拟机" rules={[{ required: true }]}>
            <Select placeholder="请选择虚拟机" disabled={!selectedHost}>
               {vms.map(v => <Select.Option key={v.value} value={v.value}>{v.label}</Select.Option>)}
            </Select>
          </Form.Item>
          <Form.Item name="host_port" label="公网端口 (外部)" rules={[{ required: true }]}>
            <InputNumber min={1} max={65535} style={{ width: '100%' }} placeholder="例如：8080" />
          </Form.Item>
          <Form.Item name="vm_port" label="虚拟机端口 (内部)" rules={[{ required: true }]}>
            <InputNumber min={1} max={65535} style={{ width: '100%' }} placeholder="例如：80" />
          </Form.Item>
          <Form.Item name="description" label="备注">
            <Input placeholder="可选" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default PortManage;
