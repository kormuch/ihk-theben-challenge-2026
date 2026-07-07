import { useState, useCallback } from 'react';
import { analyze, families, type AnalyzeResult, type ExtractedProduct, type ExistingProductInfo, type ProductFamily } from '../lib/api';
import { useEffect } from 'react';

interface FileJob {
  file: File;
  stage: 'queued' | 'analyzing' | 'extracted' | 'classified' | 'error' | 'confirmed';
  result: AnalyzeResult | null;
  editedProducts: ExtractedProduct[];
  existingProducts: Record<string, ExistingProductInfo>;
  error: string;
  confirmResult: { created: string[]; updated: string[]; errors: any[] } | null;
}

export function UploadPage() {
  const [jobs, setJobs] = useState<FileJob[]>([]);
  const [dragging, setDragging] = useState(false);
  const [fams, setFams] = useState<ProductFamily[]>([]);
  const [processing, setProcessing] = useState(false);

  useEffect(() => {
    families.list().then(setFams);
  }, []);

  const updateJob = (idx: number, patch: Partial<FileJob>) => {
    setJobs((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], ...patch };
      return next;
    });
  };

  const processFile = async (idx: number, job: FileJob) => {
    updateJob(idx, { stage: 'analyzing' });
    try {
      const res = await analyze.upload(job.file);
      if (res.status === 'error') {
        updateJob(idx, { stage: 'error', result: res, error: res.error || 'Analysis failed' });
      } else if (res.status === 'extracted' && res.extraction) {
        // Lookup existing products in DB
        const articleNumbers = res.extraction.products.map((p) => p.article_number).filter(Boolean);
        let existing: Record<string, ExistingProductInfo> = {};
        if (articleNumbers.length > 0) {
          try {
            existing = await analyze.lookup(articleNumbers);
          } catch { /* lookup is best-effort */ }
        }
        updateJob(idx, { stage: 'extracted', result: res, editedProducts: res.extraction.products, existingProducts: existing });
      } else if (res.status === 'classified') {
        updateJob(idx, { stage: 'classified', result: res });
      }
    } catch (err: any) {
      updateJob(idx, { stage: 'error', error: err.message });
    }
  };

  const handleFiles = useCallback(async (files: FileList) => {
    const newJobs: FileJob[] = Array.from(files).map((file) => ({
      file,
      stage: 'queued' as const,
      result: null,
      editedProducts: [],
      existingProducts: {},
      error: '',
      confirmResult: null,
    }));
    const startIdx = jobs.length;
    setJobs((prev) => [...prev, ...newJobs]);

    setProcessing(true);
    for (let i = 0; i < newJobs.length; i++) {
      await processFile(startIdx + i, newJobs[i]);
    }
    setProcessing(false);
  }, [jobs.length]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files.length > 0) handleFiles(e.dataTransfer.files);
  }, [handleFiles]);

  const jobHasMissingArticle = (job: FileJob) =>
    job.editedProducts.some((p) => !p.article_number?.trim());

  const handleConfirm = async (idx: number) => {
    const job = jobs[idx];
    if (!job.result || job.editedProducts.length === 0) return;
    if (jobHasMissingArticle(job)) return;
    updateJob(idx, { stage: 'analyzing' }); // reuse as "working" indicator
    try {
      const res = await analyze.confirm({
        stored_as: job.result.stored_as,
        doc_type: job.result.classification?.document_type || 'Unknown',
        products: job.editedProducts
          .filter((p) => p.family_id)
          .map((p) => ({
            article_number: p.article_number,
            name: p.name,
            family_id: p.family_id!,
            attributes: p.attributes,
          })),
      });
      updateJob(idx, { stage: 'confirmed', confirmResult: res });
    } catch (err: any) {
      updateJob(idx, { stage: 'error', error: err.message });
    }
  };

  const handleConfirmAll = async () => {
    for (let i = 0; i < jobs.length; i++) {
      if (jobs[i].stage === 'extracted' && jobs[i].editedProducts.length > 0) {
        await handleConfirm(i);
      }
    }
  };

  const updateProduct = (jobIdx: number, prodIdx: number, field: string, value: any) => {
    setJobs((prev) => {
      const next = [...prev];
      const products = [...next[jobIdx].editedProducts];
      products[prodIdx] = { ...products[prodIdx], [field]: value };
      next[jobIdx] = { ...next[jobIdx], editedProducts: products };
      return next;
    });
  };

  const removeProduct = (jobIdx: number, prodIdx: number) => {
    setJobs((prev) => {
      const next = [...prev];
      next[jobIdx] = {
        ...next[jobIdx],
        editedProducts: next[jobIdx].editedProducts.filter((_, i) => i !== prodIdx),
      };
      return next;
    });
  };

  const extractedCount = jobs.filter((j) => j.stage === 'extracted').length;
  const totalProducts = jobs.reduce((sum, j) => sum + j.editedProducts.length, 0);

  // Cross-file dedup: article_number → list of file names that contain it
  const dupMap: Record<string, string[]> = {};
  jobs.forEach((job) => {
    if (job.stage !== 'extracted') return;
    job.editedProducts.forEach((p) => {
      if (!p.article_number) return;
      if (!dupMap[p.article_number]) dupMap[p.article_number] = [];
      dupMap[p.article_number].push(job.file.name);
    });
  });
  const dupes = Object.fromEntries(Object.entries(dupMap).filter(([, files]) => files.length > 1));

  return (
    <div>
      <h1 className="text-xl font-bold text-[#f1f5f9] mb-1">AI Document Analysis</h1>
      <p className="text-xs text-gray-500 mb-6">
        Drop files — AI classifies them, extracts product data, and shows you why.
      </p>

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`border-2 border-dashed rounded-lg p-10 text-center transition-colors cursor-pointer mb-6 ${
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
        <div className="text-4xl mb-3">
          {processing ? '⟳' : '☁'}
        </div>
        <div className="text-sm font-semibold text-[#e2e8f0] mb-1">
          {processing ? `Analyzing ${jobs.filter((j) => j.stage === 'analyzing').length} file(s)...` : 'Drop files here or click'}
        </div>
        <div className="text-xs text-gray-500">PDF, CSV, JSON, XML, XLSX — multiple files at once</div>
      </div>

      {/* Bulk actions */}
      {extractedCount > 0 && (
        <div className="flex items-center justify-between bg-[#1a2030] border border-[#1f2937] rounded-lg px-4 py-3 mb-4">
          <div className="text-xs text-[#9ca3af]">
            {extractedCount} file(s) ready — {totalProducts} product(s) extracted
          </div>
          <button
            onClick={handleConfirmAll}
            className="text-xs font-semibold px-4 py-1.5 rounded-md bg-[#22c55e] text-[#0f1117] hover:bg-[#16a34a] cursor-pointer transition-colors"
          >
            Confirm All & Import
          </button>
        </div>
      )}

      {/* File jobs */}
      <div className="space-y-4">
        {jobs.map((job, jobIdx) => (
          <div key={jobIdx} className="bg-[#1a2030] border border-[#1f2937] rounded-lg overflow-hidden">
            {/* File header */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-[#1f293750]">
              <div className="flex items-center gap-3">
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                  job.stage === 'confirmed' ? 'bg-[#16a34a25] text-[#4ade80]' :
                  job.stage === 'extracted' ? 'bg-[#3b82f625] text-[#60a5fa]' :
                  job.stage === 'error' ? 'bg-[#ef444425] text-[#f87171]' :
                  job.stage === 'analyzing' || job.stage === 'queued' ? 'bg-[#f59e0b25] text-[#fbbf24]' :
                  'bg-[#1f2937] text-[#6b7280]'
                }`}>
                  {job.stage === 'queued' ? 'Queued' :
                   job.stage === 'analyzing' ? 'Analyzing...' :
                   job.stage === 'extracted' ? 'Ready' :
                   job.stage === 'classified' ? 'Low confidence' :
                   job.stage === 'confirmed' ? 'Imported' :
                   'Error'}
                </span>
                <span className="text-sm text-[#e2e8f0]">{job.file.name}</span>
                <span className="text-[10px] text-gray-600">{(job.file.size / 1024).toFixed(1)} KB</span>
              </div>
              <div className="flex items-center gap-3">
                {job.result?.classification && (
                  <span className="text-[10px] text-[#9ca3af]">
                    {job.result.classification.document_type} ({job.result.classification.confidence}%)
                  </span>
                )}
                {job.stage === 'extracted' && job.editedProducts.length > 0 && (
                  <button
                    onClick={() => handleConfirm(jobIdx)}
                    disabled={jobHasMissingArticle(job)}
                    className={`text-[10px] font-semibold px-3 py-1 rounded transition-colors ${jobHasMissingArticle(job) ? 'bg-[#374151] text-[#6b7280] cursor-not-allowed' : 'bg-[#22c55e] text-[#0f1117] hover:bg-[#16a34a] cursor-pointer'}`}
                    title={jobHasMissingArticle(job) ? 'Article number required for all products' : ''}
                  >
                    Confirm ({job.editedProducts.length})
                  </button>
                )}
              </div>
            </div>

            {/* Error */}
            {job.stage === 'error' && (
              <div className="px-5 py-3 text-xs text-[#f87171]">{job.error}</div>
            )}

            {/* Classification reasoning */}
            {job.result?.classification && job.stage !== 'queued' && job.stage !== 'analyzing' && (
              <div className="px-5 py-3 border-b border-[#1f293730]">
                <div className="text-[10px] text-gray-500 mb-1">Classification reasoning</div>
                <div className="text-xs text-[#9ca3af] italic">{job.result.classification.reasoning}</div>
                {job.result.classification.detected_products?.length > 0 && (
                  <div className="text-[10px] text-gray-500 mt-1">
                    Detected: {job.result.classification.detected_products.join(', ')}
                  </div>
                )}
              </div>
            )}

            {/* Low confidence — let user pick doc type and re-extract */}
            {job.stage === 'classified' && job.result?.needs_review && (
              <div className="px-5 py-3 space-y-2">
                <div className="text-xs text-[#fbbf24]">
                  Confidence too low for auto-extraction. Select or type a document type to retry:
                </div>
                <div className="flex items-center gap-2">
                  <select
                    defaultValue={job.result.classification?.document_type || ''}
                    id={`doctype-${jobIdx}`}
                    className="bg-[#161b27] border border-[#1f2937] rounded px-2 py-1 text-xs text-[#e2e8f0] outline-none cursor-pointer"
                  >
                    {['Datasheet', 'Lab Report', 'Certificate', 'Software Documentation', 'Bill of Materials',
                      'Marketing Material', 'Compliance Declaration', 'Safety Data Sheet', 'Product Specification', 'Test Report',
                    ].map((t) => <option key={t} value={t}>{t}</option>)}
                    <option value="__custom">Custom...</option>
                  </select>
                  <input
                    id={`doctype-custom-${jobIdx}`}
                    placeholder="Custom type..."
                    className="bg-[#161b27] border border-[#1f2937] rounded px-2 py-1 text-xs text-[#e2e8f0] outline-none w-[160px]"
                  />
                  <button
                    onClick={async () => {
                      const select = document.getElementById(`doctype-${jobIdx}`) as HTMLSelectElement;
                      const custom = document.getElementById(`doctype-custom-${jobIdx}`) as HTMLInputElement;
                      const docType = select.value === '__custom' ? custom.value : select.value;
                      if (!docType || !job.result?.stored_as) return;
                      updateJob(jobIdx, { stage: 'analyzing' as const });
                      try {
                        const res = await analyze.reExtract(job.result.stored_as, docType);
                        const articleNumbers = res.extraction.products.map((p) => p.article_number).filter(Boolean);
                        let existing: Record<string, ExistingProductInfo> = {};
                        if (articleNumbers.length > 0) {
                          try { existing = await analyze.lookup(articleNumbers); } catch {}
                        }
                        updateJob(jobIdx, {
                          stage: 'extracted',
                          result: { ...job.result!, status: 'extracted', extraction: res.extraction, classification: { ...job.result!.classification!, document_type: docType, confidence: 100 } },
                          editedProducts: res.extraction.products,
                          existingProducts: existing,
                        });
                      } catch (err: any) {
                        updateJob(jobIdx, { stage: 'error', error: err.message });
                      }
                    }}
                    className="text-[10px] font-semibold px-3 py-1 rounded bg-[#3b82f6] text-white hover:bg-[#2563eb] cursor-pointer transition-colors"
                  >
                    Re-extract
                  </button>
                </div>
              </div>
            )}

            {/* Extracted products */}
            {job.stage === 'extracted' && job.editedProducts.length > 0 && (
              <div className="px-5 py-3 space-y-3">
                {job.editedProducts.map((product, prodIdx) => {
                  const existing = job.existingProducts[product.article_number];
                  const dupFiles = dupes[product.article_number];
                  return (
                  <div key={prodIdx} className={`bg-[#0f1117] border rounded-lg p-4 ${dupFiles ? 'border-[#ef444450]' : existing ? 'border-[#f59e0b50]' : 'border-[#1f293750]'}`}>
                    {/* Cross-file duplicate warning */}
                    {dupFiles && (
                      <div className="flex items-center gap-2 mb-3 px-2 py-1.5 bg-[#ef444410] border border-[#ef444430] rounded text-xs text-[#f87171]">
                        <span className="font-semibold">Multiple sources</span>
                        <span className="text-[#e2e8f0]">— {product.article_number} also found in: {dupFiles.filter((f) => f !== job.file.name).join(', ') || 'this file (multiple)'}. Data will be merged on confirm.</span>
                      </div>
                    )}
                    {/* Existing product banner */}
                    {existing && (
                      <div className="flex items-center gap-2 mb-3 px-2 py-1.5 bg-[#f59e0b10] border border-[#f59e0b30] rounded text-xs text-[#fbbf24]">
                        <span className="font-semibold">UPDATE</span>
                        <span className="text-[#9ca3af]">— "{existing.name}" already exists in DB. Confirming will merge attributes.</span>
                      </div>
                    )}

                    <div className="flex items-start justify-between mb-3">
                      <div className="flex gap-3 items-end flex-1">
                        <div>
                          <label className={`text-[10px] uppercase tracking-wider block mb-1 ${!product.article_number?.trim() ? 'text-red-400' : 'text-gray-500'}`}>Article No. {!product.article_number?.trim() && '*'}</label>
                          <input
                            value={product.article_number}
                            onChange={(e) => updateProduct(jobIdx, prodIdx, 'article_number', e.target.value)}
                            placeholder="Required"
                            className={`bg-[#161b27] border rounded px-2 py-1 text-sm text-[#e2e8f0] outline-none w-[140px] ${!product.article_number?.trim() ? 'border-red-500' : 'border-[#1f2937]'}`}
                          />
                        </div>
                        <div className="flex-1">
                          <label className="text-[10px] text-gray-500 uppercase tracking-wider block mb-1">Name</label>
                          <input
                            value={product.name}
                            onChange={(e) => updateProduct(jobIdx, prodIdx, 'name', e.target.value)}
                            className="bg-[#161b27] border border-[#1f2937] rounded px-2 py-1 text-sm text-[#e2e8f0] outline-none w-full"
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-gray-500 uppercase tracking-wider block mb-1">Family</label>
                          <select
                            value={product.family_id || ''}
                            onChange={(e) => updateProduct(jobIdx, prodIdx, 'family_id', e.target.value)}
                            className="bg-[#161b27] border border-[#1f2937] rounded px-2 py-1 text-sm text-[#e2e8f0] outline-none cursor-pointer"
                          >
                            <option value="">— {product.family_name || 'Select'} —</option>
                            {fams.map((f) => (
                              <option key={f.id} value={f.id}>{f.name}</option>
                            ))}
                          </select>
                        </div>
                      </div>
                      <button
                        onClick={() => removeProduct(jobIdx, prodIdx)}
                        className="text-gray-600 hover:text-red-400 text-xs ml-3 mt-5 cursor-pointer"
                      >
                        ✕
                      </button>
                    </div>

                    {/* Attributes with citations + diff */}
                    <div className="space-y-1">
                      {Object.entries(product.attributes).map(([key, value]) => {
                        const citation = product.citations?.[key];
                        const oldVal = existing?.attributes?.[key];
                        const hasChanged = existing && oldVal !== undefined && String(oldVal) !== String(value);
                        const isNew = existing && oldVal === undefined;
                        return (
                          <div key={key} className="flex items-start gap-3 text-xs">
                            <div className="w-[140px] min-w-[140px] text-gray-500 pt-0.5">{key}</div>
                            <div className={`flex-1 ${isNew ? 'text-[#4ade80]' : hasChanged ? 'text-[#fbbf24]' : 'text-[#e2e8f0]'}`}>
                              {typeof value === 'boolean'
                                ? value ? '✓ Yes' : '✗ No'
                                : Array.isArray(value)
                                ? value.join(', ')
                                : String(value ?? '—')}
                              {hasChanged && (
                                <span className="text-[10px] text-[#6b7280] ml-2">was: {String(oldVal)}</span>
                              )}
                              {isNew && (
                                <span className="text-[10px] text-[#4ade8080] ml-2">new</span>
                              )}
                            </div>
                            {citation && (
                              <div className="text-[10px] text-[#4ade80] max-w-[280px] italic opacity-70" title={citation}>
                                {citation.length > 70 ? citation.slice(0, 70) + '…' : citation}
                              </div>
                            )}
                          </div>
                        );
                      })}
                      {/* Show existing attributes not in extraction */}
                      {existing && Object.entries(existing.attributes).map(([key, value]) => {
                        if (product.attributes[key] !== undefined) return null;
                        return (
                          <div key={key} className="flex items-start gap-3 text-xs">
                            <div className="w-[140px] min-w-[140px] text-gray-500 pt-0.5">{key}</div>
                            <div className="text-[#6b7280] flex-1">
                              {String(value)} <span className="text-[10px] ml-2">kept from DB</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                  );
                })}
              </div>
            )}

            {/* Confirmed */}
            {job.stage === 'confirmed' && job.confirmResult && (
              <div className="px-5 py-3 text-xs text-[#4ade80]">
                {job.confirmResult.created.length > 0 && `Created: ${job.confirmResult.created.join(', ')}. `}
                {job.confirmResult.updated.length > 0 && `Updated: ${job.confirmResult.updated.join(', ')}. `}
                {job.confirmResult.errors.length > 0 && (
                  <span className="text-[#f87171]">
                    Errors: {job.confirmResult.errors.map((e) => `${e.article_number}: ${e.error}`).join(', ')}
                  </span>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Clear */}
      {jobs.length > 0 && !processing && (
        <button
          onClick={() => setJobs([])}
          className="text-xs text-gray-600 hover:text-gray-400 mt-4 cursor-pointer"
        >
          Clear all
        </button>
      )}
    </div>
  );
}
