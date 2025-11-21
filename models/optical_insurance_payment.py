# -*- coding: utf-8 -*-
# Part of BP Optical POS. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class OpticalInsurancePayment(models.Model):
    _name = "optical.insurance.payment"
    _description = "Optical Insurance Payment Record"
    _order = "create_date desc"

    order_id = fields.Many2one(
        "pos.order",
        string="POS Order",
        required=True,
        ondelete="cascade"
    )
    payment_id = fields.Many2one(
        "pos.payment",
        string="POS Payment",
        ondelete="set null"
    )
    invoice_id = fields.Many2one(
        "account.move",
        string="Invoice",
        ondelete="set null"
    )
    
    insurance_company_id = fields.Many2one(
        "optical.insurance.company",
        string="Insurance Company",
        required=True
    )
    policy_number = fields.Char(string="Policy Number")
    member_number = fields.Char(string="Member Number")
    employer = fields.Char(string="Employer / Corporate")
    notes = fields.Text(string="Notes")
    
    amount = fields.Float(
        string="Insurance Amount",
        required=True,
        help="Amount covered by insurance for this payment"
    )
    
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="order_id.company_id",
        store=True,
        readonly=True
    )
