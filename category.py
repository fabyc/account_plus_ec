#This file is part product_barcode module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta

__all__ = ['Category']
__metaclass__ = PoolMeta


class Category:
    'Category'
    __name__ = 'product.category'
    kind = fields.Selection([
            ('', ''),
            ('food', 'Food'),
            ('health', 'Health'),
            ('clothes', 'Clothes'),
            ('education', 'Education'),
            ('home', 'Home'),
            ], 'Kind')

    @classmethod
    def __setup__(cls):
        super(Category, cls).__setup__()
