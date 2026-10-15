export const deriveRuntimeStatus = (runtimeHealth, retrievalHealth) => {
  const modelReady = runtimeHealth?.status === 'healthy'
    && runtimeHealth?.model_status === 'ready'
    && runtimeHealth?.model_loaded === true

  if (modelReady) {
    const modelLabel = runtimeHealth.model?.startsWith('granite') ? 'Granite' : 'Inference'
    return { label: `${modelLabel} ready`, type: 'green', ready: true }
  }

  if (retrievalHealth?.status === 'healthy' && retrievalHealth?.database === 'connected') {
    return { label: 'Retrieval only', type: 'gray', ready: false }
  }

  return { label: 'Unavailable', type: 'red', ready: false }
}