import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  /** Kept for existing callers. The card now uses the school's accent colour instead of a gradient per card. */
  color?: string;
  suffix?: string;
  subValue?: string | number;
  currency?: string;
  navigateTo?: string;
  onClick?: () => void;
  /** Full value shown on hover when `value` is abbreviated (e.g. "Rs 2,028,500"). */
  fullValue?: string;
}

export default function StatCard({
  title,
  value,
  icon,
  suffix,
  subValue,
  currency,
  navigateTo,
  onClick,
  fullValue,
}: StatCardProps) {
  const navigate = useNavigate();
  const { t } = useTranslation();

  const handleClick = () => {
    if (onClick) {
      onClick();
    } else if (navigateTo) {
      navigate(navigateTo);
    }
  };

  const isClickable = !!(onClick || navigateTo);

  return (
    <div
      onClick={handleClick}
      className={`stat-card group flex flex-col h-full p-5 ${isClickable ? 'stat-card-link' : ''}`}
      role={isClickable ? 'button' : undefined}
      tabIndex={isClickable ? 0 : undefined}
      aria-label={isClickable ? `${title}: ${fullValue || value}. Open details` : undefined}
      onKeyDown={isClickable ? (e) => { if (e.key === 'Enter' || e.key === ' ') handleClick(); } : undefined}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-slate-500">{title}</p>
        <span className="stat-card-icon shrink-0 w-9 h-9 rounded-lg flex items-center justify-center [&>svg]:w-[18px] [&>svg]:h-[18px]">
          {icon}
        </span>
      </div>

      <p className="mt-2 text-3xl leading-tight font-semibold tracking-tight tabular-nums text-slate-900 break-words" title={fullValue}>
        {value}
      </p>

      {(suffix || subValue !== undefined) && (
        <p className="mt-1 text-xs text-slate-500 truncate" title={String(subValue ?? '')}>
          <span className="font-medium text-slate-600">{suffix || t('dashboard.thisMonth')}:</span>{' '}
          {currency ? `${currency} ` : ''}{subValue ?? value}
        </p>
      )}

      {isClickable && (
        <div className="stat-card-more mt-auto pt-3 text-xs font-medium flex items-center gap-0.5">
          {t('dashboard.viewDetails')}
          <ChevronRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5 rtl:rotate-180" />
        </div>
      )}
    </div>
  );
}
