import axios from "axios";

const TOKEN_KEY = "skillsprint_token";

const apiClient = axios.create({
  baseURL: "http://localhost:8000",
});

// Attach the JWT (if we have one) to every outgoing request.
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// If the backend says the token is no longer valid, clear it and force a
// reload back to the login screen instead of leaving the UI in a broken
// half-authenticated state.
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
      if (!window.location.pathname.includes("login")) {
        window.location.reload();
      }
    }
    return Promise.reject(error);
  }
);

export default apiClient;
