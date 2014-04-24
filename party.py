#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta
from trytond.model import fields
from trytond.pyson import Eval

__all__ = ['Party', 'BankAccountNumber']
__metaclass__ = PoolMeta

PRIMOS = [71,67,59,53,47,43,41,37,29,23,19,17,13,7,3]
K = 11

STATES_NAME = {
    'invisible': (Eval('regime_tax') not in (
        'regimen_simplificado', 'regimen_comun', 'persona_natural',
))}


class Party:
    __name__ = 'party.party'
    vat_number_city = fields.Char('VAT Number City', states={
            'invisible': (Eval('regime_tax') != 'persona_natural'),
            })
    type_document = fields.Selection([
            ('11', 'Registro Civil de Nacimiento'),
            ('12', 'Tarjeta de Identidad'),
            ('13', 'Cedula de Ciudadania'),
            ('21', 'Tarjeta de Extranjeria'),
            ('22', 'Cedula de Extranjeria'),
            ('31', 'NIT'),
            ('41', 'Pasaporte'),
            ('42', 'Tipo de Documento Extranjero'),
            ('43', 'Sin identificacion del Exterior o para uso definido por la DIAN'),
            ('', ''),
            ], 'Type Document') 
    regime_tax = fields.Selection([
            ('', ''),
            ('autoretenedor', 'Autoretenedor'),
            ('persona_natural', 'Persona Natural'),
            ('regimen_simplificado', 'Regimen Simplificado'),
            ('regimen_comun', 'Regimen Comun'),
            ('gran_contribuyente', 'Gran Contribuyente'),
            ('entidad_estatal', 'Entidad Estatal'),
            ('domiciliado_extranjero', 'Domiciliado en Extranjero'),
            ], 'Regimen de Impuestos')
    check_digit = fields.Function(fields.Integer('DV'), 
            'get_check_digit')
    first_name = fields.Char('Primer Nombre', states=STATES_NAME)
    second_name = fields.Char('Segundo Nombre', states=STATES_NAME)
    first_family_name = fields.Char('Primer Apellido', states=STATES_NAME)
    second_family_name = fields.Char('Segundo Apellido', states=STATES_NAME)
    commercial_name = fields.Char('Commercial Name')

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls._error_messages.update({
                'invalid_vat_number': ('Invalid VAT Number "%s".')})
        cls._sql_constraints += [
            ('vat_number', 'UNIQUE(vat_number)',
                'VAT Number already exists!'),
        ]

    @classmethod
    def search_rec_name(cls, name, clause):
        parties = cls.search([
                ('vat_number',) + tuple(clause[1:]),
                ], limit=1)
        if parties:
            return [('vat_number',) + tuple(clause[1:])]
        return [('name',) + tuple(clause[1:])]

    def pre_validate(self):
        if not self.vat_number:
            return
        vat_number = self.vat_number.replace(".", "")
        if not vat_number.isdigit():
            self.raise_user_error('invalid_vat_number', (self.vat_number,))
            return

    def get_check_digit(self, name):
        if not self.vat_number or self.type_document != '31':
            return None
        vat_number = self.vat_number.replace(".", "")
        if not vat_number.isdigit():
            return None
        c = 0
        p = len(PRIMOS)-1
        for n in reversed(vat_number):
            c += int(n) * PRIMOS[p]
            p -= 1

        dv = c % 11
        if dv > 1:
            dv = 11 - dv
        return dv


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
