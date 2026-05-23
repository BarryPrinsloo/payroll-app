"""
payslip.py — Payslip PDF generator for the Payroll App by Barry Prinsloo.

Usage:
    from payslip import generate_payslip, calculate_payslip_figures

    figures = calculate_payslip_figures(employee, timesheets, year, month)
    path    = generate_payslip(company, employee, year, month, figures, output_path)
"""

import os
import calendar
from datetime import date

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

# ── Brand colours ──────────────────────────────────────────────────────────────
DARK_BLUE   = colors.HexColor("#1a3c5e")
MID_BLUE    = colors.HexColor("#2563a8")
LIGHT_BLUE  = colors.HexColor("#dbeafe")
ACCENT      = colors.HexColor("#f59e0b")
LIGHT_GREY  = colors.HexColor("#f3f4f6")
MID_GREY    = colors.HexColor("#9ca3af")
DARK_GREY   = colors.HexColor("#374151")
WHITE       = colors.white
BLACK       = colors.black


# ══════════════════════════════════════════════════════════════════════════════
# 1.  TAX / DEDUCTION CALCULATIONS
# ══════════════════════════════════════════════════════════════════════════════

# South-African PAYE tax tables 2024/2025 (annual brackets, individuals)
_PAYE_BRACKETS = [
    (237_100,  0.18, 0),
    (370_500,  0.26, 42_678),
    (512_800,  0.31, 77_362),
    (673_000,  0.36, 121_475),
    (857_900,  0.39, 179_147),
    (1_817_000, 0.41, 251_258),
    (float("inf"), 0.45, 644_489),
]
_PRIMARY_REBATE   = 17_235   # 2024/25
_SECONDARY_REBATE = 9_444    # age 65–74
_TAX_THRESHOLD    = 95_750   # below this: no tax

def _annual_paye(annual_income: float) -> float:
    """Return estimated annual PAYE for a South-African individual."""
    if annual_income <= _TAX_THRESHOLD:
        return 0.0
    tax = 0.0
    for upper, rate, base in _PAYE_BRACKETS:
        if annual_income <= upper:
            # find lower bound for this bracket
            prev_upper = 0
            for i, (u, _, _) in enumerate(_PAYE_BRACKETS):
                if u == upper:
                    if i > 0:
                        prev_upper = _PAYE_BRACKETS[i - 1][0]
                    break
            tax = base + (annual_income - prev_upper) * rate
            break
    tax -= _PRIMARY_REBATE
    return max(tax, 0.0)


