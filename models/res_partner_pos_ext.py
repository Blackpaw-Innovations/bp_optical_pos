# -*- coding: utf-8 -*-
# Part of BP Optical POS. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ResPartnerPosExt(models.Model):
    _inherit = "res.partner"

    # Computed fields for POS loading
    is_optical_patient = fields.Boolean(
        string='Is Optical Patient',
        compute='_compute_is_optical_patient',
        store=False,
    )
    has_insurance = fields.Boolean(
        string='Has Insurance',
        compute='_compute_insurance_fields',
        store=False,
    )
    insurance_company_id = fields.Many2one(
        'optical.insurance.company',
        string='Insurance Company',
        compute='_compute_insurance_fields',
        store=False,
    )
    policy_number = fields.Char(
        string='Policy Number',
        compute='_compute_insurance_fields',
        store=False,
    )
    insurance_expiry_date = fields.Date(
        string='Insurance Expiry Date',
        compute='_compute_insurance_fields',
        store=False,
    )
    patient_company = fields.Char(
        string='Patient Company',
        compute='_compute_insurance_fields',
        store=False,
    )
    insurance_invoice_number = fields.Char(
        string='Insurance Invoice Number',
        compute='_compute_insurance_fields',
        store=False,
    )
    coverage_details = fields.Text(
        string='Coverage Details',
        compute='_compute_insurance_fields',
        store=False,
    )

    @api.depends()
    def _compute_is_optical_patient(self):
        """Check if partner is linked to an optical.patient record"""
        for partner in self:
            partner.is_optical_patient = bool(
                self.env['optical.patient'].search([
                    ('partner_id', '=', partner.id)
                ], limit=1)
            )

    @api.depends()
    def _compute_insurance_fields(self):
        """Compute insurance fields from optical.patient.insurance records"""
        for partner in self:
            # Default values
            partner.has_insurance = False
            partner.insurance_company_id = False
            partner.policy_number = False
            partner.insurance_expiry_date = False
            partner.patient_company = False
            partner.insurance_invoice_number = False
            partner.coverage_details = False
            
            # Find active insurance for this patient
            insurance = self.env['optical.patient.insurance'].search([
                ('patient_id', '=', partner.id),
                ('active', '=', True),
            ], limit=1, order='date desc')
            
            if insurance:
                partner.has_insurance = True
                partner.insurance_company_id = insurance.insurance_company_id
                partner.policy_number = insurance.name
                partner.insurance_expiry_date = insurance.expiry_date
                partner.patient_company = insurance.patient_company_id or False
                partner.insurance_invoice_number = insurance.invoice_number
                partner.coverage_details = insurance.coverage_details

    @api.model
    def create_from_ui(self, partner):
        """
        Override POS UI partner creation to create optical.patient for optical POS.
        This method is called from POS when creating/editing partners.
        """
        _logger.info('[BP Optical POS] create_from_ui called for: %s', partner.get('name'))
        
        # Handle image data (standard POS logic)
        if partner.get('image_1920'):
            partner['image_1920'] = partner['image_1920'].split(',')[1]
        
        partner_id = partner.pop('id', False)
        
        if partner_id:
            # Modifying existing partner - filter out optical-specific fields
            _logger.info('[BP Optical POS] Updating existing partner %s', partner_id)
            
            # Remove optical-specific fields that don't exist on res.partner
            optical_fields = [
                'has_insurance', 'insurance_company_id', 'policy_number',
                'insurance_expiry_date', 'patient_company', 'insurance_invoice_number',
                'coverage_details', 'document', 'document_name', 'insuranceData'
            ]
            for field in optical_fields:
                partner.pop(field, None)
            
            # Update partner with remaining fields
            if partner:  # Only update if there are fields left
                self.browse(partner_id).write(partner)
            
            return partner_id
        
        # Clean up empty date_of_birth before processing
        if 'date_of_birth' in partner and not partner['date_of_birth']:
            partner['date_of_birth'] = False
        
        # Creating NEW partner - check if optical POS
        pos_session = self.env['pos.session'].search([
            ('state', '=', 'opened'),
            ('user_id', '=', self.env.uid)
        ], limit=1)
        
        is_optical_pos = pos_session and pos_session.config_id.optical_enabled
        
        _logger.info('[BP Optical POS] Creating new partner, optical POS: %s', is_optical_pos)
        
        if not is_optical_pos:
            # Not optical POS - use standard creation
            partner_id = self.create(partner).id
            return partner_id
        
        # OPTICAL POS: Create optical.patient instead
        _logger.info('[BP Optical POS] Creating optical.patient for: %s', partner.get('name'))
        
        # Extract optical insurance fields
        insurance_company_id = partner.pop('insurance_company_id', None)
        policy_number = partner.pop('policy_number', None)
        insurance_expiry_date = partner.pop('insurance_expiry_date', None)
        patient_company = partner.pop('patient_company', None)
        insurance_invoice_number = partner.pop('insurance_invoice_number', None)
        coverage_details = partner.pop('coverage_details', None)
        
        # Prepare optical.patient values
        date_of_birth = partner.get('date_of_birth')
        if not date_of_birth or date_of_birth == '':
            date_of_birth = fields.Date.today()
            
        patient_vals = {
            'name': partner.get('name'),
            'phone': partner.get('phone', ''),
            'mobile': partner.get('mobile', ''),
            'email': partner.get('email', ''),
            'date_of_birth': date_of_birth,
            'branch_id': pos_session.config_id.optical_branch_id.id if pos_session.config_id.optical_branch_id else False,
            'has_insurance': bool(insurance_company_id and policy_number),
        }
        
        # Validate and fix required fields
        if not patient_vals['email']:
            patient_vals['email'] = f"{partner.get('name', 'patient').replace(' ', '_').lower()}@pos.local"
            _logger.info('[BP Optical POS] Auto-generated email: %s', patient_vals['email'])
        
        if not patient_vals['phone']:
            patient_vals['phone'] = partner.get('mobile', 'N/A')
        
        if not patient_vals['branch_id']:
            default_branch = self.env['optical.branch'].search([], limit=1)
            if default_branch:
                patient_vals['branch_id'] = default_branch.id
                _logger.info('[BP Optical POS] Using default branch: %s', default_branch.name)
            else:
                _logger.error('[BP Optical POS] No branch available, falling back to standard partner')
                return self.create(partner).id
        
        try:
            # Create optical.patient (auto-creates and links res.partner)
            _logger.info('[BP Optical POS] Creating optical.patient record...')
            optical_patient = self.env['optical.patient'].create(patient_vals)
            partner_id = optical_patient.partner_id.id
            _logger.info('[BP Optical POS] Success! Optical patient ID: %s, Partner ID: %s', 
                       optical_patient.id, partner_id)
            
            # Create insurance if provided
            if insurance_company_id and policy_number:
                _logger.info('[BP Optical POS] Creating insurance record')
                insurance_vals = {
                    'patient_id': partner_id,
                    'insurance_company_id': int(insurance_company_id),
                    'name': policy_number,
                    'date': fields.Date.today(),
                    'active': True,
                }
                
                if insurance_expiry_date:
                    insurance_vals['expiry_date'] = insurance_expiry_date
                if patient_company:
                    insurance_vals['patient_company_id'] = patient_company
                if insurance_invoice_number:
                    insurance_vals['invoice_number'] = insurance_invoice_number
                if coverage_details:
                    insurance_vals['coverage_details'] = coverage_details
                
                self.env['optical.patient.insurance'].create(insurance_vals)
                _logger.info('[BP Optical POS] Insurance created')
            
            return partner_id
            
        except Exception as e:
            _logger.error('[BP Optical POS] Failed to create optical patient: %s', str(e), exc_info=True)
            # Fallback to standard partner creation
            return self.create(partner).id
