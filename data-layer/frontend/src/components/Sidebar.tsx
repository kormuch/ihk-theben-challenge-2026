interface SidebarProps {
  active: string;
  onNavigate: (page: string) => void;
}

const NAV_ITEMS = [
  { id: 'products', icon: '⊞', label: 'Produkte' },
  { id: 'upload', icon: '☁', label: 'Upload' },
  { id: 'families', icon: '≡', label: 'Produktfamilien' },
];

export function Sidebar({ active, onNavigate }: SidebarProps) {
  return (
    <div className="w-[220px] min-w-[220px] bg-[#161b27] border-r border-[#1f2937] flex flex-col overflow-y-auto">
      {/* Logo */}
      <div className="flex items-center gap-2 p-4 border-b border-[#1f2937]">
        <div className="w-0 h-0 border-l-[9px] border-r-[9px] border-b-[16px] border-l-transparent border-r-transparent border-b-[#22c55e]" />
        <div>
          <div className="text-[10.5px] font-extrabold tracking-[1.8px] text-white leading-tight">PAUL</div>
          <div className="text-[9px] text-gray-500 tracking-[1px]">DATA LAYER</div>
        </div>
      </div>

      {/* Nav */}
      <nav className="p-2 flex-1">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            onClick={() => onNavigate(item.id)}
            className={`flex items-center gap-2 w-full px-3 py-2 rounded-md text-[13px] cursor-pointer transition-colors mb-0.5 ${
              active === item.id
                ? 'bg-[#14532d30] text-[#4ade80]'
                : 'text-[#9ca3af] hover:bg-[#1f2937] hover:text-[#e2e8f0]'
            }`}
          >
            <span className="w-4 text-center text-[13px] opacity-70">{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>

      {/* Bottom */}
      <div className="p-2 border-t border-[#1f2937] mt-auto">
        <div className="px-3 py-1.5 text-[11px] text-gray-500">
          PAUL v0.1.0
        </div>
      </div>
    </div>
  );
}
