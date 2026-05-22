import sqlite3
import hashlib
from datetime import datetime

DB_NAME = "payroll.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Existing tables...
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT    NOT NULL UNIQUE,
            password TEXT    NOT NULL,
            email    TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER NOT NULL,
            name             TEXT    NOT NULL,
            trading_name     TEXT,
            reg_number       TEXT,
            tax_number       TEXT,
            paye_number      TEXT,
            uif_number       TEXT,
            physical_address TEXT,
            postal_address   TEXT,
            phone            TEXT,
            email            TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id          INTEGER NOT NULL,
            employee_number     TEXT    NOT NULL,
            full_name           TEXT    NOT NULL,
            id_number           TEXT,
            tax_number          TEXT,
            tax_directive       TEXT,
            job_title           TEXT,
            department          TEXT,
            employment_type     TEXT    DEFAULT 'Permanent',
            salary_type         TEXT    DEFAULT 'Monthly',
            monthly_salary      REAL    DEFAULT 0,
            hourly_rate         REAL    DEFAULT 0,
            pay_frequency       TEXT    DEFAULT 'Monthly',
            start_date          TEXT,
            end_date            TEXT,
            uif_exempt          INTEGER DEFAULT 0,
            phone               TEXT,
            email               TEXT,
            bank_name           TEXT,
            bank_account_number TEXT,
            bank_account_type   TEXT,
            bank_branch_code    TEXT,
            emergency_contact   TEXT,
            emergency_phone     TEXT,
            active              INTEGER DEFAULT 1,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)

    # === NEW: Timesheets Table ===
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS timesheets (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id    INTEGER NOT NULL,
            employee_id   INTEGER NOT NULL,
            date          TEXT    NOT NULL,
            clock_in      TEXT,
            clock_out     TEXT,
            status        TEXT    DEFAULT 'Present',
            hours         REAL    DEFAULT 0,
            amount        REAL    DEFAULT 0,
            notes         TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id),
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            UNIQUE(company_id, employee_id, date)
        )
    """)

    conn.commit()
    conn.close()

# ---------- User functions ----------
def register_user(username: str, password: str, email: str = "") -> tuple[bool, str]:
    try:
        conn = get_connection()
        conn.execute(
            "INSERT INTO users (username, password, email) VALUES (?, ?, ?)",
            (username.strip(), hash_password(password), email.strip())
        )
        conn.commit()
        conn.close()
        return True, "ok"
    except sqlite3.IntegrityError:
        return False, "Username already exists"

def login_user(username: str, password: str):
    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ? AND password = ?",
        (username.strip(), hash_password(password))
    ).fetchone()
    conn.close()
    return user

# ---------- Company functions ----------
def get_companies_for_user(user_id: int) -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM companies WHERE user_id = ? ORDER BY name",
        (user_id,)
    ).fetchall()
    conn.close()
    return rows

def create_company(user_id: int, name: str, trading_name: str = "",
                   reg_number: str = "", tax_number: str = "",
                   paye_number: str = "", uif_number: str = "",
                   physical_address: str = "", postal_address: str = "",
                   phone: str = "", email: str = "") -> tuple[bool, str]:

    if not name.strip():
        return False, "Company name is required"
    if not physical_address.strip():
        return False, "Physical address is required"

    try:
        conn = get_connection()
        conn.execute(
            """INSERT INTO companies
               (user_id, name, trading_name, reg_number, tax_number,
                paye_number, uif_number, physical_address, postal_address,
                phone, email)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, name.strip(), trading_name.strip(), reg_number.strip(),
             tax_number.strip(), paye_number.strip(), uif_number.strip(),
             physical_address.strip(), postal_address.strip(),
             phone.strip(), email.strip())
        )
        conn.commit()
        conn.close()
        return True, "ok"
    except Exception as e:
        return False, str(e)

