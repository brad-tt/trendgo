/**
 * useWorkspaceData
 *
 * 对外接口保持不变：返回 { day, error, loading, refresh, setDay, setState, state }
 * 数据来源改为 WorkspaceContext，各 View 不再独立发起 fetch。
 */
import { useWorkspace } from '../contexts/WorkspaceContext'

export function useWorkspaceData() {
  return useWorkspace()
}
