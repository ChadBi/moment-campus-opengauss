import React from 'react';
import { AlertCircle } from 'lucide-react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  icon?: React.ReactNode;
}

export const Input: React.FC<InputProps> = ({
  label,
  error,
  icon,
  className = '',
  id,
  ...props
}) => {
  const inputId = id || `input-${label?.toLowerCase().replace(/\s+/g, '-')}`;

  return (
    <div className="w-full">
      {label && (
        <label
          htmlFor={inputId}
          className="block text-sm font-medium text-ink mb-2 font-sans"
        >
          {label}
          {props.required && <span className="text-danger ml-1">*</span>}
        </label>
      )}
      <div className="relative">
        {icon && (
          <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-muted pointer-events-none">
            {icon}
          </div>
        )}
        <input
          id={inputId}
          className={`w-full h-11 px-3.5 ${icon ? 'pl-10' : ''} bg-white/78 border rounded-[13px] text-sm text-ink placeholder:text-ink-muted/70 transition-[background-color,border-color,box-shadow] duration-[180ms] ease-out focus:outline-none focus:bg-white focus:shadow-sm ${
            error
              ? 'border-danger focus:border-danger focus:shadow-none'
              : 'border-line focus:border-lake focus:shadow-sm'
          } ${className}`}
          {...props}
        />
      </div>
      {error && (
        <div className="flex items-center gap-1 mt-1.5 text-danger text-xs font-sans">
          <AlertCircle size={14} />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
};
