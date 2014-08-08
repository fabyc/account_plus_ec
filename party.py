#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
#! -*- coding: utf8 -*-
from trytond.pool import PoolMeta
from trytond.model import fields
from trytond.pyson import Eval, Equal

__all__ = ['Party', 'BankAccountNumber', 'Address', 'Company']
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
            ], 'Mandatory Accounting', required=False)
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

    @staticmethod
    def default_mandatory_accounting():
        return 'no'

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

        if vat_number.isdigit() and len(vat_number) > 9:
            is_valid = self.compute_check_digit(vat_number)
            if is_valid:
                return
        self.raise_user_error('invalid_vat_number', (self.vat_number,))

    def compute_check_digit(self, raw_number):
        "Compute the check digit - Modulus 10 y 11"
        factor = 2
        x = 0
        set_check_digit = None
        if self.type_party == 'persona_natural' or self.type_document == '05':
            cond1 = (self.type_document != '05' and len(raw_number) != 13)
            cond2 = (self.type_party == 'persona_natural' and int(raw_number[2]) > 5)
            if cond1 or cond2:
                return
            number = raw_number[:9]
            set_check_digit = raw_number[9]
            for n in number:
                y = int(n) * factor
                if y >= 10:
                    y = int(str(y)[0]) + int(str(y)[1])
                x += y
                if factor == 2:
                    factor = 1
                else:
                    factor = 2
            res = (x % 10)
            if res ==  0:
                value = 0
            else:
                value = 10 - (x % 10)
        elif self.type_party == 'entidad_publica':
            if not len(raw_number) == 13 or raw_number[2] != '6':
                return
            number = raw_number[:8]
            set_check_digit = raw_number[8]
            for n in reversed(number):
                x += int(n) * factor
                factor += 1
                if factor == 8:
                    factor = 2
            value = 11 - (x % 11)
            if value == 11:
                value = 0
        else:
            if len(raw_number) != 13 or \
                (self.type_party in ['sociedad', 'companias_seguros'] \
                and int(raw_number[2]) != 9) or raw_number[-3:] != '001':
                return
            number = raw_number[:9]
            set_check_digit = raw_number[9]
            for n in reversed(number):
                x += int(n) * factor
                factor += 1
                if factor == 8:
                    factor = 2
            value = 11 - (x % 11)
            if value == 11:
                value = 0

        return (set_check_digit == str(value))


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


class Address:
    __name__ = 'party.address'

    @staticmethod
    def default_country():
        return 'EC'


class Company:
    __name__ = 'company.company'
    sms_url = fields.Char('SMS Url')
    sms_active = fields.Boolean('SMS Active')
