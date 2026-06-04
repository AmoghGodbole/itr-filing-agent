"""
Schedule AL — Assets and Liabilities.
Mandatory in ITR-2 and ITR-3 when total income exceeds ₹50,00,000.
All values are as on March 31 of the relevant financial year.
Source: always manual — no document captures this.
"""

from pydantic import BaseModel, model_validator

SCHEDULE_AL_THRESHOLD = 5_000_000   # ₹50L — portal mandates AL above this


class ImmovableProperty(BaseModel):
    description: str = ""      # "Residential flat", "Agricultural land", etc.
    address: str = ""          # free-text; CA transcribes from title deed
    city: str = ""
    state: str = ""
    pin_code: str = ""
    value: float = 0           # cost of acquisition (or value as on March 31)


class MovableAssets(BaseModel):
    jewellery: float = 0
    paintings_collections: float = 0   # paintings, sculptures, art, archaeological items
    bullion: float = 0
    vehicles: float = 0
    others: float = 0


class FinancialAssets(BaseModel):
    bank_balance: float = 0              # total across all accounts as on March 31
    shares_securities: float = 0        # market value: equity, MF, bonds, debentures
    insurance_surrender_value: float = 0
    loans_given: float = 0              # receivables: loans extended to others
    cash_in_hand: float = 0
    others: float = 0


class Liabilities(BaseModel):
    loan_from_banks: float = 0     # outstanding home loan, vehicle loan, etc.
    loan_from_others: float = 0
    others: float = 0


class ScheduleALData(BaseModel):
    immovable_properties: list[ImmovableProperty] = []
    movable: MovableAssets = MovableAssets()
    financial: FinancialAssets = FinancialAssets()
    liabilities: Liabilities = Liabilities()

    @property
    def total_assets(self) -> float:
        immovable = sum(p.value for p in self.immovable_properties)
        movable = (self.movable.jewellery + self.movable.paintings_collections
                   + self.movable.bullion + self.movable.vehicles + self.movable.others)
        financial = (self.financial.bank_balance + self.financial.shares_securities
                     + self.financial.insurance_surrender_value + self.financial.loans_given
                     + self.financial.cash_in_hand + self.financial.others)
        return immovable + movable + financial

    @property
    def total_liabilities(self) -> float:
        return (self.liabilities.loan_from_banks + self.liabilities.loan_from_others
                + self.liabilities.others)
