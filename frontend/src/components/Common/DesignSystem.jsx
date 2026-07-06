import React, { useState } from 'react';
import { 
  ChevronDown, 
  ChevronUp, 
  Copy, 
  Check, 
  Search, 
  RefreshCw, 
  AlertTriangle, 
  Info, 
  ShieldCheck, 
  ArrowUpDown,
  Download,
  Clock,
  User,
  Activity,
  Layers,
  ArrowRight
} from 'lucide-react';

// 1. Button Component
export const Button = ({ 
  children, 
  variant = 'primary', 
  size = 'md', 
  loading = false, 
  disabled = false, 
  className = '', 
  ...props 
}) => {
  const baseStyles = 'inline-flex items-center justify-center font-semibold rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-violet-500/50 disabled:opacity-50 disabled:pointer-events-none active:scale-[0.98]';
  
  const variants = {
    primary: 'bg-[#6D28D9] hover:bg-[#7C3AED] text-white shadow-md shadow-violet-600/10 border border-violet-700/10 font-display',
    secondary: 'bg-[#EEF1F6] hover:bg-[#E6E9F0] text-[#0E1726] border border-[#E6E9F0]',
    danger: 'bg-gradient-to-r from-rose-600 to-red-600 hover:from-rose-500 hover:to-red-500 text-white shadow-md shadow-rose-500/10 border border-rose-500/10',
    ghost: 'bg-transparent hover:bg-[#EEF1F6] text-slate-500 hover:text-[#0E1726]',
    gold: 'bg-[#E9A93C] hover:bg-[#f2b653] text-[#2A1B04] font-bold shadow-md shadow-amber-500/10'
  };

  const sizes = {
    sm: 'px-3 py-1.5 text-xs gap-1.5',
    md: 'px-4 py-2 text-sm gap-2',
    lg: 'px-5 py-2.5 text-base gap-2.5'
  };

  return (
    <button
      className={`${baseStyles} ${variants[variant]} ${sizes[size]} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <RefreshCw className="w-4 h-4 animate-spin shrink-0" />}
      {children}
    </button>
  );
};

// 2. GlassCard Component
export const GlassCard = ({ children, className = '', hover = true, ...props }) => {
  return (
    <div 
      className={`glass-card p-5 ${
        hover ? 'hover:border-[#6D28D9]/25 hover:shadow-violet-600/5' : ''
      } ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};

// 3. MetricCard Component
export const MetricCard = ({ 
  title, 
  value, 
  change, 
  changeType = 'positive', 
  icon: Icon, 
  className = '' 
}) => {
  const isPositive = changeType === 'positive';
  return (
    <GlassCard className={`flex items-start justify-between ${className}`}>
      <div className="space-y-2">
        <p className="text-xs font-bold text-slate-500 uppercase tracking-wider font-display">{title}</p>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold text-[#0E1726] tracking-tight">{value}</span>
          {change && (
            <span className={`text-xs font-semibold px-2 py-0.5 rounded ${
              isPositive 
                ? 'bg-emerald-500/10 text-emerald-600 border border-emerald-500/20' 
                : 'bg-rose-500/10 text-rose-600 border border-rose-500/20'
            }`}>
              {change}
            </span>
          )}
        </div>
      </div>
      {Icon && (
        <div className="p-2.5 bg-[#6D28D9]/10 border border-[#6D28D9]/20 rounded-lg text-[#6D28D9]">
          <Icon className="w-5 h-5" />
        </div>
      )}
    </GlassCard>
  );
};

// 4. StatusBadge Component
export const StatusBadge = ({ status, className = '' }) => {
  const normalized = status?.toLowerCase() || '';
  
  let styles = 'bg-slate-100 text-slate-600 border-slate-200';
  if (['active', 'approved', 'success', 'online', 'intact', 'clean', 'approved · applied'].includes(normalized)) {
    styles = 'bg-emerald-500/10 text-emerald-700 border-emerald-500/20';
  } else if (['pending', 'warning', 'needs mfa', 'awaiting approval'].includes(normalized)) {
    styles = 'bg-amber-500/10 text-amber-700 border-amber-500/20';
  } else if (['blocked', 'error', 'failed', 'offline', 'tampered'].includes(normalized)) {
    styles = 'bg-rose-500/10 text-rose-700 border-rose-500/20';
  } else if (['info', 'processing'].includes(normalized)) {
    styles = 'bg-blue-500/10 text-blue-700 border-blue-500/20';
  }

  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold border ${styles} ${className}`}>
      {status}
    </span>
  );
};

// 5. SearchBar Component
export const SearchBar = ({ value, onChange, placeholder = 'Search...', className = '' }) => {
  return (
    <div className={`relative ${className}`}>
      <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
      <input
        type="text"
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className="w-full pl-10 pr-4 py-2 bg-white border border-[#E6E9F0] rounded-lg text-sm text-[#0E1726] placeholder-slate-400 focus:outline-none focus:border-[#6D28D9] focus:ring-1 focus:ring-[#6D28D9] transition duration-200"
      />
    </div>
  );
};

// 6. DataTable Component
export const DataTable = ({ 
  columns, 
  data, 
  loading = false, 
  onSort, 
  sortField, 
  sortOrder,
  onRowClick
}) => {
  return (
    <div className="w-full overflow-hidden border border-[#E6E9F0] rounded-xl bg-white/70 backdrop-blur-md shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm border-collapse">
          <thead>
            <tr className="border-b border-[#E6E9F0] bg-[#F5F7FA]">
              {columns.map((col) => (
                <th 
                  key={col.key} 
                  onClick={() => col.sortable && onSort?.(col.key)}
                  className={`px-6 py-4 font-bold text-slate-500 uppercase tracking-wider text-[11px] font-display ${
                    col.sortable ? 'cursor-pointer hover:text-[#0E1726] select-none' : ''
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    {col.header}
                    {col.sortable && (
                      <ArrowUpDown className={`w-3.5 h-3.5 ${sortField === col.key ? 'text-[#6D28D9]' : 'text-slate-400'}`} />
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E6E9F0]">
            {loading ? (
              [...Array(5)].map((_, idx) => (
                <tr key={idx} className="animate-pulse bg-[#F5F7FA]/30">
                  {columns.map((col) => (
                    <td key={col.key} className="px-6 py-4">
                      <div className="h-4 bg-[#E6E9F0]/60 rounded w-2/3" />
                    </td>
                  ))}
                </tr>
              ))
            ) : data.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-6 py-12 text-center text-slate-400 italic">
                  No records found.
                </td>
              </tr>
            ) : (
              data.map((row, idx) => (
                <tr 
                  key={row.id || idx} 
                  onClick={() => onRowClick?.(row)}
                  className={`hover:bg-[#F5F7FA]/50 transition-colors duration-150 ${
                    onRowClick ? 'cursor-pointer' : ''
                  }`}
                >
                  {columns.map((col) => (
                    <td key={col.key} className="px-6 py-4 text-slate-700">
                      {col.render ? col.render(row) : row[col.key]}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// 7. JSONViewer Component (Retains Dark Code Aesthetics to Match Public Gateway Nodes)
export const JSONViewer = ({ data, collapsed = false, className = '' }) => {
  const [copied, setCopied] = useState(false);
  const formatted = JSON.stringify(data, null, 2);

  const handleCopy = () => {
    navigator.clipboard.writeText(formatted);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`relative group border border-white/5 bg-[#0B1F3F] rounded-lg p-4 font-mono text-xs text-[#E7EDF9] overflow-x-auto ${className}`}>
      <button
        onClick={handleCopy}
        className="absolute top-3 right-3 p-1.5 bg-white/5 hover:bg-white/10 text-[#8FA0C4] hover:text-white rounded border border-white/5 transition-all"
        title="Copy JSON"
      >
        {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
      </button>
      <pre className="max-h-[300px] overflow-y-auto pr-8 leading-relaxed">{formatted}</pre>
    </div>
  );
};

// 8. EmptyState Component
export const EmptyState = ({ title, description, icon: Icon, actionLabel, onAction }) => {
  return (
    <div className="flex flex-col items-center justify-center text-center p-12 border border-dashed border-[#E6E9F0] rounded-xl bg-[#F5F7FA]/40">
      {Icon ? (
        <div className="p-4 bg-white border border-[#E6E9F0] rounded-full text-slate-400 mb-4 shadow-sm">
          <Icon className="w-8 h-8" />
        </div>
      ) : (
        <div className="p-4 bg-white border border-[#E6E9F0] rounded-full text-slate-400 mb-4 shadow-sm">
          <Activity className="w-8 h-8" />
        </div>
      )}
      <h3 className="text-base font-bold text-[#0E1726] mb-1 font-display">{title}</h3>
      <p className="text-sm text-slate-500 max-w-sm mb-6">{description}</p>
      {actionLabel && (
        <Button variant="secondary" size="sm" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
};

// 9. ConfirmationDialog Component
export const ConfirmationDialog = ({ 
  isOpen, 
  onClose, 
  onConfirm, 
  title, 
  message, 
  confirmLabel = 'Confirm', 
  cancelLabel = 'Cancel',
  danger = false 
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-[#08152B]/40 backdrop-blur-sm" onClick={onClose} />
      
      {/* Container */}
      <GlassCard className="relative max-w-md w-full z-10 space-y-4 shadow-xl">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${danger ? 'bg-rose-500/10 text-rose-600 border border-rose-500/20' : 'bg-amber-500/10 text-amber-600 border border-amber-500/20'}`}>
            <AlertTriangle className="w-5 h-5" />
          </div>
          <h3 className="text-base font-bold text-[#0E1726] font-display">{title}</h3>
        </div>
        <p className="text-sm text-slate-600 leading-relaxed font-sans">{message}</p>
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="ghost" size="sm" onClick={onClose}>
            {cancelLabel}
          </Button>
          <Button variant={danger ? 'danger' : 'primary'} size="sm" onClick={() => { onConfirm(); onClose(); }}>
            {confirmLabel}
          </Button>
        </div>
      </GlassCard>
    </div>
  );
};
