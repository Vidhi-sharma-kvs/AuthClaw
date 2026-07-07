import React, { useState } from 'react';
import {
  Copy,
  Check,
  Search,
  RefreshCw,
  AlertTriangle,
  Activity,
  ArrowUpDown,
} from 'lucide-react';

export const inputStyles = 'w-full rounded-lg border border-[#E6E9F0] bg-white px-3 py-2.5 text-sm text-[#0E1726] placeholder-[#6B7488] shadow-sm transition duration-200 focus:border-[#A78BFA] focus:outline-none focus:ring-2 focus:ring-[#6D28D9]/15';
export const labelStyles = 'block text-xs font-semibold text-[#475069] mb-1.5';
export const panelStyles = 'rounded-lg border border-[#E6E9F0] bg-[#F5F7FA]/70';
export const codePanelStyles = 'rounded-lg border border-[#E6E9F0] bg-[#F5F7FA] text-[#0E1726]';
export const tabBaseStyles = 'flex items-center gap-2 px-5 py-3 text-sm font-semibold border-b-2 transition-all rounded-t-lg';
export const tabActiveStyles = 'border-[#6D28D9] text-[#0E1726] bg-[#F1ECFE]';
export const tabInactiveStyles = 'border-transparent text-[#475069] hover:text-[#0E1726] hover:bg-white';

