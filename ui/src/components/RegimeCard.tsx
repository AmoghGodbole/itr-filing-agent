import { RegimeResult } from '@/lib/types'

function fmt(n: number) {
  return '₹' + Math.abs(n).toLocaleString('en-IN', { maximumFractionDigits: 0 })
}

export default function RegimeCard({ r, recommended }: { r: RegimeResult; recommended: boolean }) {
  const isRefund = r.refund_or_payable >= 0
  return (
    <div className={`rounded-xl border-2 p-5 ${recommended ? 'border-green-500 bg-green-50' : 'border-gray-200 bg-white'}`}>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-base font-semibold">{r.regime}</h3>
        {recommended && <span className="rounded-full bg-green-500 px-2 py-0.5 text-xs font-medium text-white">Recommended</span>}
      </div>
      <dl className="space-y-1.5 text-sm">
        <Row label="Gross Income" value={fmt(r.gross_income)} />
        {r.hra_exemption_claimed > 0 && <Row label="HRA Exemption" value={`– ${fmt(r.hra_exemption_claimed)}`} />}
        {r.other_sources_income > 0 && (
          <Row
            label={r.family_pension_deduction_claimed > 0 ? `Other Sources (incl. family pension, net Sec 57)` : `Other Income (AIS)`}
            value={`+ ${fmt(r.other_sources_income)}`}
          />
        )}
        {r.home_loan_interest_claimed > 0 && <Row label="HP Loss (24b)" value={`– ${fmt(r.home_loan_interest_claimed)}`} />}
        {r.hp_income !== 0 && <Row label="HP Income (Let-out)" value={r.hp_income >= 0 ? `+ ${fmt(r.hp_income)}` : `– ${fmt(Math.abs(r.hp_income))}`} />}
        {r.chapter_via_deductions > 0 && <Row label="Chapter VI-A" value={`– ${fmt(r.chapter_via_deductions)}`} />}
        {r.deduction_80d_parents_claimed > 0 && <Row label="  80D Parents" value={`– ${fmt(r.deduction_80d_parents_claimed)}`} />}
        {r.deduction_80gg_claimed > 0 && <Row label="  80GG (Rent)" value={`– ${fmt(r.deduction_80gg_claimed)}`} />}
        {r.deduction_80eea_claimed > 0 && <Row label="  80EEA (Affordable Housing)" value={`– ${fmt(r.deduction_80eea_claimed)}`} />}
        {r.capital_gains_tax && r.capital_gains_tax.stcg_for_slab_income > 0 && (
          <Row label="STCG (at slab)" value={`+ ${fmt(r.capital_gains_tax.stcg_for_slab_income)}`} />
        )}
        <div className="my-2 border-t" />
        <Row label={r.capital_gains_tax ? 'Taxable Income (slab)' : 'Taxable Income'} value={fmt(r.taxable_income)} bold />
        {r.capital_gains_tax && r.capital_gains_tax.total_tax_at_special_rates > 0 && (
          <Row label="CG Tax (special rates)" value={`+ ${fmt(r.capital_gains_tax.total_tax_at_special_rates)}`} />
        )}
        <Row label="Tax (total)" value={fmt(r.tax_payable)} />
        <Row label="TDS Paid" value={fmt(r.tds_deducted)} />
        <div className="my-2 border-t" />
        <div className={`flex justify-between font-semibold ${isRefund ? 'text-green-700' : 'text-red-600'}`}>
          <span>{isRefund ? 'Refund Due' : 'Tax Payable'}</span>
          <span>{fmt(r.refund_or_payable)}</span>
        </div>
      </dl>
    </div>
  )
}

function Row({ label, value, bold }: { label: string; value: string; bold?: boolean }) {
  return (
    <div className={`flex justify-between ${bold ? 'font-medium' : ''}`}>
      <span className="text-gray-600">{label}</span>
      <span>{value}</span>
    </div>
  )
}
