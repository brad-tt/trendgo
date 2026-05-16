import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'

import type { AppState, DailyRecord } from '../types'
import { apiClient } from '../utils/apiClient'
import { setUsdHkdRate } from '../utils/money'
import { onWorkspaceRefresh } from '../utils/workspaceEvents'

interface WorkspaceContextValue {
  state: AppState | null
  day: DailyRecord | null
  loading: boolean
  error: string
  refresh: () => Promise<void>
  switchMarket: (market: 'HK' | 'US') => Promise<void>
  switchTheme: (theme: 'dark' | 'light') => Promise<void>
  setDay: (day: DailyRecord | null) => void
  setState: (state: AppState | null) => void
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null)

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AppState | null>(null)
  const [day, setDay] = useState<DailyRecord | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const activeRef = useRef(true)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const nextState = await apiClient.get<AppState>('/api/state')
      if (!activeRef.current) return
      setState(nextState)
      setUsdHkdRate(nextState.usdHkdRate ?? 7.8)
      if (typeof document !== 'undefined') {
        document.documentElement.setAttribute('data-theme', nextState.theme ?? 'dark')
      }
      if (nextState.currentRecordPath) {
        const nextDay = await apiClient.get<DailyRecord>('/api/current-trading-day')
        if (!activeRef.current) return
        setDay(nextDay)
      } else {
        setDay(null)
      }
    } catch (err) {
      if (!activeRef.current) return
      setError(err instanceof Error ? err.message : '加载工作台数据失败。')
    } finally {
      if (activeRef.current) setLoading(false)
    }
  }, [])

  const switchMarket = useCallback(async (market: 'HK' | 'US') => {
    const response = await apiClient.put<{ state: AppState }>('/api/state/current-market', { market })
    if (!activeRef.current) return
    setState(response.state)
    setUsdHkdRate(response.state.usdHkdRate ?? 7.8)
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-theme', response.state.theme ?? 'dark')
    }
    if (response.state.currentRecordPath) {
      const nextDay = await apiClient.get<DailyRecord>('/api/current-trading-day')
      if (!activeRef.current) return
      setDay(nextDay)
    } else {
      setDay(null)
    }
  }, [])

  const switchTheme = useCallback(async (theme: 'dark' | 'light') => {
    const response = await apiClient.put<{ state: AppState }>('/api/state/theme', { theme })
    if (!activeRef.current) return
    setState(response.state)
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-theme', response.state.theme ?? theme)
    }
  }, [])

  useEffect(() => {
    activeRef.current = true
    queueMicrotask(() => {
      void refresh()
    })
    const unsubscribe = onWorkspaceRefresh(() => void refresh())
    return () => {
      activeRef.current = false
      unsubscribe()
    }
  }, [refresh])

  return (
    <WorkspaceContext.Provider value={{ state, day, loading, error, refresh, switchMarket, switchTheme, setDay, setState }}>
      {children}
    </WorkspaceContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useWorkspace(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceContext)
  if (!ctx) {
    throw new Error('useWorkspace must be used within WorkspaceProvider')
  }
  return ctx
}
