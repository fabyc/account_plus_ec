#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.company import CompanyReport

__all__ = ['ReferenceGuide']
__metaclass__ = PoolMeta


class ReferenceGuide(CompanyReport):
    'Reference Guide'
    __name__ = 'sale.reference_guide'

    @classmethod
    def __setup__(cls):
        super(ReferenceGuide, cls).__setup__()
