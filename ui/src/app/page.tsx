'use client'

import { useState } from 'react'
import Step from '@/components/Step'
import MismatchBanner from '@/components/MismatchBanner'
import RegimeCard from '@/components/RegimeCard'
import { ParseResponse, GenerateResponse } from '@/lib/types'

type AppStep = 'upload' | 'review' | 'result'

export default function Home() {
  const [step, setStep] = useState<AppStep>('upload')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Upload step state
  const [form16File, setForm16File] = useState<File | null>(null)
  const [form16File2, setForm16File2] = useState<File | null>(null)
  const [form26asFile, setForm26asFile] = useState<File | null>(null)
  const [aisFile, setAisFile] = useState<File | null>(null)
  const [brokerPlFiles, setBrokerPlFiles] = useState<File[]>([])
  const [foPlFiles, setFoPlFiles] = useState<File[]>([])

  // F&O carry-forward losses from prior years (always manual — from prior ITR acknowledgements)
  const [foCarryForward, setFoCarryForward] = useState<{ay: string; amount: string}[]>([])

  // Capital gains state — strings so empty fields stay blank; populated from broker PDF or manual entry
  const [cg, setCg] = useState({
    eq_stcg_pre: '', eq_stcg_post: '', eq_ltcg_pre: '', eq_ltcg_post: '',
    ot_stcg: '', ot_ltcg_20: '', ot_ltcg_125: '',
    pr_stcg: '', pr_ltcg_20: '', pr_ltcg_125: '',
    tds: '',
  })

  // Review step state
  const [parsed, setParsed] = useState<ParseResponse | null>(null)
  const [hraRent, setHraRent] = useState('')
  const [hraCity, setHraCity] = useState('')
  const [parentsInsurancePremium, setParentsInsurancePremium] = useState('')
  const [parentsSenior, setParentsSenior] = useState(false)
  const [homeLoanCertificate, setHomeLoanCertificate] = useState('')
  const [rentalAnnualRent, setRentalAnnualRent] = useState('')
  const [rentalMunicipalTaxes, setRentalMunicipalTaxes] = useState('')
  const [rentalHomeLoanInterest, setRentalHomeLoanInterest] = useState('')
  const [familyPension, setFamilyPension] = useState('')
  const [homeLoan80EEA, setHomeLoan80EEA] = useState('')
  const [bankAccount, setBankAccount] = useState({ account_number: '', ifsc: '', account_type: 'Savings', bank_name: '' })
  const [dateOfBirth, setDateOfBirth] = useState('')

  // Schedule AL state — assets & liabilities (required when total income > ₹50L in ITR-2)
  type PropRow = { description: string; address: string; city: string; state: string; pin_code: string; value: string }
  const emptyProp = (): PropRow => ({ description: '', address: '', city: '', state: '', pin_code: '', value: '' })
  const [alProps, setAlProps] = useState<PropRow[]>([emptyProp()])
  const [alMovable, setAlMovable] = useState({ jewellery: '', paintings: '', bullion: '', vehicles: '', others: '' })
  const [alFinancial, setAlFinancial] = useState({ bank: '', shares: '', insurance: '', loans_given: '', cash: '', others: '' })
  const [alLiabilities, setAlLiabilities] = useState({ loan_banks: '', loan_others: '', others: '' })
  const [aadhaar, setAadhaar] = useState('')
  const [mobile, setMobile] = useState('')
  const [email, setEmail] = useState('')

  // Result step state
  const [result, setResult] = useState<GenerateResponse | null>(null)

  async function handleParse() {
    if (!form16File) return
    setLoading(true)
    setError(null)
    try {
      const fd = new FormData()
      fd.append('form16_pdf', form16File)
      if (form16File2) fd.append('form16_pdf_2', form16File2)
      if (form26asFile) fd.append('form26as_pdf', form26asFile)
      if (aisFile) fd.append('ais_json', aisFile)
      brokerPlFiles.forEach(f => fd.append('broker_pl_pdfs', f))
      foPlFiles.forEach(f => fd.append('fo_pl_pdfs', f))

      const res = await fetch('/api/parse', { method: 'POST', body: fd })
      if (!res.ok) throw new Error((await res.json()).detail ?? 'Parsing failed')
      const data = await res.json()
      setParsed(data)
      // Pre-fill CG state from broker PDF parse result — CA can still edit all fields
      if (data.capital_gains) {
        const c = data.capital_gains
        setCg({
          eq_stcg_pre: c.equity.stcg_pre_jul23 ? String(c.equity.stcg_pre_jul23) : '',
          eq_stcg_post: c.equity.stcg_post_jul23 ? String(c.equity.stcg_post_jul23) : '',
          eq_ltcg_pre: c.equity.ltcg_pre_jul23 ? String(c.equity.ltcg_pre_jul23) : '',
          eq_ltcg_post: c.equity.ltcg_post_jul23 ? String(c.equity.ltcg_post_jul23) : '',
          ot_stcg: c.other.stcg_at_slab ? String(c.other.stcg_at_slab) : '',
          ot_ltcg_20: c.other.ltcg_20pct_with_indexation ? String(c.other.ltcg_20pct_with_indexation) : '',
          ot_ltcg_125: c.other.ltcg_125pct_without_indexation ? String(c.other.ltcg_125pct_without_indexation) : '',
          pr_stcg: '', pr_ltcg_20: '', pr_ltcg_125: '',
          tds: c.tds_on_gains ? String(c.tds_on_gains) : '',
        })
      }
      setStep('review')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  async function handleGenerate() {
    if (!parsed) return
    setLoading(true)
    setError(null)
    try {
      const dobForApi = dateOfBirth ? dateOfBirth.split('-').reverse().join('/') : ''
      const hasCg = Object.values(cg).some(v => v !== '' && parseFloat(v) !== 0)
      const capitalGainsPayload = hasCg ? {
        equity: {
          stcg_pre_jul23: parseFloat(cg.eq_stcg_pre) || 0,
          stcg_post_jul23: parseFloat(cg.eq_stcg_post) || 0,
          ltcg_pre_jul23: parseFloat(cg.eq_ltcg_pre) || 0,
          ltcg_post_jul23: parseFloat(cg.eq_ltcg_post) || 0,
        },
        other: {
          stcg_at_slab: parseFloat(cg.ot_stcg) || 0,
          ltcg_20pct_with_indexation: parseFloat(cg.ot_ltcg_20) || 0,
          ltcg_125pct_without_indexation: parseFloat(cg.ot_ltcg_125) || 0,
        },
        property: {
          stcg: parseFloat(cg.pr_stcg) || 0,
          ltcg_with_indexation: parseFloat(cg.pr_ltcg_20) || 0,
          ltcg_without_indexation: parseFloat(cg.pr_ltcg_125) || 0,
        },
        tds_on_gains: parseFloat(cg.tds) || 0,
      } : null
      const hasAL = alProps.some(p => parseFloat(p.value) > 0)
        || Object.values(alMovable).some(v => parseFloat(v) > 0)
        || Object.values(alFinancial).some(v => parseFloat(v) > 0)
        || Object.values(alLiabilities).some(v => parseFloat(v) > 0)
      const scheduleALPayload = hasAL ? {
        immovable_properties: alProps.filter(p => p.description || parseFloat(p.value) > 0).map(p => ({
          description: p.description, address: p.address, city: p.city,
          state: p.state, pin_code: p.pin_code, value: parseFloat(p.value) || 0,
        })),
        movable: { jewellery: parseFloat(alMovable.jewellery)||0, paintings_collections: parseFloat(alMovable.paintings)||0, bullion: parseFloat(alMovable.bullion)||0, vehicles: parseFloat(alMovable.vehicles)||0, others: parseFloat(alMovable.others)||0 },
        financial: { bank_balance: parseFloat(alFinancial.bank)||0, shares_securities: parseFloat(alFinancial.shares)||0, insurance_surrender_value: parseFloat(alFinancial.insurance)||0, loans_given: parseFloat(alFinancial.loans_given)||0, cash_in_hand: parseFloat(alFinancial.cash)||0, others: parseFloat(alFinancial.others)||0 },
        liabilities: { loan_from_banks: parseFloat(alLiabilities.loan_banks)||0, loan_from_others: parseFloat(alLiabilities.loan_others)||0, others: parseFloat(alLiabilities.others)||0 },
      } : null
      const foPayload = parsed?.fo_data ? {
        ...parsed.fo_data,
        carry_forward_losses: foCarryForward.filter(r => r.ay && parseFloat(r.amount) > 0)
          .map(r => ({ assessment_year: r.ay, loss_amount: parseFloat(r.amount) })),
      } : null

      const body = {
        form16: parsed.form16,
        form16_2: parsed.form16_2 ?? null,
        ais: parsed.ais,
        capital_gains: capitalGainsPayload,
        fo_data: foPayload,
        schedule_al: scheduleALPayload,
        hra_monthly_rent: parseFloat(hraRent) || 0,
        hra_city: hraCity,
        parents_insurance_premium: parseFloat(parentsInsurancePremium) || 0,
        parents_senior: parentsSenior,
        home_loan_interest_certificate: parseFloat(homeLoanCertificate) || 0,
        rental_annual_rent: parseFloat(rentalAnnualRent) || 0,
        rental_municipal_taxes: parseFloat(rentalMunicipalTaxes) || 0,
        rental_home_loan_interest: parseFloat(rentalHomeLoanInterest) || 0,
        family_pension: parseFloat(familyPension) || 0,
        home_loan_80eea: parseFloat(homeLoan80EEA) || 0,
        bank_account: bankAccount,
        date_of_birth: dobForApi,
        aadhaar: aadhaar || null,
        mobile: mobile || null,
        email: email || null,
      }
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error((await res.json()).detail ?? 'Generation failed')
      setResult(await res.json())
      setStep('result')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  function downloadITR() {
    if (!result) return
    const blob = new Blob([JSON.stringify(result.itr_json, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    const formName = result.is_itr3 ? 'ITR3' : result.is_itr2 ? 'ITR2' : 'ITR1'
    a.download = `${formName}_${parsed?.form16.employee_pan}_${parsed?.form16.assessment_year}.json`
    a.click()
  }

  const stepNum = step === 'upload' ? 1 : step === 'review' ? 2 : 3

  return (
    <div className="space-y-8">
      {/* Stepper */}
      <div className="flex items-center gap-6">
        <Step n={1} title="Upload Documents" active={step === 'upload'} done={stepNum > 1} />
        <div className="h-px flex-1 bg-gray-300" />
        <Step n={2} title="Review & Details" active={step === 'review'} done={stepNum > 2} />
        <div className="h-px flex-1 bg-gray-300" />
        <Step n={3} title="ITR Generated" active={step === 'result'} done={false} />
      </div>

      {error && (
        <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-700">{error}</div>
      )}

      {/* ── Step 1: Upload ── */}
      {step === 'upload' && (
        <div className="rounded-xl border bg-white p-6 shadow-sm space-y-5">
          <h2 className="text-lg font-semibold">Upload Documents</h2>

          <FileInput label="Form 16 PDF *" accept=".pdf" onChange={setForm16File} file={form16File} />
          <FileInput label="Form 16 PDF — Employer 2 (optional, job change mid-year)" accept=".pdf" onChange={setForm16File2} file={form16File2} />
          <FileInput label="Form 26AS PDF (optional)" accept=".pdf" onChange={setForm26asFile} file={form26asFile} />
          <FileInput label="AIS JSON (optional)" accept=".json" onChange={setAisFile} file={aisFile} />
          <MultiFileInput label="Broker Tax P&L PDFs — capital gains, one PDF per broker (Zerodha, Groww, CAMS, etc.)" accept=".pdf" files={brokerPlFiles} onChange={setBrokerPlFiles} />
          <MultiFileInput label="Broker F&O Tax P&L PDFs — futures & options, one PDF per broker (triggers ITR-3)" accept=".pdf" files={foPlFiles} onChange={setFoPlFiles} />
          {(brokerPlFiles.length > 0 || foPlFiles.length > 0) && (
            <p className="text-xs text-amber-600 -mt-2">
              {foPlFiles.length > 0 ? 'F&O income detected → ITR-3 will be generated. ' : ''}
              {brokerPlFiles.length > 1 ? `${brokerPlFiles.length} broker PDFs will be merged. ` : ''}
              Capital gains and F&O data will be extracted and shown for review. Property gains always manual.
            </p>
          )}

          <button
            onClick={handleParse}
            disabled={!form16File || loading}
            className="w-full rounded-lg bg-blue-600 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Extracting data…' : 'Extract & Continue →'}
          </button>
        </div>
      )}

      {/* ── Step 2: Review ── */}
      {step === 'review' && parsed && (
        <div className="space-y-5">
          {parsed.form26as && <MismatchBanner f26={parsed.form26as} />}

          {/* Extracted data summary */}
          <div className="rounded-xl border bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold">Extracted from Form 16</h2>
            <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
              <Info label="Name" value={parsed.form16.employee_name} />
              <Info label="PAN" value={parsed.form16.employee_pan} />
              <Info label="Employer" value={parsed.form16.employer.name} />
              <Info label="Assessment Year" value={parsed.form16.assessment_year} />
              <Info label="Gross Salary" value={fmt(parsed.form16.salary.gross_salary)} />
              <Info label="TDS Deducted" value={fmt(parsed.form16.tds.tds_deducted)} />
            </div>
          </div>

          {/* Second employer summary */}
          {parsed.form16_2 && (
            <div className="rounded-xl border bg-white p-6 shadow-sm">
              <div className="mb-4 flex items-center gap-2">
                <h2 className="text-lg font-semibold">Extracted from Form 16 — Employer 2</h2>
                <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">Job change mid-year</span>
              </div>
              <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
                <Info label="Employer" value={parsed.form16_2.employer.name} />
                <Info label="TAN" value={parsed.form16_2.employer.tan} />
                <Info label="Gross Salary" value={fmt(parsed.form16_2.salary.gross_salary)} />
                <Info label="TDS Deducted" value={fmt(parsed.form16_2.tds.tds_deducted)} />
              </div>
              <p className="mt-3 text-xs text-gray-500">
                Combined gross: {fmt(parsed.form16.salary.gross_salary + parsed.form16_2.salary.gross_salary)} | Combined TDS: {fmt(parsed.form16.tds.tds_deducted + parsed.form16_2.tds.tds_deducted)}
              </p>
            </div>
          )}

          {/* AIS summary */}
          {parsed.ais && (
            <div className="rounded-xl border bg-white p-6 shadow-sm">
              <h2 className="mb-4 text-lg font-semibold">From AIS</h2>
              <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
                <Info label="FD / Deposit Interest" value={fmt(parsed.ais.total_interest)} />
                <Info label="Dividends" value={fmt(parsed.ais.total_dividends)} />
                <Info label="TDS on above" value={fmt(parsed.ais.total_tds_from_ais)} />
              </div>
            </div>
          )}

          {/* F&O Summary — shown only when broker F&O PDF was parsed */}
          {parsed.fo_data && parsed.fo_data.segments.length > 0 && (
            <div className="rounded-xl border bg-white p-6 shadow-sm space-y-4">
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-semibold">F&O Income — Extracted from Broker P&L</h2>
                <span className="rounded-full bg-orange-100 px-2 py-0.5 text-xs font-medium text-orange-700">ITR-3 required</span>
              </div>
              <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
                {parsed.fo_data.segments.map((s, i) => (
                  <div key={i} className="col-span-2 grid grid-cols-4 gap-4 text-sm border-b pb-2">
                    <span className="font-medium">{s.segment}</span>
                    <Info label="Turnover" value={fmt(s.turnover)} />
                    <Info label="Net P&L" value={`${s.net_pl >= 0 ? '+' : '–'} ${fmt(Math.abs(s.net_pl))}`} />
                    <Info label="Expenses" value={fmt(parsed.fo_data!.expenses.brokerage + parsed.fo_data!.expenses.stt)} />
                  </div>
                ))}
                <Info label="Total Turnover" value={fmt(parsed.fo_data.segments.reduce((s, x) => s + x.turnover, 0))} />
                <Info label="Net F&O P&L" value={fmt(parsed.fo_data.segments.reduce((s, x) => s + x.net_pl, 0))} />
              </div>
              {parsed.fo_data.segments.reduce((s, x) => s + x.turnover, 0) > 10_000_000 && (
                <p className="text-xs font-medium text-red-600">Turnover exceeds ₹1Cr — tax audit (Sec 44AB) may be required if loss is declared. Check with CA.</p>
              )}
              {/* Carry-forward losses from prior years */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium text-gray-700">Prior-year F&O Losses to Set Off (from previous ITR acknowledgements)</p>
                  <button onClick={() => setFoCarryForward(cf => [...cf, {ay: '', amount: ''}])} className="text-xs text-blue-600 hover:text-blue-800">+ Add</button>
                </div>
                {foCarryForward.map((r, i) => (
                  <div key={i} className="flex gap-3 mb-2 items-end">
                    <label className="space-y-1 flex-1">
                      <span className="text-xs text-gray-600">Assessment Year</span>
                      <input value={r.ay} onChange={e => setFoCarryForward(cf => cf.map((x, j) => j === i ? {...x, ay: e.target.value} : x))}
                        placeholder="AY 2024-25"
                        className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400" />
                    </label>
                    <label className="space-y-1 flex-1">
                      <span className="text-xs text-gray-600">Loss Amount (₹)</span>
                      <input type="number" value={r.amount} onChange={e => setFoCarryForward(cf => cf.map((x, j) => j === i ? {...x, amount: e.target.value} : x))}
                        placeholder="0"
                        className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400" />
                    </label>
                    <button onClick={() => setFoCarryForward(cf => cf.filter((_, j) => j !== i))} className="mb-2 text-xs text-red-500">Remove</button>
                  </div>
                ))}
                {foCarryForward.length === 0 && <p className="text-xs text-gray-400">No prior-year losses. F&O losses carry forward for 8 years and set off against future business income only.</p>}
              </div>
            </div>
          )}

          {/* Capital Gains */}
          <div className="rounded-xl border bg-white p-6 shadow-sm space-y-5">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold">Capital Gains</h2>
              {brokerPlFiles.length > 0 && parsed?.capital_gains && (
                <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">Auto-extracted — verify before filing</span>
              )}
              <span className="text-xs text-gray-500 ml-auto">Triggers ITR-2 when any figure is non-zero</span>
            </div>

            {/* Equity / Equity MF — Sec 111A / 112A */}
            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">Listed Equity & Equity MF (STT paid — Sec 111A / 112A)</p>
              <div className="grid grid-cols-2 gap-3">
                <CgField label="STCG — before Jul 23, 2024 (15%)" value={cg.eq_stcg_pre} onChange={v => setCg(c => ({...c, eq_stcg_pre: v}))} />
                <CgField label="STCG — on/after Jul 23, 2024 (20%)" value={cg.eq_stcg_post} onChange={v => setCg(c => ({...c, eq_stcg_post: v}))} />
                <CgField label="LTCG — before Jul 23, 2024 (10%, ₹1L exempt)" value={cg.eq_ltcg_pre} onChange={v => setCg(c => ({...c, eq_ltcg_pre: v}))} />
                <CgField label="LTCG — on/after Jul 23, 2024 (12.5%, ₹1.25L exempt)" value={cg.eq_ltcg_post} onChange={v => setCg(c => ({...c, eq_ltcg_post: v}))} />
              </div>
            </div>

            {/* Other assets — Debt MF, bonds, gold */}
            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">Other Assets — Debt MF, Bonds, Gold (non-equity)</p>
              <div className="grid grid-cols-3 gap-3">
                <CgField label="STCG — at slab rate" value={cg.ot_stcg} onChange={v => setCg(c => ({...c, ot_stcg: v}))} />
                <CgField label="LTCG 20% with indexation (pre-Jul 23)" value={cg.ot_ltcg_20} onChange={v => setCg(c => ({...c, ot_ltcg_20: v}))} />
                <CgField label="LTCG 12.5% without indexation (post-Jul 23)" value={cg.ot_ltcg_125} onChange={v => setCg(c => ({...c, ot_ltcg_125: v}))} />
              </div>
            </div>

            {/* Property — always manual */}
            <div>
              <p className="text-sm font-medium text-gray-700 mb-1">Property Gains (always manual)</p>
              <p className="text-xs text-gray-500 mb-2">Pre-Jul 23 acquisition sold post-Jul 23: enter only the more beneficial option (20% with indexation vs 12.5% without — CA calculates both and picks the lower tax).</p>
              <div className="grid grid-cols-3 gap-3">
                <CgField label="STCG (held < 24 months) — slab rate" value={cg.pr_stcg} onChange={v => setCg(c => ({...c, pr_stcg: v}))} />
                <CgField label="LTCG 20% with CII indexation" value={cg.pr_ltcg_20} onChange={v => setCg(c => ({...c, pr_ltcg_20: v}))} />
                <CgField label="LTCG 12.5% without indexation" value={cg.pr_ltcg_125} onChange={v => setCg(c => ({...c, pr_ltcg_125: v}))} />
              </div>
              {parseFloat(cg.pr_ltcg_20) > 0 && parseFloat(cg.pr_ltcg_125) > 0 && (
                <p className="mt-2 text-xs font-medium text-red-600">
                  Both LTCG fields are non-zero — enter only one (the more beneficial option). Entering both double-taxes the same gain.
                </p>
              )}
            </div>

            {/* TDS on gains */}
            <CgField label="TDS on capital gains (from Form 26AS — Sec 194, 194IA, etc.)" value={cg.tds} onChange={v => setCg(c => ({...c, tds: v}))} />

            {/* Live preview */}
            {Object.values(cg).some(v => v !== '' && parseFloat(v) !== 0) && (() => {
              const equityStcg = (parseFloat(cg.eq_stcg_pre) || 0) * 0.15 + (parseFloat(cg.eq_stcg_post) || 0) * 0.20
              const equityLtcg = Math.max(0, (parseFloat(cg.eq_ltcg_pre) || 0) - 100000) * 0.10
                + Math.max(0, (parseFloat(cg.eq_ltcg_post) || 0) - 125000) * 0.125
              const otherLtcg = (parseFloat(cg.ot_ltcg_20) || 0) * 0.20 + (parseFloat(cg.ot_ltcg_125) || 0) * 0.125
                + (parseFloat(cg.pr_ltcg_20) || 0) * 0.20 + (parseFloat(cg.pr_ltcg_125) || 0) * 0.125
              const cgTax = equityStcg + equityLtcg + otherLtcg
              return (
                <p className="text-xs text-gray-500 border-t pt-3">
                  Approximate CG tax at special rates: <span className="font-semibold text-gray-800">₹{cgTax.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
                  <span className="ml-2 text-gray-400">(before surcharge/cess; STCG at slab rates excluded)</span>
                </p>
              )
            })()}
          </div>

          {/* HRA / 80GG */}
          <div className="rounded-xl border bg-white p-6 shadow-sm space-y-4">
            <h2 className="text-lg font-semibold">Rent Details (HRA / 80GG)</h2>
            <p className="text-sm text-gray-500">
              Leave blank if the client does not pay rent or HRA is already in Form 16.
              {parsed.form16.salary.hra === 0 && (
                <span className="ml-1 font-medium text-amber-600">No HRA component detected — 80GG will be applied automatically if rent is entered.</span>
              )}
            </p>
            <div className="grid grid-cols-2 gap-4">
              <label className="space-y-1">
                <span className="text-sm font-medium">Monthly Rent (₹)</span>
                <input type="number" value={hraRent} onChange={e => setHraRent(e.target.value)}
                  className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400" />
              </label>
              <label className="space-y-1">
                <span className="text-sm font-medium">City</span>
                <select value={hraCity} onChange={e => setHraCity(e.target.value)}
                  className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400">
                  <option value="">Select city</option>
                  <option value="delhi">Delhi (metro)</option>
                  <option value="mumbai">Mumbai (metro)</option>
                  <option value="kolkata">Kolkata (metro)</option>
                  <option value="chennai">Chennai (metro)</option>
                  <option value="other">Other (non-metro)</option>
                </select>
              </label>
            </div>
          </div>

          {/* 80D Parents */}
          <div className="rounded-xl border bg-white p-6 shadow-sm space-y-4">
            <h2 className="text-lg font-semibold">80D — Parents' Health Insurance</h2>
            <p className="text-sm text-gray-500">Employer does not capture parents' premium. Enter the annual amount paid (old regime only).</p>
            <div className="grid grid-cols-2 gap-4">
              <label className="space-y-1">
                <span className="text-sm font-medium">Annual Premium (₹)</span>
                <input type="number" value={parentsInsurancePremium} onChange={e => setParentsInsurancePremium(e.target.value)}
                  className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400" />
              </label>
              <label className="flex items-center gap-3 pt-6 cursor-pointer">
                <input type="checkbox" checked={parentsSenior} onChange={e => setParentsSenior(e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-400" />
                <span className="text-sm font-medium">One or both parents are senior citizens (60+)<br/><span className="font-normal text-gray-500">Cap increases from ₹25,000 to ₹50,000</span></span>
              </label>
            </div>
          </div>

          {/* Home Loan Bank Certificate */}
          <div className="rounded-xl border bg-white p-6 shadow-sm space-y-4">
            <h2 className="text-lg font-semibold">Home Loan Interest — Bank Certificate</h2>
            <p className="text-sm text-gray-500">Enter if the employer did not capture home loan interest in Form 16. This overrides the Form 16 value. Capped at ₹2,00,000 (old regime only).</p>
            <label className="block space-y-1">
              <span className="text-sm font-medium">Annual Interest from Bank Certificate (₹)</span>
              <input type="number" value={homeLoanCertificate}
                onChange={e => setHomeLoanCertificate(e.target.value)}
                placeholder={parsed.form16.other_deductions.home_loan_interest_24b > 0 ? `Form 16 shows ₹${fmt(parsed.form16.other_deductions.home_loan_interest_24b)}` : '0'}
                className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400" />
            </label>
          </div>

          {/* 80EEA — Affordable Housing */}
          <div className="rounded-xl border bg-white p-6 shadow-sm space-y-4">
            <h2 className="text-lg font-semibold">80EEA — Affordable Housing Home Loan</h2>
            <p className="text-sm text-gray-500">
              Extra ₹1,50,000 deduction on home loan interest for first-time buyers, stacking on top of Section 24(b).
              Conditions (CA to verify): stamp duty value ≤ ₹45L, loan sanctioned between Apr 1 2019 and Mar 31 2022, first-time buyer.
              Old regime only.
            </p>
            <label className="block space-y-1">
              <span className="text-sm font-medium">Eligible Home Loan Interest — 80EEA (₹)</span>
              <input type="number" value={homeLoan80EEA} onChange={e => setHomeLoan80EEA(e.target.value)}
                placeholder="0 — leave blank if not applicable"
                className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400" />
            </label>
            {homeLoan80EEA && parseFloat(homeLoan80EEA) > 0 && (
              <p className="text-xs text-gray-500">
                Deduction: ₹{Math.min(parseFloat(homeLoan80EEA), 150000).toLocaleString('en-IN', { maximumFractionDigits: 0 })} (capped at ₹1,50,000)
                {parseFloat(homeLoan80EEA) > 150000 ? <span className="text-amber-600"> — entered amount exceeds cap</span> : null}
              </p>
            )}
          </div>

          {/* Rental Income — Let-out Property */}
          <div className="rounded-xl border bg-white p-6 shadow-sm space-y-4">
            <h2 className="text-lg font-semibold">Rental Income — Let-out Property</h2>
            <p className="text-sm text-gray-500">
              Leave blank if the client has no let-out property. If entered, the home loan interest above is ignored — only the interest on this property applies here. HP loss is capped at ₹2,00,000 set-off.
            </p>
            <div className="grid grid-cols-3 gap-4">
              <label className="space-y-1">
                <span className="text-sm font-medium">Annual Rent Received (₹)</span>
                <input type="number" value={rentalAnnualRent} onChange={e => setRentalAnnualRent(e.target.value)}
                  className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400" />
              </label>
              <label className="space-y-1">
                <span className="text-sm font-medium">Municipal Taxes Paid (₹)</span>
                <input type="number" value={rentalMunicipalTaxes} onChange={e => setRentalMunicipalTaxes(e.target.value)}
                  className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400" />
              </label>
              <label className="space-y-1">
                <span className="text-sm font-medium">Home Loan Interest (₹)</span>
                <input type="number" value={rentalHomeLoanInterest} onChange={e => setRentalHomeLoanInterest(e.target.value)}
                  placeholder="0 if no loan on this property"
                  className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400" />
              </label>
            </div>
            {rentalAnnualRent && parseFloat(rentalAnnualRent) > 0 && (() => {
              const rent = parseFloat(rentalAnnualRent) || 0
              const muni = parseFloat(rentalMunicipalTaxes) || 0
              const loan = parseFloat(rentalHomeLoanInterest) || 0
              const av = Math.max(0, rent - muni)
              const net = av * 0.70 - loan
              return (
                <p className="text-xs text-gray-500">
                  Net HP income preview: Annual Value ₹{av.toLocaleString('en-IN')} − 30% std. deduction − ₹{loan.toLocaleString('en-IN')} interest
                  = <span className={net >= 0 ? 'text-green-700 font-medium' : 'text-amber-700 font-medium'}>
                    {net >= 0 ? `+ ₹${net.toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : `– ₹${Math.min(Math.abs(net), 200000).toLocaleString('en-IN', { maximumFractionDigits: 0 })}${Math.abs(net) > 200000 ? ' (capped at ₹2L)' : ''}`}
                  </span>
                </p>
              )
            })()}
          </div>

          {/* Schedule AL — Assets & Liabilities */}
          <div className="rounded-xl border bg-white p-6 shadow-sm space-y-5">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold">Schedule AL — Assets & Liabilities</h2>
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">Required if total income &gt; ₹50L</span>
            </div>
            <p className="text-sm text-gray-500">All values as on March 31 of the financial year. Only required in ITR-2/ITR-3 when total income exceeds ₹50,00,000. Leave blank if not applicable.</p>

            {/* Immovable properties */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-gray-700">Immovable Properties</p>
                <button onClick={() => setAlProps(ps => [...ps, emptyProp()])} className="text-xs text-blue-600 hover:text-blue-800">+ Add property</button>
              </div>
              {alProps.map((p, i) => (
                <div key={i} className="mb-3 rounded-lg border p-3 space-y-2">
                  <div className="grid grid-cols-2 gap-2">
                    <ALField label="Description" value={p.description} onChange={v => setAlProps(ps => ps.map((r, j) => j === i ? {...r, description: v} : r))} />
                    <ALField label="Value (₹)" value={p.value} onChange={v => setAlProps(ps => ps.map((r, j) => j === i ? {...r, value: v} : r))} type="number" />
                    <ALField label="Address" value={p.address} onChange={v => setAlProps(ps => ps.map((r, j) => j === i ? {...r, address: v} : r))} />
                    <ALField label="City" value={p.city} onChange={v => setAlProps(ps => ps.map((r, j) => j === i ? {...r, city: v} : r))} />
                    <ALField label="State" value={p.state} onChange={v => setAlProps(ps => ps.map((r, j) => j === i ? {...r, state: v} : r))} />
                    <ALField label="PIN Code" value={p.pin_code} onChange={v => setAlProps(ps => ps.map((r, j) => j === i ? {...r, pin_code: v} : r))} />
                  </div>
                  {alProps.length > 1 && (
                    <button onClick={() => setAlProps(ps => ps.filter((_, j) => j !== i))} className="text-xs text-red-500 hover:text-red-700">Remove</button>
                  )}
                </div>
              ))}
            </div>

            {/* Movable assets */}
            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">Movable Assets (₹)</p>
              <div className="grid grid-cols-3 gap-3">
                <CgField label="Jewellery & ornaments" value={alMovable.jewellery} onChange={v => setAlMovable(m => ({...m, jewellery: v}))} />
                <CgField label="Paintings / art / collections" value={alMovable.paintings} onChange={v => setAlMovable(m => ({...m, paintings: v}))} />
                <CgField label="Bullion" value={alMovable.bullion} onChange={v => setAlMovable(m => ({...m, bullion: v}))} />
                <CgField label="Vehicles" value={alMovable.vehicles} onChange={v => setAlMovable(m => ({...m, vehicles: v}))} />
                <CgField label="Others" value={alMovable.others} onChange={v => setAlMovable(m => ({...m, others: v}))} />
              </div>
            </div>

            {/* Financial assets */}
            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">Financial Assets (₹)</p>
              <div className="grid grid-cols-3 gap-3">
                <CgField label="Bank balance (all accounts)" value={alFinancial.bank} onChange={v => setAlFinancial(f => ({...f, bank: v}))} />
                <CgField label="Shares & securities (market value)" value={alFinancial.shares} onChange={v => setAlFinancial(f => ({...f, shares: v}))} />
                <CgField label="Insurance surrender value" value={alFinancial.insurance} onChange={v => setAlFinancial(f => ({...f, insurance: v}))} />
                <CgField label="Loans given / receivables" value={alFinancial.loans_given} onChange={v => setAlFinancial(f => ({...f, loans_given: v}))} />
                <CgField label="Cash in hand" value={alFinancial.cash} onChange={v => setAlFinancial(f => ({...f, cash: v}))} />
                <CgField label="Others" value={alFinancial.others} onChange={v => setAlFinancial(f => ({...f, others: v}))} />
              </div>
            </div>

            {/* Liabilities */}
            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">Liabilities (₹) — outstanding as on March 31</p>
              <div className="grid grid-cols-3 gap-3">
                <CgField label="Loans from banks (home, vehicle, etc.)" value={alLiabilities.loan_banks} onChange={v => setAlLiabilities(l => ({...l, loan_banks: v}))} />
                <CgField label="Loans from others" value={alLiabilities.loan_others} onChange={v => setAlLiabilities(l => ({...l, loan_others: v}))} />
                <CgField label="Others" value={alLiabilities.others} onChange={v => setAlLiabilities(l => ({...l, others: v}))} />
              </div>
            </div>

            {/* Live totals */}
            {(() => {
              const immTotal = alProps.reduce((s, p) => s + (parseFloat(p.value)||0), 0)
              const movTotal = Object.values(alMovable).reduce((s, v) => s + (parseFloat(v)||0), 0)
              const finTotal = Object.values(alFinancial).reduce((s, v) => s + (parseFloat(v)||0), 0)
              const liabTotal = Object.values(alLiabilities).reduce((s, v) => s + (parseFloat(v)||0), 0)
              const totalAssets = immTotal + movTotal + finTotal
              if (totalAssets === 0 && liabTotal === 0) return null
              return (
                <div className="border-t pt-3 flex gap-8 text-sm">
                  <span className="text-gray-500">Total Assets: <span className="font-semibold text-gray-800">{fmt(totalAssets)}</span></span>
                  <span className="text-gray-500">Total Liabilities: <span className="font-semibold text-gray-800">{fmt(liabTotal)}</span></span>
                  <span className="text-gray-500">Net Worth: <span className="font-semibold text-gray-800">{fmt(totalAssets - liabTotal)}</span></span>
                </div>
              )
            })()}
          </div>

          {/* Family Pension */}
          <div className="rounded-xl border bg-white p-6 shadow-sm space-y-4">
            <h2 className="text-lg font-semibold">Family Pension</h2>
            <p className="text-sm text-gray-500">
              Pension received by a family member of a deceased employee. Taxed as other sources income.
              Section 57(iia) allows a deduction of 1/3 of the amount or ₹15,000, whichever is lower.
              Available in both old and new regime.
            </p>
            <label className="block space-y-1">
              <span className="text-sm font-medium">Annual Family Pension Received (₹)</span>
              <input type="number" value={familyPension} onChange={e => setFamilyPension(e.target.value)}
                placeholder="0"
                className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400" />
            </label>
            {familyPension && parseFloat(familyPension) > 0 && (() => {
              const gross = parseFloat(familyPension)
              const deduction = Math.min(15000, gross / 3)
              const net = gross - deduction
              return (
                <p className="text-xs text-gray-500">
                  Sec 57 deduction: ₹{deduction.toLocaleString('en-IN', { maximumFractionDigits: 0 })} → Net taxable:{' '}
                  <span className="font-medium text-gray-700">₹{net.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
                </p>
              )
            })()}
          </div>

          {/* Bank & Filing Details */}
          <div className="rounded-xl border bg-white p-6 shadow-sm space-y-4">
            <h2 className="text-lg font-semibold">Bank & Filing Details</h2>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Account Number *" value={bankAccount.account_number}
                onChange={v => setBankAccount(b => ({ ...b, account_number: v }))} />
              <Field label="IFSC Code *" value={bankAccount.ifsc}
                onChange={v => setBankAccount(b => ({ ...b, ifsc: v }))} />
              <Field label="Bank Name *" value={bankAccount.bank_name}
                onChange={v => setBankAccount(b => ({ ...b, bank_name: v }))} />
              <label className="space-y-1">
                <span className="text-sm font-medium">Account Type</span>
                <select value={bankAccount.account_type} onChange={e => setBankAccount(b => ({ ...b, account_type: e.target.value }))}
                  className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400">
                  <option>Savings</option>
                  <option>Current</option>
                </select>
              </label>
              <label className="space-y-1">
                <span className="text-sm font-medium">Date of Birth (optional)</span>
                <input type="date" value={dateOfBirth} onChange={e => setDateOfBirth(e.target.value)}
                  className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400" />
                {dateOfBirth && parsed && (() => {
                  const dob = new Date(dateOfBirth)
                  const ayYear = parseInt(parsed.form16.assessment_year.replace('AY ', '').split('-')[0])
                  // "At any time during the previous year" — use March 31 (FY end), matching engine
                  const fyEnd = new Date(ayYear, 2, 31)
                  let age = fyEnd.getFullYear() - dob.getFullYear()
                  if ((fyEnd.getMonth() * 100 + fyEnd.getDate()) < (dob.getMonth() * 100 + dob.getDate())) age--
                  if (age >= 80) return <span className="mt-1 inline-block rounded-full bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-700">Super Senior Citizen (80+) — ₹5L exemption</span>
                  if (age >= 60) return <span className="mt-1 inline-block rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">Senior Citizen (60–79) — ₹3L exemption</span>
                  return null
                })()}
              </label>
              <Field label="Aadhaar (optional)" value={aadhaar} onChange={setAadhaar} />
              <Field label="Mobile (optional)" value={mobile} onChange={setMobile} />
              <div className="col-span-2">
                <Field label="Email (optional)" value={email} onChange={setEmail} />
              </div>
            </div>
          </div>

          <div className="flex gap-3">
            <button onClick={() => setStep('upload')} className="rounded-lg border px-5 py-2.5 text-sm font-medium hover:bg-gray-50">
              ← Back
            </button>
            <button
              onClick={handleGenerate}
              disabled={!bankAccount.account_number || !bankAccount.ifsc || !bankAccount.bank_name || loading}
              className="flex-1 rounded-lg bg-blue-600 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? 'Computing tax…' : 'Compute Tax & Generate ITR →'}
            </button>
          </div>
        </div>
      )}

      {/* ── Step 3: Result ── */}
      {step === 'result' && result && (
        <div className="space-y-5">
          <div className="rounded-xl border bg-white p-6 shadow-sm">
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-semibold">Tax Comparison</h2>
                {result.is_itr3 && <span className="rounded-full bg-orange-100 px-2 py-0.5 text-xs font-medium text-orange-700">ITR-3 (F&O Business Income)</span>}
                {result.is_itr2 && !result.is_itr3 && <span className="rounded-full bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-700">ITR-2 (Capital Gains)</span>}
              </div>
              <span className="text-sm text-gray-500">Saves ₹{result.savings.toLocaleString('en-IN', { maximumFractionDigits: 0 })} with {result.recommended_regime}</span>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <RegimeCard r={result.old_regime} recommended={result.recommended_regime === 'Old Regime'} />
              <RegimeCard r={result.new_regime} recommended={result.recommended_regime === 'New Regime'} />
            </div>
          </div>

          <div className="flex gap-3">
            <button onClick={() => setStep('review')} className="rounded-lg border px-5 py-2.5 text-sm font-medium hover:bg-gray-50">
              ← Back
            </button>
            <button onClick={downloadITR}
              className="flex-1 rounded-lg bg-green-600 py-2.5 text-sm font-semibold text-white hover:bg-green-700">
              Download {result.is_itr3 ? 'ITR-3' : result.is_itr2 ? 'ITR-2' : 'ITR-1'} JSON
            </button>
            <button onClick={() => { setStep('upload'); setParsed(null); setResult(null) }}
              className="rounded-lg border border-blue-200 px-5 py-2.5 text-sm font-medium text-blue-600 hover:bg-blue-50">
              File Another Return
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function FileInput({ label, accept, onChange, file }: { label: string; accept: string; onChange: (f: File | null) => void; file: File | null }) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium">{label}</span>
      <div className={`flex items-center justify-between rounded-lg border px-3 py-2 text-sm ${file ? 'border-green-400 bg-green-50' : 'border-gray-300'}`}>
        <span className={file ? 'text-green-700' : 'text-gray-400'}>{file ? file.name : 'No file selected'}</span>
        <label className="cursor-pointer rounded bg-gray-100 px-2 py-1 text-xs hover:bg-gray-200">
          Browse
          <input type="file" accept={accept} className="hidden" onChange={e => onChange(e.target.files?.[0] ?? null)} />
        </label>
      </div>
    </label>
  )
}

function MultiFileInput({ label, accept, files, onChange }: { label: string; accept: string; files: File[]; onChange: (f: File[]) => void }) {
  const addFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    const incoming = Array.from(e.target.files ?? [])
    // Deduplicate by name so re-selecting the same file doesn't duplicate it
    const merged = [...files, ...incoming.filter(f => !files.some(x => x.name === f.name))]
    onChange(merged)
    e.target.value = ''  // reset input so same file can be re-added after removal
  }
  const remove = (name: string) => onChange(files.filter(f => f.name !== name))

  return (
    <div className="space-y-1">
      <span className="text-sm font-medium">{label}</span>
      <div className="rounded-lg border border-gray-300 px-3 py-2 space-y-1">
        {files.length === 0 && <p className="text-sm text-gray-400">No files selected</p>}
        {files.map(f => (
          <div key={f.name} className="flex items-center justify-between rounded bg-green-50 px-2 py-1 text-sm text-green-700">
            <span>{f.name}</span>
            <button type="button" onClick={() => remove(f.name)} className="ml-2 text-green-500 hover:text-red-500 text-xs">✕</button>
          </div>
        ))}
        <label className="inline-block cursor-pointer rounded bg-gray-100 px-2 py-1 text-xs hover:bg-gray-200 mt-1">
          + Add file
          <input type="file" accept={accept} multiple className="hidden" onChange={addFiles} />
        </label>
      </div>
    </div>
  )
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="space-y-1">
      <span className="text-sm font-medium">{label}</span>
      <input type="text" value={value} onChange={e => onChange(e.target.value)}
        className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400" />
    </label>
  )
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-gray-500">{label}: </span>
      <span className="font-medium">{value}</span>
    </div>
  )
}

function fmt(n: number) {
  return '₹' + n.toLocaleString('en-IN', { maximumFractionDigits: 0 })
}

function CgField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="space-y-1">
      <span className="text-xs font-medium text-gray-600">{label}</span>
      <input
        type="number"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder="0"
        className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
      />
    </label>
  )
}

function ALField({ label, value, onChange, type = 'text' }: { label: string; value: string; onChange: (v: string) => void; type?: string }) {
  return (
    <label className="space-y-1">
      <span className="text-xs font-medium text-gray-600">{label}</span>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={type === 'number' ? '0' : ''}
        className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
      />
    </label>
  )
}
