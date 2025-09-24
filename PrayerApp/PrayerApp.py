import os
from datetime import datetime
from typing import List, Tuple

import pandas as pd
import reflex as rx
from rxconfig import config  # keep if you have rxconfig.py; safe to leave


# ---------- CSV loaders ----------

def _csv_path(filename: str) -> str:
    """Return absolute path for a CSV in the same folder as this file."""
    return os.path.join(os.path.dirname(__file__), filename)


def _format_phone_number(phone: str) -> str:
    """Format phone number from 1234567890 to (123) 456-7890"""
    # Remove any non-digit characters
    digits = ''.join(filter(str.isdigit, phone))
    
    # Check if it's a 10-digit US phone number
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    
    # Return original if not 10 digits
    return phone


def _read_csv_safe(path: str) -> Tuple[List[str], List[List[str]]]:
    """
    Read a CSV and return (headers, rows) as strings, with NaNs -> "".
    If file missing/invalid, raise an exception.
    """
    # Read CSV with all columns as strings to prevent numeric conversion
    df = pd.read_csv(path, dtype=str)
    # Convert headers to strings
    headers = [str(col) for col in df.columns.tolist()]
    # Convert all values to strings, replacing NaN with ""
    rows = []
    for _, row in df.iterrows():
        string_row = [str(cell) if pd.notna(cell) and cell != 'nan' else "" for cell in row]
        rows.append(string_row)
    return headers, rows


def load_schedule_from_csv() -> Tuple[List[str], List[List[str]]]:
    """Load schedule data; fallback to default rows if it fails."""
    try:
        headers, rows = _read_csv_safe(_csv_path("schedule.csv"))
        print(f"Loaded {len(rows)} rows with {len(headers)} columns from schedule.csv")
        print(f"Columns: {headers}")
        return headers, rows
    except Exception as e:
        print(f"Error loading schedule.csv: {e}")
        # Fallback data (Date, Event)
        return (
            ["Date", "Event"],
            [
                ["09/12/2025", "Opening CG Gathering"],
                ["09/19/2025", "Discussion"],
                ["Error", "Could not load schedule.csv - using fallback data"],
            ],
        )


def load_members_from_csv() -> Tuple[List[str], List[List[str]]]:
    """Load members data; fallback to empty if missing."""
    try:
        headers, rows = _read_csv_safe(_csv_path("members.csv"))
        
        # Format phone numbers in Contact column if it exists
        if "Contact" in headers:
            contact_index = headers.index("Contact")
            for row in rows:
                if contact_index < len(row) and row[contact_index]:
                    row[contact_index] = _format_phone_number(row[contact_index])
        
        print(f"Loaded {len(rows)} rows with {len(headers)} columns from members.csv")
        print(f"Columns: {headers}")
        return headers, rows
    except Exception as e:
        print(f"Error loading members.csv: {e}")
        # sensible fallback (empty table)
        return (["Name", "Role"], [])


# ---------- App State ----------

class State(rx.State):
    """The app state."""
    # Auth
    password: str = ""
    show_error: bool = False
    is_authenticated: bool = False

    # Schedules/Members
    schedule_headers: List[str] = []
    schedule_rows: List[List[str]] = []
    members_headers: List[str] = []
    members_rows: List[List[str]] = []

    # UI toggles
    show_members: bool = False
    show_schedule: bool = True

    # Prayer request
    prayer_request_text: str = ""

    # ---- Derived / helpers ----
    @rx.var
    def members_count(self) -> int:
        return len(self.members_rows)

    # ---- Toggles ----
    def toggle_members(self):
        self.show_members = True
        self.show_schedule = False

    def toggle_schedule(self):
        self.show_members = False
        self.show_schedule = True

    # ---- Prayer request ----
    def set_prayer_request(self, text: str):
        self.prayer_request_text = text

    def submit_prayer_request(self):
        text = self.prayer_request_text.strip()
        if not text:
            return rx.toast.error("Please enter a prayer request.")

        try:
            # Create directory
            dir_path = os.path.join(os.path.dirname(__file__), "prayer_requests")
            os.makedirs(dir_path, exist_ok=True)

            # Generate timestamped filename: mm_dd_YYYY_HH_MM_SS.txt
            now = datetime.now()
            filename = now.strftime("%m_%d_%Y_%H_%M_%S.txt")
            filepath = os.path.join(dir_path, filename)

            # Save
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(text)

            # Clear textarea
            self.prayer_request_text = ""
            return rx.toast.success("Prayer request submitted and saved.")
        except Exception as e:
            return rx.toast.error(f"Error saving prayer request: {str(e)}")

    # ---- Data loading on mount ----
    def load_data_on_mount(self):
        if not self.schedule_headers or not self.schedule_rows:
            h, r = load_schedule_from_csv()
            self.schedule_headers = h
            self.schedule_rows = r

        if not self.members_headers or not self.members_rows:
            h, r = load_members_from_csv()
            self.members_headers = h
            self.members_rows = r

    # ---- Auth handlers ----
    def set_password(self, value: str):
        self.password = value
        if self.show_error:
            self.show_error = False

    def submit_password(self):
        # change this keyword to whatever you want
        if self.password == "2ndstreet":
            self.is_authenticated = True
            return rx.redirect("/home")
        else:
            self.show_error = True

    def handle_key_down(self, key: str):
        if key == "Enter":
            return self.submit_password()

    def logout(self):
        self.is_authenticated = False
        self.password = ""
        self.show_error = False
        return rx.redirect("/")

    def check_auth_and_redirect(self):
        if not self.is_authenticated:
            return rx.redirect("/")
        return None


