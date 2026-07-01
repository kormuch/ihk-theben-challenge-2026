const BASE = '/api/v1';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Types ──────────────────────────────────────────────────────────────────

export interface ProductFamily {
  id: string;
  name: string;
  description: string | null;
  attribute_schema: Record<string, any>;
  created_at: string;
}

export interface ProductDocument {
  id: string;
  filename: string;
  original_filename: string;
  source_type: string | null;
  doc_category: string | null;
  status: string;
  error_message: string | null;
  created_at: string;
}

export interface Product {
  id: string;
  name: string;
  article_number: string;
  family_id: string;
  attributes: Record<string, any>;
  created_at: string;
  updated_at: string;
  documents?: ProductDocument[];
}

export interface IngestResult {
  document_id: string;
  filename: string;
  status: string;
  records_parsed: number;
  message: string;
}

// ── Families ───────────────────────────────────────────────────────────────

export const families = {
  list: () => request<ProductFamily[]>('/families/'),
  get: (id: string) => request<ProductFamily>(`/families/${id}`),
  create: (data: { name: string; description?: string; attribute_schema?: Record<string, any> }) =>
    request<ProductFamily>('/families/', { method: 'POST', body: JSON.stringify(data) }),
  delete: (id: string) => request<void>(`/families/${id}`, { method: 'DELETE' }),
};

// ── Products ───────────────────────────────────────────────────────────────

export const products = {
  list: (params?: { family_id?: string; search?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.family_id) qs.set('family_id', params.family_id);
    if (params?.search) qs.set('search', params.search);
    if (params?.limit) qs.set('limit', String(params.limit));
    if (params?.offset) qs.set('offset', String(params.offset));
    const q = qs.toString();
    return request<Product[]>(`/products/${q ? '?' + q : ''}`);
  },
  get: (id: string) => request<Product>(`/products/${id}`),
  create: (data: { name: string; article_number: string; family_id: string; attributes?: Record<string, any> }) =>
    request<Product>('/products/', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: { name?: string; attributes?: Record<string, any> }) =>
    request<Product>(`/products/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (id: string) => request<void>(`/products/${id}`, { method: 'DELETE' }),
};

// ── Ingest ─────────────────────────────────────────────────────────────────

export const ingest = {
  upload: (file: File, productId: string, docCategory: string = 'Technisch') => {
    const form = new FormData();
    form.append('file', file);
    form.append('product_id', productId);
    form.append('doc_category', docCategory);
    return fetch(`${BASE}/ingest/upload`, { method: 'POST', body: form }).then(async (res) => {
      if (!res.ok) throw new Error(await res.text());
      return res.json() as Promise<IngestResult>;
    });
  },
  downloadUrl: (documentId: string) => `${BASE}/ingest/documents/${documentId}/download`,
  deleteDocument: (documentId: string) =>
    request<void>(`/ingest/documents/${documentId}`, { method: 'DELETE' }),
};
