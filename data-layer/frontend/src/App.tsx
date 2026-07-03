import { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { ProductsPage } from './pages/ProductsPage';
import { ProductDetailPage } from './pages/ProductDetailPage';
import { UploadPage } from './pages/UploadPage';
import { FamiliesPage } from './pages/FamiliesPage';
import { PromptsPage } from './pages/PromptsPage';

export default function App() {
  const [page, setPage] = useState('products');
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null);

  const navigate = (p: string) => {
    setPage(p);
    setSelectedProductId(null);
  };

  return (
    <>
      <Sidebar active={page} onNavigate={navigate} />
      <main className="flex-1 overflow-y-auto p-6">
        {page === 'products' && !selectedProductId && (
          <ProductsPage
            onSelectProduct={(id) => {
              setSelectedProductId(id);
              setPage('products');
            }}
          />
        )}
        {page === 'products' && selectedProductId && (
          <ProductDetailPage
            productId={selectedProductId}
            onBack={() => setSelectedProductId(null)}
          />
        )}
        {page === 'upload' && <UploadPage />}
        {page === 'families' && <FamiliesPage />}
        {page === 'prompts' && <PromptsPage />}
      </main>
    </>
  );
}
