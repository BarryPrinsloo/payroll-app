import sys
import os


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


from PySide6.QtWidgets import (
    QApplication, QMessageBox, QListWidgetItem,
    QTableWidgetItem, QHeaderView
)
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile, QDate
from PySide6.QtGui import QColor

import database


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def load_ui(filename):
    loader = QUiLoader()
    ui_file = QFile(resource_path(filename))
    ui_file.open(QFile.ReadOnly)
    window = loader.load(ui_file)
    ui_file.close()
    return window


# ---------------------------------------------------------------------------
# Add Employee window
# ---------------------------------------------------------------------------

class AddEmployeeWindow:

    def __init__(self, company, on_saved, on_cancel):
        self.company   = company
        self.on_saved  = on_saved
        self.on_cancel = on_cancel

        self.window = load_ui("add_employee.ui")

        # Set today as default start date
        self.window.dtStartDate.setDate(QDate.currentDate())
        # Clear end date (set to minimum so specialValueText shows)
        self.window.dtEndDate.setMinimumDate(QDate(2000, 1, 1))
        self.window.dtEndDate.setDate(QDate(2000, 1, 1))

        # Show/hide salary fields based on salary type selection
        self.window.cmbSalaryType.currentTextChanged.connect(self._on_salary_type_changed)
        self._on_salary_type_changed(self.window.cmbSalaryType.currentText())

        self.window.btnSave.clicked.connect(self.save)
        self.window.btnCancel.clicked.connect(self.cancel)

    def _on_salary_type_changed(self, salary_type):
        is_monthly = salary_type == "Monthly"
        self.window.spnMonthlySalary.setVisible(is_monthly)
        self.window.lblMonthlySalary.setVisible(is_monthly)
        self.window.spnHourlyRate.setVisible(not is_monthly)
        self.window.lblHourlyRate.setVisible(not is_monthly)

    def save(self):
        salary_type = self.window.cmbSalaryType.currentText()

        end_date_val = self.window.dtEndDate.date()
        end_date = (end_date_val.toString("yyyy-MM-dd")
                    if end_date_val > QDate(2000, 1, 1) else "")

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

        if ok:
            name = self.window.txtFullName.text().strip()
            QMessageBox.information(self.window, "Saved",
                                    f"'{name}' has been added successfully.")
            self.window.close()
            self.on_saved()
        else:
            QMessageBox.warning(self.window, "Validation Error", msg)

    def cancel(self):
        self.window.close()
        self.on_cancel()

    def show(self):
        # Reset all fields
        self.window.txtEmployeeNumber.clear()
        self.window.txtFullName.clear()
        self.window.txtIdNumber.clear()
        self.window.txtTaxNumber.clear()
        self.window.txtPhone.clear()
        self.window.txtEmail.clear()
        self.window.txtJobTitle.clear()
        self.window.txtDepartment.clear()
        self.window.cmbEmploymentType.setCurrentIndex(0)
        self.window.cmbPayFrequency.setCurrentIndex(0)
        self.window.cmbSalaryType.setCurrentIndex(0)
        self.window.spnMonthlySalary.setValue(0)
        self.window.spnHourlyRate.setValue(0)
        self.window.dtStartDate.setDate(QDate.currentDate())
        self.window.dtEndDate.setDate(QDate(2000, 1, 1))
        self.window.chkUifExempt.setChecked(False)
        self.window.cmbBankName.setCurrentIndex(0)
        self.window.cmbAccountType.setCurrentIndex(0)
        self.window.txtAccountNumber.clear()
        self.window.txtBranchCode.clear()
        self.window.txtEmergencyContact.clear()
        self.window.txtEmergencyPhone.clear()
        self.window.show()


# ---------------------------------------------------------------------------
# Dashboard window
# ---------------------------------------------------------------------------

class DashboardWindow:

    COLUMNS = [
        "employee_number", "full_name", "job_title", "department",
        "salary_type", "monthly_salary", "pay_frequency", "start_date"
    ]

    def __init__(self, company, on_back):
        self.company  = company
        self.on_back  = on_back
        self._add_window = None

        self.window = load_ui("dashboard.ui")

        # Set company name in header
        display = company["name"]
        if company["trading_name"]:
            display += f"  (t/a {company['trading_name']})"
        self.window.lblCompany.setText(display)

        # Stretch table columns to fill width
        header = self.window.tblEmployees.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        # Wire buttons and search
        self.window.btnAddEmployee.clicked.connect(self.open_add_employee)
        self.window.btnEditEmployee.clicked.connect(self.edit_employee)
        self.window.btnDeactivate.clicked.connect(self.deactivate_employee)
        self.window.btnBack.clicked.connect(self.go_back)
        self.window.txtSearch.textChanged.connect(self.filter_table)

        self.refresh_employees()

    def refresh_employees(self):
        self._all_employees = database.get_employees_for_company(self.company["id"])
        self._populate_table(self._all_employees)

    def _populate_table(self, employees):
        tbl = self.window.tblEmployees
        tbl.setRowCount(0)

        for emp in employees:
            row = tbl.rowCount()
            tbl.insertRow(row)

            # Build salary/rate display string
            if emp["salary_type"] == "Monthly":
                pay_str = f"R {emp['monthly_salary']:,.2f} /mo"
            else:
                pay_str = f"R {emp['hourly_rate']:,.2f} /hr"

            values = [
                emp["employee_number"],
                emp["full_name"],
                emp["job_title"]    or "",
                emp["department"]   or "",
                emp["salary_type"],
                pay_str,
                emp["pay_frequency"],
                emp["start_date"]   or "",
            ]

            for col, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                item.setData(256, emp["id"])   # store employee id on every cell
                tbl.setItem(row, col, item)

    def filter_table(self, text):
        text = text.lower()
        if not text:
            self._populate_table(self._all_employees)
            return
        filtered = [
            e for e in self._all_employees
            if text in (e["full_name"] or "").lower()
            or text in (e["employee_number"] or "").lower()
            or text in (e["department"] or "").lower()
        ]
        self._populate_table(filtered)

    def _selected_employee_id(self):
        row = self.window.tblEmployees.currentRow()
        if row < 0:
            return None
        item = self.window.tblEmployees.item(row, 0)
        return item.data(256) if item else None

    def open_add_employee(self):
        self.window.hide()
        self._add_window = AddEmployeeWindow(
            company   = self.company,
            on_saved  = self._after_add,
            on_cancel = self._after_cancel
        )
        self._add_window.show()

    def _after_add(self):
        self.refresh_employees()
        self.window.show()

    def _after_cancel(self):
        self.window.show()

    def edit_employee(self):
        emp_id = self._selected_employee_id()
        if emp_id is None:
            QMessageBox.information(self.window, "No Selection",
                                    "Please select an employee row first.")
            return
        # TODO: open edit employee window (next step)
        QMessageBox.information(self.window, "Edit",
                                f"Edit employee ID {emp_id} — coming in the next step.")

    def deactivate_employee(self):
        emp_id = self._selected_employee_id()
        if emp_id is None:
            QMessageBox.information(self.window, "No Selection",
                                    "Please select an employee row first.")
            return

        row  = self.window.tblEmployees.currentRow()
        name = self.window.tblEmployees.item(row, 1).text()

        reply = QMessageBox.question(
            self.window, "Confirm Deactivation",
            f"Deactivate '{name}'?\nThey will no longer appear in the active list.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
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
