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
  upload: (file: File, productId: string, docCategory: string = 'Technical') => {
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

// ── Export ─────────────────────────────────────────────────────────────────

export const exportApi = {
  productsJson: () => request<{ schema_version: string; generated_at: string; products: any[] }>('/export/products.json'),
};

// ── Analyze (AI) ──────────────────────────────────────────────────────────

export interface AnalyzeResult {
  status: string;
  filename: string;
  stored_as: string;
  error?: string;
  classification?: {
    document_type: string;
    confidence: number;
    reasoning: string;
    multi_product: boolean;
    detected_products: string[];
  };
  needs_review?: boolean;
  extraction?: {
    products: ExtractedProduct[];
  };
  extraction_error?: string;
}

export interface ExtractedProduct {
  article_number: string;
  name: string;
  family_suggestion: string;
  family_id: string | null;
  family_name: string;
  attributes: Record<string, any>;
  citations: Record<string, string>;
}

export interface ConfirmResult {
  created: string[];
  updated: string[];
  errors: { article_number: string; error: string }[];
}

export interface ExistingProductInfo {
  id: string;
  name: string;
  family_id: string;
  attributes: Record<string, any>;
}

// ── Prompts ───────────────────────────────────────────────────────────────

export interface PromptsConfig {
  document_types: string[];
  classifier_prompt: string;
  extractor_base_template: string;
  extractor_prompts: Record<string, string>;
  generic_extractor_instructions: string;
}

export const prompts = {
  get: () => request<PromptsConfig>('/prompts/'),
  update: (data: Partial<PromptsConfig>) =>
    request<PromptsConfig>('/prompts/', { method: 'PUT', body: JSON.stringify(data) }),
  updateExtractor: (docType: string, instructions: string) =>
    request<{ doc_type: string; instructions: string }>(`/prompts/extractors/${encodeURIComponent(docType)}`, {
      method: 'PUT',
      body: JSON.stringify({ instructions }),
    }),
};

// ── Analyze (AI) ──────────────────────────────────────────────────────────

export const analyze = {
  upload: (file: File): Promise<AnalyzeResult> => {
    const form = new FormData();
    form.append('file', file);
    return fetch(`${BASE}/analyze/`, { method: 'POST', body: form }).then(async (res) => {
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    });
  },
  lookup: (articleNumbers: string[]) =>
    request<Record<string, ExistingProductInfo>>('/analyze/lookup', {
      method: 'POST',
      body: JSON.stringify({ article_numbers: articleNumbers }),
    }),
  reExtract: (storedAs: string, docType: string) =>
    request<{ status: string; doc_type: string; extraction: { products: ExtractedProduct[] } }>(
      '/analyze/re-extract',
      { method: 'POST', body: JSON.stringify({ stored_as: storedAs, doc_type: docType }) },
    ),
  confirm: (data: {
    stored_as: string;
    doc_type: string;
    products: { article_number: string; name: string; family_id: string; attributes: Record<string, any> }[];
  }) => request<ConfirmResult>('/analyze/confirm', { method: 'POST', body: JSON.stringify(data) }),
};
