import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from api.schemas import (
    AISIncomeOut,
    AISOut,
    BankAccountIn,
    CapitalGainsOut,
    CapitalGainsTaxOut,
    Deductions80COut,
    EmployerOut,
    EquityGainsOut,
    ExemptionsOut,
    FODataIn,
    Form16Out,
    Form26ASEntryOut,
    Form26ASOut,
    GenerateRequest,
    GenerateResponse,
    OtherDeductionsOut,
    OtherGainsOut,
    ParseResponse,
    PropertyGainsOut,
    RegimeOut,
    SalaryOut,
    ScheduleALIn,
    TDSOut,
)
from engine.computation.tax_engine import compute_optimal_regime
from engine.itr_generator.itr1_generator import BankAccount, generate_itr1
from engine.itr_generator.itr2_generator import generate_itr2
from engine.itr_generator.itr3_generator import generate_itr3
from engine.models import (
    Deductions80C,
    EmployerDetails,
    Exemptions,
    Form16Data,
    OtherDeductions,
    SalaryBreakdown,
    TDSDetails,
    merge_form16s,
)
from engine.models_ais import AISData, AISIncomeEntry
from engine.models_capital_gains import CapitalGainsSummary, EquityGainsSplit, OtherGains, PropertyGains
from engine.models_fo import CarryForwardLoss, FOData, FOExpenses, FOSegmentPL
from engine.parsers.fo_parser import parse_fo
from engine.models_schedule_al import (
    FinancialAssets, ImmovableProperty, Liabilities, MovableAssets, ScheduleALData,
)
from engine.parsers.ais_parser import parse_ais
from engine.parsers.capital_gains_parser import parse_capital_gains
from engine.parsers.form16_parser import parse_form16
from engine.parsers.form26as_parser import parse_form26as

router = APIRouter(prefix="/api", tags=["ITR"])


