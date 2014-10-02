#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
from datetime import date
import operator
from sql.aggregate import Sum
from itertools import izip, groupby
from collections import OrderedDict
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.report import Report
from trytond.pyson import Eval, PYSONEncoder
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta


__all__ = ['AuxiliaryBookStart', 'PrintAuxiliaryBook', 'AuxiliaryBook',
        'PortfolioByPartyDetailed', 'TrialBalanceDetailed', 
        'PrintTrialBalanceDetailed', 'PrintTrialBalanceDetailedStart',
        'PrintAuxiliaryParty', 'AuxiliaryParty', 'AuxiliaryPartyStart',
        'PrintTrialBalanceStart', 'PrintTrialBalance', 'TrialBalance',
        'BalanceSheet', 'IncomeStatement', 'OpenCashflowState', 'Cashflow',
        'CashflowTemplate', 'OpenCashflowStart', 'Account', 'Journal',
        'AccountAuthorization', 'ATSStart', 'ATS', 'PrintATS']

__metaclass__ = PoolMeta

def fmt_acc(val):
    # Format account number function
    fmt = '%s' + '0' * (8 - len(str(val)))
    account_code_fmt = int(fmt % val)
    return account_code_fmt


class Account:
    __name__ = 'account.account'
    cashflow = fields.Many2One('account.account.cashflow', 'Cashflow', 
        ondelete="RESTRICT", states={
            'invisible': Eval('kind') == 'view',
            },
        domain=[
            ('company', '=', Eval('company')),
            ], depends=['kind', 'company'])


class AuxiliaryBookStart(ModelView):
    'Auxiliary Book Start'
    __name__ = 'account_plus_ec.print_auxiliary_book.start'
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            required=True)
    start_period = fields.Many2One('account.period', 'Start Period',
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear')),
            ('start_date', '<=', (Eval('end_period'), 'start_date')),
            ], depends=['fiscalyear', 'end_period'])
    end_period = fields.Many2One('account.period', 'End Period',
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear')),
            ('start_date', '>=', (Eval('start_period'), 'start_date'))
            ],
        depends=['fiscalyear', 'start_period'])
    start_code = fields.Char('Start Code Range')
    end_code = fields.Char('End Code Range')
    party = fields.Many2One('party.party', 'Party')
    company = fields.Many2One('company.company', 'Company', required=True)
    posted = fields.Boolean('Posted Move', help='Show only posted move')
    empty_account = fields.Boolean('Empty Account',
            help='With account without move')

    @staticmethod
    def default_fiscalyear():
        FiscalYear = Pool().get('account.fiscalyear')
        return FiscalYear.find(
            Transaction().context.get('company'), exception=False)

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_posted():
        return False

    @staticmethod
    def default_empty_account():
        return False

    @fields.depends('fiscalyear')
    def on_change_fiscalyear(self):
        return {
            'start_period': None,
            'end_period': None,
        }


