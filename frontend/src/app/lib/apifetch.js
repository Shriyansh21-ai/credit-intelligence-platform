export const apiFetch = async (url, options = {}) => {

  let token = localStorage.getItem("token");

  let res = await fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      "Authorization": `Bearer ${token}`
    }
  });

  // 🔥 AUTO REFRESH
  if (res.status === 401) {

    const refresh = localStorage.getItem("refresh_token");

    const refreshRes = await fetch("http://127.0.0.1:8000/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh })
    });

    const data = await refreshRes.json();

    if (data.access_token) {
      localStorage.setItem("token", data.access_token);

      // retry request
      return fetch(url, {
        ...options,
        headers: {
          ...options.headers,
          "Authorization": `Bearer ${data.access_token}`
        }
      });
    } else {
      window.location.href = "/auth";
    }
  }

  return res;
};