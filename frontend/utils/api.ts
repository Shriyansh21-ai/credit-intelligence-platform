export const apiFetch = async (url: string, options: any = {}) => {
  const token = localStorage.getItem("token");

  const res = await fetch(url, {
    ...options,
    headers: {
      ...(options.headers || {}),
      "Authorization": `Bearer ${token}`,
    }
  });

  // 🔥 GLOBAL ERROR HANDLING
  if (res.status === 401) {
    localStorage.removeItem("token");
    window.location.href = "/auth";
  }

  return res;
};