import { useEffect, useState } from 'react';
import { products, families, ingest, type Product, type ProductFamily } from '../lib/api';

interface Props {
  productId: string;
  onBack: () => void;
}

export function ProductDetailPage({ productId, onBack }: Props) {
  const [product, setProduct] = useState<Product | null>(null);
  const [family, setFamily] = useState<ProductFamily | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');

  const reload = () => {
    products.get(productId).then((p) => {
      setProduct(p);
      families.get(p.family_id).then(setFamily);
    });
  };

  useEffect(reload, [productId]);

  if (!product) return <div className="text-sm text-gray-500 py-8">Loading...</div>;

  const schema = family?.attribute_schema ?? {};
  const allKeys = new Set([...Object.keys(schema), ...Object.keys(product.attributes)]);

  const handleSave = (key: string) => {
    let value: any = editValue;
    // Try to parse booleans and numbers
    if (value === 'true') value = true;
    else if (value === 'false') value = false;
    else if (!isNaN(Number(value)) && value.trim() !== '') value = Number(value);

    products.update(productId, { attributes: { [key]: value } }).then((p) => {
      setProduct(p);
      setEditing(null);
    });
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    await ingest.upload(file, productId);
    reload();
    e.target.value = '';
  };

  const originalFilename = (doc: NonNullable<Product['documents']>[number]) => {
    if (/\.[A-Za-z0-9]+$/.test(doc.original_filename)) return doc.original_filename;
    const storedExt = doc.filename.match(/\.[A-Za-z0-9]+$/)?.[0] ?? '';
    return `${doc.original_filename}${storedExt}`;
  };

  const fileExtension = (doc: NonNullable<Product['documents']>[number]) =>
    originalFilename(doc).match(/\.([A-Za-z0-9]+)$/)?.[1]?.toUpperCase();

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <button onClick={onBack} className="text-xs text-gray-500 hover:text-gray-300 cursor-pointer">
            &larr; Back to Products
          </button>
          <button
            onClick={async () => {
              if (!confirm('Delete this product?')) return;
              await products.delete(productId);
              onBack();
            }}
            className="text-xs text-gray-600 hover:text-red-400 cursor-pointer transition-colors"
          >
            Delete product
          </button>
        </div>
        <h1 className="text-xl font-bold text-[#f1f5f9]">{product.name}</h1>
        <p className="text-xs text-gray-500">
          {product.article_number}
          {family && (
            <span className="ml-2 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#16a34a25] text-[#4ade80]">
              {family.name}
            </span>
          )}
        </p>
      </div>

      <div className="grid grid-cols-[1fr_320px] gap-4">
        {/* Attributes */}
        <div className="bg-[#1a2030] border border-[#1f2937] rounded-lg p-5">
          <h2 className="text-sm font-semibold text-[#e2e8f0] mb-4">Attributes</h2>
          <div className="space-y-3">
            {[...allKeys].sort().map((key) => {
              const schemaDef = schema[key];
              const value = product.attributes[key];
              const isRequired = schemaDef?.required === true;
              const isMissing = value === undefined || value === null;
              const isEditing = editing === key;

              return (
                <div key={key} className="flex items-start gap-3">
                  <div className="w-[180px] min-w-[180px]">
                    <div className="text-[10px] text-gray-600 uppercase tracking-wider font-semibold">
                      {schemaDef?.label ?? key}
                      {schemaDef?.unit && <span className="text-gray-700 ml-1">({schemaDef.unit})</span>}
                    </div>
                    {isRequired && isMissing && (
                      <span className="text-[9px] text-red-400 font-semibold">REQUIRED — missing</span>
                    )}
                  </div>
                  <div className="flex-1">
                    {isEditing ? (
                      <div className="flex gap-2">
                        <input
                          autoFocus
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && handleSave(key)}
                          className="flex-1 bg-[#0f1117] border border-[#22c55e50] rounded px-2 py-1 text-sm text-[#e2e8f0] outline-none"
                        />
                        <button
                          onClick={() => handleSave(key)}
                          className="text-xs text-[#4ade80] hover:text-[#22c55e] cursor-pointer"
                        >
                          OK
                        </button>
                        <button
                          onClick={() => setEditing(null)}
                          className="text-xs text-gray-500 hover:text-gray-300 cursor-pointer"
                        >
                          ✕
                        </button>
                      </div>
                    ) : (
                      <div
                        onClick={() => {
                          setEditing(key);
                          setEditValue(
                            value === null || value === undefined
                              ? ''
                              : typeof value === 'object'
                              ? JSON.stringify(value)
                              : String(value)
                          );
                        }}
                        className={`text-sm cursor-pointer rounded px-2 py-1 -mx-2 transition-colors hover:bg-[#1f293740] ${
                          isMissing ? 'text-gray-600 italic' : 'text-[#e2e8f0]'
                        }`}
                      >
                        {isMissing
                          ? '—'
                          : typeof value === 'boolean'
                          ? value ? '✓ Yes' : '✗ No'
                          : Array.isArray(value)
                          ? value.join(', ')
                          : String(value)}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Documents */}
        <div className="bg-[#1a2030] border border-[#1f2937] rounded-lg p-5">
          <h2 className="text-sm font-semibold text-[#e2e8f0] mb-4">Documents</h2>

          {/* Upload */}
          <label className="block border-2 border-dashed border-[#2d3748] rounded-lg p-6 text-center cursor-pointer hover:border-[#22c55e] hover:bg-[#22c55e06] transition-colors mb-4">
            <div className="text-2xl mb-2">☁</div>
            <div className="text-xs text-gray-500">Drop file here or click</div>
            <input type="file" className="hidden" onChange={handleUpload} />
          </label>

          {/* List */}
          {product.documents && product.documents.length > 0 ? (
            <div className="space-y-2">
              {product.documents.map((doc) => (
                <div key={doc.id} className="bg-[#0f1117] border border-[#1f2937] rounded-md p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-xs font-medium text-[#e2e8f0] truncate">{doc.original_filename}</div>
                      <div className="text-[10px] text-gray-600 mt-0.5">
                        {doc.source_type?.toUpperCase()} · {doc.doc_category}
                      </div>
                    </div>
                    <span
                      className={`text-[10px] font-semibold px-2 py-0.5 rounded-full whitespace-nowrap ${
                        doc.status === 'done'
                          ? 'bg-[#16a34a25] text-[#4ade80]'
                          : doc.status === 'error'
                          ? 'bg-[#ef444425] text-[#f87171]'
                          : 'bg-[#f59e0b25] text-[#fbbf24]'
                      }`}
                    >
                      {doc.status === 'done' ? '✓ Done' : doc.status === 'error' ? '✗ Error' : '⟳ ...'}
                    </span>
                  </div>
                  {doc.status === 'error' && doc.error_message && (
                    <div className="text-[10px] text-red-400 mt-1 truncate">{doc.error_message}</div>
                  )}
                  <div className="flex gap-3 mt-2">
                    <a
                      href={ingest.downloadUrl(doc.id, originalFilename(doc))}
                      className="text-[10px] text-[#4ade80] hover:underline"
                    >
                      View original{fileExtension(doc) ? ` .${fileExtension(doc)}` : ''}
                    </a>
                    <button
                      onClick={() => ingest.deleteDocument(doc.id).then(reload)}
                      className="text-[10px] text-gray-600 hover:text-red-400 cursor-pointer"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-gray-600 text-center py-4">No documents yet.</div>
          )}
        </div>
      </div>
    </div>
  );
}
