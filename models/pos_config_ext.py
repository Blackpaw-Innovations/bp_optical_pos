# -*- coding: utf-8 -*-
# Part of BP Optical POS. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class PosConfig(models.Model):
    _inherit = "pos.config"
    
    optical_enabled = fields.Boolean(
        string="Enable Optical Features",
        help="If enabled, this POS configuration will activate optical-specific features such as optical tests, insurance split, and branch analytics."
    )
    
    optical_branch_id = fields.Many2one(
        "optical.branch",
        string="Optical Branch",
        help="Link this POS configuration to an Optical Branch from bp_optical_core."
    )
    
    optical_force_invoice = fields.Boolean(
        string="Always Create Invoice",
        default=True,
        help="If enabled, any order with a customer will always generate an invoice automatically."
    )
    
    optical_require_customer = fields.Boolean(
        string="Require Customer for Orders",
        default=True,
        help="If enabled, POS orders must have a customer set before they can be validated."
    )
    
    optical_insurance_journal_id = fields.Many2one(
        "account.journal",
        string="Default Insurance Journal",
        domain="[('type', '=', 'sale')]",
        help="Journal used for Invoices when the order includes Insurance payments."
    )

