import { useState, useEffect } from 'react';
import { RefreshCw } from 'lucide-react';

export function UpdateBanner() {
  const [showBanner, setShowBanner] = useState(false);

  useEffect(() => {
    const handleUpdate = () => setShowBanner(true);
    const handleVersionChange = () => setShowBanner(true);

    window.addEventListener('sw-update-available', handleUpdate);
    window.addEventListener('sw-version-changed', handleVersionChange);

    return () => {
      window.removeEventListener('sw-update-available', handleUpdate);
      window.removeEventListener('sw-version-changed', handleVersionChange);
    };
  }, []);

  if (!showBanner) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 bg-blue-600 text-white px-4 py-3 rounded-xl shadow-lg flex items-center gap-3">
      <RefreshCw size={18} className="animate-spin" />
      <span className="text-sm font-medium">Update available</span>
      <button
        onClick={() => window.location.reload()}
        className="bg-white text-blue-600 px-3 py-1.5 rounded-lg text-sm font-bold hover:bg-blue-50 transition-colors"
      >
        Reload
      </button>
    </div>
  );
}
