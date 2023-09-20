from gspread import service_account, Spreadsheet


class SheetsDriver:
    def __init__(self, credentials_file: str):
        self.service = service_account(filename=credentials_file)

    def open_by_key(self, sheet_id: str) -> Spreadsheet:
        return self.service.open_by_key(sheet_id)
