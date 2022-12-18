#!/usr/bin/env python3
"""Repare CoLRev projects."""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.operation

if TYPE_CHECKING:
    import colrev.review_manager


# pylint: disable=too-few-public-methods


class Repare(colrev.operation.Operation):
    """Repare a CoLRev project"""

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
    ) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=colrev.operation.OperationsType.check,
            notify_state_transition_operation=False,
        )

    def __fix_files(self, *, records: dict) -> None:

        # pylint: disable=too-many-branches

        # fix file no longer available
        local_index = self.review_manager.get_local_index()
        pdf_get_operation = self.review_manager.get_pdf_get_operation()

        records = self.review_manager.dataset.load_records_dict()
        for record_dict in records.values():
            if "file" not in record_dict:
                continue
            full_path = self.review_manager.path / Path(record_dict["file"])

            if full_path.is_file():
                continue

            if Path(str(full_path) + ".pdf").is_file():
                Path(str(full_path) + ".pdf").rename(full_path)

            # Check / replace multiple blanks in file and filename
            parent_dir = full_path.parent
            same_dir_pdfs = [
                x.relative_to(self.review_manager.path)
                for x in parent_dir.glob("*.pdf")
            ]
            for same_dir_pdf in same_dir_pdfs:
                if record_dict["file"].replace("  ", " ") == str(same_dir_pdf).replace(
                    "  ", " "
                ):
                    same_dir_pdf.rename(str(same_dir_pdf).replace("  ", " "))
                    record_dict["file"] = record_dict["file"].replace("  ", " ")

            full_path = self.review_manager.path / Path(record_dict["file"])

            if not full_path.is_file():
                # Fix broken symlinks based on local_index

                if os.path.islink(full_path) and not os.path.exists(full_path):
                    self.review_manager.logger.debug(
                        f" remove broken symlink: {full_path}"
                    )
                    full_path.unlink()

                try:

                    record = colrev.record.Record(data=record_dict)
                    retrieved_record = local_index.retrieve(
                        record_dict=record.data, include_file=True
                    )

                    if "file" in retrieved_record:
                        record.update_field(
                            key="file",
                            value=str(retrieved_record["file"]),
                            source="local_index",
                            append_edit=False,
                        )
                        pdf_get_operation.import_file(record=record)
                        if "fulltext" in retrieved_record:
                            del retrieved_record["fulltext"]
                        self.review_manager.logger.info(
                            f" fix broken symlink: {record_dict['ID']}"
                        )
                    else:
                        self.review_manager.logger.debug(
                            f" file not linked in retrieved record: {record_dict['ID']}"
                        )

                except colrev_exceptions.RecordNotInIndexException:
                    self.review_manager.logger.debug(
                        f" record not in index: {record_dict['ID']}"
                    )

            if full_path.is_file():
                continue

            record_dict["colrev_status_backup"] = record_dict["colrev_status"]
            del record_dict["file"]
            record_dict[
                "colrev_status"
            ] = colrev.record.RecordState.rev_prescreen_included

    def __fix_provenance(self, *, records: dict) -> None:

        # pylint: disable=too-many-nested-blocks
        # pylint: disable=too-many-branches

        source_feeds = {}
        for source in self.review_manager.settings.sources:
            source_feeds[
                str(source.filename).replace("data/search/", "")
            ] = source.get_feed(
                review_manager=self.review_manager,
                source_identifier="NA",
                update_only=False,
            ).feed_records

        for record_dict in records.values():
            record = colrev.record.Record(data=record_dict)
            if "colrev_data_provenance" not in record.data:
                record.data["colrev_data_provenance"] = {}
            if "colrev_masterdata_provenance" not in record.data:
                record.data["colrev_masterdata_provenance"] = {}
            if "pdf_hash" in record.data:
                record.data["colrev_pdf_id"] = record.data["pdf_hash"]
                del record.data["pdf_hash"]
            if "pdf_prep_hints" in record.data:
                del record.data["pdf_prep_hints"]
            if "grobid-version" in record.data:
                del record.data["grobid-version"]

            for key in record.data["colrev_data_provenance"]:
                if key not in record.data:
                    del record.data["colrev_data_provenance"][key]

            mdk_to_remove = []
            for key in record.data["colrev_masterdata_provenance"]:
                if (
                    key not in record.data
                    and "CURATED" != key
                    and "not_missing"
                    not in record.data["colrev_masterdata_provenance"][key]["note"]
                ):
                    mdk_to_remove += [key]
            for key in mdk_to_remove:
                del record.data["colrev_masterdata_provenance"][key]

            for key in record.data.keys():
                if key in [
                    "colrev_status",
                    "colrev_origin",
                    "colrev_masterdata_provenance",
                    "colrev_data_provenance",
                    "colrev_pdfid",
                    "colrev_id",
                    "ID",
                    "ENTRYTYPE",
                    "screening_criteria",
                ]:
                    continue
                if key in colrev.record.Record.identifying_field_keys:
                    if "CURATED" not in record.data["colrev_masterdata_provenance"]:
                        if key in record.data["colrev_masterdata_provenance"]:
                            if not any(
                                record.data["colrev_masterdata_provenance"][key][
                                    "source"
                                ].startswith(sf)
                                for sf in list(source_feeds.keys())
                            ):
                                del record.data["colrev_masterdata_provenance"][key]
                        if key not in record.data["colrev_masterdata_provenance"]:
                            for origin in record.data["colrev_origin"]:
                                origin_source, origin_id = origin.split("/")
                                if key in source_feeds[origin_source][origin_id]:
                                    record.add_masterdata_provenance(
                                        key=key, source=origin_source, note=""
                                    )
                        if key not in record.data["colrev_masterdata_provenance"]:
                            record.add_masterdata_provenance(
                                key=key, source="manual", note=""
                            )

                else:

                    if key in record.data["colrev_data_provenance"]:
                        if not any(
                            record.data["colrev_data_provenance"][key][
                                "source"
                            ].startswith(sf)
                            for sf in list(source_feeds.keys())
                        ):
                            del record.data["colrev_data_provenance"][key]
                    if key not in record.data["colrev_data_provenance"]:
                        for origin in record.data["colrev_origin"]:
                            origin_source, origin_id = origin.split("/")
                            if key in source_feeds[origin_source][origin_id]:
                                record.add_data_provenance(
                                    key=key, source=origin_source, note=""
                                )
                    if "tei_file" == key:
                        record.add_data_provenance(
                            key=key, source="file|grobid", note=""
                        )
                    if "colrev_pdf_id" == key:
                        record.add_data_provenance(
                            key=key, source="file|pdf_hash", note=""
                        )

                    if key not in record.data["colrev_data_provenance"]:
                        record.add_data_provenance(key=key, source="manual", note="")

    def main(self) -> None:
        """Repare a CoLRev project (main entrypoint)"""

        # pylint: disable=too-many-nested-blocks
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-statements

        # Try: open settings, except: notify & start repare

        # ...

        # Try: open records, except: notify & start repare
        try:
            records = self.review_manager.dataset.load_records_dict()
        except AttributeError:
            self.review_manager.logger.error("Could not read bibtex file")

            separated_records = {}  # type: ignore
            with open(
                self.review_manager.dataset.records_file, encoding="utf-8"
            ) as file:
                record_str = ""
                line = file.readline()

                while line:
                    if line == "\n":
                        records = self.review_manager.dataset.load_records_dict(
                            load_str=record_str
                        )
                        if len(records) != 1:
                            print(record_str)
                        else:
                            separated_records = {**separated_records, **records}
                        record_str = ""
                    record_str += line
                    line = file.readline()
            self.review_manager.dataset.save_records_dict_to_file(
                records=separated_records, save_path=Path("extracted.bib")
            )
            try:
                records = self.review_manager.dataset.load_records_dict()
            except AttributeError:
                return

        self.__fix_provenance(records=records)

        self.__fix_files(records=records)

        self.review_manager.dataset.save_records_dict(records=records)


if __name__ == "__main__":
    pass
