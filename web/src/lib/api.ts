/**
 * api.ts — API client for Kharcha Tracker FastAPI backend.
 * Uses fetch() with JWT bearer token auth.
 */

const TOKEN_KEY = 'kharcha_token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function saveToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function isLoggedIn(): boolean {
  return !!getToken();
}

async function request<T>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Only set Content-Type for non-FormData bodies
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(url, { ...options, headers });

  if (res.status === 401) {
    clearToken();
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }

  if (!res.ok) {
    const errBody = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errBody.detail || `HTTP ${res.status}`);
  }

  // Handle blob responses for CSV downloads
  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('text/csv') || contentType.includes('application/octet-stream')) {
    return res.blob() as unknown as T;
  }

  return res.json();
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  return request('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
}

export async function register(username: string, password: string): Promise<LoginResponse> {
  return request('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
}

// ── Stats ─────────────────────────────────────────────────────────────────────

export interface StatsSummary {
  today_spend: number;
  week_spend: number;
  month_spend: number;
  total_spend: number;
  total_saved: number;
  total_fees: number;
  total_orders: number;
  avg_order: number;
}

export interface AppStat {
  app_name: string;
  orders: number;
  total_spent: number;
  total_saved: number;
  total_fees: number;
  avg_order: number;
}

export interface CategoryStat {
  category: string;
  item_count: number;
  total_spent: number;
  avg_price: number;
}

export interface SpendPoint {
  label: string;
  spend: number;
  avg: number;
}

export interface HeatmapPoint {
  date: string;
  amount: number;
}

export interface ItemFrequency {
  name: string;
  brand: string;
  category: string;
  times: number;
  avg_price: number;
  min_price: number;
  max_price: number;
  total_spent: number;
}

export interface PriceTrendPoint {
  date: string;
  price: number;
  avg: number;
}

export interface SavingsInsight {
  type: string;
  title: string;
  description: string;
  impact: number;
}

export async function getSummary(): Promise<StatsSummary> {
  return request('/api/stats/summary');
}

export async function getStatsByApp(): Promise<{ apps: AppStat[] }> {
  return request('/api/stats/by-app');
}

export async function getStatsByCategory(): Promise<{ categories: CategoryStat[] }> {
  return request('/api/stats/by-category');
}

export async function getRecentOrders(limit = 5): Promise<{ orders: Order[] }> {
  return request(`/api/stats/recent-orders?limit=${limit}`);
}

export async function getSpendingOverTime(period = 'weekly'): Promise<{ data: SpendPoint[] }> {
  return request(`/api/stats/spending-over-time?period=${period}`);
}

export async function getDailyHeatmap(): Promise<{ data: HeatmapPoint[] }> {
  return request('/api/stats/daily-heatmap');
}

export async function getItemFrequency(limit = 20, category?: string): Promise<{ items: ItemFrequency[] }> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (category) params.set('category', category);
  return request(`/api/stats/item-frequency?${params}`);
}

export async function getTopItems(limit = 10): Promise<{ items: ItemFrequency[] }> {
  return request(`/api/stats/top-items?limit=${limit}`);
}

export async function getPriceTrend(itemName: string): Promise<{ data: PriceTrendPoint[] }> {
  return request(`/api/stats/price-trend?item_name=${encodeURIComponent(itemName)}`);
}

export async function getSavingsInsights(): Promise<{ insights: SavingsInsight[] }> {
  return request('/api/stats/savings-insights');
}

export async function getItemsPerApp(): Promise<{ data: Array<{ app_name: string; unique_items: number; total_items: number; avg_price: number; total_spent: number }> }> {
  return request('/api/stats/items-per-app');
}

// ── Orders ────────────────────────────────────────────────────────────────────

export interface Order {
  id: number;
  order_date: string;
  app_name: string;
  app_category: string;
  order_id: string | null;
  total_amount: number;
  delivery_fee: number;
  discount: number;
  notes: string | null;
  created_at?: string;
}

