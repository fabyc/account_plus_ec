#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
#! -*- coding: utf8 -*-
from trytond.pool import PoolMeta
from trytond.model import fields
from trytond.pyson import Eval, Equal

__all__ = ['Party', 'BankAccountNumber']
__metaclass__ = PoolMeta


class Party:
    __name__ = 'party.party'
    vat_number_city = fields.Char('VAT Number City', states={
            'readonly': ~Eval('active', True)})
    type_document = fields.Selection([
                ('', ''),
                ('04', 'RUC'),
                ('05', 'Cedula'),
                ('06', 'Pasaporte'),
                ('07', 'Consumidor Final'),
            ], 'Type Document', states={
                'readonly': ~Eval('active', True),
                'required': Equal(Eval('vat_country'), 'EC'),
            },  depends=['active'])
    mandatory_accounting = fields.Selection([
            ('yes', 'Yes'),
            ('no', 'No'),
            ], 'Mandatory Accounting')
    first_name = fields.Char('Primer Nombre')
    second_name = fields.Char('Segundo Nombre')
    first_family_name = fields.Char('Primer Apellido')
    second_family_name = fields.Char('Segundo Apellido')
    commercial_name = fields.Char('Commercial Name')
    type_party = fields.Selection([
        ('', ''),
        ('sociedad', 'Sociedad'),
        ('persona_natural', 'Personal natural'),
        ('contribuyente_especial', 'Contribuyente especial'),
        ('entidad_publica', 'Entidad del sector publico'),
        ('companias_seguros', 'Companias de aseguros y reaseguros'),
        ], 'Type Party', required=False)
    registro_mercantil = fields.Char('Registro Mercantil', states={
            'readonly': ~Eval('active', True)})
    start_activities = fields.Date('Start Activities')

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls._error_messages.update({
                'invalid_vat_number': ('Invalid VAT Number "%s".')})
        cls._sql_constraints += [
            ('vat_number', 'UNIQUE(vat_number)',
                'VAT Number already exists!'),
        ]

    @staticmethod
    def default_vat_country():
        return 'EC'

    @classmethod
    def search_rec_name(cls, name, clause):
        parties = cls.search([
                ('vat_number',) + tuple(clause[1:]),
                ], limit=1)
        if parties:
            return [('vat_number',) + tuple(clause[1:])]
        return [('name',) + tuple(clause[1:])]

    @classmethod
    def validate(cls, parties):
        for party in parties:
            if party.type_document == '04' and bool(party.vat_number):
                super(Party, cls).validate(parties)

    def pre_validate(self):
        if not self.vat_number:
            return
        vat_number = self.vat_number.replace(".", "")

        if vat_number.isdigit() and len(self.vat_number) > 8:
            check_digit = self.vat_number[8]
            computed_check_digit = self.compute_check_digit(self.vat_number[:8])
            if computed_check_digit == int(check_digit):
                return
        self.raise_user_error('invalid_vat_number', (self.vat_number,))


    @classmethod
    def compute_check_digit(cls, number):
        "Compute the check digit - Modulus 11"
        factor = 2
        x = 0
        for n in reversed(number):
            x += int(n) * factor
            factor += 1
            if factor == 8:
                factor = 2
        return (11 - (x % 11))


class BankAccountNumber:
    __name__ = 'bank.account.number'

    @classmethod
    def __setup__(cls):
        super(BankAccountNumber, cls).__setup__()
        new_sel = [
            ('checking_account', 'Checking Account'),
            ('saving_account', 'Saving Account'),
        ]
        if new_sel not in cls.type.selection:
            cls.type.selection.extend(new_sel)
