function getCookie(name) {
  const match = document.cookie.split("; ").find((row) => row.startsWith(name + "="));
  return match ? decodeURIComponent(match.split("=")[1]) : null;
}

async function ensureCsrf() {
  if (!getCookie("csrftoken")) {
    await fetch("/api/auth/csrf/", { credentials: "same-origin" });
  }
}

export class ApiError extends Error {
  constructor(status, data) {
    super(`API ${status}`);
    this.status = status;
    this.data = data;
  }
}

export async function api(path, { method = "GET", body } = {}) {
  const opts = { method, credentials: "same-origin", headers: { Accept: "application/json" } };
  if (method !== "GET") {
    await ensureCsrf();
    // Токен читаем каждый раз: после входа Django выдаёт новый
    opts.headers["X-CSRFToken"] = getCookie("csrftoken");
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
  }
  const res = await fetch(`/api${path}`, opts);
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}