def calculate_payslip_figures(
    employee:   dict,
    timesheets: list,   # list of sqlite3.Row / dict for the pay period
    year:       int,
    month:      int,
) -> dict:
    """
    Derive gross pay, deductions and net pay for one employee in one pay period.

    Returns a dict with keys:
        gross_pay, days_worked, hours_worked,
        paye, uif_employee, uif_employer,
        total_deductions, net_pay,
        period_label, working_days_in_month
    """
    salary_type = employee.get("salary_type", "Monthly")
    monthly_salary = float(employee.get("monthly_salary", 0) or 0)
    hourly_rate    = float(employee.get("hourly_rate",    0) or 0)
    uif_exempt     = bool(employee.get("uif_exempt",      0))

    # ── Count actual attendance from timesheets ──────────────────────────────
    days_worked  = 0
    hours_worked = 0.0
    for ts in timesheets:
        ts_dict = dict(ts) if not isinstance(ts, dict) else ts
        status = ts_dict.get("status", "Present")
        if status == "Present":
            days_worked  += 1
            hours_worked += float(ts_dict.get("hours", 0) or 0)

    # ── Working days in the month (Mon–Fri) ──────────────────────────────────
    _, days_in_month = calendar.monthrange(year, month)
    working_days = sum(
        1 for d in range(1, days_in_month + 1)
        if date(year, month, d).weekday() < 5
    )

    # ── Gross pay ────────────────────────────────────────────────────────────
    if salary_type == "Hourly":
        gross_pay = hours_worked * hourly_rate
    else:
        # Salaried: prorate if we have timesheet data; full month if no data
        if timesheets:
            gross_pay = (monthly_salary / working_days) * days_worked if working_days else monthly_salary
        else:
            gross_pay = monthly_salary

    # ── PAYE ─────────────────────────────────────────────────────────────────
    annual_income = gross_pay * 12
    paye_annual   = _annual_paye(annual_income)
    paye_monthly  = paye_annual / 12

    # ── UIF (1 % employee + 1 % employer, capped at R17 712 pa) ─────────────
    UIF_RATE = 0.01
    UIF_ANNUAL_CAP = 17_712
    uif_employee = 0.0
    uif_employer = 0.0
    if not uif_exempt:
        uif_annual   = min(annual_income * UIF_RATE, UIF_ANNUAL_CAP)
        uif_employee = uif_annual / 12
        uif_employer = uif_employee  # employer matches

    total_deductions = paye_monthly + uif_employee
    net_pay          = gross_pay - total_deductions

    month_name   = calendar.month_name[month]
    period_label = f"{month_name} {year}"

    return {
        "gross_pay":            round(gross_pay,         2),
        "days_worked":          days_worked,
        "hours_worked":         round(hours_worked,      2),
        "working_days_in_month": working_days,
        "paye":                 round(paye_monthly,      2),
        "uif_employee":         round(uif_employee,      2),
        "uif_employer":         round(uif_employer,      2),
        "total_deductions":     round(total_deductions,  2),
        "net_pay":              round(net_pay,           2),
        "period_label":         period_label,
        "salary_type":          salary_type,
        "monthly_salary":       monthly_salary,
        "hourly_rate":          hourly_rate,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 2.  PDF GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def _fmt(amount: float) -> str:
    """Format a rand amount: R 1 234.56"""
    return f"R {amount:,.2f}"


def generate_payslip(
    company:     dict,
    employee:    dict,
    year:        int,
    month:       int,
    figures:     dict,
    output_path: str,
) -> str:
    """
    Generate a single-employee payslip PDF and return the file path.

    Args:
        company      : dict-like with company fields
        employee     : dict-like with employee fields
        year / month : pay period
        figures      : output of calculate_payslip_figures()
        output_path  : full path for the PDF file

    Returns:
        output_path  (same value, for convenience)
    """
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    styles = getSampleStyleSheet()

    def style(name="Normal", **kw):
        base = styles[name]
        return ParagraphStyle(name + str(id(kw)), parent=base, **kw)

    story = []

    page_w = A4[0] - 30 * mm   # usable width

    # ── HEADER BLOCK ─────────────────────────────────────────────────────────
    company_name    = company.get("name",             "")
    trading_name    = company.get("trading_name",     "")
    reg_number      = company.get("reg_number",       "")
    paye_number     = company.get("paye_number",      "")
    uif_number      = company.get("uif_number",       "")
    physical_addr   = company.get("physical_address", "").replace("\n", " | ")
    company_phone   = company.get("phone",            "")
    company_email   = company.get("email",            "")

    display_name = company_name
    if trading_name:
        display_name += f" t/a {trading_name}"

    header_left = (
        f"<b><font color='white' size='14'>{display_name}</font></b><br/>"
        f"<font color='#dbeafe' size='8'>{physical_addr}</font><br/>"
        f"<font color='#dbeafe' size='8'>"
        + (f"Tel: {company_phone}   " if company_phone else "")
        + (f"Email: {company_email}" if company_email else "")
        + "</font>"
    )
    header_right = (
        "<font color='white' size='8'>"
        + (f"Reg: {reg_number}<br/>" if reg_number else "")
        + (f"PAYE: {paye_number}<br/>" if paye_number else "")
        + (f"UIF: {uif_number}" if uif_number else "")
        + "</font>"
    )

    header_data = [[
        Paragraph(header_left,  style(fontSize=9, textColor=WHITE, leading=13)),
        Paragraph(header_right, style(fontSize=8, textColor=WHITE, leading=13, alignment=TA_RIGHT)),
    ]]
    header_table = Table(header_data, colWidths=[page_w * 0.65, page_w * 0.35])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), DARK_BLUE),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (0, -1), 10),
        ("RIGHTPADDING",  (-1, 0), (-1, -1), 10),
    ]))
    story.append(header_table)

    # ── PAYSLIP TITLE BAND ───────────────────────────────────────────────────
    title_data = [[
        Paragraph("<b><font color='white'>PAYSLIP</font></b>",
                  style(fontSize=13, textColor=WHITE, alignment=TA_LEFT)),
        Paragraph(
            f"<font color='white'>Pay Period: {figures['period_label']}</font>",
            style(fontSize=10, textColor=WHITE, alignment=TA_RIGHT)
        ),
    ]]
    title_table = Table(title_data, colWidths=[page_w * 0.5, page_w * 0.5])
    title_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), MID_BLUE),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (0, -1), 10),
        ("RIGHTPADDING",  (-1, 0), (-1, -1), 10),
    ]))
    story.append(title_table)
    story.append(Spacer(1, 4 * mm))

    # ── EMPLOYEE INFO ────────────────────────────────────────────────────────
    emp_number   = employee.get("employee_number", "")
    full_name    = employee.get("full_name",        "")
    id_number    = employee.get("id_number",        "N/A")
    tax_number   = employee.get("tax_number",       "N/A")
    job_title    = employee.get("job_title",        "N/A")
    department   = employee.get("department",       "N/A")
    emp_type     = employee.get("employment_type",  "N/A")
    start_date   = employee.get("start_date",       "N/A")
    bank_name    = employee.get("bank_name",        "N/A")
    bank_acc     = employee.get("bank_account_number", "")
    bank_type    = employee.get("bank_account_type",   "")
    bank_branch  = employee.get("bank_branch_code",    "")

    # Mask account number (show last 4 digits only)
    if bank_acc and len(bank_acc) > 4:
        bank_acc_display = "*" * (len(bank_acc) - 4) + bank_acc[-4:]
    else:
        bank_acc_display = bank_acc or "N/A"

    def info_row(label, value):
        return [
            Paragraph(f"<b>{label}</b>", style(fontSize=8, textColor=DARK_GREY)),
            Paragraph(str(value),        style(fontSize=8, textColor=BLACK)),
        ]

    emp_info_data = [
        info_row("Employee Number", emp_number),
        info_row("Full Name",       full_name),
        info_row("SA ID Number",    id_number),
        info_row("Tax Number",      tax_number),
    ]
    job_info_data = [
        info_row("Job Title",         job_title),
        info_row("Department",        department),
        info_row("Employment Type",   emp_type),
        info_row("Start Date",        start_date),
    ]
    bank_info_data = [
        info_row("Bank",           bank_name),
        info_row("Account",        bank_acc_display),
        info_row("Account Type",   bank_type or "N/A"),
        info_row("Branch Code",    bank_branch or "N/A"),
    ]

    col_w = page_w / 3

    def build_info_section(rows, bg):
        t = Table(rows, colWidths=[col_w * 0.42, col_w * 0.58])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), bg),
            ("ROWBACKGROUNDS",(0, 0), (-1, -1), [bg, WHITE]),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ]))
        return t

    info_row_layout = [[
        build_info_section(emp_info_data,  LIGHT_BLUE),
        build_info_section(job_info_data,  LIGHT_GREY),
        build_info_section(bank_info_data, LIGHT_BLUE),
    ]]
    info_outer = Table(info_row_layout, colWidths=[col_w, col_w, col_w])
    info_outer.setStyle(TableStyle([
        ("VALIGN",  (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(info_outer)
    story.append(Spacer(1, 5 * mm))

    # ── EARNINGS TABLE ───────────────────────────────────────────────────────
    story.append(Paragraph("<b>Earnings</b>",
                           style(fontSize=9, textColor=DARK_BLUE, spaceBefore=2)))
    story.append(Spacer(1, 1 * mm))

    salary_type = figures["salary_type"]
    if salary_type == "Hourly":
        rate_label  = "Hourly Rate"
        rate_value  = _fmt(figures["hourly_rate"])
        qty_label   = f"Hours Worked ({figures['hours_worked']:.2f} hrs)"
    else:
        rate_label  = "Monthly Salary"
        rate_value  = _fmt(figures["monthly_salary"])
        working_days = figures["working_days_in_month"]
        days_worked  = figures["days_worked"]
        qty_label   = (
            f"Days Worked ({days_worked} / {working_days} working days)"
            if days_worked > 0 else "Monthly (no timesheet data)"
        )

    earnings_data = [
        [
            Paragraph("<b>Description</b>", style(fontSize=8, textColor=WHITE)),
            Paragraph("<b>Rate</b>",        style(fontSize=8, textColor=WHITE, alignment=TA_RIGHT)),
            Paragraph("<b>Quantity</b>",    style(fontSize=8, textColor=WHITE, alignment=TA_RIGHT)),
            Paragraph("<b>Amount</b>",      style(fontSize=8, textColor=WHITE, alignment=TA_RIGHT)),
        ],
        [
            Paragraph(qty_label,   style(fontSize=8)),
            Paragraph(rate_value,  style(fontSize=8, alignment=TA_RIGHT)),
            Paragraph(
                f"{figures['hours_worked']:.2f} hrs" if salary_type == "Hourly"
                else f"{figures['days_worked']} days",
                style(fontSize=8, alignment=TA_RIGHT)
            ),
            Paragraph(_fmt(figures["gross_pay"]), style(fontSize=8, alignment=TA_RIGHT)),
        ],
        [
            Paragraph("<b>Gross Pay</b>", style(fontSize=9, textColor=DARK_BLUE)),
            Paragraph("",                 style(fontSize=8)),
            Paragraph("",                 style(fontSize=8)),
            Paragraph(f"<b>{_fmt(figures['gross_pay'])}</b>",
                      style(fontSize=9, textColor=DARK_BLUE, alignment=TA_RIGHT)),
        ],
    ]

    earn_col_w = [page_w * 0.45, page_w * 0.18, page_w * 0.17, page_w * 0.20]
    earn_table = Table(earnings_data, colWidths=earn_col_w)
    earn_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), DARK_BLUE),
        ("ROWBACKGROUNDS",(0, 1), (-1, -2), [WHITE, LIGHT_GREY]),
        ("BACKGROUND",    (0, -1), (-1, -1), LIGHT_BLUE),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("LINEBELOW",     (0, -1), (-1, -1), 0.5, MID_BLUE),
    ]))
    story.append(earn_table)
    story.append(Spacer(1, 4 * mm))

    # ── DEDUCTIONS TABLE ─────────────────────────────────────────────────────
    story.append(Paragraph("<b>Deductions</b>",
                           style(fontSize=9, textColor=DARK_BLUE)))
    story.append(Spacer(1, 1 * mm))

    ded_data = [
        [
            Paragraph("<b>Description</b>", style(fontSize=8, textColor=WHITE)),
            Paragraph("<b>Note</b>",         style(fontSize=8, textColor=WHITE, alignment=TA_RIGHT)),
            Paragraph("<b>Amount</b>",        style(fontSize=8, textColor=WHITE, alignment=TA_RIGHT)),
        ],
        [
            Paragraph("PAYE (Income Tax)", style(fontSize=8)),
            Paragraph("SARS estimated",    style(fontSize=8, textColor=MID_GREY, alignment=TA_RIGHT)),
            Paragraph(_fmt(figures["paye"]), style(fontSize=8, alignment=TA_RIGHT)),
        ],
        [
            Paragraph("UIF (Employee Contribution)", style(fontSize=8)),
            Paragraph("1% of gross" if not employee.get("uif_exempt") else "Exempt",
                      style(fontSize=8, textColor=MID_GREY, alignment=TA_RIGHT)),
            Paragraph(_fmt(figures["uif_employee"]), style(fontSize=8, alignment=TA_RIGHT)),
        ],
        [
            Paragraph("<b>Total Deductions</b>", style(fontSize=9, textColor=colors.HexColor("#dc2626"))),
            Paragraph("",                         style(fontSize=8)),
            Paragraph(f"<b>{_fmt(figures['total_deductions'])}</b>",
                      style(fontSize=9, textColor=colors.HexColor("#dc2626"), alignment=TA_RIGHT)),
        ],
    ]

    ded_col_w = [page_w * 0.50, page_w * 0.28, page_w * 0.22]
    ded_table = Table(ded_data, colWidths=ded_col_w)
    ded_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), DARK_BLUE),
        ("ROWBACKGROUNDS",(0, 1), (-1, -2), [WHITE, LIGHT_GREY]),
        ("BACKGROUND",    (0, -1), (-1, -1), colors.HexColor("#fef2f2")),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("LINEBELOW",     (0, -1), (-1, -1), 0.5, colors.HexColor("#dc2626")),
    ]))
    story.append(ded_table)
    story.append(Spacer(1, 4 * mm))

    # ── EMPLOYER UIF NOTE ────────────────────────────────────────────────────
    if figures["uif_employer"] > 0:
        story.append(Paragraph(
            f"Employer UIF Contribution (not deducted from employee): "
            f"<b>{_fmt(figures['uif_employer'])}</b>",
            style(fontSize=8, textColor=MID_GREY)
        ))
        story.append(Spacer(1, 3 * mm))

    # ── NET PAY BANNER ───────────────────────────────────────────────────────
    net_data = [[
        Paragraph("<b><font color='white' size='11'>NET PAY</font></b>",
                  style(fontSize=11, textColor=WHITE)),
        Paragraph(
            f"<b><font color='white' size='14'>{_fmt(figures['net_pay'])}</font></b>",
            style(fontSize=14, textColor=WHITE, alignment=TA_RIGHT)
        ),
    ]]
    net_table = Table(net_data, colWidths=[page_w * 0.5, page_w * 0.5])
    net_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), MID_BLUE),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (0, -1), 12),
        ("RIGHTPADDING",  (-1, 0), (-1, -1), 12),
        ("ROUNDEDCORNERS", [3]),
    ]))
    story.append(net_table)
    story.append(Spacer(1, 5 * mm))

    # ── TIMESHEET SUMMARY (if available) ────────────────────────────────────
    story.append(Paragraph("<b>Attendance Summary</b>",
                           style(fontSize=9, textColor=DARK_BLUE)))
    story.append(Spacer(1, 1 * mm))

    working_days = figures["working_days_in_month"]
    days_worked  = figures["days_worked"]
    hours_worked = figures["hours_worked"]

    att_data = [
        [
            Paragraph("<b>Working Days in Month</b>", style(fontSize=8, textColor=WHITE)),
            Paragraph("<b>Days Present</b>",          style(fontSize=8, textColor=WHITE, alignment=TA_CENTER)),
            Paragraph("<b>Days Absent/Leave</b>",     style(fontSize=8, textColor=WHITE, alignment=TA_CENTER)),
            Paragraph("<b>Total Hours</b>",            style(fontSize=8, textColor=WHITE, alignment=TA_CENTER)),
        ],
        [
            Paragraph(str(working_days),              style(fontSize=10)),
            Paragraph(str(days_worked),               style(fontSize=10, alignment=TA_CENTER)),
            Paragraph(str(working_days - days_worked),style(fontSize=10, alignment=TA_CENTER)),
            Paragraph(f"{hours_worked:.2f}",          style(fontSize=10, alignment=TA_CENTER)),
        ],
    ]
    att_col_w = [page_w * 0.28, page_w * 0.24, page_w * 0.24, page_w * 0.24]
    att_table = Table(att_data, colWidths=att_col_w)
    att_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), DARK_BLUE),
        ("BACKGROUND",    (0, 1), (-1, 1), LIGHT_GREY),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("LINEBELOW",     (0, -1), (-1, -1), 0.5, MID_GREY),
    ]))
    story.append(att_table)
    story.append(Spacer(1, 5 * mm))

    # ── DISCLAIMER FOOTER ────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=MID_GREY))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "This payslip is generated by the Payroll App by Barry Prinsloo. "
        "PAYE figures are estimates based on the 2024/2025 SARS tax tables and "
        "the primary rebate only. Please consult a registered tax practitioner for "
        "official tax advice. UIF contributions are calculated at 1% each for "
        "employee and employer, capped at R17 712 per annum.",
        style(fontSize=7, textColor=MID_GREY, leading=10)
    ))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        f"Printed: {date.today().strftime('%d %B %Y')}  |  "
        f"Payroll App by Barry Prinsloo",
        style(fontSize=7, textColor=MID_GREY, alignment=TA_RIGHT)
    ))

    # ── BUILD ────────────────────────────────────────────────────────────────
    doc.build(story)
    return output_path


# ══════════════════════════════════════════════════════════════════════════════
# 3.  CONVENIENCE: get timesheets for a period from the database
# ══════════════════════════════════════════════════════════════════════════════

def get_timesheets_for_period(company_id: int, employee_id: int,
                               year: int, month: int) -> list:
    """
    Pull all timesheet rows for one employee in a given year/month.
    Returns a list of sqlite3.Row objects.
    """
    import database
    import calendar as _cal

    _, days_in_month = _cal.monthrange(year, month)
    date_from = f"{year}-{month:02d}-01"
    date_to   = f"{year}-{month:02d}-{days_in_month:02d}"

    conn = database.get_connection()
    rows = conn.execute("""
        SELECT * FROM timesheets
        WHERE company_id = ? AND employee_id = ?
          AND date BETWEEN ? AND ?
        ORDER BY date
    """, (company_id, employee_id, date_from, date_to)).fetchall()
    conn.close()
    return rows
