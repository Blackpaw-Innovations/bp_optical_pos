# -*- coding: utf-8 -*-
# Part of BP Optical POS. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class StockLocation(models.Model):
    _inherit = "stock.location"

    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Analytic Account (POS Invoices)",
        help="If set, invoices created from POS using this location will have this analytic account applied to their invoice lines."
    )
