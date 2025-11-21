# -*- coding: utf-8 -*-
# Part of BP Optical POS. See LICENSE file for full copyright and licensing details.

from odoo import models


class PosSession(models.Model):
    _inherit = "pos.session"
    
    def _loader_params_pos_payment_method(self):
        """Override to add is_insurance_method to loaded fields"""
        result = super()._loader_params_pos_payment_method()
        result['search_params']['fields'].append('is_insurance_method')
        return result
    
    def _loader_params_res_partner(self):
        """Override to add optical fields to partner loading"""
        result = super()._loader_params_res_partner()
        result['search_params']['fields'].extend([
            'date_of_birth',
            'is_optical_patient',
            'has_insurance',
            'insurance_company_id',
            'policy_number',
            'insurance_expiry_date',
            'patient_company',
            'insurance_invoice_number',
            'coverage_details',
        ])
        return result
    
    def _loader_params_optical_insurance_company(self):
        """Load insurance companies for optical POS"""
        return {
            'search_params': {
                'domain': [('active', '=', True)],
                'fields': ['id', 'name', 'code'],
                'order': 'name',
            },
        }
    
    def _get_pos_ui_optical_insurance_company(self, params):
        """Load insurance companies for POS UI"""
        return self.env['optical.insurance.company'].search_read(**params['search_params'])
    
    def _pos_data_process(self, loaded_data):
        """Override to add insurance companies to loaded data"""
        super()._pos_data_process(loaded_data)
        if self.config_id.optical_enabled:
            loaded_data['optical.insurance.company'] = self._get_pos_ui_optical_insurance_company(
                self._loader_params_optical_insurance_company()
            )
