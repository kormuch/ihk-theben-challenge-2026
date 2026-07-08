import { useEffect, useState } from 'react';
import { products, families, exportApi, legacyTheben, type Product, type ProductFamily } from '../lib/api';

interface Props {
  onSelectProduct: (id: string) => void;
}

export function ProductsPage({ onSelectProduct }: Props) {
  const [items, setItems] = useState<Product[]>([]);
  const [fams, setFams] = useState<ProductFamily[]>([]);
  const [search, setSearch] = useState('');
  const [familyFilter, setFamilyFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newArticle, setNewArticle] = useState('');
  const [newFamily, setNewFamily] = useState('');
  const [creating, setCreating] = useState(false);
  const [importingLegacy, setImportingLegacy] = useState(false);
  const [importingBundled, setImportingBundled] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    products
      .list({ search: search || undefined, family_id: familyFilter || undefined })
      .then(setItems)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    families.list().then(setFams);
  }, []);

  useEffect(load, [search, familyFilter]);

  const familyName = (fid: string) => fams.find((f) => f.id === fid)?.name ?? '—';

  const handleCreate = async () => {
    if (!newName || !newArticle || !newFamily) return;
    setCreating(true);
    try {
      await products.create({ name: newName, article_number: newArticle, family_id: newFamily });
      setNewName('');
      setNewArticle('');
      setNewFamily('');
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
    if (confirmDeleteId === id) {
      setConfirmDeleteId(null);
      await products.delete(id);
      load();
    } else {
      setConfirmDeleteId(id);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-[#f1f5f9]">Products</h1>
          <p className="text-xs text-gray-500">{items.length} products loaded</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={async () => {
              setImportingBundled(true);
              try {
                const res = await legacyTheben.importBundledProducts();
                alert(`Imported ${res.count} bundled Theben product(s). Created: ${res.created.length}, updated: ${res.updated.length}.`);
                load();
              } catch (err: any) {
                alert('Bundled Theben import failed: ' + err.message);
              } finally {
                setImportingBundled(false);
              }
            }}
            disabled={importingBundled}
            className="text-xs font-semibold px-3 py-1.5 rounded-md bg-[#64748b] text-white hover:bg-[#475569] disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors"
          >
            {importingBundled ? 'Importing...' : 'Import Bundled Theben'}
          </button>
          <button
            onClick={async () => {
              setImportingLegacy(true);
              try {
                const res = await legacyTheben.importProducts();
                alert(`Imported ${res.count} product(s) from ${res.source}. Created: ${res.created.length}, updated: ${res.updated.length}.`);
                load();
              } catch (err: any) {
                alert('Theben REST import failed: ' + err.message);
              } finally {
                setImportingLegacy(false);
              }
            }}
            disabled={importingLegacy}
            className="text-xs font-semibold px-3 py-1.5 rounded-md bg-[#0ea5e9] text-white hover:bg-[#0284c7] disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors"
          >
            {importingLegacy ? 'Importing...' : 'Import Theben REST'}
          </button>
          <button
            onClick={async () => {
              try {
                const res = await exportApi.productsJson();
                alert(`Exported ${res.products.length} products to product-layer.`);
              } catch (err: any) {
                alert('Export failed: ' + err.message);
              }
            }}
            className="text-xs font-semibold px-3 py-1.5 rounded-md bg-[#3b82f6] text-white hover:bg-[#2563eb] cursor-pointer transition-colors"
          >
            Export to Product Layer
          </button>
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="text-xs font-semibold px-3 py-1.5 rounded-md bg-[#22c55e] text-[#0f1117] hover:bg-[#16a34a] cursor-pointer transition-colors"
          >
            + New Product
          </button>
        </div>
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
          <div className="w-[160px]">
            <label className="text-[10px] text-gray-500 uppercase tracking-wider block mb-1">Article No.</label>
            <input
              value={newArticle}
              onChange={(e) => setNewArticle(e.target.value)}
              className="w-full bg-[#0f1117] border border-[#1f2937] rounded-md px-3 py-2 text-sm text-[#e2e8f0] outline-none focus:border-[#22c55e50]"
            />
          </div>
          <div className="w-[160px]">
            <label className="text-[10px] text-gray-500 uppercase tracking-wider block mb-1">Family</label>
            <select
              value={newFamily}
              onChange={(e) => setNewFamily(e.target.value)}
              className="w-full bg-[#0f1117] border border-[#1f2937] rounded-md px-3 py-2 text-sm text-[#e2e8f0] outline-none cursor-pointer"
            >
              <option value="">— Select —</option>
              {fams.map((f) => (
                <option key={f.id} value={f.id}>{f.name}</option>
              ))}
            </select>
          </div>
          <button
            onClick={handleCreate}
            disabled={creating || !newName || !newArticle || !newFamily}
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

      {/* Filters */}
      <div className="flex gap-3 mb-5">
        <input
          type="text"
          placeholder="Search (name / article no.)"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 bg-[#0f1117] border border-[#1f2937] rounded-md px-3 py-2 text-sm text-[#e2e8f0] outline-none focus:border-[#22c55e50]"
        />
        <select
          value={familyFilter}
          onChange={(e) => setFamilyFilter(e.target.value)}
          className="bg-[#0f1117] border border-[#1f2937] rounded-md px-3 py-2 text-sm text-[#e2e8f0] outline-none cursor-pointer"
        >
          <option value="">All Families</option>
          {fams.map((f) => (
            <option key={f.id} value={f.id}>{f.name}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      {loading ? (
        <div className="text-sm text-gray-500 py-8 text-center">Loading products...</div>
      ) : items.length === 0 ? (
        <div className="text-sm text-gray-500 py-8 text-center">No products found.</div>
      ) : (
        <table className="w-full border-collapse">
          <thead>
            <tr>
              <th className="text-left text-[10px] text-gray-600 font-semibold uppercase tracking-wider px-3 py-2 border-b border-[#1f2937]">Article No.</th>
              <th className="text-left text-[10px] text-gray-600 font-semibold uppercase tracking-wider px-3 py-2 border-b border-[#1f2937]">Name</th>
              <th className="text-left text-[10px] text-gray-600 font-semibold uppercase tracking-wider px-3 py-2 border-b border-[#1f2937]">Family</th>
              <th className="text-left text-[10px] text-gray-600 font-semibold uppercase tracking-wider px-3 py-2 border-b border-[#1f2937]">Attributes</th>
              <th className="text-left text-[10px] text-gray-600 font-semibold uppercase tracking-wider px-3 py-2 border-b border-[#1f2937]">Created</th>
              <th className="w-8 border-b border-[#1f2937]"></th>
            </tr>
          </thead>
          <tbody>
            {items.map((p) => (
              <tr
                key={p.id}
                onClick={() => onSelectProduct(p.id)}
                className="cursor-pointer hover:bg-[#1f293720] transition-colors"
              >
                <td className="px-3 py-2.5 text-sm text-[#e2e8f0] font-medium border-b border-[#1f293710]">{p.article_number}</td>
                <td className="px-3 py-2.5 text-sm text-[#9ca3af] border-b border-[#1f293710]">{p.name}</td>
                <td className="px-3 py-2.5 border-b border-[#1f293710]">
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#16a34a25] text-[#4ade80]">
                    {familyName(p.family_id)}
                  </span>
                </td>
                <td className="px-3 py-2.5 text-sm text-[#9ca3af] border-b border-[#1f293710]">{Object.keys(p.attributes).length}</td>
                <td className="px-3 py-2.5 text-xs text-gray-600 border-b border-[#1f293710]">{new Date(p.created_at).toLocaleDateString('en')}</td>
                <td className="px-1 py-2.5 border-b border-[#1f293710]">
                  <button
                    onClick={(e) => handleDelete(e, p.id)}
                    onBlur={() => setConfirmDeleteId(null)}
                    className={`text-xs cursor-pointer transition-colors ${confirmDeleteId === p.id ? 'text-red-500 font-bold' : 'text-gray-700 hover:text-red-400'}`}
                    title={confirmDeleteId === p.id ? 'Click again to confirm' : 'Delete'}
                  >
                    {confirmDeleteId === p.id ? 'Sure?' : '✕'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
