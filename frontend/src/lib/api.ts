import { env } from '../config/env';

export const API_CONFIG = {
  baseURL: env.VITE_API_URL,
  headers: {
    'Content-Type': 'application/json',
    ...(env.VITE_ACCESS_TOKEN && {
      Authorization: `Bearer ${env.VITE_ACCESS_TOKEN}`,
    }),
  },
} as const;

type ApiResponse<T = any> = Promise<Response>;

export const apiClient = {
  async get<T>(endpoint: string, params?: Record<string, any>): ApiResponse<T> {
    const url = new URL(`${API_CONFIG.baseURL}${endpoint}`);
    if (params) {
      Object.entries(params).forEach(([key, value]) => 
        url.searchParams.append(key, value)
      );
    }

    return await fetch(url.toString(), {
      method: 'GET',
      headers: API_CONFIG.headers,
    });
  },

  async post<T>(endpoint: string, data?: any, params?: Record<string, string>): ApiResponse<T> {
    const url = new URL(`${API_CONFIG.baseURL}${endpoint}`);
    if (params) {
      Object.entries(params).forEach(([key, value]) => 
        url.searchParams.append(key, value)
      );
    }

    return await fetch(url.toString(), {
      method: 'POST',
      headers: API_CONFIG.headers,
      body: JSON.stringify(data),
    });
  },

  async put<T>(endpoint: string, params?: Record<string, string>, data?: any): ApiResponse<T> {
    const url = new URL(`${API_CONFIG.baseURL}${endpoint}`);
    if (params) {
      Object.entries(params).forEach(([key, value]) => 
        url.searchParams.append(key, value)
      );
    }

    return await fetch(url.toString(), {
      method: 'PUT',
      headers: API_CONFIG.headers,
      body: data ? JSON.stringify(data) : undefined,
    });
  },

  async delete<T>(endpoint: string, params?: Record<string, string>): ApiResponse<T> {
    const url = new URL(`${API_CONFIG.baseURL}${endpoint}`);
    if (params) {
      Object.entries(params).forEach(([key, value]) => 
        url.searchParams.append(key, value)
      );
    }

    return await fetch(url.toString(), {
      method: 'DELETE',
      headers: API_CONFIG.headers,
    });
  },
};