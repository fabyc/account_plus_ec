#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.wizard import Wizard, StateTransition, Button, StateView
from trytond.transaction import Transaction

__all__ = ['Invoice', 'InvoiceForceDrawStart', 'InvoiceForceDraw']
__metaclass__ = PoolMeta


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

