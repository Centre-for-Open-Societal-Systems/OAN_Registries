import base64
import io
import xlsxwriter
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date, timedelta


class G2PLivestockDashboard(models.TransientModel):
    _name = 'g2p.livestock.dashboard'
    _description = 'Livestock Registry Dashboard'

    # ------------------------------------------------------------------
    # Filter option lists
    # ------------------------------------------------------------------
    @api.model
    def get_filter_options(self):
        Registry = self.env['g2p.livestock.registry']
        Line = self.env['g2p.livestock.registry.line']

        regions = self.env['g2p.region'].search_read([], ['id', 'name'])
        woredas = self.env['g2p.woreda'].search_read([], ['id', 'name'])

        owners = Registry.search_read([('owner_id', '!=', False)], ['owner_id'])
        seen, owner_options = set(), []
        for r in owners:
            if r['owner_id'] and r['owner_id'][0] not in seen:
                seen.add(r['owner_id'][0])
                owner_options.append({'id': r['owner_id'][0], 'name': r['owner_id'][1]})

        # Updated: Get species from g2p.livestock.type
        species_records = self.env['g2p.livestock.type'].search([])
        species_options = [{'id': s.id, 'name': s.name} for s in species_records]

        return {
            'regions': regions,
            'woredas': woredas,
            'owners': owner_options,
            'species': species_options,
        }

    # ------------------------------------------------------------------
    # Build search domains from filters
    # ------------------------------------------------------------------
    def _build_domains(self, filters):
        filters = filters or {}
        reg_domain = []
        line_domain = []

        if filters.get('region_id'):
            reg_domain.append(('region_id', '=', filters['region_id']))
        if filters.get('woreda_id'):
            reg_domain.append(('woreda_id', '=', filters['woreda_id']))
        if filters.get('owner_id'):
            reg_domain.append(('owner_id', '=', filters['owner_id']))
        if filters.get('date_from'):
            reg_domain.append(('registration_date', '>=', filters['date_from']))
        if filters.get('date_to'):
            reg_domain.append(('registration_date', '<=', filters['date_to']))

        # Updated: Use species_id instead of species
        if filters.get('species'):
            line_domain.append(('species_id', '=', filters['species']))

        # Line-level filters via parent registry
        if reg_domain:
            matching_registries = self.env['g2p.livestock.registry'].search(reg_domain)
            line_domain.append(('registry_id', 'in', matching_registries.ids))

        return reg_domain, line_domain

    # ------------------------------------------------------------------
    # Main dashboard data
    # ------------------------------------------------------------------
    @api.model
    def get_dashboard_data(self, filters=None):
        Registry = self.env['g2p.livestock.registry']
        Line = self.env['g2p.livestock.registry.line']
        today = date.today()

        reg_domain, line_domain = self._build_domains(filters)

        all_reg = Registry.search(reg_domain)
        all_lines = Line.search(line_domain)

        total_registries = len(all_reg)
        total_animals = len(all_lines)

        verified = len(all_reg.filtered(lambda r: r.state == 'verified'))
        draft = len(all_reg.filtered(lambda r: r.state == 'draft'))
        archived = len(all_reg.filtered(lambda r: r.state == 'archived'))

        # ---- Health breakdown ----
        health = {
            'healthy': len(all_lines.filtered(lambda l: l.health_status == 'healthy')),
            'sick': len(all_lines.filtered(lambda l: l.health_status == 'sick')),
            'quarantined': len(all_lines.filtered(lambda l: l.health_status == 'quarantined')),
            'deceased': len(all_lines.filtered(lambda l: l.health_status == 'deceased')),
        }

        # ---- Vaccination breakdown ----
        vaccination = {
            'up_to_date': len(all_lines.filtered(lambda l: l.vaccination_status == 'up_to_date')),
            'overdue': len(all_lines.filtered(lambda l: l.vaccination_status == 'overdue')),
            'none': len(all_lines.filtered(lambda l: l.vaccination_status == 'none')),
        }

        # ---- Species breakdown (Updated) ----
        species_map = {}
        for line in all_lines:
            sp = line.species_id.name if line.species_id else 'Other'
            species_map[sp] = species_map.get(sp, 0) + 1

        species_breakdown = sorted(
            [{'label': k, 'count': v} for k, v in species_map.items()],
            key=lambda x: -x['count']
        )

        # ---- Region breakdown ----
        region_map = {}
        for reg in all_reg:
            region_name = reg.region_id.name if reg.region_id else 'Unknown'
            region_map[region_name] = region_map.get(region_name, 0) + 1

        region_breakdown = sorted(
            [{'label': k, 'count': v} for k, v in region_map.items()],
            key=lambda x: -x['count']
        )

        # ---- 12-month registration trend ----
        trend = []
        for i in range(11, -1, -1):
            month_start = (today.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
            if month_start.month == 12:
                month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                month_end = month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)

            count = len(all_reg.filtered(
                lambda r, ms=month_start, me=month_end:
                r.registration_date and ms <= r.registration_date <= me
            ))
            trend.append({'month': month_start.strftime('%b %Y'), 'count': count})

        # ---- Sync status ----
        sync = {
            'synced': len(all_reg.filtered(lambda r: r.sync_status == 'synced')),
            'pending': len(all_reg.filtered(lambda r: r.sync_status == 'pending')),
            'conflict': len(all_reg.filtered(lambda r: r.sync_status == 'conflict')),
            'failed': len(all_reg.filtered(lambda r: r.sync_status == 'failed')),
        }

        # ---- Source system breakdown ----
        source_map = {}
        for reg in all_reg:
            src = reg.source_system or 'manual'
            source_map[src] = source_map.get(src, 0) + 1
        source_breakdown = [{'label': k.upper(), 'count': v} for k, v in source_map.items()]

        # ---- Recent registrations (last 7 days) ----
        last_7 = today - timedelta(days=7)
        recent_records = all_reg.filtered(
            lambda r: r.registration_date and r.registration_date >= last_7
        ).sorted('registration_date', reverse=True)[:10]

        recent = [{
            'name': r.name,
            'owner': r.owner_id.name if r.owner_id else r.farmer_id or '-',
            'woreda': r.woreda_id.name if r.woreda_id else '-',
            'state': r.state,
            'date': r.registration_date.strftime('%d %b %Y') if r.registration_date else '-',
        } for r in recent_records]

        # ---- Alerts ----
        alerts = []
        if sync['conflict'] > 0:
            alerts.append({'type': 'danger', 'msg': f"{sync['conflict']} records have sync conflicts."})
        if sync['failed'] > 0:
            alerts.append({'type': 'danger', 'msg': f"{sync['failed']} records failed to sync."})
        if sync['pending'] > 0:
            alerts.append({'type': 'warning', 'msg': f"{sync['pending']} records pending sync."})
        if vaccination['overdue'] > 0:
            alerts.append({'type': 'warning', 'msg': f"{vaccination['overdue']} animals have overdue vaccinations."})
        if health['sick'] > 0:
            alerts.append({'type': 'danger', 'msg': f"{health['sick']} animals currently marked as Sick."})
        if health['quarantined'] > 0:
            alerts.append({'type': 'warning', 'msg': f"{health['quarantined']} animals in quarantine."})

        return {
            'total_registries': total_registries,
            'total_animals': total_animals,
            'verified': verified,
            'draft': draft,
            'archived': archived,
            'health': health,
            'vaccination': vaccination,
            'species_breakdown': species_breakdown,
            'region_breakdown': region_breakdown[:8],
            'trend': trend,
            'sync': sync,
            'source_breakdown': source_breakdown,
            'recent': recent,
            'alerts': alerts,
            'as_of': today.strftime('%d %b %Y'),
        }

    # ------------------------------------------------------------------
    # Excel Export
    # ------------------------------------------------------------------
    @api.model
    def action_export_report(self, filters=None):
        _, line_domain = self._build_domains(filters)
        lines = self.env['g2p.livestock.registry.line'].search(line_domain)

        if not lines:
            raise UserError(_("No records match the current filters — nothing to export."))

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Dashboard Export')
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})

        headers = [
            'Ear Tag', 'Species', 'Breed', 'Owner', 'Region', 'Woreda',
            'Health Status', 'Vaccination Status', 'Age', 'Registration Date',
        ]
        for col, title in enumerate(headers):
            sheet.write(0, col, title, header_format)

        for row, rec in enumerate(lines, start=1):
            reg = rec.registry_id
            sheet.write(row, 0, rec.ear_tag_id or '')
            sheet.write(row, 1, rec.species_id.name if rec.species_id else '')   # Updated
            sheet.write(row, 2, rec.breed or '')
            sheet.write(row, 3, rec.owner_id.name or '')
            sheet.write(row, 4, reg.region_id.name or '')
            sheet.write(row, 5, reg.woreda_id.name or '')
            sheet.write(row, 6, dict(rec._fields['health_status'].selection).get(rec.health_status, ''))
            sheet.write(row, 7, dict(rec._fields['vaccination_status'].selection).get(rec.vaccination_status, ''))
            sheet.write(row, 8, rec.age or '')
            sheet.write(row, 9, str(rec.registration_date or ''))

        workbook.close()
        output.seek(0)

        attachment = self.env['ir.attachment'].create({
            'name': 'Dashboard_Report_%s.xlsx' % fields.Datetime.now().strftime('%Y%m%d_%H%M%S'),
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': 'g2p.livestock.dashboard',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return '/web/content/%s?download=true' % attachment.id

    # ------------------------------------------------------------------
    # PDF Export (remains mostly unchanged)
    # ------------------------------------------------------------------
    @api.model
    def action_export_report_pdf(self, filters=None):
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet

        data = self.get_dashboard_data(filters)
        styles = getSampleStyleSheet()
        output = io.BytesIO()
        doc = SimpleDocTemplate(output, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
        story = []

        story.append(Paragraph("Livestock Registry — Statistics Report", styles['Title']))
        story.append(Paragraph("As of %s" % data['as_of'], styles['Normal']))

        filters = filters or {}
        if any(filters.values()):
            active = ', '.join('%s: %s' % (k, v) for k, v in filters.items() if v)
            story.append(Paragraph("Filters applied — %s" % active, styles['Italic']))

        story.append(Spacer(1, 14))

        # ---- KPI summary ----
        story.append(Paragraph("Summary", styles['Heading2']))
        kpi_rows = [
            ['Metric', 'Value'],
            ['Total Registries', str(data['total_registries'])],
            ['Total Animals', str(data['total_animals'])],
            ['Verified', str(data['verified'])],
            ['Draft', str(data['draft'])],
            ['Archived', str(data['archived'])],
        ]
        kpi_table = Table(kpi_rows, colWidths=[8 * cm, 8 * cm])
        kpi_table.setStyle(_table_style(header_row=True))
        story.append(kpi_table)
        story.append(Spacer(1, 14))

        # ---- Health breakdown ----
        story.append(Paragraph("Health Status", styles['Heading2']))
        health_rows = [['Status', 'Count']] + [
            [label, str(data['health'][key])]
            for key, label in [
                ('healthy', 'Healthy'), ('sick', 'Sick'),
                ('quarantined', 'Quarantined'), ('deceased', 'Deceased'),
            ]
        ]
        health_table = Table(health_rows, colWidths=[8 * cm, 8 * cm])
        health_table.setStyle(_table_style(header_row=True))
        story.append(health_table)
        story.append(Spacer(1, 14))

        # ---- Vaccination breakdown ----
        story.append(Paragraph("Vaccination Status", styles['Heading2']))
        vax_rows = [['Status', 'Count']] + [
            [label, str(data['vaccination'][key])]
            for key, label in [
                ('up_to_date', 'Up to date'), ('overdue', 'Overdue'), ('none', 'None'),
            ]
        ]
        vax_table = Table(vax_rows, colWidths=[8 * cm, 8 * cm])
        vax_table.setStyle(_table_style(header_row=True))
        story.append(vax_table)
        story.append(Spacer(1, 14))

        # ---- Species breakdown ----
        if data['species_breakdown']:
            story.append(Paragraph("Species Breakdown", styles['Heading2']))
            species_rows = [['Species', 'Count']] + [
                [row['label'], str(row['count'])] for row in data['species_breakdown']
            ]
            species_table = Table(species_rows, colWidths=[8 * cm, 8 * cm])
            species_table.setStyle(_table_style(header_row=True))
            story.append(species_table)
            story.append(Spacer(1, 14))

        # ---- Region breakdown ----
        if data['region_breakdown']:
            story.append(Paragraph("Region Breakdown", styles['Heading2']))
            region_rows = [['Region', 'Count']] + [
                [row['label'], str(row['count'])] for row in data['region_breakdown']
            ]
            region_table = Table(region_rows, colWidths=[8 * cm, 8 * cm])
            region_table.setStyle(_table_style(header_row=True))
            story.append(region_table)
            story.append(Spacer(1, 14))

        # ---- Sync status ----
        story.append(Paragraph("Sync Status", styles['Heading2']))
        sync_rows = [['Status', 'Count']] + [
            [label, str(data['sync'][key])]
            for key, label in [
                ('synced', 'Synced'), ('pending', 'Pending'),
                ('conflict', 'Conflict'), ('failed', 'Failed'),
            ]
        ]
        sync_table = Table(sync_rows, colWidths=[8 * cm, 8 * cm])
        sync_table.setStyle(_table_style(header_row=True))
        story.append(sync_table)
        story.append(Spacer(1, 14))

        # ---- Source system breakdown ----
        if data['source_breakdown']:
            story.append(Paragraph("Source System Breakdown", styles['Heading2']))
            source_rows = [['Source', 'Count']] + [
                [row['label'], str(row['count'])] for row in data['source_breakdown']
            ]
            source_table = Table(source_rows, colWidths=[8 * cm, 8 * cm])
            source_table.setStyle(_table_style(header_row=True))
            story.append(source_table)
            story.append(Spacer(1, 14))

        # ---- Alerts ----
        if data['alerts']:
            story.append(Paragraph("Alerts", styles['Heading2']))
            for alert in data['alerts']:
                color_hex = '#dc2626' if alert['type'] == 'danger' else '#d97706'
                story.append(Paragraph(
                    '<font color="%s">&#8226; %s</font>' % (color_hex, alert['msg']),
                    styles['Normal']))
            story.append(Spacer(1, 14))

        # ---- Recent registrations (last 7 days) ----
        if data['recent']:
            story.append(Paragraph("Recent Registrations (Last 7 Days)", styles['Heading2']))
            recent_rows = [['Owner', 'Woreda', 'State', 'Date']] + [
                [r['owner'], r['woreda'], r['state'], r['date']]
                for r in data['recent']
            ]
            recent_table = Table(recent_rows, colWidths=[5 * cm, 4 * cm, 3 * cm, 3.5 * cm])
            recent_table.setStyle(_table_style(header_row=True))
            story.append(recent_table)

        doc.build(story)
        output.seek(0)

        attachment = self.env['ir.attachment'].create({
            'name': 'Dashboard_Report_%s.pdf' % fields.Datetime.now().strftime('%Y%m%d_%H%M%S'),
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': 'g2p.livestock.dashboard',
            'mimetype': 'application/pdf',
        })

        return '/web/content/%s?download=true' % attachment.id


def _table_style(header_row=False):
    from reportlab.lib import colors
    from reportlab.platypus import TableStyle
    style = [
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]
    if header_row:
        style += [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e0e7ff')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ]
    return TableStyle(style)