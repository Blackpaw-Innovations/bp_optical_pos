# -*- coding: utf-8 -*-
# Part of BP Optical POS. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import AccessError

# Logic moved to bp_optical_core/models/optical_test.py
class OpticalTest(models.Model):
    _inherit = "optical.test"
    pass
