# -*- coding: utf-8 -*-
# Part of BP Optical POS. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = "account.move"
    
    is_insurance_invoice = fields.Boolean(
        string="Insurance Invoice",
        default=False,
        help="Indicates this invoice was created through insurance payment method"
    )
    associated_patient = fields.Many2one(
        "res.partner",
        string="Associated Patient",
        help="The actual customer/patient for this insurance invoice"
    )
    associated_patient_name = fields.Char(
        related="associated_patient.name",
        string="Patient Name",
        readonly=True,
        store=True
    )

    # New fields for Insurance Invoice handling
    paying_with_insurance = fields.Boolean(
        string="Paying with Insurance",
        default=False,
        help="Toggle to indicate if this invoice is being paid via insurance."
    )
    
    patient_has_insurance = fields.Boolean(
        string="Patient Has Insurance",
        compute="_compute_patient_has_insurance",
        store=False,
        help="Technical field to control visibility of the insurance toggle."
    )
    
    insurance_payment_ids = fields.One2many(
        "optical.insurance.payment",
        "invoice_id",
        string="Insurance Payments",
        help="Insurance payment details associated with this invoice."
    )
    
    branch_id = fields.Many2one(
        "optical.branch",
        string="Branch",
        help="The branch where this invoice was created."
    )
    
    insurance_company_id = fields.Many2one(
        "optical.insurance.company",
        string="Insurance Company",
        compute="_compute_insurance_company",
        store=True,
        help="The insurance company associated with this invoice."
    )

    @api.depends('insurance_payment_ids', 'insurance_payment_ids.insurance_company_id')
    def _compute_insurance_company(self):
        for move in self:
            # Take the first insurance payment's company if available
            # In most cases there should be only one insurance company per invoice
            if move.insurance_payment_ids:
                move.insurance_company_id = move.insurance_payment_ids[0].insurance_company_id
            else:
                move.insurance_company_id = False

    @api.depends('partner_id')
    def _compute_patient_has_insurance(self):
        """Check if the selected customer has any active insurance."""
        for move in self:
            move.patient_has_insurance = False
            if move.partner_id:
                # Check if partner has insurance (using the logic from res_partner_pos_ext)
                # We can check the optical.patient.insurance model directly
                insurance_count = self.env['optical.patient.insurance'].search_count([
                    ('patient_id', '=', move.partner_id.id),
                    ('active', '=', True)
                ])
                if insurance_count > 0:
                    move.patient_has_insurance = True