class PrintAuxiliaryBook(Wizard):
    'Print Auxiliary Book'
    __name__ = 'account_plus_ec.print_auxiliary_book'
    start = StateView('account_plus_ec.print_auxiliary_book.start',
        'account_plus_ec.print_auxiliary_book_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateAction('account_plus_ec.report_auxiliary_book')

    def do_print_(self, action):
        if self.start.start_period:
            start_period = self.start.start_period.id
        else:
            start_period = None
        if self.start.end_period:
            end_period = self.start.end_period.id
        else:
            end_period = None

        if not self.start.party:
            party = None
        else:
            party = self.start.party.id
        data = {
            'company': self.start.company.id,
            'fiscalyear': self.start.fiscalyear.id,
            'start_period': start_period,
            'end_period': end_period,
            'posted': self.start.posted,
            'start_code': self.start.start_code,
            'end_code': self.start.end_code,
            'party': party,
            'empty_account': self.start.empty_account,
            }
        return action, data

    def transition_print_(self):
        return 'end'


class AuxiliaryBook(Report):
    __name__ = 'account.auxiliary_book'

    @classmethod
    def parse(cls, report, objects, data, localcontext):
        pool = Pool()
        Account = pool.get('account.account')
        Period = pool.get('account.period')
        Company = pool.get('company.company')
        Party = pool.get('party.party')
        company = Company(data['company'])

        accounts = Account.search([
                ('company', '=', data['company']),
                ('kind', '!=', 'view'),
                ], order=[('code', 'ASC'), ('id', 'ASC')])

        start_period_name = None
        end_period_name = None

        if data['start_code'] or data['end_code']:
            if not data['start_code']:
                start_code = 0
            else:
                start_code = fmt_acc(data['start_code'])
            if not data['end_code']:
                end_code = 99999999
            else:
                end_code = fmt_acc(data['end_code'])
            accounts = cls.get_accounts_range(accounts, start_code, end_code)
            print accounts

        party = None
        if data['party']:
            party, = Party.search([
                    ('id', '=', data['party']),
                    ])
        # --------------------------------------------------------------
        start_period_ids = [0]
        start_periods = []
        if data['start_period']:
            start_period = Period(data['start_period'])
            start_periods = Period.search([
                    ('fiscalyear', '=', data['fiscalyear']),
                    ('end_date', '<=', start_period.start_date),
                    ])
            start_period_ids = [p.id for p in start_periods]
            start_period_name = start_period.name

        with Transaction().set_context(
                fiscalyear=data['fiscalyear'],
                periods=start_period_ids,
                party=data['party'],
                posted=data['posted']):
            start_accounts = Account.browse(accounts)
        id2start_account = {}
        for account in start_accounts:
            id2start_account[account.id] = account

        # --------------------------------------------------------------
        end_period_ids = []
        if data['end_period']:
            end_period = Period(data['end_period'])
            end_periods = Period.search([
                    ('fiscalyear', '=', data['fiscalyear']),
                    ('end_date', '<=', end_period.start_date),
                    ])
            if end_period not in end_periods:
                end_periods.append(end_period)
            end_period_name = end_period.name
        else:
            end_periods = Period.search([
                    ('fiscalyear', '=', data['fiscalyear']),
                    ])
        end_period_ids = [p.id for p in end_periods]

        with Transaction().set_context(
                fiscalyear=data['fiscalyear'],
                periods=end_period_ids,
                party=data['party'],
                posted=data['posted']):
            end_accounts = Account.browse(accounts)
        id2end_account = {}
        for account in end_accounts:
            id2end_account[account.id] = account

        periods = end_periods
        periods.sort(lambda x, y: cmp(x.start_date, y.start_date))
        periods.sort(lambda x, y: cmp(x.end_date, y.end_date))
        # --------------------------------------------------------------

        if not data['empty_account']:
            account2lines = dict(cls.get_lines(accounts,
                end_periods, data['posted'], data['party']))
            accounts = Account.browse(
                [a.id for a in accounts if a in account2lines]
                )

        account_id2lines = cls.lines(accounts,
            list(set(end_periods).difference(set(start_periods))),
            data['posted'], data['party'])

        # --------------------------------------------------------------
        localcontext['start_period_name'] = start_period_name
        localcontext['end_period_name'] = end_period_name
        localcontext['start_code'] = data['start_code']
        localcontext['end_code'] = data['end_code']
        localcontext['party'] = party
        localcontext['accounts'] = accounts
        localcontext['id2start_account'] = id2start_account
        localcontext['id2end_account'] = id2end_account
        localcontext['digits'] = company.currency.digits
        localcontext['lines'] = lambda account_id: account_id2lines[account_id]
        localcontext['company'] = company
        return super(AuxiliaryBook, cls).parse(report, objects, data,
            localcontext)

    @classmethod
    def get_accounts_range(cls, accounts, start_code, end_code):
        filtered_accounts = []
        for account in accounts:
            val = fmt_acc(account.code)
            if val >= start_code and val <= end_code:
                filtered_accounts.append(account)
        return filtered_accounts

    @classmethod
    def get_lines(cls, accounts, periods, posted, party=None):
        MoveLine = Pool().get('account.move.line')
        clause = [
            ('account', 'in', [a.id for a in accounts]),
            ('period', 'in', [p.id for p in periods]),
            ('state', '!=', 'draft'),
            ]
        if party:
            clause.append(('party', '=', party))
        if posted:
            clause.append(('move.state', '=', 'posted'))
        lines = MoveLine.search(clause,
            order=[
                ('account', 'ASC'),
                ('date', 'ASC'),
                ])
        key = operator.attrgetter('account')
        lines.sort(key=key)
        return groupby(lines, key)

    @classmethod
    def lines(cls, accounts, periods, posted, party=None):
        Move = Pool().get('account.move')

        res = dict((a.id, []) for a in accounts)
        account2lines = cls.get_lines(accounts, periods, posted, party)

        state_selections = dict(Move.fields_get(
                fields_names=['state'])['state']['selection'])

        for account, lines in account2lines:
            balance = Decimal('0.0')
            for line in lines:
                balance += line.debit - line.credit
                party = ''
                if line.party:
                    party = line.party.rec_name
                res[account.id].append({
                        'date': line.date,
                        'move': line.move.rec_name,
                        'party': party,
                        'debit': line.debit,
                        'credit': line.credit,
                        'balance': balance,
                        'description': line.move.description or line.description or '',
                        'origin': (line.move.origin.rec_name
                            if line.move.origin else ''),
                        'state': state_selections.get(line.move.state,
                            line.move.state),
                        })
        return res


class PortfolioByPartyDetailed(Report):
    __name__ = 'party.portfolio_party_detailed'

    @classmethod
    def parse(cls, report, objects, data, localcontext):
        pool = Pool()
        AccountInvoice = pool.get('account.invoice')
        new_objects = []
        now = date.today()
        for party in objects:
            invoices = AccountInvoice.search([
                    ('party', '=', party.id),
                    ('state', 'not in', ['paid', 'cancel']),
                    ], order=[('id', 'ASC')])
            new_invoices = []
            sum_invoices = 0
            if not invoices:
                continue

            #FIXME TRANSLATIONS
            for invoice in invoices:
                sum_invoices += invoice.total_amount
                if invoice.invoice_date:
                    invoice.aged = (now - invoice.invoice_date).days
                else:
                    invoice.aged = ''
                if invoice.state == 'draft':
                    invoice.state = 'Borrador'
                elif invoice.state == 'validated':
                    invoice.state = 'Validada'
                elif invoice.state == 'posted':
                    invoice.state = 'Registrada'
                new_invoices.append(invoice)

            party.invoices = new_invoices
            party.sum_invoices = sum_invoices
            new_objects.append(party)
        return super(PortfolioByPartyDetailed, cls).parse(report, 
                new_objects, data, localcontext)


class PrintTrialBalanceDetailedStart(ModelView):
    'Print Trial Balance Detailed'
    __name__ = 'account_plus_ec.print_trial_balance_detailed.start'
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            required=True, depends=['start_period', 'end_period'])
    start_period = fields.Many2One('account.period', 'Start Period',
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear')),
            ('start_date', '<=', (Eval('end_period'), 'start_date'))
            ],
        depends=['end_period', 'fiscalyear'])
    end_period = fields.Many2One('account.period', 'End Period',
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear')),
            ('start_date', '>=', (Eval('start_period'), 'start_date'))
            ],
        depends=['start_period', 'fiscalyear'])
    start_code = fields.Integer('Start Code')
    end_code = fields.Integer('End Code')
    party = fields.Many2One('party.party', 'Party')
    company = fields.Many2One('company.company', 'Company', required=True)
    posted = fields.Boolean('Posted Move', help='Show only posted move')
    empty_account = fields.Boolean('Empty Account',
            help='With account without move')

    @staticmethod
    def default_fiscalyear():
        FiscalYear = Pool().get('account.fiscalyear')
        return FiscalYear.find(
            Transaction().context.get('company'), exception=False)

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_posted():
        return False

    @staticmethod
    def default_empty_account():
        return False

    @fields.depends('fiscalyear')
    def on_change_fiscalyear(self):
        return {
            'start_period': None,
            'end_period': None,
            }


