# -*- coding: utf-8 -*-
# Part of BP Optical POS. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class PosPayment(models.Model):
    _inherit = "pos.payment"
    
    is_insurance = fields.Boolean(
        string="Is Insurance Payment",
        default=False,
        help="Indicates this payment is an insurance payment"
    )
    insurance_data_id = fields.Many2one(
        "optical.insurance.payment",
        string="Insurance Payment Details",
        ondelete="set null"
    )
