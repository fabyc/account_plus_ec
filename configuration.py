#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta

__all__ = ['Configuration']

__metaclass__ = PoolMeta

class Configuration:
    'Account Configuration'
    __name__ = 'account.configuration'
    resolution = fields.Char('Resolution')