# ---------- UI Components ----------

def index() -> rx.Component:
    """Login page."""
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.vstack(
                rx.text("Enter keyword to access:", size="4", weight="bold"),
                rx.input(
                    placeholder="keyword",
                    type="password",
                    value=State.password,
                    on_change=State.set_password,
                    on_key_down=State.handle_key_down,
                    width="300px",
                ),
                rx.cond(
                    State.show_error,
                    rx.text("Keyword is incorrect.", color="red", size="2"),
                    rx.text("", size="2"),
                ),
                rx.button(
                    "Submit",
                    on_click=State.submit_password,
                    width="300px",
                    color_scheme="blue",
                ),
                spacing="2",
                align="center",
            ),
            spacing="5",
            justify="center",
            align="center",
            min_height="85vh",
            width="100%",
        ),
        display="flex",
        justify_content="center",
        align_items="center",
        width="100%",
        min_height="100vh",
    )


def _table_from(headers: List[str], rows: List[List[str]]) -> rx.Component:
    """Helper to render a responsive table from headers/rows."""
    return rx.box(
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.foreach(headers, lambda h: rx.table.column_header_cell(h))
                )
            ),
            rx.table.body(
                rx.foreach(
                    rows,
                    lambda row: rx.table.row(
                        rx.foreach(
                            row,
                            lambda cell: rx.table.cell(cell, white_space="nowrap"),
                        )
                    ),
                )
            ),
        ),
        width="100%",
        overflow_x="auto",
    )


def home() -> rx.Component:
    """Home page (protected)."""
    return rx.cond(
        State.is_authenticated,
        rx.container(
            rx.color_mode.button(position="top-right"),
            rx.vstack(
                # Toggle buttons
                rx.hstack(
                    rx.button(
                        "Schedule",
                        on_click=State.toggle_schedule,
                        color_scheme=rx.cond(State.show_schedule, "blue", "gray"),
                        variant=rx.cond(State.show_schedule, "solid", "outline"),
                        size="3",
                        width="180px",
                    ),
                    rx.button(
                        rx.text(f"Members ({State.members_count})"),
                        on_click=State.toggle_members,
                        color_scheme=rx.cond(State.show_members, "blue", "gray"),
                        variant=rx.cond(State.show_members, "solid", "outline"),
                        size="3",
                        width="180px",
                    ),
                    rx.link(
                        rx.button(
                            "Prayer Requests",
                            color_scheme="green",
                            variant="solid",
                            size="3",
                            width="180px",
                        ),
                        href="/prayer_requests",
                    ),
                    spacing="4",
                    justify="center",
                ),
                # Conditional table display
                rx.cond(
                    State.show_members,
                    _table_from(State.members_headers, State.members_rows),
                    _table_from(State.schedule_headers, State.schedule_rows),
                ),
                spacing="5",
                align="center",
                width="100%",
            ),
            padding="2rem",
            width="100%",
            on_mount=State.load_data_on_mount,
        ),
        # Not authenticated -> loading/redirect view
        rx.container(
            rx.vstack(
                rx.text("Redirecting to login...", size="5"),
                spacing="5",
                justify="center",
                align="center",
                min_height="85vh",
            ),
            display="flex",
            justify_content="center",
            align_items="center",
            width="100%",
            min_height="100vh",
            on_mount=State.check_auth_and_redirect,
        ),
    )


def prayer_requests() -> rx.Component:
    """Prayer Requests page (protected)."""
    return rx.cond(
        State.is_authenticated,
        rx.container(
            rx.color_mode.button(position="top-right"),
            rx.vstack(
                rx.text("Submit your prayer requests here:", size="5"),
                rx.vstack(
                    rx.text_area(
                        placeholder="Please share your prayer request here...",
                        value=State.prayer_request_text,
                        on_change=State.set_prayer_request,
                        width="100%",
                        max_width="600px",
                        height="200px",
                        resize="vertical",
                    ),
                    rx.button(
                        "Submit Prayer Request",
                        on_click=State.submit_prayer_request,
                        color_scheme="blue",
                        size="3",
                        width="300px",
                    ),
                    spacing="3",
                    align="center",
                    width="100%",
                ),
                rx.link(
                    rx.button(
                        "Back to Home",
                        color_scheme="gray",
                        size="3",
                    ),
                    href="/home",
                ),
                spacing="6",
                align="center",
                min_height="85vh",
            ),
            padding="2rem",
            display="flex",
            justify_content="center",
            align_items="center",
            width="100%",
            min_height="100vh",
        ),
        # Not authenticated -> loading/redirect view
        rx.container(
            rx.vstack(
                rx.text("Redirecting to login...", size="5"),
                spacing="5",
                justify="center",
                align="center",
                min_height="85vh",
            ),
            display="flex",
            justify_content="center",
            align_items="center",
            width="100%",
            min_height="100vh",
            on_mount=State.check_auth_and_redirect,
        ),
    )


# ---------- App ----------

app = rx.App()
app.add_page(index)
app.add_page(home, route="/home")
app.add_page(prayer_requests, route="/prayer_requests")
