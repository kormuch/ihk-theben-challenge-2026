import { useEffect, useState } from 'react';
import { families, type ProductFamily } from '../lib/api';

export function FamiliesPage() {
  const [items, setItems] = useState<ProductFamily[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [creating, setCreating] = useState(false);

  const load = () => {
    setLoading(true);
    families.list().then(setItems).finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleCreate = async () => {
    if (!newName) return;
    setCreating(true);
    try {
      await families.create({ name: newName, description: newDesc || undefined });
      setNewName('');
      setNewDesc('');
      setShowCreate(false);
      load();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!confirm('Delete this family and all its products?')) return;
    await families.delete(id);
    load();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-[#f1f5f9]">Product Families</h1>
          <p className="text-xs text-gray-500">{items.length} families</p>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="text-xs font-semibold px-3 py-1.5 rounded-md bg-[#22c55e] text-[#0f1117] hover:bg-[#16a34a] cursor-pointer transition-colors"
        >
          + New Family
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="bg-[#1a2030] border border-[#1f2937] rounded-lg p-4 mb-5 flex gap-3 items-end">
          <div className="flex-1">
            <label className="text-[10px] text-gray-500 uppercase tracking-wider block mb-1">Name</label>
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="w-full bg-[#0f1117] border border-[#1f2937] rounded-md px-3 py-2 text-sm text-[#e2e8f0] outline-none focus:border-[#22c55e50]"
            />
          </div>
          <div className="flex-1">
            <label className="text-[10px] text-gray-500 uppercase tracking-wider block mb-1">Description</label>
            <input
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              className="w-full bg-[#0f1117] border border-[#1f2937] rounded-md px-3 py-2 text-sm text-[#e2e8f0] outline-none focus:border-[#22c55e50]"
            />
          </div>
          <button
            onClick={handleCreate}
            disabled={creating || !newName}
            className="text-xs font-semibold px-4 py-2 rounded-md bg-[#22c55e] text-[#0f1117] hover:bg-[#16a34a] disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors"
          >
            {creating ? '...' : 'Create'}
          </button>
          <button
            onClick={() => setShowCreate(false)}
            className="text-xs text-gray-500 hover:text-gray-300 px-2 py-2 cursor-pointer"
          >
            Cancel
          </button>
        </div>
      )}

      {loading ? (
        <div className="text-sm text-gray-500 py-8 text-center">Loading...</div>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {items.map((f) => (
            <div key={f.id} className="bg-[#1a2030] border border-[#1f2937] rounded-lg p-5 relative group">
              <button
                onClick={(e) => handleDelete(e, f.id)}
                className="absolute top-3 right-3 text-gray-700 hover:text-red-400 text-xs cursor-pointer transition-colors opacity-0 group-hover:opacity-100"
                title="Delete"
              >
                ✕
              </button>
              <div className="text-sm font-semibold text-[#f1f5f9] mb-1">{f.name}</div>
              <div className="text-xs text-gray-500 mb-3">{f.description}</div>
              <div className="text-[10px] text-gray-600">
                {Object.keys(f.attribute_schema).length} defined attributes
              </div>
              <div className="flex flex-wrap gap-1 mt-2">
                {Object.entries(f.attribute_schema).map(([key, def]: [string, any]) => (
                  <span
                    key={key}
                    className={`text-[9px] px-1.5 py-0.5 rounded ${
                      def.required
                        ? 'bg-[#16a34a15] text-[#4ade80]'
                        : 'bg-[#1f2937] text-[#6b7280]'
                    }`}
                  >
                    {def.label ?? key}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
