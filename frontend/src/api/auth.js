import { apiClient } from "./client";

export async function registerRequest({ email, password, fullName }) {
  const { data } = await apiClient.post("/auth/register", {
    email,
    password,
    full_name: fullName || undefined,
  });
  return data;
}

export async function loginRequest({ email, password }) {
  const form = new URLSearchParams();
  form.set("username", email);
  form.set("password", password);
  const { data } = await apiClient.post("/auth/login", form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return data; // { access_token, token_type }
}

export async function fetchCurrentUser() {
  const { data } = await apiClient.get("/auth/me");
  return data;
}