export interface OrderItem {
  id?: number;
  name: string;
  brand: string;
  category: string;
  quantity: string;
  unit_price: number;
  total_price: number;
}

export async function getOrders(skip = 0, limit = 50, appName?: string, search?: string): Promise<{ orders: Order[]; total: number }> {
  const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
  if (appName) params.set('app_name', appName);
  if (search) params.set('search', search);
  return request(`/api/orders?${params}`);
}

export async function getOrder(id: number): Promise<{ order: Order; items: OrderItem[] }> {
  return request(`/api/orders/${id}`);
}

export async function createOrder(order: Omit<Order, 'id' | 'created_at'> & { items: OrderItem[] }): Promise<{ id: number; message: string }> {
  return request('/api/orders', {
    method: 'POST',
    body: JSON.stringify(order),
  });
}

export async function updateOrder(id: number, order: Omit<Order, 'id' | 'created_at'> & { items: OrderItem[] }): Promise<{ message: string }> {
  return request(`/api/orders/${id}`, {
    method: 'PUT',
    body: JSON.stringify(order),
  });
}

export async function deleteOrder(id: number): Promise<{ message: string }> {
  return request(`/api/orders/${id}`, { method: 'DELETE' });
}

// ── Upload / Parse ────────────────────────────────────────────────────────────

export interface ParsedOrder {
  resolved_app: string | null;
  resolved_category: string | null;
  order_date: string | null;
  order_id: string | null;
  total_amount: number;
  delivery_fee: number;
  discount: number;
  items: OrderItem[];
}

export async function parseUpload(file: File, appName?: string): Promise<{ parsed: ParsedOrder }> {
  const formData = new FormData();
  formData.append('file', file);
  if (appName) formData.append('app_name', appName);
  return request('/api/upload/parse', {
    method: 'POST',
    body: formData,
  });
}

export async function saveOrder(order: {
  order_date: string;
  app_name: string;
  app_category?: string;
  order_id?: string;
  total_amount: number;
  delivery_fee: number;
  discount: number;
  notes?: string;
  items: OrderItem[];
  skip_duplicate_check?: boolean;
}): Promise<{ id: number; message: string }> {
  return request('/api/upload/save', {
    method: 'POST',
    body: JSON.stringify(order),
  });
}

// ── Cleanup ───────────────────────────────────────────────────────────────────

export interface DuplicateCluster {
  canonical_suggestion: string;
  score: number;
  variants: string[];
  brand_suggestions: string[];
  category_suggestions: string[];
}

export interface ItemAlias {
  id: number;
  raw_name: string;
  raw_brand: string;
  canonical_name: string;
  canonical_brand: string;
  canonical_cat: string;
}

export async function getCleanupClusters(): Promise<{ clusters: DuplicateCluster[] }> {
  return request('/api/cleanup/clusters');
}

export async function getAliases(): Promise<{ aliases: ItemAlias[] }> {
  return request('/api/cleanup/aliases');
}

export async function mergeItems(data: {
  variants: string[];
  canonical_name: string;
  canonical_brand: string;
  canonical_cat: string;
}): Promise<{ message: string }> {
  return request('/api/cleanup/merge', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function deleteAlias(id: number): Promise<{ message: string }> {
  return request(`/api/cleanup/aliases/${id}`, { method: 'DELETE' });
}

// ── Settings ──────────────────────────────────────────────────────────────────

export interface KeyPoolStatus {
  index: number;
  suffix: string;
  count: number;
  exhausted: boolean;
  active: boolean;
}

export async function getKeyPoolStatus(): Promise<{ keys: KeyPoolStatus[] }> {
  return request('/api/settings/key-pool');
}

export async function updatePassword(newPassword: string): Promise<{ message: string }> {
  return request('/api/settings/update-password', {
    method: 'POST',
    body: JSON.stringify({ new_password: newPassword }),
  });
}

export async function healthCheck(): Promise<{ status: string; app: string; version: string }> {
  return request('/api/health');
}
