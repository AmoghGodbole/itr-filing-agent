"""
Glue file: binds all feature files to the shared step definitions.
pytest-bdd discovers scenarios from each feature file and matches steps
defined in common_steps.py (imported via conftest or directly).
"""
import pytest
from pytest_bdd import scenarios

from tests.bdd.steps.common_steps import *  # noqa: F401,F403 — imports all step definitions

# Register all 13 feature files
scenarios("01_basic_itr1.feature")
scenarios("02_ais_income.feature")
scenarios("03_manual_hra.feature")
scenarios("04_80gg.feature")
scenarios("05_two_form16s.feature")
scenarios("06_home_loan.feature")
scenarios("07_senior_citizen.feature")
scenarios("08_letout_property.feature")
scenarios("09_capital_gains_itr2.feature")
scenarios("10_property_sale.feature")
scenarios("11_fo_trader_itr3.feature")
scenarios("12_fo_plus_cg.feature")
scenarios("13_schedule_al.feature")