export const Button = ({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  className = '',
  ...props
}) => {
  const baseStyles = 'inline-flex items-center justify-center font-semibold rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-[#6D28D9]/25 disabled:opacity-50 disabled:pointer-events-none active:scale-[0.98]';

  const variants = {
    primary: 'bg-[#6D28D9] hover:bg-[#7C3AED] text-white shadow-md shadow-violet-600/10 border border-violet-700/10 font-display',
    secondary: 'bg-white hover:bg-[#F5F7FA] text-[#0E1726] border border-[#E6E9F0] shadow-sm',
    danger: 'bg-rose-600 hover:bg-rose-500 text-white shadow-md shadow-rose-500/10 border border-rose-500/10',
    ghost: 'bg-transparent hover:bg-[#F1ECFE] text-[#475069] hover:text-[#6D28D9]',
    gold: 'bg-[#E9A93C] hover:bg-[#f2b653] text-[#2A1B04] font-bold shadow-md shadow-amber-500/10',
  };

  const sizes = {
    sm: 'px-3 py-1.5 text-xs gap-1.5',
    md: 'px-4 py-2 text-sm gap-2',
    lg: 'px-5 py-2.5 text-base gap-2.5',
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

export const GlassCard = ({ children, className = '', hover = true, ...props }) => {
  return (
    <div
      className={`glass-card p-5 ${
        hover ? 'hover:border-[#A78BFA]/60 hover:shadow-[0_1px_2px_rgba(11,31,63,0.05),0_12px_30px_-12px_rgba(11,31,63,0.18)]' : ''
      } ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};

export const MetricCard = ({
  title,
  value,
  change,
  changeType = 'positive',
  icon: Icon,
  className = '',
}) => {
  const isPositive = changeType === 'positive';
  return (
    <GlassCard className={`flex items-start justify-between ${className}`}>
      <div className="space-y-2">
        <p className="text-xs font-bold text-[#6B7488] uppercase tracking-wider font-display">{title}</p>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold text-[#0E1726] tracking-tight">{value}</span>
          {change && (
            <span className={`text-xs font-semibold px-2 py-0.5 rounded border ${
              isPositive
                ? 'bg-emerald-500/10 text-emerald-700 border-emerald-500/20'
                : 'bg-rose-500/10 text-rose-700 border-rose-500/20'
            }`}>
              {change}
            </span>
          )}
        </div>
      </div>
      {Icon && (
        <div className="p-2.5 bg-[#F1ECFE] border border-[#A78BFA]/30 rounded-lg text-[#6D28D9]">
          <Icon className="w-5 h-5" />
        </div>
      )}
    </GlassCard>
  );
};

export const StatusBadge = ({ status, className = '' }) => {
  const normalized = status?.toLowerCase() || '';

  let styles = 'bg-[#F5F7FA] text-[#475069] border-[#E6E9F0]';
  if (['active', 'approved', 'success', 'online', 'intact', 'clean', 'approved · applied', 'connected', 'completed'].includes(normalized)) {
    styles = 'bg-emerald-500/10 text-emerald-700 border-emerald-500/20';
  } else if (['pending', 'warning', 'needs mfa', 'awaiting approval'].includes(normalized)) {
    styles = 'bg-amber-500/10 text-amber-700 border-amber-500/20';
  } else if (['blocked', 'error', 'failed', 'offline', 'tampered', 'rejected', 'expired'].includes(normalized)) {
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

export const SearchBar = ({ value, onChange, placeholder = 'Search...', className = '' }) => {
  return (
    <div className={`relative ${className}`}>
      <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#6B7488]" />
      <input
        type="text"
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className="w-full pl-10 pr-4 py-2 bg-white border border-[#E6E9F0] rounded-lg text-sm text-[#0E1726] placeholder-[#6B7488] focus:outline-none focus:border-[#A78BFA] focus:ring-2 focus:ring-[#6D28D9]/15 transition duration-200"
      />
    </div>
  );
};

export const DataTable = ({
  columns,
  data,
  loading = false,
  onSort,
  sortField,
  onRowClick,
}) => {
  return (
    <div className="w-full overflow-hidden border border-[#E6E9F0] rounded-xl bg-white/85 backdrop-blur-md shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm border-collapse">
          <thead>
            <tr className="border-b border-[#E6E9F0] bg-[#F5F7FA]">
              {columns.map((col) => (
                <th
                  key={col.key}
                  onClick={() => col.sortable && onSort?.(col.key)}
                  className={`px-6 py-4 font-bold text-[#6B7488] uppercase tracking-wider text-[11px] font-display ${
                    col.sortable ? 'cursor-pointer hover:text-[#0E1726] select-none' : ''
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    {col.header}
                    {col.sortable && (
                      <ArrowUpDown className={`w-3.5 h-3.5 ${sortField === col.key ? 'text-[#6D28D9]' : 'text-[#6B7488]'}`} />
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E6E9F0]">
            {loading ? (
              [...Array(5)].map((_, idx) => (
                <tr key={idx} className="animate-pulse bg-[#F5F7FA]/50">
                  {columns.map((col) => (
                    <td key={col.key} className="px-6 py-4">
                      <div className="h-4 bg-[#E6E9F0] rounded w-2/3" />
                    </td>
                  ))}
                </tr>
              ))
            ) : data.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-6 py-12 text-center text-[#6B7488] italic">
                  No records found.
                </td>
              </tr>
            ) : (
              data.map((row, idx) => (
                <tr
                  key={row.id || idx}
                  onClick={() => onRowClick?.(row)}
                  className={`hover:bg-[#F5F7FA]/70 transition-colors duration-150 ${
                    onRowClick ? 'cursor-pointer' : ''
                  }`}
                >
                  {columns.map((col) => (
                    <td key={col.key} className="px-6 py-4 text-[#475069]">
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

export const JSONViewer = ({ data, className = '' }) => {
  const [copied, setCopied] = useState(false);
  const formatted = JSON.stringify(data, null, 2);

  const handleCopy = () => {
    navigator.clipboard.writeText(formatted);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`relative group border border-[#E6E9F0] bg-[#F5F7FA] rounded-lg p-4 font-mono text-xs text-[#0E1726] overflow-x-auto ${className}`}>
      <button
        onClick={handleCopy}
        className="absolute top-3 right-3 p-1.5 bg-white hover:bg-[#F1ECFE] text-[#6B7488] hover:text-[#6D28D9] rounded border border-[#E6E9F0] transition-all"
        title="Copy JSON"
      >
        {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
      </button>
      <pre className="max-h-[300px] overflow-y-auto pr-8 leading-relaxed">{formatted}</pre>
    </div>
  );
};

export const EmptyState = ({ title, description, icon: Icon, actionLabel, onAction }) => {
  const EmptyIcon = Icon || Activity;
  return (
    <div className="flex flex-col items-center justify-center text-center p-12 border border-dashed border-[#E6E9F0] rounded-xl bg-[#F5F7FA]/70">
      <div className="p-4 bg-white border border-[#E6E9F0] rounded-full text-[#6D28D9] mb-4 shadow-sm">
        <EmptyIcon className="w-8 h-8" />
      </div>
      <h3 className="text-base font-bold text-[#0E1726] mb-1 font-display">{title}</h3>
      <p className="text-sm text-[#475069] max-w-sm mb-6">{description}</p>
      {actionLabel && (
        <Button variant="secondary" size="sm" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
};

export const ConfirmationDialog = ({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  danger = false,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-[#0E1726]/35 backdrop-blur-sm" onClick={onClose} />

      <GlassCard className="relative max-w-md w-full z-10 space-y-4 shadow-xl" hover={false}>
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${danger ? 'bg-rose-500/10 text-rose-600 border border-rose-500/20' : 'bg-amber-500/10 text-amber-600 border border-amber-500/20'}`}>
            <AlertTriangle className="w-5 h-5" />
          </div>
          <h3 className="text-base font-bold text-[#0E1726] font-display">{title}</h3>
        </div>
        <p className="text-sm text-[#475069] leading-relaxed font-sans">{message}</p>
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
