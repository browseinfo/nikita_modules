# -*- coding: utf-8 -*-
##############################################################################
#
#    Author: Guewen Baconnier
#    Copyright 2013 Camptocamp SA
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


class StockReservation(models.Model):
    _inherit = 'stock.reservation'

    sale_line_id = fields.Many2one(
        'sale.order.line',
        string='Sale Order Line',
        ondelete='cascade',
        copy=False)
    sale_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        related='sale_line_id.order_id')
    default_start_date = fields.Date(string='Default Start Date')
    default_end_date = fields.Date(string='Default End Date')

    @api.multi
    def release(self):
        for rec in self:
            rec.sale_line_id = False
        return super(StockReservation, self).release()

    @api.model
    def release_exceeded(self, ids=None):
        """ Release all the reservation having an exceeded validity date """
        domain = [('date_validity', '<', fields.date.today()),
                  ('state', '=', 'assigned')]
        if ids:
            domain.append(('id', 'in', ids))
        nonvalidated_reserve_ids = self.search(domain)
        nonvalidated_reserve_ids.release()

        reserve_domain = [('default_start_date', '=', fields.date.today()),
                  ('has_stock_reservation', '=', False)]
        to_reserve_ids = self.env['sale.order'].search(reserve_domain)
        default_fields = ['location_id', 'location_dest_id', 'default_start_date', 'default_end_date']
        for reserve_id in to_reserve_ids:
            wizard_obj = self.env['sale.stock.reserve'].with_context(active_model='sale.order', active_id=reserve_id.id
                                                                     , active_ids=[reserve_id.id])
            defaults = wizard_obj.default_get(default_fields)
            wizard_id=wizard_obj.create(defaults)
            wizard_id.button_reserve()

        release_domain = [('default_end_date', '<', fields.date.today()),
                  ('state', '=', 'assigned')]
        to_release_ids = self.search(release_domain)
        to_release_ids.release()
        return True

