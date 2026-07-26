import React from 'react';
import { AlertCircle } from 'lucide-react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  icon?: React.ReactNode;
  /** UX-01.7: 描述元素 ID（用于 aria-describedby 关联提示文本） */
  describedby?: string;
}

export const Input: React.FC<InputProps> = ({
  label,
  error,
  icon,
  className = '',
  id,
  describedby,
  ...props
}) => {
  const inputId = id || `input-${label?.toLowerCase().replace(/\s+/g, '-')}`;
  // UX-01.7: 错误提示元素 ID（aria-describedby 关联）
  const errorId = `${inputId}-error`;
  // 合并 aria-describedby：既包含外部传入的提示，也包含错误提示
  const ariaDescribedby = [describedby, error ? errorId : null]
    .filter(Boolean)
    .join(' ') || undefined;

  return (
    <div className="w-full">
      {label && (
        <label
          htmlFor={inputId}
          className="block text-sm font-medium text-ink mb-1.5 font-sans"
        >
          {label}
          {props.required && <span className="text-danger ml-1" aria-hidden="true">*</span>}
        </label>
      )}
      <div className="relative">
        {icon && (
          <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-muted pointer-events-none" aria-hidden="true">
            {icon}
          </div>
        )}
        <input
          id={inputId}
          className={`w-full h-10 px-3.5 ${icon ? 'pl-10' : ''} bg-paper border rounded-[10px] text-[14px] text-ink placeholder:text-ink-muted/60 transition-[background-color,border-color,box-shadow] duration-200 ease-[cubic-bezier(0.16,1,0.3,1)] focus:outline-none focus:border-lake ${
            error
              ? 'border-danger focus:border-danger'
              : 'border-line'
          } ${className}`}
          aria-invalid={error ? true : undefined}
          aria-describedby={ariaDescribedby}
          {...props}
        />
      </div>
      {error && (
        <div
          id={errorId}
          role="alert"
          className="flex items-center gap-1 mt-1.5 text-danger text-xs font-sans"
        >
          <AlertCircle size={13} aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
};
