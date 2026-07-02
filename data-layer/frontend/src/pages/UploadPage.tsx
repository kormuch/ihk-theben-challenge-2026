import { useEffect, useState, useCallback } from 'react';
import { products, ingest, type Product, type IngestResult } from '../lib/api';

export function UploadPage() {
  const [productList, setProductList] = useState<Product[]>([]);
  const [selectedProduct, setSelectedProduct] = useState('');
  const [docCategory, setDocCategory] = useState('Technisch');
  const [results, setResults] = useState<IngestResult[]>([]);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    products.list({ limit: 500 }).then(setProductList);
  }, []);

  const handleFiles = useCallback(
    async (files: FileList) => {
      if (!selectedProduct) {
        alert('Bitte zuerst ein Produkt auswählen.');
        return;
      }
      setUploading(true);
      const newResults: IngestResult[] = [];
      for (const file of Array.from(files)) {
        try {
          const result = await ingest.upload(file, selectedProduct, docCategory);
          newResults.push(result);
        } catch (err: any) {
          newResults.push({
            document_id: '',
            filename: file.name,
            status: 'error',
            records_parsed: 0,
            message: err.message ?? 'Upload fehlgeschlagen',
          });
        }
      }
      setResults((prev) => [...newResults, ...prev]);
      setUploading(false);
    },
    [selectedProduct, docCategory],
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      if (e.dataTransfer.files.length > 0) handleFiles(e.dataTransfer.files);
    },
    [handleFiles],
  );

  return (
    <div>
      <h1 className="text-xl font-bold text-[#f1f5f9] mb-1">Datei-Upload</h1>
      <p className="text-xs text-gray-500 mb-6">
        Dateien hochladen, automatisch parsen und Attribute ins Produkt übernehmen.
      </p>

      {/* Config */}
      <div className="flex gap-3 mb-5">
        <select
          value={selectedProduct}
          onChange={(e) => setSelectedProduct(e.target.value)}
          className="flex-1 bg-[#0f1117] border border-[#1f2937] rounded-md px-3 py-2 text-sm text-[#e2e8f0] outline-none cursor-pointer"
        >
          <option value="">— Produkt wählen —</option>
          {productList.map((p) => (
            <option key={p.id} value={p.id}>
              {p.article_number} — {p.name}
            </option>
          ))}
        </select>
        <select
          value={docCategory}
          onChange={(e) => setDocCategory(e.target.value)}
          className="bg-[#0f1117] border border-[#1f2937] rounded-md px-3 py-2 text-sm text-[#e2e8f0] outline-none cursor-pointer"
        >
          <option>Technisch</option>
          <option>Regulatorik</option>
          <option>Marketing</option>
          <option>Qualität</option>
        </select>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors cursor-pointer mb-6 ${
          dragging
            ? 'border-[#22c55e] bg-[#22c55e0a]'
            : 'border-[#2d3748] hover:border-[#22c55e] hover:bg-[#22c55e06]'
        }`}
        onClick={() => {
          const input = document.createElement('input');
          input.type = 'file';
          input.multiple = true;
          input.onchange = () => input.files && handleFiles(input.files);
          input.click();
        }}
      >
        <div className="text-4xl mb-3">☁</div>
        <div className="text-sm font-semibold text-[#e2e8f0] mb-1">
          {uploading ? 'Upload läuft...' : 'Dateien hier ablegen oder klicken'}
        </div>
        <div className="text-xs text-gray-500">CSV, JSON, XML, XLSX, PDF — mehrere Dateien gleichzeitig</div>
      </div>

      {/* Results */}
      {results.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-[#e2e8f0] mb-3">Ergebnisse</h2>
          <div className="space-y-2">
            {results.map((r, i) => (
              <div key={i} className="bg-[#1a2030] border border-[#1f2937] rounded-lg p-4 flex items-start gap-3">
                <span
                  className={`text-[10px] font-semibold px-2 py-0.5 rounded-full whitespace-nowrap mt-0.5 ${
                    r.status === 'done'
                      ? 'bg-[#16a34a25] text-[#4ade80]'
                      : 'bg-[#ef444425] text-[#f87171]'
                  }`}
                >
                  {r.status === 'done' ? '✓' : '✗'}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="text-sm text-[#e2e8f0] font-medium">{r.filename}</div>
                  <div className="text-xs text-gray-500 mt-0.5">{r.message}</div>
                  {r.records_parsed > 0 && (
                    <div className="text-[10px] text-[#4ade80] mt-1">{r.records_parsed} Datensätze extrahiert</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