class PrintTrialBalanceDetailed(Wizard):
    'Print Trial Balance Detailed'
    __name__ = 'account_plus_ec.print_trial_balance_detailed'
    start = StateView('account_plus_ec.print_trial_balance_detailed.start',
        'account_plus_ec.print_trial_balance_detailed_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateAction('account_plus_ec.report_trial_balance_detailed')

    def do_print_(self, action):
        if self.start.start_period:
            start_period = self.start.start_period.id
        else:
            start_period = None
        if self.start.end_period:
            end_period = self.start.end_period.id
        else:
            end_period = None
        if self.start.party:
            party_id = self.start.party.id
        else:
            party_id = None
        if self.start.start_code:
            start_code = self.start.start_code
        else:
            start_code = None
        if self.start.end_code:
            end_code = self.start.end_code
        else:
            end_code = None
        data = {
            'company': self.start.company.id,
            'fiscalyear': self.start.fiscalyear.id,
            'start_period': start_period,
            'end_period': end_period,
            'start_code': start_code,
            'end_code': end_code,
            'party': party_id,
            'posted': self.start.posted,
            'empty_account': self.start.empty_account,
            }
        return action, data

    def transition_print_(self):
        return 'end'


class TrialBalanceDetailed(Report):
    __name__ = 'account_plus_ec.trial_balance_detailed'

    @classmethod
    def parse(cls, report, objects, data, localcontext):
        pool = Pool()
        Account = pool.get('account.account')
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Period = pool.get('account.period')
        Company = pool.get('company.company')
        Party = pool.get('party.party')
        cursor = Transaction().cursor

        move = Move.__table__()
        line = Line.__table__()
        start_period_name = None
        end_period_name = None

        # ----- Set Periods -----
        start_periods = []
        if data['start_period']:
            start_period = Period(data['start_period'])
            start_periods = Period.search([
                    ('fiscalyear', '=', data['fiscalyear']),
                    ('end_date', '<=', start_period.start_date),
                    ])
            start_period_name = start_period.name

        if data['end_period']:
            end_period = Period(data['end_period'])
            end_periods = Period.search([
                    ('fiscalyear', '=', data['fiscalyear']),
                    ('end_date', '<=', end_period.start_date),
                    ])
            end_periods = list(set(end_periods).difference(
                    set(start_periods)))
            end_period_name = end_period.name
            if end_period not in end_periods:
                end_periods.append(end_period)
        else:
            end_periods = Period.search([
                    ('fiscalyear', '=', data['fiscalyear']),
                    ])
            end_periods = list(set(end_periods).difference(
                    set(start_periods)))

        # Select Query for In
        in_periods = [p.id for p in end_periods]
        move_ = move.select(move.id, where = (move.period.in_(in_periods)))
        select_ = line.select(
                line.account, line.party, Sum(line.debit), Sum(line.credit),
                where=line.move.in_(move_),
                group_by=(line.account, line.party),
                order_by=line.account,
                )
        if data['party']:
            where_party = select_.where & (line.party == data['party'])
            select_.where = select_.where & where_party
        cursor.execute(*select_)
        res = cursor.fetchall()

        id2account = {}
        id2party = {}
        accs_ids = []
        parties_ids = []
        for r in res:
            accs_ids.append(r[0])
            if r[1]:
                parties_ids.append(r[1])
        for acc in Account.browse(accs_ids):
            id2account[acc.id] = acc
        for party in Party.browse(parties_ids):
            id2party[party.id] = party

        # Select Query for Start
        start_periods_ids = [p.id for p in start_periods]
        start_accounts = {}
        if start_periods_ids:
            move_ = move.select(move.id)
            move_.where = (move.period.in_(start_periods_ids))

            select_ = line.select(
                    line.account, line.party, Sum(line.debit) - Sum(line.credit),
                    where=line.move.in_(move_) & line.account.in_(accs_ids),
                    group_by=(line.account, line.party),
                    order_by=line.account,
                    )

            if data['party']:
                select_.where = select_.where & where_party

            #print tuple(select_)
            cursor.execute(*select_)

            res_start = cursor.fetchall()

            for r in res_start:
                acc_obj = id2account[r[0]]
                code = fmt_acc(acc_obj.code)
                if code not in start_accounts.keys():
                    start_accounts[code] = {}
                start_accounts[code].update({r[1]: r[2]})
        # agregar rango de cuentas
        accounts = {}
        for r in res:
            vat_number = ''
            party = ''
            if r[1]:
                party = id2party[r[1]].name
                vat_number = id2party[r[1]].vat_number
            acc_obj = id2account[r[0]]
            code = fmt_acc(acc_obj.code)
            if code not in accounts.keys():
                accounts[code] = [
                    acc_obj, [], {'debits': 0, 'credits': 0}
                    ]
            start_balance = 0
            if start_accounts and start_accounts.get(code) and \
                    start_accounts[code].get(r[1]):
                    start_balance = start_accounts[code][r[1]]
            values = {
                'vat_number': vat_number,
                'party': party,
                'start_balance': start_balance,
                'debit': r[2],
                'credit': r[3],
                'end_balance': start_balance + r[2] - r[3],
            }
            accounts[code][1].append(values)
            accounts[code][2]['debits'] += r[2]
            accounts[code][2]['credits'] += r[3]

        localcontext['accounts'] = OrderedDict(sorted(accounts.items()))
        localcontext['start_period'] = start_period_name
        localcontext['end_period'] = end_period_name
        localcontext['company'] = Company(data['company'])
        return super(TrialBalanceDetailed, cls).parse(report, objects, data,
            localcontext)


class AuxiliaryPartyStart(ModelView):
    'Auxiliary Party Start'
    __name__ = 'account_plus_ec.print_auxiliary_party.start'
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            required=True)
    start_period = fields.Many2One('account.period', 'Start Period',
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear')),
            ('start_date', '<=', (Eval('end_period'), 'start_date')),
            ], depends=['fiscalyear', 'end_period'])
    end_period = fields.Many2One('account.period', 'End Period',
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear')),
            ('start_date', '>=', (Eval('start_period'), 'start_date'))
            ],
        depends=['fiscalyear', 'start_period'])
    party = fields.Many2One('party.party', 'Party', required=True)
    company = fields.Many2One('company.company', 'Company', required=True)
    posted = fields.Boolean('Posted Move', help='Show only posted move')
    empty_account = fields.Boolean('Empty Account',
            help='With account without move')

    @staticmethod
    def default_fiscalyear():
        FiscalYear = Pool().get('account.fiscalyear')
        return FiscalYear.find(
            Transaction().context.get('company'), exception=False)

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_posted():
        return False

    @staticmethod
    def default_empty_account():
        return False

    @fields.depends('fiscalyear')
    def on_change_fiscalyear(self):
        return {
            'start_period': None,
            'end_period': None,
            }


