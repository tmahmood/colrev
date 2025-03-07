#! /usr/bin/env python
"""Creation of TEI as a PDF preparation operation"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.env.utils
import colrev.record
from colrev.constants import Fields

if TYPE_CHECKING:
    import colrev.ops.pdf_prep

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PDFPrepPackageEndpointInterface)
@dataclass
class TEIPDFPrep(JsonSchemaMixin):
    """Prepare PDFs by creating an annotated TEI document"""

    settings_class = colrev.env.package_manager.DefaultSettings
    TEI_PATH_RELATIVE = Path("data/.tei/")
    ci_supported: bool = False

    def __init__(
        self, *, pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep, settings: dict
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

        if not pdf_prep_operation.review_manager.in_ci_environment():
            grobid_service = pdf_prep_operation.review_manager.get_grobid_service()
            grobid_service.start()
            self.tei_path = (
                pdf_prep_operation.review_manager.path / self.TEI_PATH_RELATIVE
            )
            self.tei_path.mkdir(exist_ok=True, parents=True)
            pdf_prep_operation.docker_images_to_stop.append(grobid_service.GROBID_IMAGE)

    def prep_pdf(
        self,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,
        record: colrev.record.Record,
        pad: int,  # pylint: disable=unused-argument
    ) -> dict:
        """Prepare the analysis of PDFs by creating a TEI (based on GROBID)"""

        if not record.data.get(Fields.FILE, "NA").endswith(".pdf"):
            return record.data

        if not record.get_tei_filename().is_file():
            pdf_prep_operation.review_manager.logger.debug(
                f" creating tei: {record.data['ID']}"
            )
            _ = pdf_prep_operation.review_manager.get_tei(
                pdf_path=Path(record.data[Fields.FILE]),
                tei_path=record.get_tei_filename(),
            )

        return record.data
