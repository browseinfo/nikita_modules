# -*- encoding: utf-8 -*-
##############################################################################
#
#    Account Cut-off Prepaid module for OpenERP
#    Copyright (C) 2013 Akretion (http://www.akretion.com)
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


from openerp.osv import orm, fields
from openerp.tools.translate import _
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
from datetime import datetime


class account_cutoff(orm.Model):
    _inherit = 'account.cutoff'

    _columns = {
        'source_journal_ids': fields.many2many(
            'account.journal', id1='cutoff_id', id2='journal_id',
            string='Source Journals', readonly=True,
            states={'draft': [('readonly', False)]}),
        'forecast': fields.boolean(
            'Forecast',
            readonly=True, states={'draft': [('readonly', False)]},
            help="The Forecast mode allows the user to compute "
            "the prepaid revenue/expense between 2 dates in the future."),
        'start_date': fields.date('Start Date'),
        'end_date': fields.date('End Date'),
    }

    def _get_default_source_journals(self, cr, uid, context=None):
        if context is None:
            context = {}
        journal_obj = self.pool['account.journal']
        res = []
        type = context.get('type')
        mapping = {
            'prepaid_expense': ('purchase', 'purchase_refund'),
            'prepaid_revenue': ('sale', 'sale_refund'),
            }
        if type in mapping:
            src_journal_ids = journal_obj.search(
                cr, uid, [('type', 'in', mapping[type])])
            if src_journal_ids:
                res = src_journal_ids
        return res

    _defaults = {
        'source_journal_ids': _get_default_source_journals,
        }

    _sql_constraints = [(
        'date_type_forecast_company_uniq',
        'unique(cutoff_date, company_id, type, forecast, start_date, end_date)',
        'A cut-off of the same type already exists with the same date(s) !'
        )]

    def _check_start_end_dates(self, cr, uid, ids):
        for prepaid in self.browse(cr, uid, ids):
            if prepaid.forecast and prepaid.start_date and prepaid.end_date \
                    and prepaid.start_date > prepaid.end_date:
                return False
        return True

    _constraints = [
        (_check_start_end_dates, "The start date is after the end date!",
            ['start_date', 'end_date', 'forecast']),
    ]

    def forecast_onchange(self, cr, uid, ids, forecast, context=None):
        res = {'value': {}}
        line_ids = self.pool['account.cutoff.line'].search(
            cr, uid, [('parent_id', 'in', ids)], context=context)
        self.pool['account.cutoff.line'].unlink(
            cr, uid, line_ids, context=context)
        if forecast:
            res['value']['cutoff_date'] = False
        else:
            res['value']['start_date'] = False
            res['value']['end_date'] = False
        return res

    def _prepare_prepaid_lines(
            self, cr, uid, ids, aml, cur_cutoff, mapping, context=None):
        start_date = datetime.strptime(
            aml['start_date'], DEFAULT_SERVER_DATE_FORMAT)
        end_date = datetime.strptime(
            aml['end_date'], DEFAULT_SERVER_DATE_FORMAT)
        # Here, we compute the amount of the cutoff
        # That's the important part !
        total_days = (end_date - start_date).days + 1
        if cur_cutoff['forecast']:
            out_days = 0
            forecast_start_date = datetime.strptime(
                cur_cutoff['start_date'], DEFAULT_SERVER_DATE_FORMAT)
            forecast_end_date = datetime.strptime(
                cur_cutoff['end_date'], DEFAULT_SERVER_DATE_FORMAT)
            if aml['end_date'] > cur_cutoff['end_date']:
                out_days += (end_date - forecast_end_date).days
            if aml['start_date'] < cur_cutoff['start_date']:
                out_days += (forecast_start_date - start_date).days
            prepaid_days = total_days - out_days
        else:
            cutoff_date_str = cur_cutoff['cutoff_date']
            cutoff_date = datetime.strptime(
                cutoff_date_str, DEFAULT_SERVER_DATE_FORMAT)
            if aml['start_date'] > cutoff_date_str:
                prepaid_days = total_days
            else:
                prepaid_days = (end_date - cutoff_date).days
        if total_days:
            cutoff_amount = (aml['debit'] - aml['credit'])\
                * prepaid_days / float(total_days)
        else:
            raise orm.except_orm(
                _('Error:'),
                "Should never happen. Total days should always be > 0")

        # we use account mapping here
        if aml['account_id'][0] in mapping:
            cutoff_account_id = mapping[aml['account_id'][0]]
        else:
            cutoff_account_id = aml['account_id'][0]

        res = {
            'parent_id': ids[0],
            'move_line_id': aml['id'],
            'partner_id': aml['partner_id'] and aml['partner_id'][0] or False,
            'name': aml['name'],
            'start_date': aml['start_date'],
            'end_date': aml['end_date'],
            'account_id': aml['account_id'][0],
            'cutoff_account_id': cutoff_account_id,
            'analytic_account_id':
            aml['analytic_account_id'] and aml['analytic_account_id'][0]
            or False,
            'total_days': total_days,
            'prepaid_days': prepaid_days,
            'amount': aml['credit'] - aml['debit'],
            'currency_id': cur_cutoff['company_currency_id'][0],
            'cutoff_amount': cutoff_amount,
            }
        return res

    def get_prepaid_lines(self, cr, uid, ids, context=None):
        assert len(ids) == 1,\
            'This function should only be used for a single id at a time'
        aml_obj = self.pool['account.move.line']
        line_obj = self.pool['account.cutoff.line']
        mapping_obj = self.pool['account.cutoff.mapping']
        cur_cutoff = self.read(
            cr, uid, ids[0], [
                'line_ids', 'source_journal_ids', 'cutoff_date', 'company_id',
                'type', 'company_currency_id', 'forecast', 'start_date',
                'end_date',
                ],
            context=context)
        src_journal_ids = cur_cutoff['source_journal_ids']
        if not src_journal_ids:
            raise orm.except_orm(
                _('Error:'), _("You should set at least one Source Journal."))
        cutoff_date_str = cur_cutoff['cutoff_date']
        # Delete existing lines
        if cur_cutoff['line_ids']:
            line_obj.unlink(cr, uid, cur_cutoff['line_ids'], context=context)

        if cur_cutoff['forecast']:
            domain = [
                ('start_date', '<=', cur_cutoff['end_date']),
                ('end_date', '>=', cur_cutoff['start_date']),
                ('journal_id', 'in', src_journal_ids)
                ]
        else:
            domain = [
                ('start_date', '!=', False),
                ('journal_id', 'in', src_journal_ids),
                ('end_date', '>', cutoff_date_str),
                ('date', '<=', cutoff_date_str)
                ]

        # Search for account move lines in the source journals
        aml_ids = aml_obj.search(cr, uid, domain, context=context)
        # Create mapping dict
        mapping = mapping_obj._get_mapping_dict(
            cr, uid, cur_cutoff['company_id'][0], cur_cutoff['type'],
            context=context)

        # Loop on selected account move lines to create the cutoff lines
        for aml in aml_obj.read(
                cr, uid, aml_ids, [
                    'credit', 'debit', 'start_date', 'end_date', 'account_id',
                    'analytic_account_id', 'partner_id', 'name'
                    ],
                context=context):

            line_obj.create(
                cr, uid, self._prepare_prepaid_lines(
                    cr, uid, ids, aml, cur_cutoff, mapping, context=context),
                context=context)
        return True

    def _inherit_default_cutoff_account_id(self, cr, uid, context=None):
        if context is None:
            context = {}
        account_id = super(account_cutoff, self).\
            _inherit_default_cutoff_account_id(cr, uid, context=context)
        type = context.get('type')
        company = self.pool['res.users'].browse(
            cr, uid, uid, context=context).company_id
        if type == 'prepaid_revenue':
            account_id = company.default_prepaid_revenue_account_id.id or False
        elif type == 'prepaid_expense':
            account_id = company.default_prepaid_expense_account_id.id or False
        return account_id


class account_cutoff_line(orm.Model):
    _inherit = 'account.cutoff.line'

    _columns = {
        'move_line_id': fields.many2one(
            'account.move.line', 'Accout Move Line', readonly=True),
        'move_date': fields.related(
            'move_line_id', 'date', type='date',
            string='Account Move Date', readonly=True),
        'invoice_id': fields.related(
            'move_line_id', 'invoice', type='many2one',
            relation='account.invoice', string='Invoice', readonly=True),
        'start_date': fields.date('Start Date', readonly=True),
        'end_date': fields.date('End Date', readonly=True),
        'total_days': fields.integer('Total Number of Days', readonly=True),
        'prepaid_days': fields.integer(
            'Prepaid Days', readonly=True,
            help="In regular mode, this is the number of days after the "
            "cut-off date. In forecast mode, this is the number of days "
            "between the start date and the end date."),
        }
