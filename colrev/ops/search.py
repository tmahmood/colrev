#! /usr/bin/env python
"""CoLRev search operation: Search for relevant records."""
from __future__ import annotations

<<<<<<< HEAD
import json
import time
=======
>>>>>>> 8913e1a6 (split search / search_feed)
from pathlib import Path
from typing import Optional

import colrev.exceptions as colrev_exceptions
import colrev.operation
import colrev.settings
import colrev.ui_cli.cli_colors as colors


class Search(colrev.operation.Operation):
    """Search for new records"""

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        notify_state_transition_operation: bool = True,
    ) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=colrev.operation.OperationsType.search,
            notify_state_transition_operation=notify_state_transition_operation,
        )

        self.sources = review_manager.settings.sources

    def get_unique_filename(self, file_path_string: str, suffix: str = ".bib") -> Path:
        """Get a unique filename for a (new) SearchSource"""

        file_path_string = file_path_string.replace("+", "_").replace(" ", "_")

        if file_path_string.endswith(suffix):
            file_path_string = file_path_string.rstrip(suffix)
            # suffix = ""
        filename = Path(f"data/search/{file_path_string}{suffix}")
        existing_filenames = [x.filename for x in self.sources]
        if filename not in existing_filenames:
            return filename

        i = 1
        while filename in existing_filenames:
            filename = Path(f"data/search/{file_path_string}_{i}{suffix}")
            i += 1

        return filename

    def add_source(self, *, add_source: colrev.settings.SearchSource) -> None:
        """Add a new source"""

        package_manager = self.review_manager.get_package_manager()
        endpoint_dict = package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.search_source,
            selected_packages=[add_source.get_dict()],
            operation=self,
        )
        endpoint = endpoint_dict[add_source.endpoint.lower()]
        endpoint.validate_source(search_operation=self, source=add_source)  # type: ignore

        self.review_manager.logger.info(f"{colors.GREEN}Add source:{colors.END}")
        print(add_source)
        self.review_manager.settings.sources.append(add_source)
        self.review_manager.save_settings()

        print()

        self.main(selection_str=str(add_source.filename), rerun=False, skip_commit=True)
        fname = add_source.filename
        if fname.is_absolute():
            fname = add_source.filename.relative_to(self.review_manager.path)
        self.review_manager.create_commit(
            msg=f"Add search source {fname}",
        )

    def __get_search_sources(
        self, *, selection_str: Optional[str] = None
    ) -> list[colrev.settings.SearchSource]:
        sources_selected = self.sources
        if selection_str:
            if selection_str != "all":
                sources_selected = [
                    f
                    for f in self.sources
                    if str(f.filename) in selection_str.split(",")
                ]
            if len(sources_selected) == 0:
                available_options = [str(f.filename) for f in self.sources]
                raise colrev_exceptions.ParameterError(
                    parameter="selection_str",
                    value=selection_str,
                    options=available_options,
                )

        for source in sources_selected:
            source.filename = self.review_manager.path / Path(source.filename)
        return sources_selected

    def __remove_forthcoming(self, *, source: colrev.settings.SearchSource) -> None:
        with open(source.get_corresponding_bib_file(), encoding="utf8") as bibtex_file:
            records = self.review_manager.dataset.load_records_dict(
                load_str=bibtex_file.read()
            )

            record_list = list(records.values())
            before = len(record_list)
            record_list = [r for r in record_list if "forthcoming" != r.get("year", "")]
            changed = len(record_list) - before
            if changed > 0:
                self.review_manager.logger.info(
                    f"{colors.GREEN}Removed {changed} forthcoming{colors.END}"
                )
            else:
                self.review_manager.logger.info(f"Removed {changed} forthcoming")

            records = {r["ID"]: r for r in record_list}

            self.review_manager.dataset.save_records_dict_to_file(
                records=records, save_path=source.get_corresponding_bib_file()
            )

    @colrev.operation.Operation.decorate()
    def main(
        self,
        *,
        selection_str: Optional[str] = None,
        rerun: bool,
        skip_commit: bool = False,
    ) -> None:
        """Search for records (main entrypoint)"""

        if selection_str:
            if Path(selection_str) not in [
                s.filename for s in self.review_manager.settings.sources
            ]:
                raise colrev_exceptions.ParameterError(
                    parameter="select",
                    value=selection_str,
                    options=[
                        str(s.filename) for s in self.review_manager.settings.sources
                    ],
                )

        rerun_flag = "" if not rerun else f" ({colors.GREEN}rerun{colors.END})"
        self.review_manager.logger.info(f"Search{rerun_flag}")
        self.review_manager.logger.info(
            "Retrieve new records from an API or files (search sources)."
        )
        self.review_manager.logger.info(
            "See https://colrev.readthedocs.io/en/latest/manual/metadata_retrieval/search.html"
        )

        # Reload the settings because the search sources may have been updated
        self.review_manager.settings = self.review_manager.load_settings()

        package_manager = self.review_manager.get_package_manager()

        for source in self.__get_search_sources(selection_str=selection_str):
            endpoint_dict = package_manager.load_packages(
                package_type=colrev.env.package_manager.PackageEndpointType.search_source,
                selected_packages=[source.get_dict()],
                operation=self,
                only_ci_supported=self.review_manager.in_ci_environment(),
            )
            # if source.endpoint.lower() not in endpoint_dict:
            #     continue
            endpoint = endpoint_dict[source.endpoint.lower()]
            endpoint.validate_source(search_operation=self, source=source)  # type: ignore

            if not endpoint.api_search_supported:  # type: ignore
                continue

            if not self.review_manager.high_level_operation:
                print()
            self.review_manager.logger.info(
                f"search [{source.endpoint} > data/search/{source.filename.name}]"
            )

            try:
                endpoint.run_search(search_operation=self, rerun=rerun)  # type: ignore
            except colrev.exceptions.ServiceNotAvailableException as exc:
                if not self.review_manager.force_mode:
                    raise colrev_exceptions.ServiceNotAvailableException(
                        source.endpoint
                    ) from exc
                self.review_manager.logger.warning("ServiceNotAvailableException")

            if source.filename.is_file():
                self.__format_source_file(source=source)

                self.review_manager.dataset.format_records_file()
                self.review_manager.dataset.add_record_changes()
                self.review_manager.dataset.add_changes(path=source.filename)
                if not skip_commit:
                    self.review_manager.create_commit(msg="Run search")

    def setup_custom_script(self) -> None:
        """Setup a custom search script"""

        filedata = colrev.env.utils.get_package_file_content(
            file_path=Path("template/custom_scripts/custom_search_source_script.py")
        )

        if filedata:
            with open("custom_search_source_script.py", "w", encoding="utf-8") as file:
                file.write(filedata.decode("utf-8"))

        self.review_manager.dataset.add_changes(
            path=Path("custom_search_source_script.py")
        )

        new_source = colrev.settings.SearchSource(
            endpoint="custom_search_source_script",
            filename=Path("data/search/custom_search.bib"),
            search_type=colrev.settings.SearchType.DB,
            search_parameters={},
            load_conversion_package_endpoint={"endpoint": "colrev.bibtex"},
            comment="",
        )

        self.review_manager.settings.sources.append(new_source)
        self.review_manager.save_settings()

    def view_sources(self) -> None:
        """View the sources info"""

        for source in self.sources:
            self.review_manager.p_printer.pprint(source)
