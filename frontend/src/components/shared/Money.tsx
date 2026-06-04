interface MoneyProps {
  value: string;
  className?: string;
  showSign?: boolean;
}

export function Money({ value, className = '', showSign = false }: MoneyProps) {
  const num = parseFloat(value);
  const formatted = new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Math.abs(num));

  const sign = showSign && num < 0 ? '−' : '';

  return (
    <span
      className={`tabular ${className}`}
      style={{ fontFamily: '"JetBrains Mono", ui-monospace, monospace', fontVariantNumeric: 'tabular-nums' }}
    >
      {sign}${formatted}
    </span>
  );
}
