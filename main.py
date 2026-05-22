import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMessageBox, QListWidgetItem,
    QTableWidgetItem, QHeaderView, QTimeEdit, QComboBox
)
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile, QDate, QTime, Qt   # ← Qt added here
from PySide6.QtGui import QColor

import database

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def load_ui(filename):
    loader = QUiLoader()
    ui_file = QFile(resource_path(filename))
    ui_file.open(QFile.ReadOnly)
    window = loader.load(ui_file)
    ui_file.close()
    return window

# ---------------------------------------------------------------------------
# Unified Add / Edit Employee Window
# ---------------------------------------------------------------------------

class AddEmployeeWindow:

    def __init__(self, company, on_saved, on_cancel, employee=None):
        self.company   = company
        self.on_saved  = on_saved
        self.on_cancel = on_cancel
        self.employee  = employee
        self.is_edit   = employee is not None

        self.window = load_ui("add_employee.ui")

        self.window.cmbSalaryType.currentTextChanged.connect(self._on_salary_type_changed)
        self._on_salary_type_changed(self.window.cmbSalaryType.currentText())

        self.window.btnSave.clicked.connect(self.save)
        self.window.btnCancel.clicked.connect(self.cancel)

        if self.is_edit:
            self.window.setWindowTitle("Payroll App by Barry Prinsloo — Edit Employee")
            self.window.lblTitle.setText("Edit Employee")
            self.window.btnSave.setText("💾 Save Changes")
            self._load_employee_data()
        else:
            self.window.dtStartDate.setDate(QDate.currentDate())
            self.window.dtEndDate.setMinimumDate(QDate(2000, 1, 1))
            self.window.dtEndDate.setDate(QDate(2000, 1, 1))

    def _on_salary_type_changed(self, salary_type):
        is_monthly = salary_type == "Monthly"
        self.window.spnMonthlySalary.setVisible(is_monthly)
        self.window.lblMonthlySalary.setVisible(is_monthly)
        self.window.spnHourlyRate.setVisible(not is_monthly)
        self.window.lblHourlyRate.setVisible(not is_monthly)

    def _set_combo_by_text(self, combo, text):
        for i in range(combo.count()):
            if combo.itemText(i) == text:
                combo.setCurrentIndex(i)
                return

    def _load_employee_data(self):
        emp = dict(self.employee) if self.employee else {}
        self.window.txtEmployeeNumber.setText(emp.get("employee_number", ""))
        self.window.txtFullName.setText(emp.get("full_name", ""))
        self.window.txtIdNumber.setText(emp.get("id_number", ""))
        self.window.txtTaxNumber.setText(emp.get("tax_number", ""))
        self.window.txtPhone.setText(emp.get("phone", ""))
        self.window.txtEmail.setText(emp.get("email", ""))
        self.window.txtJobTitle.setText(emp.get("job_title", ""))
        self.window.txtDepartment.setText(emp.get("department", ""))

        self._set_combo_by_text(self.window.cmbEmploymentType, emp.get("employment_type", "Permanent"))
        self._set_combo_by_text(self.window.cmbPayFrequency, emp.get("pay_frequency", "Monthly"))
        self._set_combo_by_text(self.window.cmbSalaryType, emp.get("salary_type", "Monthly"))
        self._set_combo_by_text(self.window.cmbBankName, emp.get("bank_name", ""))
        self._set_combo_by_text(self.window.cmbAccountType, emp.get("bank_account_type", ""))

        self.window.spnMonthlySalary.setValue(float(emp.get("monthly_salary", 0)))
        self.window.spnHourlyRate.setValue(float(emp.get("hourly_rate", 0)))
        self.window.chkUifExempt.setChecked(bool(emp.get("uif_exempt", 0)))

        if emp.get("start_date"):
            self.window.dtStartDate.setDate(QDate.fromString(emp["start_date"], "yyyy-MM-dd"))
        if emp.get("end_date"):
            self.window.dtEndDate.setDate(QDate.fromString(emp["end_date"], "yyyy-MM-dd"))
        else:
            self.window.dtEndDate.setDate(QDate(2000, 1, 1))

        self.window.txtAccountNumber.setText(emp.get("bank_account_number", ""))
        self.window.txtBranchCode.setText(emp.get("bank_branch_code", ""))
        self.window.txtEmergencyContact.setText(emp.get("emergency_contact", ""))
        self.window.txtEmergencyPhone.setText(emp.get("emergency_phone", ""))

    def save(self):
        salary_type = self.window.cmbSalaryType.currentText()
        end_date_val = self.window.dtEndDate.date()
        end_date = end_date_val.toString("yyyy-MM-dd") if end_date_val > QDate(2000, 1, 1) else ""

        if self.is_edit:
            ok, msg = database.update_employee(
                employee_id         = self.employee["id"],
                company_id          = self.company["id"],
                employee_number     = self.window.txtEmployeeNumber.text(),
                full_name           = self.window.txtFullName.text(),
                id_number           = self.window.txtIdNumber.text(),
                tax_number          = self.window.txtTaxNumber.text(),
                job_title           = self.window.txtJobTitle.text(),
                department          = self.window.txtDepartment.text(),
                employment_type     = self.window.cmbEmploymentType.currentText(),
                salary_type         = salary_type,
                monthly_salary      = self.window.spnMonthlySalary.value(),
                hourly_rate         = self.window.spnHourlyRate.value(),
                pay_frequency       = self.window.cmbPayFrequency.currentText(),
                start_date          = self.window.dtStartDate.date().toString("yyyy-MM-dd"),
                end_date            = end_date,
                uif_exempt          = self.window.chkUifExempt.isChecked(),
                phone               = self.window.txtPhone.text(),
                email               = self.window.txtEmail.text(),
                bank_name           = self.window.cmbBankName.currentText(),
                bank_account_number = self.window.txtAccountNumber.text(),
                bank_account_type   = self.window.cmbAccountType.currentText(),
                bank_branch_code    = self.window.txtBranchCode.text(),
                emergency_contact   = self.window.txtEmergencyContact.text(),
                emergency_phone     = self.window.txtEmergencyPhone.text(),
            )
            success_msg = "updated successfully"
        else:
            ok, msg = database.create_employee(
                company_id          = self.company["id"],
                employee_number     = self.window.txtEmployeeNumber.text(),
                full_name           = self.window.txtFullName.text(),
                id_number           = self.window.txtIdNumber.text(),
                tax_number          = self.window.txtTaxNumber.text(),
                job_title           = self.window.txtJobTitle.text(),
                department          = self.window.txtDepartment.text(),
                employment_type     = self.window.cmbEmploymentType.currentText(),
                salary_type         = salary_type,
                monthly_salary      = self.window.spnMonthlySalary.value(),
                hourly_rate         = self.window.spnHourlyRate.value(),
                pay_frequency       = self.window.cmbPayFrequency.currentText(),
                start_date          = self.window.dtStartDate.date().toString("yyyy-MM-dd"),
                end_date            = end_date,
                uif_exempt          = self.window.chkUifExempt.isChecked(),
                phone               = self.window.txtPhone.text(),
                email               = self.window.txtEmail.text(),
                bank_name           = self.window.cmbBankName.currentText(),
                bank_account_number = self.window.txtAccountNumber.text(),
                bank_account_type   = self.window.cmbAccountType.currentText(),
                bank_branch_code    = self.window.txtBranchCode.text(),
                emergency_contact   = self.window.txtEmergencyContact.text(),
                emergency_phone     = self.window.txtEmergencyPhone.text(),
            )
            success_msg = "added successfully"

        if ok:
            name = self.window.txtFullName.text().strip()
            QMessageBox.information(self.window, "Success", f"'{name}' has been {success_msg}.")
            self.window.close()
            self.on_saved()
        else:
            QMessageBox.warning(self.window, "Validation Error", msg)

    def cancel(self):
        self.window.close()
        self.on_cancel()

    def show(self):
        if not self.is_edit:
            for w in [self.window.txtEmployeeNumber, self.window.txtFullName, self.window.txtIdNumber,
                      self.window.txtTaxNumber, self.window.txtPhone, self.window.txtEmail,
                      self.window.txtJobTitle, self.window.txtDepartment, self.window.txtAccountNumber,
                      self.window.txtBranchCode, self.window.txtEmergencyContact, self.window.txtEmergencyPhone]:
                w.clear()
            self.window.cmbEmploymentType.setCurrentIndex(0)
            self.window.cmbPayFrequency.setCurrentIndex(0)
            self.window.cmbSalaryType.setCurrentIndex(0)
            self.window.cmbBankName.setCurrentIndex(0)
            self.window.cmbAccountType.setCurrentIndex(0)
            self.window.spnMonthlySalary.setValue(0)
            self.window.spnHourlyRate.setValue(0)
            self.window.dtStartDate.setDate(QDate.currentDate())
            self.window.dtEndDate.setDate(QDate(2000, 1, 1))
            self.window.chkUifExempt.setChecked(False)
        self.window.show()