# ---------- Employee functions ----------
def get_employees_for_company(company_id: int, active_only: bool = True) -> list:
    conn = get_connection()
    if active_only:
        rows = conn.execute(
            "SELECT * FROM employees WHERE company_id = ? AND active = 1 ORDER BY full_name",
            (company_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM employees WHERE company_id = ? ORDER BY full_name",
            (company_id,)
        ).fetchall()
    conn.close()
    return rows

def employee_number_exists(company_id: int, employee_number: str, exclude_id: int = None) -> bool:
    conn = get_connection()
    query = "SELECT id FROM employees WHERE company_id = ? AND employee_number = ?"
    params = [company_id, employee_number.strip()]
    if exclude_id:
        query += " AND id != ?"
        params.append(exclude_id)
    row = conn.execute(query, params).fetchone()
    conn.close()
    return row is not None

def create_employee(company_id: int, employee_number: str, full_name: str,
                    id_number: str = "", tax_number: str = "",
                    tax_directive: str = "", job_title: str = "",
                    department: str = "", employment_type: str = "Permanent",
                    salary_type: str = "Monthly", monthly_salary: float = 0,
                    hourly_rate: float = 0, pay_frequency: str = "Monthly",
                    start_date: str = "", end_date: str = "",
                    uif_exempt: bool = False, phone: str = "", email: str = "",
                    bank_name: str = "", bank_account_number: str = "",
                    bank_account_type: str = "", bank_branch_code: str = "",
                    emergency_contact: str = "",
                    emergency_phone: str = "") -> tuple[bool, str]:

    if not full_name.strip():
        return False, "Full name is required"
    if not employee_number.strip():
        return False, "Employee number is required"
    if employee_number_exists(company_id, employee_number):
        return False, f"Employee number '{employee_number}' already exists in this company"
    if salary_type == "Monthly" and monthly_salary <= 0:
        return False, "Monthly salary must be greater than zero"
    if salary_type == "Hourly" and hourly_rate <= 0:
        return False, "Hourly rate must be greater than zero"

    try:
        conn = get_connection()
        conn.execute(
            """INSERT INTO employees
               (company_id, employee_number, full_name, id_number, tax_number,
                tax_directive, job_title, department, employment_type,
                salary_type, monthly_salary, hourly_rate, pay_frequency,
                start_date, end_date, uif_exempt, phone, email,
                bank_name, bank_account_number, bank_account_type,
                bank_branch_code, emergency_contact, emergency_phone, active)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
            (company_id, employee_number.strip(), full_name.strip(),
             id_number.strip(), tax_number.strip(), tax_directive.strip(),
             job_title.strip(), department.strip(), employment_type,
             salary_type, monthly_salary, hourly_rate, pay_frequency,
             start_date, end_date, 1 if uif_exempt else 0,
             phone.strip(), email.strip(), bank_name.strip(),
             bank_account_number.strip(), bank_account_type,
             bank_branch_code.strip(), emergency_contact.strip(),
             emergency_phone.strip())
        )
        conn.commit()
        conn.close()
        return True, "ok"
    except Exception as e:
        return False, str(e)

def update_employee(employee_id: int, company_id: int, employee_number: str, full_name: str,
                    id_number: str = "", tax_number: str = "",
                    tax_directive: str = "", job_title: str = "",
                    department: str = "", employment_type: str = "Permanent",
                    salary_type: str = "Monthly", monthly_salary: float = 0,
                    hourly_rate: float = 0, pay_frequency: str = "Monthly",
                    start_date: str = "", end_date: str = "",
                    uif_exempt: bool = False, phone: str = "", email: str = "",
                    bank_name: str = "", bank_account_number: str = "",
                    bank_account_type: str = "", bank_branch_code: str = "",
                    emergency_contact: str = "",
                    emergency_phone: str = "") -> tuple[bool, str]:

    if not full_name.strip():
        return False, "Full name is required"
    if not employee_number.strip():
        return False, "Employee number is required"
    if employee_number_exists(company_id, employee_number, exclude_id=employee_id):
        return False, f"Employee number '{employee_number}' already exists in this company"
    if salary_type == "Monthly" and monthly_salary <= 0:
        return False, "Monthly salary must be greater than zero"
    if salary_type == "Hourly" and hourly_rate <= 0:
        return False, "Hourly rate must be greater than zero"

    try:
        conn = get_connection()
        conn.execute(
            """UPDATE employees SET
                employee_number = ?, full_name = ?, id_number = ?, tax_number = ?,
                tax_directive = ?, job_title = ?, department = ?, employment_type = ?,
                salary_type = ?, monthly_salary = ?, hourly_rate = ?, pay_frequency = ?,
                start_date = ?, end_date = ?, uif_exempt = ?, phone = ?, email = ?,
                bank_name = ?, bank_account_number = ?, bank_account_type = ?,
                bank_branch_code = ?, emergency_contact = ?, emergency_phone = ?
               WHERE id = ? AND company_id = ?""",
            (employee_number.strip(), full_name.strip(),
             id_number.strip(), tax_number.strip(), tax_directive.strip(),
             job_title.strip(), department.strip(), employment_type,
             salary_type, monthly_salary, hourly_rate, pay_frequency,
             start_date, end_date, 1 if uif_exempt else 0,
             phone.strip(), email.strip(), bank_name.strip(),
             bank_account_number.strip(), bank_account_type,
             bank_branch_code.strip(), emergency_contact.strip(),
             emergency_phone.strip(), employee_id, company_id)
        )
        conn.commit()
        conn.close()
        return True, "ok"
    except Exception as e:
        return False, str(e)

# ---------- Company Delete Function ----------
def delete_company(company_id: int) -> tuple[bool, str]:
    try:
        conn = get_connection()
        conn.execute("DELETE FROM employees WHERE company_id = ?", (company_id,))
        conn.execute("DELETE FROM companies WHERE id = ?", (company_id,))
        conn.commit()
        conn.close()
        return True, "ok"
    except Exception as e:
        return False, str(e)
    
    # ==================== Existing functions (unchanged) ====================
# ... [All your existing functions: register_user, login_user, companies, employees, etc.]

def get_employees_for_company(company_id: int, active_only: bool = True) -> list:
    conn = get_connection()
    if active_only:
        rows = conn.execute(
            "SELECT * FROM employees WHERE company_id = ? AND active = 1 ORDER BY full_name",
            (company_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM employees WHERE company_id = ? ORDER BY full_name",
            (company_id,)
        ).fetchall()
    conn.close()
    return rows

# ==================== NEW TIMESHEET FUNCTIONS ====================

def save_daily_timesheet(company_id: int, date: str, entries: list) -> tuple[bool, str]:
    """entries = list of dicts: {'employee_id', 'clock_in', 'clock_out', 'status', 'hours', 'amount'}"""
    try:
        conn = get_connection()
        for entry in entries:
            conn.execute("""
                INSERT INTO timesheets 
                (company_id, employee_id, date, clock_in, clock_out, status, hours, amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(company_id, employee_id, date) 
                DO UPDATE SET 
                    clock_in = excluded.clock_in,
                    clock_out = excluded.clock_out,
                    status = excluded.status,
                    hours = excluded.hours,
                    amount = excluded.amount
            """, (
                company_id, 
                entry['employee_id'], 
                date, 
                entry.get('clock_in'),
                entry.get('clock_out'),
                entry.get('status', 'Present'),
                entry.get('hours', 0),
                entry.get('amount', 0)
            ))
        conn.commit()
        conn.close()
        return True, "Timesheet saved successfully"
    except Exception as e:
        return False, str(e)
    
def get_employee_timesheet_for_date(company_id: int, employee_id: int, date: str):
    """Get timesheet for ONE specific employee on a specific date"""
    conn = get_connection()
    rows = conn.execute("""
        SELECT t.*, e.full_name, e.employee_number 
        FROM timesheets t
        JOIN employees e ON t.employee_id = e.id
        WHERE t.company_id = ? AND t.employee_id = ? AND t.date = ?
        ORDER BY t.date
    """, (company_id, employee_id, date)).fetchall()
    conn.close()
    return rows

def get_timesheet_for_date(company_id: int, date: str):
    conn = get_connection()
    rows = conn.execute("""
        SELECT t.*, e.full_name, e.employee_number, e.salary_type, e.hourly_rate 
        FROM timesheets t
        JOIN employees e ON t.employee_id = e.id
        WHERE t.company_id = ? AND t.date = ?
        ORDER BY e.full_name
    """, (company_id, date)).fetchall()
    conn.close()
    return rows