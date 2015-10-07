# -*- encoding: utf-8 -*-
##############################################################################
#
#    PnP Sale Rental module for Odoo
#    Copyright (C) 2015 Pnp Hi-Tech Solutions
#    @author Alexis de Lattre <alexis.delattre@akretion.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp import models, fields, api


class CreateRentalProduct(models.TransientModel):
    _inherit = 'create.rental.product'

    def _default_rental_categ(self):
        assert self.env.context.get('active_model') == 'product.product',\
            'Wrong underlying model, should be product.product'
        product = self.env['product.product'].browse(
            self.env.context.get('active_id'))
        return product and product.categ_id.id or False

    categ_id = fields.Many2one(default=_default_rental_categ)


class StockChangeProductQty(models.TransientModel):
    _inherit = 'stock.change.product.qty'

    @api.model
    def default_get(self, fields):
        res = super(StockChangeProductQty, self).default_get(fields)
        if 'location_id' in fields:
            whs = self.env['stock.warehouse'].search(
                [('company_id', '=', self._uid)])
            wh1 = whs and whs[0] or None
            res['location_id'] = wh1 and wh1.rental_in_location_id.id or False
        return res