def _save_upload(upload: UploadFile, suffix: str) -> Path:
    """Save an uploaded file to a temp path and return it."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(upload.file.read())
    finally:
        tmp.close()  # always close so the FD is released before parsers open the same path
    return Path(tmp.name)


# ── /api/parse ───────────────────────────────────────────────────────────────

@router.post("/parse", response_model=ParseResponse)
async def parse(
    form16_pdf: UploadFile = File(..., description="Form 16 PDF"),
    form16_pdf_2: Optional[UploadFile] = File(None, description="Form 16 PDF from second employer (job change)"),
    form26as_pdf: Optional[UploadFile] = File(None, description="Form 26AS PDF (optional)"),
    ais_json: Optional[UploadFile] = File(None, description="AIS JSON from IT portal (optional)"),
    broker_pl_pdf: Optional[UploadFile] = File(None, description="Broker tax P&L PDF for capital gains (Zerodha, Groww, CAMS, etc.)"),
    fo_pl_pdf: Optional[UploadFile] = File(None, description="Broker F&O tax P&L PDF (Zerodha, Groww, Upstox, Angel One)"),
):
    """
    Step 1 — Upload documents and extract all data.
    Returns parsed data for CA to review and correct before generating the ITR.
    """
    form16_path = _save_upload(form16_pdf, ".pdf")
    try:
        form16 = parse_form16(form16_path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Form 16 parsing failed: {e}")
    finally:
        form16_path.unlink(missing_ok=True)

    form16_2_out = None
    if form16_pdf_2 and form16_pdf_2.filename:
        f16_2_path = _save_upload(form16_pdf_2, ".pdf")
        try:
            form16_2 = parse_form16(f16_2_path)
            if form16_2.employee_pan != form16.employee_pan:
                raise HTTPException(
                    status_code=422,
                    detail=f"PAN mismatch between Form 16s: {form16.employee_pan} vs {form16_2.employee_pan}",
                )
            if form16_2.assessment_year != form16.assessment_year:
                raise HTTPException(
                    status_code=422,
                    detail=f"Assessment year mismatch: {form16.assessment_year} vs {form16_2.assessment_year}",
                )
            form16_2_out = _form16_to_out(form16_2)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Form 16 (employer 2) parsing failed: {e}")
        finally:
            f16_2_path.unlink(missing_ok=True)

    f26_out = None
    if form26as_pdf and form26as_pdf.filename:
        f26_path = _save_upload(form26as_pdf, ".pdf")
        try:
            f26 = parse_form26as(f26_path)
            f26_out = Form26ASOut(
                financial_year=f26.financial_year,
                part_a=[Form26ASEntryOut(**e.__dict__) for e in f26.part_a],
                part_c=[Form26ASEntryOut(**e.__dict__) for e in f26.part_c],
                salary_tds=f26.get_salary_tds(),
                non_salary_tds=f26.get_non_salary_tds(),
                tds_mismatch=f26.tds_mismatch_with_form16(form16.tds.tds_deducted),
                form16_tds=form16.tds.tds_deducted,
            )
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Form 26AS parsing failed: {e}")
        finally:
            f26_path.unlink(missing_ok=True)

    ais_out = None
    if ais_json and ais_json.filename:
        ais_path = _save_upload(ais_json, ".json")
        try:
            ais = parse_ais(ais_path)
            ais_out = AISOut(
                taxpayer_name=ais.taxpayer_name,
                financial_year=ais.financial_year,
                savings_account_interest=[AISIncomeOut(**e.__dict__) for e in ais.savings_account_interest],
                deposit_interest=[AISIncomeOut(**e.__dict__) for e in ais.deposit_interest],
                dividends=[AISIncomeOut(**e.__dict__) for e in ais.dividends],
                total_interest=ais.total_interest,
                total_dividends=ais.total_dividends,
                total_tds_from_ais=ais.total_tds_from_ais,
            )
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"AIS parsing failed: {e}")
        finally:
            ais_path.unlink(missing_ok=True)

    cg_out = None
    if broker_pl_pdf and broker_pl_pdf.filename:
        pl_path = _save_upload(broker_pl_pdf, ".pdf")
        try:
            cg = parse_capital_gains(pl_path)
            cg_out = _cg_to_out(cg)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Broker P&L parsing failed: {e}")
        finally:
            pl_path.unlink(missing_ok=True)

    fo_out = None
    if fo_pl_pdf and fo_pl_pdf.filename:
        fo_path = _save_upload(fo_pl_pdf, ".pdf")
        try:
            fo = parse_fo(fo_path)
            fo_out = _fo_to_out(fo)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"F&O P&L parsing failed: {e}")
        finally:
            fo_path.unlink(missing_ok=True)

    return ParseResponse(
        form16=_form16_to_out(form16),
        form16_2=form16_2_out,
        form26as=f26_out,
        ais=ais_out,
        capital_gains=cg_out,
        fo_data=fo_out,
    )


# ── /api/generate ─────────────────────────────────────────────────────────────

@router.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    """
    Step 2 — Compute tax and generate ITR-1 JSON.
    Accepts the (optionally edited) parsed data from /api/parse.
    """
    form16_primary = _out_to_form16(req.form16)
    second_form16 = _out_to_form16(req.form16_2) if req.form16_2 else None
    try:
        form16 = merge_form16s(form16_primary, second_form16) if second_form16 else form16_primary
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    ais = _out_to_ais(req.ais) if req.ais else None

    capital_gains = _out_to_cg(req.capital_gains) if req.capital_gains else None
    fo_data = _in_to_fo(req.fo_data) if req.fo_data else None

    computation = compute_optimal_regime(
        form16,
        ais=ais,
        hra_monthly_rent=req.hra_monthly_rent,
        hra_city=req.hra_city,
        parents_insurance_premium=req.parents_insurance_premium,
        parents_senior=req.parents_senior,
        home_loan_interest_cert=req.home_loan_interest_certificate,
        date_of_birth=req.date_of_birth,
        rental_annual_rent=req.rental_annual_rent,
        rental_municipal_taxes=req.rental_municipal_taxes,
        rental_home_loan_interest=req.rental_home_loan_interest,
        family_pension=req.family_pension,
        home_loan_80eea=req.home_loan_80eea,
        capital_gains=capital_gains,
        fo_data=fo_data,
    )

    bank = BankAccount(
        account_number=req.bank_account.account_number,
        ifsc=req.bank_account.ifsc,
        account_type=req.bank_account.account_type,
        bank_name=req.bank_account.bank_name,
    )

    schedule_al = _in_to_schedule_al(req.schedule_al) if req.schedule_al else None

    if computation.is_itr3 and fo_data:
        itr_json = generate_itr3(
            form16, computation, bank, fo_data,
            capital_gains=capital_gains,
            aadhaar_number=req.aadhaar, mobile=req.mobile, email=req.email,
            date_of_birth=req.date_of_birth or None,
            second_form16=second_form16, schedule_al=schedule_al,
        )
    elif computation.is_itr2 and capital_gains:
        itr_json = generate_itr2(
            form16, computation, bank, capital_gains,
            aadhaar_number=req.aadhaar, mobile=req.mobile, email=req.email,
            date_of_birth=req.date_of_birth or None,
            second_form16=second_form16, schedule_al=schedule_al,
        )
    else:
        itr_json = generate_itr1(
            form16, computation, bank,
            aadhaar_number=req.aadhaar, mobile=req.mobile, email=req.email,
            date_of_birth=req.date_of_birth or None,
            second_form16=second_form16,
        )

    return GenerateResponse(
        old_regime=_regime_to_out(computation.old_regime),
        new_regime=_regime_to_out(computation.new_regime),
        recommended_regime=computation.recommended_regime,
        savings=computation.savings,
        is_itr2=computation.is_itr2,
        is_itr3=computation.is_itr3,
        itr_json=itr_json,
    )


# ── Conversion helpers ────────────────────────────────────────────────────────

def _form16_to_out(f: Form16Data) -> Form16Out:
    return Form16Out(
        assessment_year=f.assessment_year,
        financial_year=f.financial_year,
        employee_name=f.employee_name,
        employee_pan=f.employee_pan,
        employer=EmployerOut(**f.employer.model_dump()),
        salary=SalaryOut(**f.salary.model_dump()),
        exemptions=ExemptionsOut(**f.exemptions.model_dump()),
        deductions_80c=Deductions80COut(**f.deductions_80c.model_dump()),
        other_deductions=OtherDeductionsOut(**f.other_deductions.model_dump()),
        tds=TDSOut(tds_deducted=f.tds.tds_deducted, tds_deposited=f.tds.tds_deposited),
        professional_tax=f.professional_tax,
    )


def _out_to_form16(o: Form16Out) -> Form16Data:
    return Form16Data(
        assessment_year=o.assessment_year,
        financial_year=o.financial_year,
        employee_name=o.employee_name,
        employee_pan=o.employee_pan,
        employer=EmployerDetails(**o.employer.model_dump()),
        salary=SalaryBreakdown(**o.salary.model_dump()),
        exemptions=Exemptions(**o.exemptions.model_dump()),
        deductions_80c=Deductions80C(**o.deductions_80c.model_dump()),
        other_deductions=OtherDeductions(**o.other_deductions.model_dump()),
        tds=TDSDetails(
            tds_deducted=o.tds.tds_deducted,
            tds_deposited=o.tds.tds_deposited,
        ),
        professional_tax=o.professional_tax,
    )


def _out_to_ais(o: AISOut) -> AISData:
    def to_entries(items):
        return [AISIncomeEntry(source_name=i.source_name, amount=i.amount, tds_deducted=i.tds_deducted) for i in items]

    savings = to_entries(o.savings_account_interest)
    deposits = to_entries(o.deposit_interest)
    dividends = to_entries(o.dividends)

    # Recompute all totals from the (possibly CA-edited) entry lists so that edits to
    # individual line items are reflected in the engine's income and TDS computation.
    all_entries = savings + deposits + dividends
    return AISData(
        taxpayer_name=o.taxpayer_name,
        financial_year=o.financial_year,
        savings_account_interest=savings,
        deposit_interest=deposits,
        dividends=dividends,
        total_savings_interest=sum(e.amount for e in savings),
        total_deposit_interest=sum(e.amount for e in deposits),
        total_interest=sum(e.amount for e in savings) + sum(e.amount for e in deposits),
        total_dividends=sum(e.amount for e in dividends),
        total_tds_from_ais=sum(e.tds_deducted for e in all_entries),
    )


def _regime_to_out(r) -> RegimeOut:
    cg_tax_out = None
    if r.capital_gains_result is not None:
        cg = r.capital_gains_result
        cg_tax_out = CapitalGainsTaxOut(
            exempt_112a_pre_jul23=cg.exempt_112a_pre_jul23,
            exempt_112a_post_jul23=cg.exempt_112a_post_jul23,
            taxable_stcg_111a_pre=cg.taxable_stcg_111a_pre,
            taxable_stcg_111a_post=cg.taxable_stcg_111a_post,
            taxable_ltcg_112a_pre=cg.taxable_ltcg_112a_pre,
            taxable_ltcg_112a_post=cg.taxable_ltcg_112a_post,
            taxable_ltcg_20pct=cg.taxable_ltcg_20pct,
            taxable_ltcg_125pct=cg.taxable_ltcg_125pct,
            stcg_for_slab_income=cg.stcg_for_slab_income,
            total_tax_at_special_rates=cg.total_tax_at_special_rates,
        )
    return RegimeOut(
        regime=r.regime,
        gross_income=r.gross_income,
        taxable_income=r.taxable_income,
        hra_exemption_claimed=r.hra_exemption_claimed,
        other_sources_income=r.other_sources_income,
        chapter_via_deductions=r.chapter_via_deductions,
        home_loan_interest_claimed=r.home_loan_interest_claimed,
        hp_income=r.hp_income,
        deduction_80d_parents_claimed=r.deduction_80d_parents_claimed,
        deduction_80gg_claimed=r.deduction_80gg_claimed,
        deduction_80eea_claimed=r.deduction_80eea_claimed,
        family_pension_deduction_claimed=r.family_pension_deduction_claimed,
        tax_before_cess=r.tax_before_cess,
        surcharge=r.surcharge,
        cess=r.cess,
        tax_after_cess=r.tax_after_cess,
        rebate_87a=r.rebate_87a,
        tax_payable=r.tax_payable,
        tds_deducted=r.tds_deducted,
        refund_or_payable=r.refund_or_payable,
        capital_gains_tax=cg_tax_out,
    )


def _cg_to_out(cg: CapitalGainsSummary) -> CapitalGainsOut:
    return CapitalGainsOut(
        equity=EquityGainsOut(**cg.equity.model_dump()),
        other=OtherGainsOut(**cg.other.model_dump()),
        property=PropertyGainsOut(**cg.property_gains.model_dump()),
        tds_on_gains=cg.tds_on_gains,
    )


def _out_to_cg(o: CapitalGainsOut) -> CapitalGainsSummary:
    return CapitalGainsSummary(
        equity=EquityGainsSplit(**o.equity.model_dump()),
        other=OtherGains(**o.other.model_dump()),
        property_gains=PropertyGains(**o.property.model_dump()),
        tds_on_gains=o.tds_on_gains,
    )


def _in_to_schedule_al(o: ScheduleALIn) -> ScheduleALData:
    return ScheduleALData(
        immovable_properties=[ImmovableProperty(**p.model_dump()) for p in o.immovable_properties],
        movable=MovableAssets(**o.movable.model_dump()),
        financial=FinancialAssets(**o.financial.model_dump()),
        liabilities=Liabilities(**o.liabilities.model_dump()),
    )


def _fo_to_out(fo: FOData) -> FODataIn:
    from api.schemas import CarryForwardLossIn, FOExpensesIn, FOSegmentIn
    return FODataIn(
        segments=[FOSegmentIn(**s.model_dump()) for s in fo.segments],
        expenses=FOExpensesIn(**fo.expenses.model_dump(exclude={"total"})),
        carry_forward_losses=[CarryForwardLossIn(**c.model_dump()) for c in fo.carry_forward_losses],
        tds_on_fo=fo.tds_on_fo,
    )


def _in_to_fo(o: FODataIn) -> FOData:
    return FOData(
        segments=[FOSegmentPL(**s.model_dump()) for s in o.segments],
        expenses=FOExpenses(**o.expenses.model_dump()),
        carry_forward_losses=[CarryForwardLoss(**c.model_dump()) for c in o.carry_forward_losses],
        tds_on_fo=o.tds_on_fo,
    )
