export const deriveRuntimeStatus = (runtimeHealth, retrievalHealth) => {
  const qwenReady = runtimeHealth?.status === 'healthy'
    && runtimeHealth?.model_status === 'ready'
    && runtimeHealth?.model_loaded === true

  if (qwenReady) {
    return { label: 'Qwen ready', type: 'green', ready: true }
  }

  if (retrievalHealth?.status === 'healthy' && retrievalHealth?.database === 'connected') {
    return { label: 'Retrieval only', type: 'gray', ready: false }
  }

  return { label: 'Unavailable', type: 'red', ready: false }
}