# ---------------------------------------------------------------------------
# Timesheet Entry Window
# ---------------------------------------------------------------------------

class TimesheetEntryWindow:
    def __init__(self, company, on_close):
        self.company = company
        self.on_close = on_close
        self.window = load_ui("timesheet_entry.ui")
        
        self.window.dtDate.setDate(QDate.currentDate())
        self.window.dtDate.dateChanged.connect(self.load_employees)
        
        self.window.btnSave.clicked.connect(self.save_timesheet)
        self.window.btnCancel.clicked.connect(self.close_window)

        self.load_employees()

    def load_employees(self):
        date_str = self.window.dtDate.date().toString("yyyy-MM-dd")
        tbl = self.window.tblEmployees
        tbl.setRowCount(0)
        tbl.setColumnCount(6)
        tbl.setHorizontalHeaderLabels(["Emp #", "Full Name", "Clock In", "Clock Out", "Status", "Hours"])

        employees = database.get_employees_for_company(self.company["id"])
        
        for emp in employees:
            row = tbl.rowCount()
            tbl.insertRow(row)
            
            tbl.setItem(row, 0, QTableWidgetItem(emp["employee_number"]))
            tbl.setItem(row, 1, QTableWidgetItem(emp["full_name"]))

            # Clock In
            time_in = QTimeEdit()
            time_in.setTime(QTime(8, 0))
            tbl.setCellWidget(row, 2, time_in)

            # Clock Out
            time_out = QTimeEdit()
            time_out.setTime(QTime(17, 0))
            tbl.setCellWidget(row, 3, time_out)

            # Status
            status_combo = QComboBox()
            status_combo.addItems(["Present", "Leave", "Absent", "Sick"])
            status_combo.setCurrentText("Present")
            tbl.setCellWidget(row, 4, status_combo)

            # Hours (Read only)
            hours_item = QTableWidgetItem("8.00")
            hours_item.setFlags(hours_item.flags() & ~Qt.ItemIsEditable)
            tbl.setItem(row, 5, hours_item)

            # Store employee ID
            tbl.item(row, 0).setData(256, emp["id"])

    def save_timesheet(self):
        date_str = self.window.dtDate.date().toString("yyyy-MM-dd")
        tbl = self.window.tblEmployees
        entries = []

        for row in range(tbl.rowCount()):
            emp_id = tbl.item(row, 0).data(256)
            time_in_w = tbl.cellWidget(row, 2)
            time_out_w = tbl.cellWidget(row, 3)
            status_w = tbl.cellWidget(row, 4)

            clock_in = time_in_w.time().toString("HH:mm") if time_in_w else None
            clock_out = time_out_w.time().toString("HH:mm") if time_out_w else None
            status = status_w.currentText() if status_w else "Present"

            hours = 8.0 if status == "Present" else 0.0

            entries.append({
                'employee_id': emp_id,
                'clock_in': clock_in,
                'clock_out': clock_out,
                'status': status,
                'hours': hours,
                'amount': 0.0
            })

        ok, msg = database.save_daily_timesheet(self.company["id"], date_str, entries)
        if ok:
            QMessageBox.information(self.window, "Success", f"Timesheet for {date_str} saved successfully!")
            self.close_window()
        else:
            QMessageBox.warning(self.window, "Error", msg)

    def close_window(self):
        self.window.close()
        self.on_close()

    def show(self):
        self.window.show()

