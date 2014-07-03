#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .move import *
from .configuration import *
from .party import *
from .invoice import *
from .account import *
from .sale import *

def register():
    Pool.register(
        Party,
        Configuration,
        Move,
        Line,
        Invoice,
        MoveForceDrawStart,
        InvoiceForceDrawStart,
        AuxiliaryBookStart,
        AuxiliaryPartyStart,
        PrintTrialBalanceDetailedStart,
        PrintTrialBalanceStart,
        BankAccountNumber,
        module='account_plus_ec', type_='model')
    Pool.register(
        AccountMoveSheet,
        AuxiliaryBook,
        AuxiliaryParty,
        TrialBalanceDetailed,
        PortfolioByPartyDetailed,
        TrialBalance,
        BalanceSheet,
        IncomeStatement,
        WithholdCertificate,
        ReferenceGuide,
        module='account_plus_ec', type_='report')
    Pool.register(
        MoveForceDraw,
        InvoiceForceDraw,
        PrintAuxiliaryBook,
        PrintTrialBalanceDetailed,
        PrintAuxiliaryParty,
        PrintTrialBalance,
        module='account_plus_ec', type_='wizard')
