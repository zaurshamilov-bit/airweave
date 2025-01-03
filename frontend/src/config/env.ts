interface Env {
  VITE_API_URL: string;
  VITE_ACCESS_TOKEN?: string;
}

export const env: Env = {
  VITE_API_URL: import.meta.env.VITE_API_URL || 'http://localhost:8001',
  VITE_ACCESS_TOKEN: import.meta.env.VITE_ACCESS_TOKEN || '',
};