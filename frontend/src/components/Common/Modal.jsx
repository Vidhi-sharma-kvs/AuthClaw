import React, { useEffect } from 'react';
import { X } from 'lucide-react';

const Modal = ({ isOpen, onClose, title, children }) => {
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape') onClose();
    };

    if (isOpen) {
      document.body.style.overflow = 'hidden';
      window.addEventListener('keydown', handleEscape);
    }

    return () => {
      document.body.style.overflow = 'unset';
      window.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Overlay backdrop */}
      <div 
        className="absolute inset-0 bg-[#0E1726]/35 backdrop-blur-sm transition-opacity duration-300" 
        onClick={onClose}
      />
      
      {/* Modal Container */}
      <div className="relative w-full max-w-lg overflow-hidden rounded-xl border border-[#E6E9F0] bg-[#FBFAF9]/95 shadow-[0_1px_2px_rgba(11,31,63,0.05),0_24px_60px_-24px_rgba(11,31,63,0.35)] backdrop-blur-xl transition-all duration-300 z-10">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#E6E9F0] px-6 py-4 bg-white/80">
          <h3 className="text-base font-bold text-[#0E1726] font-display">
            {title}
          </h3>
          <button 
            onClick={onClose} 
            className="rounded-lg p-1 text-[#6B7488] hover:bg-[#F1ECFE] hover:text-[#6D28D9] transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 max-h-[80vh] overflow-y-auto custom-scrollbar">
          {children}
        </div>
      </div>
    </div>
  );
};

export default Modal;
