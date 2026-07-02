import { useEffect, useState } from 'react';
import { products, families, type Product, type ProductFamily } from '../lib/api';

interface Props {
  onSelectProduct: (id: string) => void;
}

export function ProductsPage({ onSelectProduct }: Props) {
  const [items, setItems] = useState<Product[]>([]);
  const [fams, setFams] = useState<ProductFamily[]>([]);
  const [search, setSearch] = useState('');
  const [familyFilter, setFamilyFilter] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    families.list().then(setFams);
  }, []);

  useEffect(() => {
    setLoading(true);
    products
      .list({ search: search || undefined, family_id: familyFilter || undefined })
      .then(setItems)
      .finally(() => setLoading(false));
  }, [search, familyFilter]);

  const familyName = (fid: string) => fams.find((f) => f.id === fid)?.name ?? '—';

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-[#f1f5f9]">Produkte</h1>
          <p className="text-xs text-gray-500">{items.length} Produkte geladen</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-5">
        <input
          type="text"
          placeholder="Suche (Name / Artikelnr.)"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 bg-[#0f1117] border border-[#1f2937] rounded-md px-3 py-2 text-sm text-[#e2e8f0] outline-none focus:border-[#22c55e50]"
        />
        <select
          value={familyFilter}
          onChange={(e) => setFamilyFilter(e.target.value)}
          className="bg-[#0f1117] border border-[#1f2937] rounded-md px-3 py-2 text-sm text-[#e2e8f0] outline-none cursor-pointer"
        >
          <option value="">Alle Familien</option>
          {fams.map((f) => (
            <option key={f.id} value={f.id}>{f.name}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      {loading ? (
        <div className="text-sm text-gray-500 py-8 text-center">Lade Produkte...</div>
      ) : items.length === 0 ? (
        <div className="text-sm text-gray-500 py-8 text-center">Keine Produkte gefunden.</div>
      ) : (
        <table className="w-full border-collapse">
          <thead>
            <tr>
              <th className="text-left text-[10px] text-gray-600 font-semibold uppercase tracking-wider px-3 py-2 border-b border-[#1f2937]">Artikelnr.</th>
              <th className="text-left text-[10px] text-gray-600 font-semibold uppercase tracking-wider px-3 py-2 border-b border-[#1f2937]">Name</th>
              <th className="text-left text-[10px] text-gray-600 font-semibold uppercase tracking-wider px-3 py-2 border-b border-[#1f2937]">Familie</th>
              <th className="text-left text-[10px] text-gray-600 font-semibold uppercase tracking-wider px-3 py-2 border-b border-[#1f2937]">Attribute</th>
              <th className="text-left text-[10px] text-gray-600 font-semibold uppercase tracking-wider px-3 py-2 border-b border-[#1f2937]">Erstellt</th>
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
                <td className="px-3 py-2.5 text-xs text-gray-600 border-b border-[#1f293710]">{new Date(p.created_at).toLocaleDateString('de')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
