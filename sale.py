#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.company import CompanyReport

__all__ = ['ReferenceGuide', 'SaleReport']
__metaclass__ = PoolMeta


class ReferenceGuide(CompanyReport):
    'Reference Guide'
    __name__ = 'sale.reference_guide'

    @classmethod
    def __setup__(cls):
        super(ReferenceGuide, cls).__setup__()


class SaleReport:
    __name__ = 'sale.sale'

    @classmethod
    def parse(cls, report, objects, data, localcontext):
        for obj in objects:
            untaxed_food = 0
            untaxed_education = 0
            untaxed_clothes = 0
            untaxed_health = 0
            for line in obj.lines:
                if line.product.kind == 'food':
                    untaxed_food += line.amount
                elif line.product.kind == 'education':
                    untaxed_education += line.amount
                elif line.product.kind == 'clothes':
                    untaxed_clothes += line.amount
                elif line.product.kind == 'health':
                    untaxed_health += line.amount
                else:
                    continue
            setattr(obj, 'untaxed_food', untaxed_food)
            setattr(obj, 'untaxed_education', untaxed_education)
            setattr(obj, 'untaxed_clothes', untaxed_clothes)
            setattr(obj, 'untaxed_health', untaxed_health)

        return super(SaleReport, cls).parse(report, objects, data,
            localcontext)
