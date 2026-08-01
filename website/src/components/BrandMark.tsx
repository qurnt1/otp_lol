type BrandMarkProps = { className?: string };

export function BrandMark({ className }: BrandMarkProps) {
  return (
    <svg className={className} viewBox="0 0 48 48" aria-hidden="true" focusable="false">
      <rect className="brand-mark__base" width="48" height="48" rx="8" />
      <circle className="brand-mark__signal" cx="24" cy="24" r="13" />
      <path className="brand-mark__cross" d="M24 6v11M24 31v11M6 24h11M31 24h11" />
      <circle className="brand-mark__core" cx="24" cy="24" r="3" />
    </svg>
  );
}

