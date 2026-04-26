# -*- coding: utf-8 -*-
###############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
from datetime import datetime, date, timedelta

from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)

class HrEmployeeDocument(models.Model):
    """Create a new module for retrieving document files, allowing users
     to input details about the documents."""
    _name = 'hr.employee.document'
    _description = 'HR Employee Documents'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Document Number', required=True, copy=False,
                       help="Enter Document Number")
    document_id = fields.Many2one('employee.checklist',
                                  string='Document',
                                  required=True,
                                  help="Choose Employee Checklist for"
                                       " Employee Document")
    description = fields.Text(string='Description', copy=False,
                              help="Description for Employee Document")
    expiry_date = fields.Date(string='Expiry Date', copy=False,
                              help="Choose Expiry Date for Employee Document")
    employee_id = fields.Many2one('hr.employee', copy=False, string="Employee",
                                  help="Choose Employee for Employee Document")
    doc_attachment_ids = fields.Many2many('ir.attachment',
                                          'doc_attach_ids',
                                          'doc_id', 'attach_id3',
                                          string="Attachment",
                                          help='You can attach the copy'
                                               'of your document',
                                          copy=False)
    issue_date = fields.Date(string='Issue Date',
                             default=fields.Date.context_today, copy=False,
                             help="Choose Issue Date for Employee Document")
    before_days = fields.Integer(string='Notify Before (Days)', copy=False,
                                 help='Number of days before expiry to start notifications. If empty defaults to 7.')
    notification_type = fields.Selection([
        ('single', 'Notification on expiry date'),
        ('multi', 'Notification before few days'),
        ('everyday', 'Everyday till expiry date'),
        ('everyday_after', 'Notification on and after expiry')
    ], string='Notification Type', default='multi', copy=False,
        help='Choose how notifications should be scheduled for this document.')

    def mail_reminder(self):
        """Cron executed method to post reminders / create activities.

        Notification logic per document based on notification_type:
          single: create only on expiry date.
          multi: once per day starting (expiry - before_days) until expiry.
          everyday: every day from today (if within window) up to expiry.
          everyday_after: on expiry date and every day after until renewed
                           (i.e., while still expired) for max 30 days.
        Activities are assigned to all users belonging to HR Officer
        (group_hr_user) and Employees Administrator (group_hr_manager).
        """
        today = date.today()
        _logger.info("Running document expiry check for %s", today)
        documents = self.search([('expiry_date', '!=', False)])
        # Pre-fetch partners in HR groups
        # hr_groups = self.env.ref('hr.group_hr_user'), self.env.ref('hr.group_hr_manager')
        hr_groups = self.env.ref('hr.group_hr_user')
        partner_ids = []
        for grp in hr_groups:
            partner_ids.extend(grp.users.mapped('partner_id.id'))
        partner_ids = list(set(filter(None, partner_ids)))
        _logger.debug("HR partners to notify: %s", partner_ids)
        Activity = self.env['mail.activity']
        for doc in documents:
            if not doc.expiry_date:
                continue
            _logger.debug("Checking document %s (expiry %s)", doc.name, doc.expiry_date)
            before_days = doc.before_days if doc.before_days else 7
            start_day = doc.expiry_date - timedelta(days=before_days)
            create_today = False
            if doc.notification_type == 'single':
                create_today = today == doc.expiry_date
            elif doc.notification_type == 'multi':
                create_today = start_day <= today <= doc.expiry_date
            elif doc.notification_type == 'everyday':
                create_today = today <= doc.expiry_date and today >= start_day
            elif doc.notification_type == 'everyday_after':
                # from expiry day and for 30 days after (or until replaced)
                create_today = today >= doc.expiry_date and today <= doc.expiry_date + timedelta(days=30)
            if not create_today:
                continue
            # Avoid duplicate activity for same day & document by checking existing
            existing = Activity.search([
                ('res_model', '=', doc._name),
                ('res_id', '=', doc.id),
                ('activity_type_id', '=', self.env.ref('mail.mail_activity_data_todo').id),
                ('date_deadline', '=', today),
            ])
            if existing:
                continue
            note = _("Document %s (%s) will expire on %s") % (doc.name, doc.document_id.name, doc.expiry_date)
            for pid in partner_ids:
                Activity.create({
                    'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                    'res_model_id': self.env['ir.model']._get_id(doc._name),
                    'res_id': doc.id,
                    'user_id': self.env['res.partner'].browse(pid).user_ids[:1].id,
                    'date_deadline': today,
                    'summary': _('Employee Document Expiry Reminder'),
                    'note': note,
                })
            # Optionally still send legacy email for backward compatibility
            if doc.employee_id and doc.employee_id.work_email:
                mail_content = ("Hello %s,<br/>Your Document %s will expire on %s. Please renew it before the expiry date." % (
                    doc.employee_id.name, doc.name, doc.expiry_date))
                main_content = {
                    'subject': _('Document-%s Expiring On %s') % (
                        doc.name, doc.expiry_date),
                    'author_id': self.env.user.partner_id.id,
                    'body_html': mail_content,
                    'email_to': doc.employee_id.work_email,
                }
                self.env['mail.mail'].create(main_content).send()

    @api.onchange('expiry_date')
    def check_expr_date(self):
        """Function to obtain a validation error for expired documents."""
        if self.expiry_date and self.expiry_date < date.today():
            return {
                'warning': {
                    'title': _('Document Expired.'),
                    'message': _("Your Document Is Already Expired.")
                }
            }
