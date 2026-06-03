import { badgeClass } from '@/lib/crm';

export default function StatusBadge({ value }) {
  return <span className={`bdg ${badgeClass(value)}`}>{value || '—'}</span>;
}
