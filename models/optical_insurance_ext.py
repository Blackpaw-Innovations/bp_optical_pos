# -*- coding: utf-8 -*-
# Part of BP Optical POS. See LICENSE file for full copyright and licensing details.

from odoo import models, fields

# Fields and logic moved to bp_optical_core/models/optical_config.py
class OpticalInsuranceCompany(models.Model):
    _inherit = "optical.insurance.company"
    pass