# ---------------------------------------------------------------------------
# Employee Details Window (with Edit Support)
# ---------------------------------------------------------------------------

class EmployeeDetailsWindow:
    def __init__(self, company, employee, on_close):
        self.company = company
        self.employee = dict(employee)
        self.on_close = on_close
        self.current_timesheets = []  # To keep track of edited data

        self.window = load_ui("employee_details.ui")

        self.window.setWindowTitle(f"Details - {self.employee['full_name']}")
        self.window.lblTitle.setText(f"Employee Details - {self.employee['full_name']}")

        self.window.btnClose.clicked.connect(self.close)
        self.window.btnSaveTimesheet.clicked.connect(self.save_timesheet_changes)

        self.display_employee_info()
        self.load_all_timesheets()

    def display_employee_info(self):
        emp = self.employee
        info_text = f"""
        <h2>{emp['full_name']}</h2>
        <p><b>Employee Number:</b> {emp.get('employee_number', 'N/A')}</p>
        <p><b>ID Number:</b> {emp.get('id_number', 'N/A')}</p>
        <p><b>Job Title:</b> {emp.get('job_title', 'N/A')}</p>
        <p><b>Department:</b> {emp.get('department', 'N/A')}</p>
        <p><b>Employment Type:</b> {emp.get('employment_type', 'N/A')}</p>
        <p><b>Salary Type:</b> {emp.get('salary_type', 'N/A')}</p>
        <p><b>Monthly Salary:</b> R {emp.get('monthly_salary', 0):,.2f}</p>
        <p><b>Hourly Rate:</b> R {emp.get('hourly_rate', 0):,.2f}</p>
        <p><b>Start Date:</b> {emp.get('start_date', 'N/A')}</p>
        <p><b>Phone:</b> {emp.get('phone', 'N/A')}</p>
        <p><b>Email:</b> {emp.get('email', 'N/A')}</p>
        """
        self.window.lblInfo.setText(info_text)

    def load_all_timesheets(self):
        tbl = self.window.tblTimesheet
        tbl.setRowCount(0)
        self.current_timesheets = []

        conn = database.get_connection()
        rows = conn.execute("""
            SELECT t.id, t.date, t.clock_in, t.clock_out, t.status, t.hours
            FROM timesheets t
            WHERE t.company_id = ? AND t.employee_id = ?
            ORDER BY t.date DESC
        """, (self.company["id"], self.employee["id"])).fetchall()
        conn.close()

        for ts in rows:
            ts_dict = dict(ts)
            self.current_timesheets.append(ts_dict)

            row = tbl.rowCount()
            tbl.insertRow(row)

            # Date (Read only)
            date_item = QTableWidgetItem(ts_dict["date"])
            date_item.setFlags(date_item.flags() & ~Qt.ItemIsEditable)
            tbl.setItem(row, 0, date_item)

            # Clock In - Editable
            tbl.setItem(row, 1, QTableWidgetItem(ts_dict.get("clock_in", "")))

            # Clock Out - Editable
            tbl.setItem(row, 2, QTableWidgetItem(ts_dict.get("clock_out", "")))

            # Status - Editable (ComboBox)
            status_combo = QComboBox()
            status_combo.addItems(["Present", "Leave", "Absent", "Sick"])
            status_combo.setCurrentText(ts_dict.get("status", "Present"))
            tbl.setCellWidget(row, 3, status_combo)

            # Hours (Read only)
            hours_item = QTableWidgetItem(f"{float(ts_dict.get('hours', 0)):.2f}")
            hours_item.setFlags(hours_item.flags() & ~Qt.ItemIsEditable)
            tbl.setItem(row, 4, hours_item)

            # Store row index and record id
            tbl.item(row, 0).setData(256, ts_dict["id"])

    def save_timesheet_changes(self):
        tbl = self.window.tblTimesheet
        entries = []

        for row in range(tbl.rowCount()):
            record_id = tbl.item(row, 0).data(256)
            clock_in = tbl.item(row, 1).text().strip()
            clock_out = tbl.item(row, 2).text().strip()
            status_widget = tbl.cellWidget(row, 3)
            status = status_widget.currentText() if status_widget else "Present"

            hours = 8.0 if status == "Present" else 0.0

            entries.append({
                'id': record_id,
                'clock_in': clock_in if clock_in else None,
                'clock_out': clock_out if clock_out else None,
                'status': status,
                'hours': hours
            })

        # Update database
        conn = database.get_connection()
        for entry in entries:
            conn.execute("""
                UPDATE timesheets 
                SET clock_in = ?, clock_out = ?, status = ?, hours = ?
                WHERE id = ?
            """, (entry['clock_in'], entry['clock_out'], entry['status'], 
                  entry['hours'], entry['id']))
        conn.commit()
        conn.close()

        QMessageBox.information(self.window, "Success", "Timesheet changes saved successfully!")
        self.load_all_timesheets()  # Refresh table

    def close(self):
        self.window.close()
        self.on_close()

    def show(self):
        self.window.show()

