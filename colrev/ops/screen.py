#! /usr/bin/env python
"""CoLRev screen operation: Screen documents."""
from __future__ import annotations

import math
from pathlib import Path

import colrev.exceptions as colrev_exceptions
import colrev.operation
import colrev.record
import colrev.settings
from colrev.constants import Colors
from colrev.constants import Fields


class Screen(colrev.operation.Operation):
    """Screen records (based on PDFs)"""

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        notify_state_transition_operation: bool = True,
    ) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=colrev.operation.OperationsType.screen,
            notify_state_transition_operation=notify_state_transition_operation,
        )

        self.verbose = True

    def __include_all_in_screen_precondition(self, *, records: dict) -> bool:
        if not [
            r
            for r in records.values()
            if r[Fields.STATUS] == colrev.record.RecordState.pdf_prepared
        ]:
            if [
                r
                for r in records.values()
                if r[Fields.STATUS] == colrev.record.RecordState.md_processed
            ]:
                self.review_manager.logger.warning(
                    "No records to screen. Use "
                    f"{Colors.ORANGE}colrev prescreen --include_all{Colors.END} instead"
                )
            else:
                self.review_manager.logger.warning("No records to screen.")
            return False
        return True

    def include_all_in_screen(self, *, persist: bool) -> None:
        """Include all records in the screen"""

        if persist:
            self.review_manager.settings.screen.screen_package_endpoints = []
            self.review_manager.save_settings()

        records = self.review_manager.dataset.load_records_dict()

        if not self.__include_all_in_screen_precondition(records=records):
            return

        selected_record_ids = [
            r[Fields.ID]
            for r in records.values()
            if colrev.record.RecordState.pdf_prepared == r[Fields.STATUS]
        ]

        screening_criteria = self.get_screening_criteria()

        saved_args = locals()
        saved_args["include_all"] = ""
        pad = 50
        for record_id, record in records.items():
            if record[Fields.STATUS] != colrev.record.RecordState.pdf_prepared:
                continue
            self.review_manager.report_logger.info(
                f" {record_id}".ljust(pad, " ") + "Included in screen (automatically)"
            )
            if len(screening_criteria) == 0:
                record.update(screening_criteria="NA")
            else:
                record.update(
                    screening_criteria=";".join([e + "=in" for e in screening_criteria])
                )
            record.update(colrev_status=colrev.record.RecordState.rev_included)

        self.review_manager.dataset.save_records_dict(records=records)
        self.__print_stats(selected_record_ids=selected_record_ids)
        self.review_manager.create_commit(
            msg="Screen (include_all)",
            manual_author=False,
        )

    def get_screening_criteria(self) -> list:
        """Get the list of screening criteria from settings"""

        return list(self.review_manager.settings.screen.criteria.keys())

    def set_screening_criteria(
        self, *, screening_criteria: dict[str, colrev.settings.ScreenCriterion]
    ) -> None:
        """Set the screening criteria in the settings"""
        self.review_manager.settings.screen.criteria = screening_criteria
        self.review_manager.save_settings()

    def get_data(self) -> dict:
        """Get the data (records to screen)"""

        # pylint: disable=duplicate-code
        records_headers = self.review_manager.dataset.load_records_dict(
            header_only=True
        )
        record_header_list = list(records_headers.values())
        nr_tasks = len(
            [
                x
                for x in record_header_list
                if colrev.record.RecordState.pdf_prepared == x[Fields.STATUS]
            ]
        )
        pad = 0
        if record_header_list:
            pad = min((max(len(x[Fields.ID]) for x in record_header_list) + 2), 35)
        items = self.review_manager.dataset.read_next_record(
            conditions=[{Fields.STATUS: colrev.record.RecordState.pdf_prepared}]
        )
        screen_data = {"nr_tasks": nr_tasks, "PAD": pad, "items": items}
        # self.review_manager.logger.debug(
        #     self.review_manager.p_printer.pformat(screen_data)
        # )
        return screen_data

    def add_criterion(self, *, criterion_to_add: str) -> None:
        """Add a screening criterion to the records and settings"""

        assert criterion_to_add.count(",") == 2
        (
            criterion_name,
            criterion_type_str,
            criterion_explanation,
        ) = criterion_to_add.split(",")
        criterion_type = colrev.settings.ScreenCriterionType[criterion_type_str]

        records = self.review_manager.dataset.load_records_dict()

        if criterion_name not in self.review_manager.settings.screen.criteria:
            add_criterion = colrev.settings.ScreenCriterion(
                explanation=criterion_explanation,
                criterion_type=criterion_type,
                comment="",
            )
            self.review_manager.settings.screen.criteria[criterion_name] = add_criterion

            self.review_manager.save_settings()
            self.review_manager.dataset.add_setting_changes()
        else:
            print(f"Error: criterion {criterion_name} already in settings")
            return

        for record_dict in records.values():
            if record_dict[Fields.STATUS] in [
                colrev.record.RecordState.rev_included,
                colrev.record.RecordState.rev_synthesized,
            ]:
                record_dict[Fields.SCREENING_CRITERIA] += f";{criterion_name}=TODO"
                # Note : we set the status to pdf_prepared because the screening
                # decisions have to be updated (resulting in inclusion or exclusion)
                record = colrev.record.Record(data=record_dict)
                record.set_status(target_state=colrev.record.RecordState.pdf_prepared)
            if record_dict[Fields.STATUS] == colrev.record.RecordState.rev_excluded:
                record_dict[Fields.SCREENING_CRITERIA] += f";{criterion_name}=TODO"
                # Note : no change in colrev_status
                # because at least one of the other criteria led to exclusion decision

        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.create_commit(
            msg=f"Add screening criterion: {criterion_name}",
        )

    def delete_criterion(self, *, criterion_to_delete: str) -> None:
        """Delete a screening criterion from the records and settings"""
        records = self.review_manager.dataset.load_records_dict()

        if criterion_to_delete in self.review_manager.settings.screen.criteria:
            del self.review_manager.settings.screen.criteria[criterion_to_delete]
            self.review_manager.save_settings()
            self.review_manager.dataset.add_setting_changes()
        else:
            print(f"Error: criterion {criterion_to_delete} not in settings")
            return

        for record_dict in records.values():
            if record_dict[Fields.STATUS] in [
                colrev.record.RecordState.rev_included,
                colrev.record.RecordState.rev_synthesized,
            ]:
                record_dict[Fields.SCREENING_CRITERIA] = (
                    record_dict[Fields.SCREENING_CRITERIA]
                    .replace(f"{criterion_to_delete}=TODO", "")
                    .replace(f"{criterion_to_delete}=in", "")
                    .replace(f"{criterion_to_delete}=out", "")
                    .replace(";;", ";")
                    .lstrip(";")
                    .rstrip(";")
                )
                # Note : colrev_status does not change
                # because the other screening criteria do not change

            if record_dict[Fields.STATUS] in [colrev.record.RecordState.rev_excluded]:
                record_dict[Fields.SCREENING_CRITERIA] = (
                    record_dict[Fields.SCREENING_CRITERIA]
                    .replace(f"{criterion_to_delete}=TODO", "")
                    .replace(f"{criterion_to_delete}=in", "")
                    .replace(f"{criterion_to_delete}=out", "")
                    .replace(";;", ";")
                    .lstrip(";")
                    .rstrip(";")
                )

                if (
                    "=out" not in record_dict[Fields.SCREENING_CRITERIA]
                    and "=TODO" not in record_dict[Fields.SCREENING_CRITERIA]
                ):
                    record = colrev.record.Record(data=record_dict)
                    record.set_status(
                        target_state=colrev.record.RecordState.rev_included
                    )

        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.create_commit(
            msg=f"Removed screening criterion: {criterion_to_delete}",
        )

    def create_screen_split(self, *, create_split: int) -> list:
        """Split the screen between researchers"""

        data = self.get_data()
        nrecs = math.floor(data["nr_tasks"] / create_split)

        self.review_manager.logger.info(
            f"Creating screen splits for {create_split} researchers " f"({nrecs} each)"
        )

        screen_splits = []
        for _ in range(0, create_split):
            added: list[str] = []
            while len(added) < nrecs:
                added.append(next(data["items"])[Fields.ID])
            addition = "colrev screen --split " + ",".join(added)
            screen_splits.append(addition)

        return screen_splits

    def setup_custom_script(self) -> None:
        """Setup a custom screen script"""

        filedata = colrev.env.utils.get_package_file_content(
            file_path=Path("template/custom_scripts/custom_screen_script.py")
        )

        if filedata:
            with open("custom_screen_script.py", "w", encoding="utf-8") as file:
                file.write(filedata.decode("utf-8"))

        self.review_manager.dataset.add_changes(path=Path("custom_screen_script.py"))

        self.review_manager.settings.screen.screen_package_endpoints.append(
            {"endpoint": "custom_screen_script"}
        )
        self.review_manager.save_settings()

    def __screen_include_all(self, *, records: dict) -> None:
        self.review_manager.logger.info("Screen: Include all records")
        for record_dict in records.values():
            if record_dict[Fields.STATUS] == colrev.record.RecordState.pdf_prepared:
                record = colrev.record.Record(data=record_dict)
                record.set_status(target_state=colrev.record.RecordState.rev_included)
        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.create_commit(
            msg="Screen (include_all)",
            manual_author=False,
        )

    def __print_stats(self, *, selected_record_ids: list) -> None:
        records = self.review_manager.dataset.load_records_dict(header_only=True)
        screen_excluded = [
            r[Fields.ID]
            for r in records.values()
            if colrev.record.RecordState.rev_excluded == r[Fields.STATUS]
            and r[Fields.ID] in selected_record_ids
        ]
        screen_included = [
            r[Fields.ID]
            for r in records.values()
            if colrev.record.RecordState.rev_included == r[Fields.STATUS]
            and r[Fields.ID] in selected_record_ids
        ]

        if not screen_excluded and not screen_included:
            return

        print()
        self.review_manager.logger.info("Statistics")
        for record_dict in records.values():
            if record_dict[Fields.ID] in screen_excluded:
                reasons = record_dict.get(Fields.SCREENING_CRITERIA, "NA")
                if reasons == "NA":
                    reasons = ""
                else:
                    reasons = f"({reasons})"
                self.review_manager.logger.info(
                    f" {record_dict['ID']}".ljust(40)
                    + f"pdf_prepared → rev_excluded {Colors.RED}{reasons}{Colors.END}"
                )
            elif record_dict[Fields.ID] in screen_included:
                self.review_manager.logger.info(
                    f" {Colors.GREEN}{record_dict['ID']}".ljust(45)
                    + f"pdf_prepared → rev_included{Colors.END}"
                )

        nr_screen_excluded = len(screen_excluded)
        nr_screen_included = len(screen_included)

        self.review_manager.logger.info(
            "Excluded".ljust(29) + f"{nr_screen_excluded}".rjust(10, " ") + " records"
        )
        self.review_manager.logger.info(
            "Included".ljust(29) + f"{nr_screen_included}".rjust(10, " ") + " records"
        )

    def screen(
        self,
        *,
        record: colrev.record.Record,
        screen_inclusion: bool,
        screening_criteria: str,
        PAD: int = 40,
    ) -> None:
        """Save the screen decision"""

        PAD = 40
        if screen_inclusion:
            screening_criteria_list = self.get_screening_criteria()
            if len(screening_criteria_list) == 0:
                record.data.update(screening_criteria="NA")
            else:
                record.data.update(
                    screening_criteria=";".join(
                        [e + "=in" for e in screening_criteria_list]
                    )
                )
            record.set_status(target_state=colrev.record.RecordState.rev_included)

            self.review_manager.report_logger.info(
                f" {record.data['ID']}".ljust(PAD, " ") + "Included in screen"
            )
        else:
            record.data[Fields.SCREENING_CRITERIA] = screening_criteria
            record.set_status(target_state=colrev.record.RecordState.rev_excluded)
            self.review_manager.report_logger.info(
                f" {record.data['ID']}".ljust(PAD, " ") + "Excluded in screen"
            )

        record_dict = record.get_data()
        self.review_manager.dataset.save_records_dict(
            records={record_dict[Fields.ID]: record_dict}, partial=True
        )

    def __auto_include(self, *, records: dict) -> list:
        selected_auto_include_ids = [
            r[Fields.ID]
            for r in records.values()
            if colrev.record.RecordState.pdf_prepared == r[Fields.STATUS]
            and r.get("include_flag", "0") == "1"
        ]
        if not selected_auto_include_ids:
            return selected_auto_include_ids
        self.review_manager.logger.info(
            f"{Colors.GREEN}Automatically including records with include_flag{Colors.END}"
        )

        for record_dict in records.values():
            if record_dict[Fields.ID] not in selected_auto_include_ids:
                continue
            record = colrev.record.Record(data=record_dict)
            self.screen(
                record=record,
                screen_inclusion=True,
                screening_criteria="",
            )
            record.remove_field(key="include_flag")

        self.review_manager.create_commit(
            msg="Include records (include_flag)", manual_author=True
        )
        return selected_auto_include_ids

    @colrev.operation.Operation.decorate()
    def main(self, *, split_str: str = "NA") -> None:
        """Screen records for inclusion (main entrypoint)"""

        self.review_manager.logger.info("Screen")
        self.review_manager.logger.info(
            "In the screen, records are included or excluded "
            "based on the PDFs and screening criteria."
        )
        self.review_manager.logger.info(
            "See https://colrev.readthedocs.io/en/latest/manual/pdf_screen/screen.html"
        )

        # pylint: disable=duplicate-code
        split = []
        if split_str != "NA":
            split = split_str.split(",")
            if "" in split:
                split.remove("")

        records = self.review_manager.dataset.load_records_dict()

        package_manager = self.review_manager.get_package_manager()

        if not self.review_manager.settings.screen.screen_package_endpoints:
            self.__screen_include_all(records=records)
            return

        for (
            screen_package_endpoint
        ) in self.review_manager.settings.screen.screen_package_endpoints:
            endpoint_dict = package_manager.load_packages(
                package_type=colrev.env.package_manager.PackageEndpointType.screen,
                selected_packages=self.review_manager.settings.screen.screen_package_endpoints,
                operation=self,
                only_ci_supported=self.review_manager.in_ci_environment(),
            )
            if screen_package_endpoint["endpoint"] not in endpoint_dict:
                self.review_manager.logger.info(
                    f'Skip {screen_package_endpoint["endpoint"]} (not available)'
                )
                if self.review_manager.in_ci_environment():
                    raise colrev_exceptions.ServiceNotAvailableException(
                        dep="colrev sceen",
                        detailed_trace="sceen not available in ci environment",
                    )
                raise colrev_exceptions.ServiceNotAvailableException(
                    dep="colrev sceen", detailed_trace="sceen not available"
                )

            endpoint = endpoint_dict[screen_package_endpoint["endpoint"]]

            selected_auto_include_ids = self.__auto_include(records=records)

            selected_record_ids = [
                r[Fields.ID]
                for r in records.values()
                if colrev.record.RecordState.pdf_prepared == r[Fields.STATUS]
                and not r.get("include_flag", "0") == "1"
            ]
            if split:
                split = [x for x in selected_record_ids if x in split]

            endpoint.run_screen(self, records, selected_record_ids)  # type: ignore

            self.__print_stats(
                selected_record_ids=selected_record_ids + selected_auto_include_ids
            )

        self.review_manager.logger.info(
            f"{Colors.GREEN}Completed screen operation{Colors.END}"
        )
