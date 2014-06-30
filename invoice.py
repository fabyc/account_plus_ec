#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import ModelView, fields
from trytond.pyson import Eval
from trytond.pool import PoolMeta
from trytond.wizard import Wizard, StateTransition
from trytond.transaction import Transaction
from trytond.modules.company import CompanyReport

__all__ = ['Invoice', 'InvoiceForceDrawStart', 'InvoiceForceDraw',
    'WithholdCertificate']
__metaclass__ = PoolMeta


GTA_CODE_TAX = {
        'IVA': '2',
        'ICE': '3',
        'RETENCION': '4',
}

def fmt(num):
    return str(round(num, 2))


class Invoice:
    'Invoice'
    __name__ = 'account.invoice'
    estimate_pay_date = fields.Date('Estimate Pay Date', 
            states={'readonly': Eval('state') == 'paid'}
            )


class InvoiceForceDrawStart(ModelView):
    'Invoice Force Draw'
    __name__ = 'account.invoice.force_draw.start'


class InvoiceForceDraw(Wizard):
    'Invoice Force Draw'
    __name__ = 'account.invoice.force_draw'
    start_state = 'force_draw'
    force_draw = StateTransition()

    def transition_force_draw(self):
        cursor = Transaction().cursor
        ids = tuple(Transaction().context['active_ids'])
        if len(ids) == 1:
            ids = str(ids).replace(',', '')
        else:
            ids = str(ids)
        query = "UPDATE account_invoice SET state='draft' WHERE id IN %s"
        cursor.execute(query % ids)
        return 'end'


class WithholdCertificate(CompanyReport):
    'Invoice Withhold Certificate'
    __name__ = 'account.invoice.withhold_certificate'

    @classmethod
    def __setup__(cls):
        super(WithholdCertificate, cls).__setup__()

    @classmethod
    def parse(cls, report, objects, data, localcontext=None):
        new_objects = []
        for obj in objects:
            obj.withholdings = []
            obj.total_withholding = Decimal(0)
            if not obj.move or obj.state not in ('posted', 'paid'):
                continue
            for invoice_tax in obj.taxes:
                if invoice_tax.tax.group.code != GTA_CODE_TAX['RETENCION']:
                    continue
                obj.withholdings.append({
                    'fiscalyear': obj.move.period.fiscalyear.code,
                    'base': invoice_tax.base,
                    'tax': invoice_tax.tax.name,
                    'tax_code': invoice_tax.tax_code.code,
                    'withhold_rate': fmt(invoice_tax.tax.rate * 100),
                    'amount': fmt(invoice_tax.amount),
                })
                obj.total_withholding += invoice_tax.amount
                new_objects.append(obj)
                
        return super(WithholdCertificate, cls).parse(report,
                new_objects, data, localcontext)