class PrintAuxiliaryParty(Wizard):
    'Print Auxiliary Party'
    __name__ = 'account_plus_ec.print_auxiliary_party'
    start = StateView('account_plus_ec.print_auxiliary_party.start',
        'account_plus_ec.print_auxiliary_party_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateAction('account_plus_ec.report_auxiliary_party')

    def do_print_(self, action):
        if self.start.start_period:
            start_period = self.start.start_period.id
        else:
            start_period = None
        if self.start.end_period:
            end_period = self.start.end_period.id
        else:
            end_period = None
        if not self.start.party:
            party = None
        else:
            party = self.start.party.id
        data = {
            'company': self.start.company.id,
            'fiscalyear': self.start.fiscalyear.id,
            'start_period': start_period,
            'end_period': end_period,
            'posted': self.start.posted,
            'party': party,
            'empty_account': self.start.empty_account,
            }
        return action, data

    def transition_print_(self):
        return 'end'


class AuxiliaryParty(Report):
    __name__ = 'account.auxiliary_party'

    @classmethod
    def parse(cls, report, objects, data, localcontext):
        pool = Pool()
        Period = pool.get('account.period')
        Company = pool.get('company.company')
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')
        Party = pool.get('party.party')
        company = Company(data['company'])
        dom_move = []
        #Add context Transaction for company and fiscalyear
        #    dom_move = [('company', '=', company)]
        if data.get('posted'):
            dom_move.append(('state', '=', 'posted'))
        if data.get('start_period'):
            dom_move.append(('period', '>=', data['start_period']))
        if data.get('end_period'):
            dom_move.append(('period', '<=', data['end_period']))

        moves = Move.search_read(dom_move, order=[
                ('date', 'ASC'), ('id', 'ASC')
                ], fields_names=['id'],
        )
        moves_ids = [move['id'] for move in moves]
        objects = []

        lines = MoveLine.search([
                ('move', 'in', moves_ids),
                ('party', '=', data['party']),
                ], order=[('id', 'ASC')])
        start_period = None
        end_period = None
        if lines:
            debits_ = []
            credits_ = []
            new_lines = []

            for line in lines:
                new_line = {
                    'date': line.move.date,
                    'post_number': line.move.post_number,
                    'account_code': line.account.code,
                    'account_name': line.account.name,
                    'description': line.description,
                    'debit': line.debit,
                    'credit': line.credit,
                    'base': None,
                }
                base = Decimal(0)
                for tax_line in line.tax_lines:
                    if tax_line.tax.invoice_tax_code != tax_line.code:
                        continue
                    for l in line.move.lines:
                        for tx_line in l.tax_lines:
                            if tx_line.code == tax_line.tax.invoice_base_code:
                                base += tx_line.amount
                new_line.update({'base': base})
                new_lines.append(new_line)
                debits_.append(line.debit) 
                credits_.append(line.credit) 
            db = sum(debits_)
            cr = sum(credits_)
            party = Party(data['party'])
            objects.append({
                    'name': party.rec_name,
                    'vat_number': party.vat_number,
                    'lines': new_lines,
                    'debit': db,
                    'credit': cr,
                    'balance': (db - cr),
                    })
            if data['start_period']:
                start_period = Period(data['start_period'])
                start_period = start_period.name
            if data['end_period']:
                end_period = Period(data['end_period'])
                end_period = end_period.name
        localcontext['start_period'] = start_period
        localcontext['end_period'] = end_period
        localcontext['company'] = company
        return super(AuxiliaryParty, cls).parse(report, objects, data,
                localcontext)


#Must be fixed in 3.2
class PrintTrialBalanceStart:
    'Print Trial Balance'
    __name__ = 'account.print_trial_balance.start'
    accounts_with_balance = fields.Boolean('Accounts with Balance', 
            help='Show accounts with balances in previous periods')


class PrintTrialBalance:
    'Print Trial Balance'
    __name__ = 'account.print_trial_balance'

    def do_print_(self, action):
        action, data = super(PrintTrialBalance, self).do_print_(action)
        data.update({
                'accounts_with_balance': self.start.accounts_with_balance,
                })
        return action, data


class TrialBalance:
    __name__ = 'account.trial_balance'

    @classmethod
    def parse(cls, report, objects, data, localcontext):
        pool = Pool()
        Account = pool.get('account.account')
        Period = pool.get('account.period')
        Company = pool.get('company.company')

        company = Company(data['company'])

        accounts = Account.search([
                ('company', '=', data['company']),
                ('kind', '!=', 'view'),
                ])

        start_periods = []
        if data['start_period']:
            start_period = Period(data['start_period'])
            start_periods = Period.search([
                    ('fiscalyear', '=', data['fiscalyear']),
                    ('end_date', '<=', start_period.start_date),
                    ])

        if data['end_period']:
            end_period = Period(data['end_period'])
            end_periods = Period.search([
                    ('fiscalyear', '=', data['fiscalyear']),
                    ('end_date', '<=', end_period.start_date),
                    ])
            end_periods = list(set(end_periods).difference(
                    set(start_periods)))
            if end_period not in end_periods:
                end_periods.append(end_period)
        else:
            end_periods = Period.search([
                    ('fiscalyear', '=', data['fiscalyear']),
                    ])
            end_periods = list(set(end_periods).difference(
                    set(start_periods)))

        start_period_ids = [p.id for p in start_periods] or [0]
        end_period_ids = [p.id for p in end_periods]

        with Transaction().set_context(
                fiscalyear=data['fiscalyear'],
                periods=start_period_ids,
                posted=data['posted']):
            start_accounts = Account.browse(accounts)

        with Transaction().set_context(
                fiscalyear=None,
                periods=end_period_ids,
                posted=data['posted']):
            in_accounts = Account.browse(accounts)

        with Transaction().set_context(
                fiscalyear=data['fiscalyear'],
                periods=start_period_ids + end_period_ids,
                posted=data['posted']):
            end_accounts = Account.browse(accounts)

        to_remove = []
        if not data['empty_account']:
            for account in in_accounts:
                if account.debit == Decimal('0.0') \
                        and account.credit == Decimal('0.0'):
                    to_remove.append(account.id)

        accounts = []
        for start_account, in_account, end_account in izip(
                start_accounts, in_accounts, end_accounts):
            if in_account.id in to_remove:
                if not data['accounts_with_balance'] or \
                    start_account.balance == Decimal('0.0'):
                    continue

            accounts.append({
                    'code': start_account.code,
                    'name': start_account.name,
                    'start_balance': start_account.balance,
                    'debit': in_account.debit,
                    'credit': in_account.credit,
                    'end_balance': end_account.balance,
                    })

        periods = end_periods
        localcontext['accounts'] = accounts
        periods.sort(key=operator.attrgetter('start_date'))
        localcontext['start_period'] = periods[0]
        periods.sort(key=operator.attrgetter('end_date'))
        localcontext['end_period'] = periods[-1]
        localcontext['company'] = company
        localcontext['digits'] = company.currency.digits
        localcontext['sum'] = lambda accounts, field: cls.sum(accounts, field)
        return Report.parse(report, objects, data, localcontext)

    @classmethod
    def sum(cls, accounts, field):
        amount = Decimal('0.0')
        for account in accounts:
            amount += account[field]
        return amount


class BalanceSheet(Report):
    'Sheet Balance'
    __name__ = 'account.balance_sheet'

    @classmethod
    def parse(cls, report, objects, data, localcontext):
        localcontext['company'] = Transaction().context.get('company.rec_name')
        localcontext['date'] = Transaction().context.get('date')
        return super(BalanceSheet, cls).parse(report, objects, data, localcontext)


class IncomeStatement(Report):
    'Income Statement'
    __name__ = 'account.income_statement'

    @classmethod
    def parse(cls, report, objects, data, localcontext):
        localcontext['company'] = Transaction().context.get('company.rec_name')
        localcontext['date'] = Transaction().context.get('date')
        return super(IncomeStatement, cls).parse(report, objects, data, localcontext)


class CashflowTemplate(ModelSQL, ModelView):
    'Account Cashflow Template'
    __name__ = 'account.account.cashflow.template'
    name = fields.Char('Name', required=True, translate=True)
    parent = fields.Many2One('account.account.cashflow.template', 'Parent',
            ondelete="RESTRICT")
    childs = fields.One2Many('account.account.cashflow.template', 'parent',
        'Children')
    sequence = fields.Integer('Sequence')
    display_balance = fields.Selection([
        ('debit-credit', 'Debit - Credit'),
        ('credit-debit', 'Credit - Debit'),
        ], 'Display Balance', required=True)

    @classmethod
    def __setup__(cls):
        super(CashflowTemplate, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        super(CashflowTemplate, cls).__register__(module_name)

    @classmethod
    def validate(cls, records):
        super(CashflowTemplate, cls).validate(records)
        cls.check_recursion(records, rec_name='name')

    @staticmethod
    def order_sequence(tables):
        table, _ = tables[None]
        return [table.sequence == None, table.sequence]

    @staticmethod
    def default_display_balance():
        return 'debit-credit'

    def get_rec_name(self, name):
        if self.parent:
            return self.parent.get_rec_name(name) + '\\' + self.name
        else:
            return self.name

    def _get_cashflow_value(self, cashflow=None):
        '''
        Set the values for account creation.
        '''
        res = {}
        if not cashflow or cashflow.name != self.name:
            res['name'] = self.name
        if not cashflow or cashflow.sequence != self.sequence:
            res['sequence'] = self.sequence
        if not cashflow or cashflow.display_balance != self.display_balance:
            res['display_balance'] = self.display_balance
        if not cashflow or cashflow.template != self:
            res['template'] = self.id
        return res

    def create_cashflow(self, company_id, template2cashflow=None, parent_id=None):
        '''
        Create recursively cashflows based on template.
        template2cashflow is a dictionary with template id as key and cashflow id as
        value, used to convert template id into cashflow. The dictionary is filled
        with new cashflows.
        Return the id of the cashflow created
        '''
        pool = Pool()
        Cashflow = pool.get('account.account.cashflow')
        Lang = pool.get('ir.lang')
        Config = pool.get('ir.configuration')

        if template2cashflow is None:
            template2cashflow = {}

        if self.id not in template2cashflow:
            vals = self._get_cashflow_value()
            vals['company'] = company_id
            vals['parent'] = parent_id

            new_cashflow, = Cashflow.create([vals])

            prev_lang = self._context.get('language') or Config.get_language()
            prev_data = {}
            for field_name, field in self._fields.iteritems():
                if getattr(field, 'translate', False):
                    prev_data[field_name] = getattr(self, field_name)
            for lang in Lang.get_translatable_languages():
                if lang == prev_lang:
                    continue
                with Transaction().set_context(language=lang):
                    template = self.__class__(self.id)
                    data = {}
                    for field_name, field in template._fields.iteritems():
                        if (getattr(field, 'translate', False)
                                and (getattr(template, field_name) !=
                                    prev_data[field_name])):
                            data[field_name] = getattr(template, field_name)
                    if data:
                        Cashflow.write([new_cashflow], data)
            template2cashflow[self.id] = new_cashflow.id
        new_id = template2cashflow[self.id]

        new_childs = []
        for child in self.childs:
            new_childs.append(child.create_cashflow(company_id,
                template2cashflow=template2cashflow, parent_id=new_id))
        return new_id


class Cashflow(ModelSQL, ModelView):
    'Account Cashflow'
    __name__ = 'account.account.cashflow'
    name = fields.Char('Name', size=None, required=True, translate=True)
    parent = fields.Many2One('account.account.cashflow', 'Parent',
        ondelete="RESTRICT", domain=[
            ('company', '=', Eval('company')),
            ], depends=['company'])
    childs = fields.One2Many('account.account.cashflow', 'parent', 'Children',
        domain=[
            ('company', '=', Eval('company')),
        ], depends=['company'])
    sequence = fields.Integer('Sequence',
        help='Use to order the account cashflow')
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
            'get_currency_digits')
    amount = fields.Function(fields.Numeric('Amount',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits']),
        'get_amount')
    display_balance = fields.Selection([
        ('debit-credit', 'Debit - Credit'),
        ('credit-debit', 'Credit - Debit'),
        ], 'Display Balance', required=True)
    company = fields.Many2One('company.company', 'Company', required=True,
            ondelete="RESTRICT")
    template = fields.Many2One('account.account.cashflow.template', 'Template')
    accounts = fields.One2Many('account.account', 'cashflow', 'Accounts',
            add_remove=[], domain=[ 
                ('kind', '!=', 'view'),
            ])

    @classmethod
    def __setup__(cls):
        super(Cashflow, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        super(Cashflow, cls).__register__(module_name)

    @classmethod
    def validate(cls, cashflows):
        super(Cashflow, cls).validate(cashflows)
        cls.check_recursion(cashflows, rec_name='name')

    @staticmethod
    def order_sequence(tables):
        table, _ = tables[None]
        return [table.sequence == None, table.sequence]

    @staticmethod
    def default_balance_sheet():
        return False

    @staticmethod
    def default_income_statement():
        return False

    @staticmethod
    def default_display_balance():
        return 'debit-credit'

    def get_currency_digits(self, name):
        return self.company.currency.digits

    @classmethod
    def get_amount(cls, cashflows, name):
        pool = Pool()
        Account = pool.get('account.account')

        res = {}
        for cashflow_ in cashflows:
            res[cashflow_.id] = Decimal('0.0')

        childs = cls.search([
                ('parent', 'child_of', [t.id for t in cashflows]),
                ])
        cashflow_sum = {}
        for cashflow_ in childs:
            cashflow_sum[cashflow_.id] = Decimal('0.0')

        accounts = Account.search([
                ('cashflow', 'in', [t.id for t in childs]),
                ('kind', '!=', 'view'),
                ])
        for account in accounts:
            cashflow_sum[account.cashflow.id] += (account.debit - account.credit)

        for cashflow_ in cashflows:
            childs = cls.search([
                    ('parent', 'child_of', [cashflow_.id]),
                    ])
            for child in childs:
                res[cashflow_.id] += cashflow_sum[child.id]
            res[cashflow_.id] = cashflow_.company.currency.round(res[cashflow_.id])
            if cashflow_.display_balance == 'credit-debit':
                res[cashflow_.id] = - res[cashflow_.id]
        return res

    def get_rec_name(self, name):
        if self.parent:
            return self.parent.get_rec_name(name) + '\\' + self.name
        else:
            return self.name

    @classmethod
    def delete(cls, cashflows):
        cashflows = cls.search([
                ('parent', 'child_of', [t.id for t in cashflows]),
                ])
        super(Cashflow, cls).delete(cashflows)

    def update_cashflow(self, template2cashflow=None):
        '''
        Update recursively cashflows based on template.
        template2cashflow is a dictionary with template id as key and cashflow id as
        value, used to convert template id into cashflow. The dictionary is filled
        with new cashflows
        '''
        pool = Pool()
        Lang = pool.get('ir.lang')
        Config = pool.get('ir.configuration')

        if template2cashflow is None:
            template2cashflow = {}

        if self.template:
            vals = self.template._get_cashflow_value(cashflow=self)
            if vals:
                self.write([self], vals)

            prev_lang = self._context.get('language') or Config.get_language()
            prev_data = {}
            for field_name, field in self.template._fields.iteritems():
                if getattr(field, 'translate', False):
                    prev_data[field_name] = getattr(self.template, field_name)
            for lang in Lang.get_translatable_languages():
                if lang == prev_lang:
                    continue
                with Transaction().set_context(language=lang):
                    cashflow_ = self.__class__(self.id)
                    data = {}
                    for field_name, field in (
                            cashflow_.template._fields.iteritems()):
                        if (getattr(field, 'translate', False)
                                and (getattr(cashflow_.template, field_name) !=
                                    prev_data[field_name])):
                            data[field_name] = getattr(cashflow_.template,
                                field_name)
                    if data:
                        self.write([cashflow_], data)
            template2cashflow[self.template.id] = self.id

        for child in self.childs:
            child.update_cashflow(template2cashflow=template2cashflow)


class OpenCashflowStart(ModelView):
    'Open Cashflow State'
    __name__ = 'account.open_cashflow_state.start'
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
        required=True)
    start_period = fields.Many2One('account.period', 'Start Period',
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear')),
            ('start_date', '<=', (Eval('end_period'), 'start_date'))
            ],
        depends=['end_period', 'fiscalyear'])
    end_period = fields.Many2One('account.period', 'End Period',
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear')),
            ('start_date', '>=', (Eval('start_period'), 'start_date')),
            ],
        depends=['start_period', 'fiscalyear'])
    company = fields.Many2One('company.company', 'Company', required=True)
    posted = fields.Boolean('Posted Move', help='Show only posted move')

    @staticmethod
    def default_fiscalyear():
        FiscalYear = Pool().get('account.fiscalyear')
        return FiscalYear.find(
            Transaction().context.get('company'), exception=False)

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_posted():
        return False

    @fields.depends('fiscalyear')
    def on_change_fiscalyear(self):
        return {
            'start_period': None,
            'end_period': None,
            }


