import { useEffect, useState } from 'react';
import { prompts, type PromptsConfig } from '../lib/api';

export function PromptsPage() {
  const [config, setConfig] = useState<PromptsConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState<'classifier' | 'extractors'>('classifier');
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [dirty, setDirty] = useState(false);
  const [toast, setToast] = useState('');

  const load = () => {
    setLoading(true);
    prompts.get().then((data) => {
      setConfig(data);
      if (!selectedType && data.document_types.length > 0) {
        setSelectedType(data.document_types[0]);
      }
    }).finally(() => setLoading(false));
  };

  useEffect(load, []);

  useEffect(() => {
    if (!config) return;
    if (activeTab === 'classifier') {
      setEditValue(config.classifier_prompt);
    } else if (selectedType) {
      setEditValue(config.extractor_prompts[selectedType] || config.generic_extractor_instructions);
    }
    setDirty(false);
  }, [activeTab, selectedType, config]);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(''), 2500);
  };

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    try {
      if (activeTab === 'classifier') {
        const updated = await prompts.update({ classifier_prompt: editValue });
        setConfig(updated);
      } else if (selectedType) {
        await prompts.updateExtractor(selectedType, editValue);
        setConfig({
          ...config,
          extractor_prompts: { ...config.extractor_prompts, [selectedType]: editValue },
        });
      }
      setDirty(false);
      showToast('Saved');
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveBaseTemplate = async () => {
    if (!config) return;
    setSaving(true);
    try {
      const updated = await prompts.update({ extractor_base_template: baseEdit });
      setConfig(updated);
      setBaseEdit(updated.extractor_base_template);
      setBaseDirty(false);
      showToast('Base template saved');
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSaving(false);
    }
  };

  const [baseEdit, setBaseEdit] = useState('');
  const [baseDirty, setBaseDirty] = useState(false);
  const [showBase, setShowBase] = useState(false);

  useEffect(() => {
    if (config) setBaseEdit(config.extractor_base_template);
  }, [config]);

  if (loading || !config) {
    return <div className="text-sm text-gray-500 py-8 text-center">Loading prompts...</div>;
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-xl font-bold text-[#f1f5f9]">AI Prompt Configuration</h1>
        <p className="text-xs text-gray-500 mt-1">
          View and edit the prompts sent to the AI for document classification and data extraction.
          Changes take effect immediately on the next analysis.
        </p>
      </div>

      {/* Toast */}
      {toast && (
        <div className="fixed top-4 right-4 bg-[#22c55e] text-[#0f1117] text-xs font-semibold px-4 py-2 rounded-md shadow-lg z-50">
          {toast}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-5">
        {(['classifier', 'extractors'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`text-xs font-semibold px-4 py-2 rounded-md cursor-pointer transition-colors ${
              activeTab === tab
                ? 'bg-[#22c55e] text-[#0f1117]'
                : 'bg-[#1a2030] text-[#9ca3af] hover:bg-[#1f2937] hover:text-[#e2e8f0]'
            }`}
          >
            {tab === 'classifier' ? 'Stage 1: Classifier' : 'Stage 2: Extractors'}
          </button>
        ))}
      </div>

      {/* Classifier tab */}
      {activeTab === 'classifier' && (
        <div>
          <div className="bg-[#1a2030] border border-[#1f2937] rounded-lg p-5">
            <div className="flex items-center justify-between mb-3">
              <div>
                <div className="text-sm font-semibold text-[#f1f5f9]">Classifier Prompt</div>
                <div className="text-[10px] text-gray-500 mt-0.5">
                  This prompt determines which document type a file is. Uses placeholders: {'{types}'} and {'{content}'}.
                </div>
              </div>
              <button
                onClick={handleSave}
                disabled={!dirty || saving}
                className="text-xs font-semibold px-4 py-1.5 rounded-md bg-[#22c55e] text-[#0f1117] hover:bg-[#16a34a] disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors"
              >
                {saving ? '...' : 'Save'}
              </button>
            </div>
            <textarea
              value={editValue}
              onChange={(e) => { setEditValue(e.target.value); setDirty(true); }}
              rows={20}
              className="w-full bg-[#0f1117] border border-[#1f2937] rounded-md px-4 py-3 text-xs text-[#e2e8f0] font-mono outline-none focus:border-[#22c55e50] resize-y leading-relaxed"
            />
          </div>

          {/* Document types list */}
          <div className="bg-[#1a2030] border border-[#1f2937] rounded-lg p-5 mt-4">
            <div className="text-sm font-semibold text-[#f1f5f9] mb-2">Document Types</div>
            <div className="text-[10px] text-gray-500 mb-3">
              These are the labels the classifier can assign. They also determine which extractor prompt is used.
            </div>
            <div className="flex flex-wrap gap-2">
              {config.document_types.map((t) => (
                <span key={t} className="text-[11px] px-2.5 py-1 rounded bg-[#14532d30] text-[#4ade80]">
                  {t}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Extractors tab */}
      {activeTab === 'extractors' && (
        <div>
          {/* Base template toggle */}
          <div className="bg-[#1a2030] border border-[#1f2937] rounded-lg p-4 mb-4">
            <button
              onClick={() => setShowBase(!showBase)}
              className="flex items-center gap-2 text-xs font-semibold text-[#9ca3af] hover:text-[#e2e8f0] cursor-pointer transition-colors"
            >
              <span className={`transition-transform ${showBase ? 'rotate-90' : ''}`}>&rsaquo;</span>
              Base Extraction Template (shared by all extractors)
            </button>
            {showBase && (
              <div className="mt-3">
                <div className="text-[10px] text-gray-500 mb-2">
                  Wraps every extractor. Placeholders: {'{doc_type}'}, {'{specific_instructions}'}, {'{content}'}.
                </div>
                <textarea
                  value={baseEdit}
                  onChange={(e) => { setBaseEdit(e.target.value); setBaseDirty(true); }}
                  rows={16}
                  className="w-full bg-[#0f1117] border border-[#1f2937] rounded-md px-4 py-3 text-xs text-[#e2e8f0] font-mono outline-none focus:border-[#22c55e50] resize-y leading-relaxed"
                />
                <div className="flex justify-end mt-2">
                  <button
                    onClick={handleSaveBaseTemplate}
                    disabled={!baseDirty || saving}
                    className="text-xs font-semibold px-4 py-1.5 rounded-md bg-[#22c55e] text-[#0f1117] hover:bg-[#16a34a] disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors"
                  >
                    {saving ? '...' : 'Save Base Template'}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Per-type extractors */}
          <div className="flex gap-4">
            {/* Type selector */}
            <div className="w-[200px] min-w-[200px]">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Document Type</div>
              <div className="flex flex-col gap-0.5">
                {config.document_types.map((t) => (
                  <button
                    key={t}
                    onClick={() => setSelectedType(t)}
                    className={`text-left text-xs px-3 py-2 rounded-md cursor-pointer transition-colors ${
                      selectedType === t
                        ? 'bg-[#14532d30] text-[#4ade80]'
                        : 'text-[#9ca3af] hover:bg-[#1f2937] hover:text-[#e2e8f0]'
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            {/* Editor */}
            <div className="flex-1">
              {selectedType && (
                <div className="bg-[#1a2030] border border-[#1f2937] rounded-lg p-5">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <div className="text-sm font-semibold text-[#f1f5f9]">{selectedType} Extractor</div>
                      <div className="text-[10px] text-gray-500 mt-0.5">
                        Specific instructions for extracting data from {selectedType} documents.
                      </div>
                    </div>
                    <button
                      onClick={handleSave}
                      disabled={!dirty || saving}
                      className="text-xs font-semibold px-4 py-1.5 rounded-md bg-[#22c55e] text-[#0f1117] hover:bg-[#16a34a] disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors"
                    >
                      {saving ? '...' : 'Save'}
                    </button>
                  </div>
                  <textarea
                    value={editValue}
                    onChange={(e) => { setEditValue(e.target.value); setDirty(true); }}
                    rows={16}
                    className="w-full bg-[#0f1117] border border-[#1f2937] rounded-md px-4 py-3 text-xs text-[#e2e8f0] font-mono outline-none focus:border-[#22c55e50] resize-y leading-relaxed"
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
