# -*- coding: utf-8 -*-
# Part of BP Optical POS. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"
    
    is_insurance_method = fields.Boolean(
        string="Insurance Payment Method",
        default=False,
        help="When enabled, this payment method will trigger insurance info collection for POS orders."
    )