class OpenCashflowState(Wizard):
    'Open Cashflow State'
    __name__ = 'account.open_cashflow_state'
    start = StateView('account.open_cashflow_state.start',
        'account_plus_ec.open_cashflow_state_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Open', 'open_', 'tryton-ok', default=True),
            ])
    open_ = StateAction('account_plus_ec.act_account_cashflow_state_tree')

    def do_open_(self, action):
        pool = Pool()
        Period = pool.get('account.period')

        start_periods = []
        if self.start.start_period:
            start_periods = Period.search([
                    ('fiscalyear', '=', self.start.fiscalyear.id),
                    ('end_date', '<=', self.start.start_period.start_date),
                    ])

        end_periods = []
        if self.start.end_period:
            end_periods = Period.search([
                    ('fiscalyear', '=', self.start.fiscalyear.id),
                    ('end_date', '<=', self.start.end_period.start_date),
                    ])
            end_periods = list(set(end_periods).difference(
                    set(start_periods)))
            if self.start.end_period not in end_periods:
                end_periods.append(self.start.end_period)
        else:
            end_periods = Period.search([
                    ('fiscalyear', '=', self.start.fiscalyear.id),
                    ])
            end_periods = list(set(end_periods).difference(
                    set(start_periods)))

        action['pyson_context'] = PYSONEncoder().encode({
                'periods': [p.id for p in end_periods],
                'posted': self.start.posted,
                'company': self.start.company.id,
                })
        return action, {}


