import { apiClient } from "./client";

export async function uploadDocuments(files, onProgress) {
  const formData = new FormData();
  Array.from(files).forEach((file) => formData.append("files", file));

  const { data } = await apiClient.post("/documents/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (event) => {
      if (onProgress && event.total) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    },
  });
  return data;
}

export async function listDocuments() {
  const { data } = await apiClient.get("/documents/");
  return data;
}

export async function renameDocument(id, title) {
  const { data } = await apiClient.patch(`/documents/${id}`, { title });
  return data;
}

export async function deleteDocument(id) {
  const { data } = await apiClient.delete(`/documents/${id}`);
  return data;
}