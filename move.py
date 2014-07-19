#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import fields, ModelView
from trytond.pool import PoolMeta, Pool
from trytond.modules.company import CompanyReport
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateTransition

__all__ = ['AccountMoveSheet', 'Move', 'MoveForceDraw', 'Line',
        'MoveForceDrawStart']
__metaclass__ = PoolMeta


class Move:
    'Account Move'
    __name__ = 'account.move'
    balance = fields.Function(fields.Numeric('Balance', digits=(16, 2)),
        'on_change_with_balance')

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()

    @fields.depends('lines')
    def on_change_with_balance(self, name=None):
        res = Decimal('0.0')
        for line in self.lines:
            res += (line.debit or 0) - (line.credit or 0)
        return res


class Line:
    'Account Move Line'
    __name__ = 'account.move.line'

    @classmethod
    def __setup__(cls):
        super(Line, cls).__setup__()
        cls._order[0] = ('debit', 'DESC')

    @classmethod
    def query_get(cls, table):
        # THIS METHOD ADD PARTY CONTEXT TO QUERYS
        '''
        Return SQL clause and fiscal years for account move line
        depending of the context.
        table is the SQL instance of account.move.line table
        '''
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        Move = pool.get('account.move')
        Period = pool.get('account.period')
        move = Move.__table__()
        period = Period.__table__()
        party = None
        if Transaction().context.get('party'):
            party = Transaction().context.get('party')
            party_sql = (table.party == party)

        if Transaction().context.get('date'):
            fiscalyears = FiscalYear.search([
                    ('start_date', '<=', Transaction().context['date']),
                    ('end_date', '>=', Transaction().context['date']),
                    ], limit=1)

            fiscalyear_id = fiscalyears and fiscalyears[0].id or 0

            if Transaction().context.get('posted'):
                return ((table.state != 'draft')
                    & table.move.in_(move.join(period,
                            condition=move.period == period.id
                            ).select(move.id,
                            where=(move.fiscalyear == fiscalyear_id)
                            & (move.date <= Transaction().context['date'])
                            & (move.state == 'posted'))),
                    [f.id for f in fiscalyears])
            else:
                return ((table.state != 'draft')
                    & table.move.in_(move.join(period,
                            condition=move.period == period.id
                            ).select(move.id,
                            where=(period.fiscalyear == fiscalyear_id)
                            & (move.date <= Transaction().context['date']))),
                    [f.id for f in fiscalyears])

        if Transaction().context.get('periods'):
            if Transaction().context.get('fiscalyear'):
                fiscalyear_ids = [Transaction().context['fiscalyear']]
            else:
                fiscalyear_ids = []
            if Transaction().context.get('posted'):
                if party:
                    return ((table.state != 'draft') & party_sql
                        & table.move.in_(
                        move.select(move.id,
                            where=move.period.in_(
                                        Transaction().context['periods'])
                                    & (move.state == 'posted'))),
                        fiscalyear_ids)
                else:
                    return ((table.state != 'draft')
                        & table.move.in_(
                                move.select(move.id,
                                    where=move.period.in_(
                                        Transaction().context['periods'])
                                    & (move.state == 'posted'))),
                        fiscalyear_ids)
            else:
                if party:
                    return ((table.state != 'draft') & party_sql
                        & table.move.in_(
                        move.select(move.id,
                            where=move.period.in_(
                                Transaction().context['periods']))),
                        fiscalyear_ids)
                else:
                    return ((table.state != 'draft')
                        & table.move.in_(
                        move.select(move.id,
                            where=move.period.in_(
                                Transaction().context['periods']))),
                        fiscalyear_ids)
        else:
            if not Transaction().context.get('fiscalyear'):
                fiscalyears = FiscalYear.search([
                    ('state', '=', 'open'),
                    ])
                fiscalyear_ids = [f.id for f in fiscalyears] or [0]
            else:
                fiscalyear_ids = [Transaction().context.get('fiscalyear')]

            if Transaction().context.get('posted'):
                return ((table.state != 'draft')
                    & table.move.in_(
                        move.select(move.id,
                            where=move.period.in_(
                                period.select(period.id,
                                    where=period.fiscalyear.in_(
                                        fiscalyear_ids)))
                            & (move.state == 'posted'))),
                    fiscalyear_ids)
            else:
                return ((table.state != 'draft')
                    & table.move.in_(
                        move.select(move.id,
                            where=move.period.in_(
                                period.select(period.id,
                                    where=period.fiscalyear.in_(
                                        fiscalyear_ids))))),
                    fiscalyear_ids)


class MoveForceDrawStart(ModelView):
    'Move Force Draw'
    __name__ = 'account.move.force_draw.start'


class MoveForceDraw(Wizard):
    'Move Force Draw'
    __name__ = 'account.move.force_draw'
    start_state = 'force_draw'
    force_draw = StateTransition()

    def transition_force_draw(self):
        cursor = Transaction().cursor
        ids = tuple(Transaction().context['active_ids'])
        if len(ids) == 1:
            ids = str(ids).replace(',', '')
        else:
            ids = str(ids)
        query = "UPDATE account_move SET state='draft' WHERE id IN %s"
        cursor.execute(query % ids)
        return 'end'


class AccountMoveSheet(CompanyReport):
    'Account Move Sheet'
    __name__ = 'account.move.sheet'

    @classmethod
    def __setup__(cls):
        super(AccountMoveSheet, cls).__setup__()

    @classmethod
    def parse(cls, report, objects, data, localcontext=None):
        localcontext['company'] = Transaction().context.get('company')
        new_objects = []
        for obj in objects:
            debits_ = []
            credits_ = []
            for line in obj.lines:
                debits_.append(line.debit)
                credits_.append(line.credit)
            setattr(obj, 'sum_debits', sum(debits_))
            setattr(obj, 'sum_credits', sum(credits_))
            new_objects.append(obj)

        return super(AccountMoveSheet, cls).parse(report,
                new_objects, data, localcontext)