class AccountAuthorization(ModelView, ModelSQL):
    'Authorization Accounting Documents'
    __name__ = 'account.authorization'
    sequence = fields.Many2One('ir.sequence', 'Secuencia')
    name = fields.Char('Num. de Autorizacion', size=128, required=True)
    serie_entidad = fields.Char('Serie Entidad', size=3, required=True)
    serie_emision = fields.Char('Serie Emision', size=3, required=True)
    num_start = fields.Integer('Desde', required=True)
    num_end = fields.Integer('Hasta', required=True)
    is_electronic = fields.Boolean('Factura Electronica')
    expiration_date = fields.Date('Vence', required=True)
    active = fields.Boolean('Activo')
    in_type = fields.Selection([
            ('interno', 'Internas'),
            ('externo', 'Externas'),
            ], 'Tipo Interno', readonly=True)
    type_ = fields.Many2One('account.ats.doc', 'Tipo de Comprobante',
            required=True)
    company = fields.Many2One('company.company', 'Company', required=True)


class Journal:
    __name__ = 'account.journal'
    auth_id = fields.Many2One('account.authorization', 'Autorizacion',
            help='Autorizacion utilizada para Facturas y Liquidaciones de Compra')
    auth_ret_id = fields.Many2One('account.authorization','Autorizacion de Ret.',
            help='Autorizacion utilizada para Retenciones, facturas y liquidaciones')


class ATSStart(ModelView):
    'Print ATS'
    __name__ = 'account_plus_ec.print_ats.start'
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
        required=True)
    periods = fields.Many2Many('account.period', None, None, 'Periods',
        domain=[('fiscalyear', '=', Eval('fiscalyear'))],
        help='Leave empty for all periods of fiscal year')


class PrintATS(Wizard):
    'Print ATS'
    __name__ = 'account_plus_ec.print_ats'
    start = StateView('account_plus_ec.print_ats.start',
        'account_plus_ec.print_ats_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-ok', default=True),
            ])
    print_ = StateAction('account_plus_ec.report_ats')

    def do_print_(self, action):
        data = {
            'fiscalyear': self.start.fiscalyear.id,
            'periods': self.start.periods,
            }
        return action, data

    def transition_print_(self):
        return 'end'


class ATS(Report):
    __name__ = 'account_plus_ec.ats'

    @classmethod
    def parse(cls, report, objects, data, localcontext):
        pool = Pool()
        Account = pool.get('account.move')
        Period = pool.get('account.period')
        Company = pool.get('company.company')
        #localcontext['company'] = company
        return super(AuxiliaryBook, cls).parse(report, objects, data,
            localcontext)
