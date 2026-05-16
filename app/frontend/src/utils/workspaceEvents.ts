const WORKSPACE_REFRESH_EVENT = 'toptrader:workspace-refresh'

export function emitWorkspaceRefresh() {
  window.dispatchEvent(new CustomEvent(WORKSPACE_REFRESH_EVENT))
}

export function onWorkspaceRefresh(listener: () => void) {
  window.addEventListener(WORKSPACE_REFRESH_EVENT, listener)
  return () => window.removeEventListener(WORKSPACE_REFRESH_EVENT, listener)
}