# ---------------------------------------------------------------------------
# Dashboard Window
# ---------------------------------------------------------------------------

class DashboardWindow:

    def __init__(self, company, on_back):
        self.company  = company
        self.on_back  = on_back
        self._add_window = None
        self._timesheet_window = None

        self.window = load_ui("dashboard.ui")

        # Fix for sqlite3.Row
        company_dict = dict(self.company)
        display = company_dict["name"]
        if company_dict.get("trading_name"):
            display += f"  (t/a {company_dict['trading_name']})"
        self.window.lblCompany.setText(display)

        header = self.window.tblEmployees.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        # Button connections
        self.window.btnAddEmployee.clicked.connect(self.open_add_employee)
        self.window.btnEditEmployee.clicked.connect(self.edit_employee)
        self.window.btnDeactivate.clicked.connect(self.deactivate_employee)
        self.window.btnBack.clicked.connect(self.go_back)
        self.window.txtSearch.textChanged.connect(self.filter_table)
        self.window.btnViewDetails.clicked.connect(self.open_employee_details)
        
        if hasattr(self.window, 'btnEnterTimesheet'):
            self.window.btnEnterTimesheet.clicked.connect(self.open_timesheet_entry)

        self.refresh_employees()

    def refresh_employees(self):
        self._all_employees = database.get_employees_for_company(self.company["id"])
        self._populate_table(self._all_employees)

    def _populate_table(self, employees):
        tbl = self.window.tblEmployees
        tbl.setRowCount(0)

        for emp in employees:
            emp_dict = dict(emp)
            row = tbl.rowCount()
            tbl.insertRow(row)

            if emp_dict["salary_type"] == "Monthly":
                pay_str = f"R {emp_dict['monthly_salary']:,.2f} /mo"
            else:
                pay_str = f"R {emp_dict['hourly_rate']:,.2f} /hr"

            values = [
                emp_dict["employee_number"], emp_dict["full_name"], emp_dict.get("job_title",""),
                emp_dict.get("department",""), emp_dict["salary_type"], pay_str,
                emp_dict["pay_frequency"], emp_dict.get("start_date","")
            ]

            for col, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                item.setData(256, emp_dict["id"])
                tbl.setItem(row, col, item)

    def filter_table(self, text):
        text = text.lower()
        if not text:
            self._populate_table(self._all_employees)
            return
        filtered = [e for e in self._all_employees if text in (e.get("full_name","") or "").lower() or
                    text in (e.get("employee_number","") or "").lower() or
                    text in (e.get("department","") or "").lower()]
        self._populate_table(filtered)

    def _selected_employee_id(self):
        row = self.window.tblEmployees.currentRow()
        if row < 0: return None
        item = self.window.tblEmployees.item(row, 0)
        return item.data(256) if item else None

    def open_add_employee(self):
        self.window.hide()
        self._add_window = AddEmployeeWindow(self.company, self._after_add, self._after_cancel)
        self._add_window.show()

    def edit_employee(self):
        emp_id = self._selected_employee_id()
        if emp_id is None:
            QMessageBox.information(self.window, "No Selection", "Please select an employee first.")
            return

        employees = database.get_employees_for_company(self.company["id"], active_only=False)
        employee = next((e for e in employees if e["id"] == emp_id), None)
        if not employee:
            QMessageBox.warning(self.window, "Error", "Employee not found.")
            return

        self.window.hide()
        self._add_window = AddEmployeeWindow(self.company, self._after_edit, self._after_cancel, employee)
        self._add_window.show()

    def _after_add(self):
        self.refresh_employees()
        self.window.show()

    def _after_edit(self):
        self.refresh_employees()
        self.window.show()

    def _after_cancel(self):
        self.window.show()

    def open_timesheet_entry(self):
        self.window.hide()
        self._timesheet_window = TimesheetEntryWindow(self.company, self._after_timesheet_close)
        self._timesheet_window.show()

    def _after_timesheet_close(self):
        self.window.show()

    def deactivate_employee(self):
        # ... keep your existing code
        emp_id = self._selected_employee_id()
        if emp_id is None:
            QMessageBox.information(self.window, "No Selection", "Please select an employee first.")
            return
        row = self.window.tblEmployees.currentRow()
        name = self.window.tblEmployees.item(row, 1).text()
        reply = QMessageBox.question(self.window, "Confirm", f"Deactivate '{name}'?", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            conn = database.get_connection()
            conn.execute("UPDATE employees SET active = 0 WHERE id = ?", (emp_id,))
            conn.commit()
            conn.close()
            self.refresh_employees()

    def go_back(self):
        self.window.close()
        self.on_back()

    def show(self):
        self.window.show()

    def open_employee_details(self):
        emp_id = self._selected_employee_id()
        if emp_id is None:
            QMessageBox.information(self.window, "No Selection", "Please select an employee first.")
            return

        employees = database.get_employees_for_company(self.company["id"], active_only=False)
        employee = next((e for e in employees if e["id"] == emp_id), None)
        if not employee:
            QMessageBox.warning(self.window, "Error", "Employee not found.")
            return

        self.window.hide()
        self._details_window = EmployeeDetailsWindow(
            company=self.company,
            employee=employee,
            on_close=self._after_details_close
        )
        self._details_window.show()

    def _after_details_close(self):
        self.window.show()

# ---------------------------------------------------------------------------
# Create Company window
# ---------------------------------------------------------------------------

class CreateCompanyWindow:

    def __init__(self, user, on_saved, on_cancel):
        self.user      = user
        self.on_saved  = on_saved
        self.on_cancel = on_cancel

        self.window = load_ui("create_company.ui")
        self.window.btnSave.clicked.connect(self.save)
        self.window.btnCancel.clicked.connect(self.cancel)

    def save(self):
        ok, msg = database.create_company(
            user_id          = self.user["id"],
            name             = self.window.txtName.text(),
            trading_name     = self.window.txtTradingName.text(),
            reg_number       = self.window.txtRegNumber.text(),
            tax_number       = self.window.txtTaxNumber.text(),
            paye_number      = self.window.txtPaye.text(),
            uif_number       = self.window.txtUif.text(),
            physical_address = self.window.txtPhysical.toPlainText(),
            postal_address   = self.window.txtPostal.toPlainText(),
            phone            = self.window.txtPhone.text(),
            email            = self.window.txtEmail.text(),
        )
        if ok:
            name = self.window.txtName.text().strip()
            QMessageBox.information(self.window, "Saved",
                                    f"'{name}' has been created successfully.")
            self.window.close()
            self.on_saved()
        else:
            QMessageBox.warning(self.window, "Validation Error", msg)

    def cancel(self):
        self.window.close()
        self.on_cancel()

    def show(self):
        for w in [self.window.txtName, self.window.txtTradingName,
                  self.window.txtRegNumber, self.window.txtTaxNumber,
                  self.window.txtPaye, self.window.txtUif,
                  self.window.txtPhone, self.window.txtEmail]:
            w.clear()
        self.window.txtPhysical.clear()
        self.window.txtPostal.clear()
        self.window.show()


# ---------------------------------------------------------------------------
# Select Company window
# ---------------------------------------------------------------------------

class SelectCompanyWindow:

    def __init__(self, user, on_logout):
        self.user      = user
        self.on_logout = on_logout
        self._create_window    = None
        self._dashboard_window = None

        self.window = load_ui("select_company.ui")
        self.window.lblUser.setText(f"Logged in as:  {user['username']}")

        self.window.btnOpen.clicked.connect(self.open_company)
        self.window.btnCreate.clicked.connect(self.open_create)
        self.window.btnDelete.clicked.connect(self.delete_company)   # NEW
        self.window.btnLogout.clicked.connect(self.logout)

        self.refresh_list()

    def refresh_list(self):
        self.window.lstCompanies.clear()
        self._companies = database.get_companies_for_user(self.user["id"])

        if self._companies:
            self.window.lblNoCompanies.hide()
            for company in self._companies:
                display = company["name"]
                if company["trading_name"]:
                    display += f"  (t/a {company['trading_name']})"
                item = QListWidgetItem(display)
                item.setData(256, company["id"])
                self.window.lstCompanies.addItem(item)
        else:
            self.window.lblNoCompanies.show()

    def open_company(self):
        selected = self.window.lstCompanies.currentItem()
        if not selected:
            QMessageBox.information(self.window, "No Selection",
                                    "Please select a company from the list first.")
            return

        company_id = selected.data(256)
        company    = next(c for c in self._companies if c["id"] == company_id)

        self.window.hide()
        self._dashboard_window = DashboardWindow(
            company = company,
            on_back = self._after_dashboard_back
        )
        self._dashboard_window.show()

    def delete_company(self):
        selected = self.window.lstCompanies.currentItem()
        if not selected:
            QMessageBox.information(self.window, "No Selection",
                                    "Please select a company to delete.")
            return

        company_id = selected.data(256)
        company_name = selected.text()

        reply = QMessageBox.question(
            self.window, "Confirm Deletion",
            f"Delete company '{company_name}'?\n\n"
            "This will permanently delete the company and ALL its employees.\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            ok, msg = database.delete_company(company_id)
            if ok:
                QMessageBox.information(self.window, "Deleted",
                                        f"Company '{company_name}' has been deleted.")
                self.refresh_list()
            else:
                QMessageBox.warning(self.window, "Delete Failed", msg)

    # ... rest of methods unchanged
    def _after_dashboard_back(self):
        self.refresh_list()
        self.window.show()

    def open_create(self):
        self.window.hide()
        self._create_window = CreateCompanyWindow(
            user      = self.user,
            on_saved  = self._after_save,
            on_cancel = self._after_cancel
        )
        self._create_window.show()

    def _after_save(self):
        self.refresh_list()
        self.window.show()

    def _after_cancel(self):
        self.window.show()

    def logout(self):
        self.window.close()
        self.on_logout()

    def show(self):
        self.window.show()


# ---------------------------------------------------------------------------
# Register window
# ---------------------------------------------------------------------------

class RegisterWindow:

    def __init__(self, on_back):
        self.on_back = on_back
        self.window  = load_ui("register.ui")
        self.window.btnRegister.clicked.connect(self.register)
        self.window.btnBack.clicked.connect(self.go_back)

    def register(self):
        username = self.window.txtUsername.text().strip()
        email    = self.window.txtEmail.text().strip()
        password = self.window.txtPassword.text()
        confirm  = self.window.txtConfirm.text()

        if not username:
            QMessageBox.warning(self.window, "Validation", "Username is required.")
            return
        if len(password) < 4:
            QMessageBox.warning(self.window, "Validation",
                                "Password must be at least 4 characters.")
            return
        if password != confirm:
            QMessageBox.warning(self.window, "Validation", "Passwords do not match.")
            return

        ok, msg = database.register_user(username, password, email)
        if ok:
            QMessageBox.information(self.window, "Success",
                                    f"Account created for '{username}'.\nYou can now log in.")
            self.go_back()
        else:
            QMessageBox.warning(self.window, "Registration Failed", msg)

    def go_back(self):
        self.window.close()
        self.on_back()

    def show(self):
        self.window.show()


# ---------------------------------------------------------------------------
# Login window
# ---------------------------------------------------------------------------

class LoginWindow:

    def __init__(self):
        self.window = load_ui("login.ui")
        self.window.btnLogin.clicked.connect(self.login)
        self.window.btnRegister.clicked.connect(self.open_register)
        self._register_window       = None
        self._select_company_window = None

    def login(self):
        username = self.window.txtUsername.text().strip()
        password = self.window.txtPassword.text()

        if not username or not password:
            QMessageBox.warning(self.window, "Login Failed",
                                "Please enter your username and password.")
            return

        user = database.login_user(username, password)
        if user:
            self.window.hide()
            self._select_company_window = SelectCompanyWindow(
                user      = user,
                on_logout = self._after_logout
            )
            self._select_company_window.show()
        else:
            QMessageBox.warning(self.window, "Login Failed",
                                "Invalid username or password.")

    def open_register(self):
        self.window.hide()
        self._register_window = RegisterWindow(on_back=self.show)
        self._register_window.show()

    def _after_logout(self):
        self.show()

    def show(self):
        self.window.txtUsername.clear()
        self.window.txtPassword.clear()
        self.window.show()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

database.init_db()

app = QApplication(sys.argv)

login = LoginWindow()
login.show()

sys.exit(app.exec())