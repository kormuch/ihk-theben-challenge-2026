import { useEffect, useState } from 'react';
import { families, type ProductFamily } from '../lib/api';

export function FamiliesPage() {
  const [items, setItems] = useState<ProductFamily[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    families.list().then(setItems).finally(() => setLoading(false));
  };

  useEffect(load, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-[#f1f5f9]">Produktfamilien</h1>
          <p className="text-xs text-gray-500">{items.length} Familien</p>
        </div>
      </div>

      {loading ? (
        <div className="text-sm text-gray-500 py-8 text-center">Lade...</div>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {items.map((f) => (
            <div key={f.id} className="bg-[#1a2030] border border-[#1f2937] rounded-lg p-5">
              <div className="text-sm font-semibold text-[#f1f5f9] mb-1">{f.name}</div>
              <div className="text-xs text-gray-500 mb-3">{f.description}</div>
              <div className="text-[10px] text-gray-600">
                {Object.keys(f.attribute_schema).length} definierte Attribute
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
