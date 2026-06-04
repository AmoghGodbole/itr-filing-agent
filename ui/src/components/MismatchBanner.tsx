import { Form26ASData } from '@/lib/types'

export default function MismatchBanner({ f26 }: { f26: Form26ASData }) {
  if (!f26.tds_mismatch) return null
  const diff = Math.abs(f26.salary_tds - f26.form16_tds).toLocaleString('en-IN', { maximumFractionDigits: 0 })
  return (
    <div className="rounded-lg border border-yellow-300 bg-yellow-50 p-4 text-sm text-yellow-800">
      <strong>TDS Mismatch Detected</strong> — Form 16 shows ₹{f26.form16_tds.toLocaleString('en-IN', { maximumFractionDigits: 0 })} but
      Form 26AS shows ₹{f26.salary_tds.toLocaleString('en-IN', { maximumFractionDigits: 0 })} (difference: ₹{diff}).
      Review with the employer before filing.
    </div>
  )
}
