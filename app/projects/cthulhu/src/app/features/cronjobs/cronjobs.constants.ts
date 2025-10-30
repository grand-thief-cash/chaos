// 映射运行状态到徽章颜色与文本
export const RUN_STATUS_BADGE: Record<string, { status: 'success' | 'error' | 'processing' | 'default' | 'warning'; text: string }> = {
  SCHEDULED: { status: 'processing', text: '排队' },
  RUNNING: { status: 'processing', text: '运行中' },
  SUCCESS: { status: 'success', text: '成功' },
  FAILED: { status: 'error', text: '失败' },
  TIMEOUT: { status: 'error', text: '超时' },
  RETRYING: { status: 'warning', text: '重试中' },
  CALLBACK_PENDING: { status: 'processing', text: '待回调' },
  CALLBACK_SUCCESS: { status: 'success', text: '回调成功' },
  FAILED_TIMEOUT: { status: 'error', text: '失败/超时' },
  CANCELED: { status: 'default', text: '已取消' },
  SKIPPED: { status: 'default', text: '跳过' },
  FAILURE_SKIP: { status: 'default', text: '失败跳过' },
  CONCURRENT_SKIP: { status: 'warning', text: '并发跳过' },
  OVERLAP_SKIP: { status: 'warning', text: '重叠跳过' }
};

