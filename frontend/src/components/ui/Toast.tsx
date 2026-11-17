import { CheckCircle2, Info, TriangleAlert, XCircle } from 'lucide-react';
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react';

type ToastTone = 'success' | 'info' | 'warning' | 'danger';
interface Item {
  id: number;
  text: string;
  tone: ToastTone;
}

const ICONS = {
  success: <CheckCircle2 className="h-4 w-4 text-success" aria-hidden />,
  info: <Info className="h-4 w-4 text-info" aria-hidden />,
  warning: <TriangleAlert className="h-4 w-4 text-warning" aria-hidden />,
  danger: <XCircle className="h-4 w-4 text-danger" aria-hidden />,
};

const ToastContext = createContext<{ show: (text: string, tone?: ToastTone) => void }>({ show: () => undefined });

/** Short messages at the top centre that disappear after 4 seconds. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Item[]>([]);
  const next = useRef(0);
  const show = useCallback((text: string, tone: ToastTone = 'success') => {
    const id = ++next.current;
    setItems((all) => [...all, { id, text, tone }]);
    setTimeout(() => setItems((all) => all.filter((t) => t.id !== id)), 4000);
  }, []);
  const value = useMemo(() => ({ show }), [show]);
  return (
    <ToastContext.Provider value={value}>
      {children}
      <div aria-live="polite" role="status" className="pointer-events-none fixed inset-x-0 top-4 z-[60] flex flex-col items-center gap-2 px-4">
        {items.map((t) => (
          <div key={t.id} className="pointer-events-auto flex items-center gap-2 rounded-lg bg-surface px-4 py-2.5 text-sm shadow-card">
            {ICONS[t.tone]}
            {t.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
