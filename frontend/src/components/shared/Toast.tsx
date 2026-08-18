import { AnimatePresence, motion } from 'framer-motion';
import { CheckCircle2, Info, XCircle } from 'lucide-react';
import type { Toast } from '../../hooks/useToast';

interface ToastListProps {
  toasts: Toast[];
  onDismiss: (id: string) => void;
}

const VARIANT_STYLES: Record<Toast['variant'], string> = {
  success: 'bg-emerald-900 text-white',
  error: 'bg-red-900 text-white',
  info: 'bg-gray-900 text-white',
};

const VARIANT_ICON: Record<Toast['variant'], typeof CheckCircle2> = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
};

export function ToastList({ toasts, onDismiss }: ToastListProps) {
  return (
    <div className="fixed bottom-6 right-6 z-[100] flex flex-col gap-2 items-end pointer-events-none">
      <AnimatePresence>
        {toasts.map(toast => {
          const Icon = VARIANT_ICON[toast.variant];
          return (
            <motion.div
              key={toast.id}
              initial={{ opacity: 0, y: 12, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.96 }}
              transition={{ duration: 0.18, ease: 'easeOut' }}
              className={`pointer-events-auto flex items-center gap-2.5 rounded-lg px-4 py-2.5 text-sm font-medium shadow-lg ${VARIANT_STYLES[toast.variant]}`}
              onClick={() => onDismiss(toast.id)}
            >
              <Icon className="h-4 w-4 shrink-0 opacity-90" />
              {toast.message}
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
