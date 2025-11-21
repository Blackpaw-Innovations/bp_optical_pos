# -*- coding: utf-8 -*-
# Part of BP Optical POS. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class OpticalBranchPLWizard(models.TransientModel):
    _name = "optical.branch.pl.wizard"
    _description = "Branch Profit & Loss Report Wizard"

    date_from = fields.Date(string="Start Date", required=True, default=lambda self: fields.Date.context_today(self).replace(day=1))
    date_to = fields.Date(string="End Date", required=True, default=fields.Date.context_today)
    branch_ids = fields.Many2many("optical.branch", string="Branches", required=True)
    target_move = fields.Selection([('posted', 'Posted Entries'), ('all', 'All Entries')], string="Target Moves", default='posted')

    def action_print_report(self):
        self.ensure_one()
        data = {
            'ids': self.ids,
            'model': self._name,
            'form': {
                'date_from': self.date_from,
                'date_to': self.date_to,
                'branch_ids': self.branch_ids.ids,
                'target_move': self.target_move,
            },
        }
        return self.env.ref('bp_optical_pos.action_report_optical_branch_pl').report_action(self, data=data)

class ReportOpticalBranchPL(models.AbstractModel):
    _name = "report.bp_optical_pos.report_optical_branch_pl"
    _description = "Branch Profit & Loss Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        if not data.get('form'):
            raise UserError(_("Form content is missing, this report cannot be printed."))

        date_from = data['form']['date_from']
        date_to = data['form']['date_to']
        branch_ids = data['form']['branch_ids']
        target_move = data['form']['target_move']

        branches = self.env['optical.branch'].browse(branch_ids)
        analytic_accounts = branches.mapped('analytic_account_id')

        if not analytic_accounts:
            raise UserError(_("The selected branches do not have Analytic Accounts configured."))

        # Prepare domain
        domain = [
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('analytic_distribution', '!=', False), # Optimization: only lines with analytic distribution
            ('account_id.account_type', 'in', ('income', 'income_other', 'expense', 'expense_depreciation', 'expense_direct_cost')),
        ]
        
        if target_move == 'posted':
            domain.append(('parent_state', '=', 'posted'))

        # Fetch lines
        move_lines = self.env['account.move.line'].search(domain)

        # Filter by analytic account manually (since analytic_distribution is a JSON)
        # We need to check if any of our analytic accounts are in the distribution
        filtered_lines = self.env['account.move.line']
        analytic_account_ids_str = [str(aid) for aid in analytic_accounts.ids]
        
        for line in move_lines:
            if line.analytic_distribution:
                # Check if any of the keys in analytic_distribution match our accounts
                if any(aid in line.analytic_distribution for aid in analytic_account_ids_str):
                    filtered_lines += line

        # Aggregate data
        income_lines = []
        expense_lines = []
        total_income = 0.0
        total_expense = 0.0

        # Group by account
        account_totals = {}
        for line in filtered_lines:
            account = line.account_id
            # For P&L: Credit - Debit (Income is usually Credit, Expense is Debit)
            # But standard Odoo stores Debit as positive, Credit as negative in signed_amount?
            # Actually balance = debit - credit.
            # Income: usually Credit balance (negative). We want to show it as positive.
            # Expense: usually Debit balance (positive).
            
            balance = line.balance # debit - credit
            
            if account not in account_totals:
                account_totals[account] = 0.0
            account_totals[account] += balance

        for account, balance in account_totals.items():
            # Invert balance for Income to show as positive
            if account.account_type in ('income', 'income_other'):
                amount = -balance
                total_income += amount
                income_lines.append({'name': account.name, 'code': account.code, 'amount': amount})
            else:
                amount = balance
                total_expense += amount
                expense_lines.append({'name': account.name, 'code': account.code, 'amount': amount})

        return {
            'doc_ids': docids,
            'doc_model': 'optical.branch.pl.wizard',
            'date_from': date_from,
            'date_to': date_to,
            'branches': branches,
            'income_lines': sorted(income_lines, key=lambda x: x['code']),
            'expense_lines': sorted(expense_lines, key=lambda x: x['code']),
            'total_income': total_income,
            'total_expense': total_expense,
            'net_profit': total_income - total_expense,
            'company': self.env.company,
        }
