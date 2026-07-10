import React, { createContext, useContext, useState } from 'react';

const ToastContext = createContext();

export const ToastProvider = ({ children }) => {
  const [toasts, setToasts] = useState([]);

  const addToast = (message, type = 'success') => {
    const id = Date.now();
    setToasts((prev) => {
      const duplicate = prev.some((toast) => toast.message === message && toast.type === type);
      if (duplicate) return prev;
      return [...prev.slice(-4), { id, message, type }];
    });
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  };

  const removeToast = (id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <div className="fixed bottom-4 left-4 right-4 z-50 flex flex-col gap-2 sm:left-auto sm:w-full sm:max-w-sm">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            onClick={() => removeToast(toast.id)}
            className={`cursor-pointer p-4 rounded-lg shadow-xl border backdrop-blur-xl flex justify-between items-center transition-all transform duration-300 ${
              toast.type === 'success'
                ? 'bg-emerald-950/80 border-emerald-500/30 text-emerald-200 shadow-emerald-500/5'
                : toast.type === 'error'
                ? 'bg-rose-950/80 border-rose-500/30 text-rose-200 shadow-rose-500/5'
                : 'bg-amber-950/80 border-amber-500/30 text-amber-200 shadow-amber-500/5'
            }`}
          >
            <span className="text-sm font-medium">{toast.message}</span>
            <span className="text-xs opacity-50 ml-4">x</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
};

export const useToast = () => useContext(ToastContext);
export default ToastProvider;
