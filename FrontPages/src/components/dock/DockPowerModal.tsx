import React from 'react'
import { Modal, Row, Col, Button } from 'antd'
import {
    PlayCircleOutlined,
    PauseCircleOutlined,
    RedoOutlined,
    PoweroffOutlined,
    ThunderboltOutlined
} from '@ant-design/icons'

interface DockPowerModalProps {
    open: boolean
    onCancel: () => void
    vmUuid: string
    onAction: (action: string) => void
}

const DockPowerModal: React.FC<DockPowerModalProps> = ({
    open,
    onCancel,
    vmUuid,
    onAction
}) => {
    return (
        <Modal
            title="电源操作"
            open={open}
            onCancel={onCancel}
            footer={null}
            width={400}
        >
            <p className="mb-4">选择对虚拟机 "<strong>{vmUuid}</strong>" 执行的操作：</p>
            <Row gutter={[12, 12]}>
                <Col span={12}>
                    <Button
                        block
                        type="primary"
                        className="bg-green-500 hover:bg-green-600 dark:bg-green-600 dark:hover:bg-green-700"
                        icon={<PlayCircleOutlined/>}
                        onClick={() => onAction('start')}
                    >
                        启动
                    </Button>
                </Col>
                <Col span={12}>
                    <Button
                        block
                        className="bg-yellow-500 hover:bg-yellow-600 dark:bg-yellow-600 dark:hover:bg-yellow-700 text-white"
                        icon={<PauseCircleOutlined/>}
                        onClick={() => onAction('stop')}
                    >
                        关机
                    </Button>
                </Col>
                <Col span={12}>
                    <Button
                        block
                        type="primary"
                        icon={<RedoOutlined/>}
                        onClick={() => onAction('reset')}
                    >
                        重启
                    </Button>
                </Col>
                <Col span={12}>
                    <Button
                        block
                        className="bg-gray-500 hover:bg-gray-600 dark:bg-gray-600 dark:hover:bg-gray-700 text-white"
                        icon={<PauseCircleOutlined/>}
                        onClick={() => onAction('pause')}
                    >
                        暂停
                    </Button>
                </Col>
                <Col span={12}>
                    <Button
                        block
                        className="bg-purple-600 hover:bg-purple-700 dark:bg-purple-700 dark:hover:bg-purple-800 text-white"
                        icon={<PlayCircleOutlined/>}
                        onClick={() => onAction('resume')}
                    >
                        恢复
                    </Button>
                </Col>
                <Col span={12}>
                    <Button
                        block
                        danger
                        icon={<PoweroffOutlined/>}
                        onClick={() => onAction('hard_stop')}
                    >
                        强制关机
                    </Button>
                </Col>
                <Col span={12}>
                    <Button
                        block
                        danger
                        icon={<ThunderboltOutlined/>}
                        onClick={() => onAction('hard_reset')}
                    >
                        强制重启
                    </Button>
                </Col>
            </Row>
        </Modal>
    )
}

export default DockPowerModal
