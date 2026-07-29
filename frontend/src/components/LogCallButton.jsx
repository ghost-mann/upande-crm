import { useStore } from '../store';
import Icon from './Icon';

// "Log call" row action for the pipeline tables.
//
// Prefills the dialog with the record as the call's reference and whatever number
// the row carries, so logging a call from a lead is one click rather than a
// re-typed number. The backend field lists include mobile/phone for exactly this.
export function callNumberOf(row) {
  return row?.mobile_no || row?.phone || row?.whatsapp_no || row?.contact_mobile || '';
}

export default function LogCallButton({ row, doctype }) {
  const openCallDialog = useStore((s) => s.openCallDialog);
  const number = callNumberOf(row);
  return (
    <button
      className="text-ink-3 hover:text-gold-text"
      title={number ? `Log a call to ${number}` : 'Log a call'}
      onClick={(e) => {
        e.stopPropagation();
        openCallDialog({
          type: 'Outgoing',
          number,
          reference_doctype: doctype,
          reference_name: row.name,
        });
      }}
    >
      <Icon name="add_call" className="text-[16px]" />
    </button>
  );
}

// The action column, shared so every pipeline table offers it identically.
export function logCallColumn(doctype) {
  return {
    key: 'log_call',
    label: '',
    thStyle: { width: 34 },
    render: (r) => <LogCallButton row={r} doctype={doctype} />,
  };
}
