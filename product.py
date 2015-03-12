#This file is part product_barcode module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta

__all__ = ['Product']
__metaclass__ = PoolMeta


class Product:
    'Product'
    __name__ = 'product.product'
    kind = fields.Selection([
            ('', ''),
            ('food', 'Food'),
            ('health', 'Health'),
            ('clothes', 'Clothes'),
            ('education', 'Education'),
            ], 'Kind')

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()
