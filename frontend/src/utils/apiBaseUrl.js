const getApiBaseUrl = () => {
  const envUrl = import.meta.env.VITE_API_URL;
  if (envUrl && envUrl.trim()) {
    return envUrl.replace(/\/$/, '');
  }

  // Use same-origin relative API route handled by frontend nginx proxy.
  return '';
};

export default getApiBaseUrl;