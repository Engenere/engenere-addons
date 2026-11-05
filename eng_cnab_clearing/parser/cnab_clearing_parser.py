# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import datetime

from odoo import _, fields
from odoo.exceptions import UserError

from odoo.addons.l10n_br_account_payment_brcobranca.parser.cnab_file_parser import (
    CNABFileParser,
    dict_brcobranca_bank,
)

# Type of the single clearing account row built for each liquidation
CLEARING_ROW_TYPE = "eng_cnab_clearing"

# Rows of CNABFileParser._get_accounting_entries() kept by the clearing flow,
# with the side that carries their amount. The opposite row of each pair goes
# through the bank account of the journal and is dropped, like both tariff
# rows.
RESULT_ROW_SIDES = {
    "desconto": "debit",
    "abatimento": "debit",
    "juros_mora": "credit",
}

# Banks whose statement splits the daily collection credit by receiving bank:
# every liquidation of their return files must state the receiving bank. Each
# Ailos credit union is a branch of bank 085, and its statement credits a title
# paid at another credit union together with those of the other banks, so the
# receiving branch counts too.
RECEIVING_BANK_REQUIRED_CODES = ("085",)


class EngClearingCNABParser(CNABFileParser):
    """CNAB return parser of the clearing flow.

    Only a journal with the clearing flow enabled uses it, instantiating it
    directly. The generic lookup (new_move_parser) never returns it, not even
    for a database without this module served by the same process.
    """

    @classmethod
    def parser_for(cls, parser_name):
        return False

    def __init__(self, journal, *args, file_hash=None, **kwargs):
        super().__init__(journal, *args, **kwargs)
        self.file_hash = file_hash
        # Filled by the journal once the return log and its events exist
        self.events_by_position = {}
        self.current_position = None

    # Validation, before any processing

    def process_return_file(self, data):
        """Validate every detail record, then process them one at a time.

        While any record of the file is invalid nothing is processed: no
        cnab_state is written and no occurrence date falls back to the credit
        date or to today. Processing one record at a time ties every event
        and every entry to the position of its record in the file.
        """
        self._eng_validate_records(data)
        result_row_list = []
        for position, record in enumerate(data, start=1):
            first_new_event = len(self.cnab_return_events)
            self.current_position = position
            result_row_list += super().process_return_file([record])
            for event in self.cnab_return_events[first_new_event:]:
                event["eng_record_position"] = position
                event["eng_receiving_bank_code"] = (
                    record.get("banco_recebedor") or False
                )
                event["eng_receiving_branch_code"] = (
                    record.get("agencia_recebedora_com_dv") or False
                )
        return result_row_list

    def _eng_validate_records(self, data):
        bank_name = dict_brcobranca_bank[self.bank.code_bc]
        registration_code = self._get_allowed_registration_code(bank_name)
        date_format = self._get_date_format(bank_name)[1]
        errors = []
        for position, record in enumerate(data, start=1):
            if int(record["codigo_registro"]) != registration_code:
                continue
            for reason in self._eng_get_record_errors(record, bank_name, date_format):
                errors.append(
                    _(
                        "%(record)s (own number %(own_number)s): %(reason)s",
                        record=self._eng_get_record_reference(record, position),
                        own_number=record.get("nosso_numero"),
                        reason=reason,
                    )
                )
        if errors:
            raise UserError(
                _(
                    "The CNAB return file %(file_name)s was not imported because "
                    "some of its records are invalid, and none of its records "
                    "was processed. Ask the bank for a corrected file.\n"
                    "%(errors)s",
                    file_name=self.env.context.get("file_name") or "",
                    errors="\n".join(errors),
                )
            )

    def _eng_get_record_reference(self, record, position):
        """How an error message points to a record of the return file.

        By the sequence number the bank gives the record in the file, when
        it has one. Else by its position in the list of records the
        BRCobranca API reads from the file, which is not a line of the file
        (the list leaves the header out, for instance): the message says
        which of the two references it shows.
        """
        sequence = str(record.get("sequencial") or "").strip().lstrip("0")
        if sequence:
            return _("Record with sequence number %(sequence)s", sequence=sequence)
        return _(
            "Record in position %(position)s of the records read from the file, "
            "which has no sequence number",
            position=position,
        )

    def _eng_get_record_errors(self, record, bank_name, date_format):
        reasons = []
        occurrence_problem = self._eng_get_date_problem(
            record.get("data_ocorrencia"), date_format
        )
        if occurrence_problem == "missing":
            reasons.append(_("the occurrence date is missing"))
        elif occurrence_problem == "zeroed":
            reasons.append(_("the occurrence date is zeroed"))
        elif occurrence_problem == "invalid":
            reasons.append(
                _(
                    "the occurrence date %(value)s is invalid",
                    value=record.get("data_ocorrencia"),
                )
            )
        if self._eng_is_liquidation(record, bank_name):
            if self._eng_get_date_problem(record.get("data_credito"), date_format):
                reasons.append(_("the liquidation has no valid credit date"))
            if self.bank.code_bc in RECEIVING_BANK_REQUIRED_CODES:
                if not self._eng_get_receiving_bank(record):
                    reasons.append(_("the liquidation has no receiving bank"))
                elif not self._eng_get_receiving_bank_class(record):
                    reasons.append(_("the liquidation has no receiving branch"))
        return reasons

    @staticmethod
    def _eng_get_date_problem(value, date_format):
        """Why a CNAB date is unusable: "missing", "zeroed" or "invalid".

        None when the date is valid.
        """
        text = str(value or "").strip()
        if not text:
            return "missing"
        if not text.strip("0"):
            return "zeroed"
        try:
            datetime.datetime.strptime(text, date_format)
        except ValueError:
            return "invalid"
        return None

    def _eng_is_liquidation(self, record, bank_name):
        """Same rule as process_return_file(): the record is a liquidation
        when its occurrence code is a liquidation code of the CNAB config of
        the installment it refers to."""
        installments = self.env["account.move.line"].search(
            [
                (
                    "own_number_without_zfill",
                    "=",
                    self._get_own_number_without_zfill(record, bank_name),
                ),
                ("journal_payment_mode_id", "=", self.journal.id),
            ]
        )
        liquidation_codes = installments.mapped(
            "cnab_config_id.liq_return_move_code_ids.code"
        )
        return str(record.get("codigo_ocorrencia")) in liquidation_codes

    @staticmethod
    def _eng_get_receiving_bank(record):
        """Receiving bank code of the record, "" when blank or zeroed."""
        code = str(record.get("banco_recebedor") or "").strip()
        return code.zfill(3) if code.strip("0") else ""

    @staticmethod
    def _eng_get_branch(record, key):
        """Branch of the record under that key, "" when blank or zeroed."""
        branch = str(record.get(key) or "").strip()
        return branch if branch.strip("0") else ""

    def _eng_get_receiving_bank_class(self, record):
        """Where the title was paid, as the bank statement splits the credit.

        False when the return does not tell it, which only a liquidation
        outside RECEIVING_BANK_REQUIRED_CODES gets past the validation with.
        """
        receiving_bank = self._eng_get_receiving_bank(record)
        if not receiving_bank:
            return False
        if receiving_bank != self.bank.code_bc:
            return "other"
        if self.bank.code_bc not in RECEIVING_BANK_REQUIRED_CODES:
            return "own"
        own_branch = self._eng_get_branch(record, "agencia_com_dv")
        receiving_branch = self._eng_get_branch(record, "agencia_recebedora_com_dv")
        if not own_branch or not receiving_branch:
            return False
        return "own" if receiving_branch == own_branch else "other"

    # Processing of the validated records

    def _get_occurrence_date(self, linha_cnab, date_format, zeros_date):
        """Occurrence date of a validated record.

        Never falls back to the credit date or to today: the records without
        a valid occurrence date were refused by _eng_validate_records().
        """
        return datetime.datetime.strptime(
            str(linha_cnab["data_ocorrencia"]).strip(), date_format
        ).date()

    def _get_accounting_entries(self, linha_cnab, account_move_line, payment_lines):
        row_list, log_event_payment = super()._get_accounting_entries(
            linha_cnab, account_move_line, payment_lines
        )
        credit_date = fields.Date.to_date(log_event_payment["real_payment_date"])
        if credit_date < self.journal.eng_bank_cutover_date:
            # Credit before the cutover date: legacy flow, through the bank
            return row_list, log_event_payment
        clearing_rows = self._eng_get_clearing_rows(
            linha_cnab,
            account_move_line,
            row_list,
            log_event_payment["payment_value"],
            credit_date,
        )
        return clearing_rows, log_event_payment

    def _eng_get_clearing_rows(
        self, record, installment, row_list, received_amount, credit_date
    ):
        """Rows of the clearing entry of one liquidation.

        Keeps the installment row and the result rows (interest, discount
        and rebate) of _get_accounting_entries(), drops the rows that go
        through the bank account and both tariff rows (the tariff stays on
        the event), and adds a single clearing account row with the received
        amount, due on the credit date. The installment row carries the
        occurrence date, which becomes the date of the entry, and is the only
        row with a cnab_returned_ref, so that _post() still reconciles it
        with the installment.
        """
        installment_rows = [row for row in row_list if row["type"] == "liquidado"]
        if not installment_rows:
            raise UserError(
                _(
                    "The CNAB return file %(file_name)s was not imported: "
                    "%(record)s (own number %(own_number)s) is a liquidation "
                    "that settles no amount of the installment.",
                    file_name=self.env.context.get("file_name") or "",
                    record=self._eng_get_record_reference(
                        record, self.current_position
                    ),
                    own_number=record.get("nosso_numero"),
                )
            )
        bank_name = dict_brcobranca_bank[self.bank.code_bc]
        zeros_date, date_format = self._get_date_format(bank_name)
        occurrence_date = self._get_occurrence_date(record, date_format, zeros_date)
        clearing_row = {
            "name": _(
                "CNAB receipt %(document)s", document=installment.document_number
            ),
            "debit": received_amount,
            "credit": 0.0,
            "account_id": (
                self.journal.eng_cnab_receipt_method_line_id.payment_account_id.id
            ),
            "partner_id": installment.partner_id.id,
            "type": CLEARING_ROW_TYPE,
            "payment_line_ids": [],
            "cnab_returned_ref": False,
            "date_maturity": credit_date,
            "eng_cnab_receiving_bank_class": self._eng_get_receiving_bank_class(record),
            "eng_occurrence_date": occurrence_date,
            "eng_record_position": self.current_position,
        }
        result_rows = []
        for row in row_list:
            side = RESULT_ROW_SIDES.get(row["type"])
            if side and row[side]:
                result_rows.append(dict(row, cnab_returned_ref=False))
        return [
            clearing_row,
            *result_rows,
            *(dict(row, date=occurrence_date) for row in installment_rows),
        ]

    def get_move_line_vals(self, line, *args, **kwargs):
        vals = super().get_move_line_vals(line, *args, **kwargs)
        if line["type"] == CLEARING_ROW_TYPE:
            vals.update(
                {
                    "partner_id": line["partner_id"],
                    "date_maturity": line["date_maturity"],
                    "eng_cnab_clearing": True,
                    "eng_cnab_receiving_bank_class": line[
                        "eng_cnab_receiving_bank_class"
                    ],
                    "eng_cnab_return_event_id": self._eng_get_event(line).id,
                }
            )
        return vals

    # Called by the journal

    def eng_set_return_log(self, cnab_return_log):
        self.events_by_position = {
            event.eng_record_position: event for event in cnab_return_log.event_ids
        }

    def eng_get_move_vals(self, row_list):
        """Clearing values of the entry built from row_list.

        Empty for the rows of the legacy flow (credit before the cutover).
        """
        for row in row_list:
            if row["type"] == CLEARING_ROW_TYPE:
                return {
                    "eng_cnab_clearing": True,
                    "eng_cnab_occurrence_date": row["eng_occurrence_date"],
                    "eng_cnab_credit_date": row["date_maturity"],
                    "eng_cnab_return_event_id": self._eng_get_event(row).id,
                }
        return {}

    def _eng_get_event(self, row):
        return self.events_by_position[row["eng_record_position"]]
