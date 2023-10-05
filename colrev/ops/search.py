#! /usr/bin/env python
"""CoLRev search operation: Search for relevant records."""
from __future__ import annotations

import typing
from pathlib import Path
from typing import Callable
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
        self.review_manager = review_manager
        self.sources = review_manager.settings.sources
        self.package_manager = self.review_manager.get_package_manager()

    def get_unique_filename(self, file_path_string: str, suffix: str = ".bib") -> Path:
        """Get a unique filename for a (new) SearchSource"""

        self.review_manager.load_settings()
        self.sources = self.review_manager.settings.sources

        file_path_string = (
            file_path_string.replace("+", "_").replace(" ", "_").replace(";", "_")
        )

        if file_path_string.endswith(suffix):
            file_path_string = file_path_string.rstrip(suffix)
        filename = Path(f"data/search/{file_path_string}{suffix}")
        existing_filenames = [x.filename for x in self.sources]
        if all(x != filename for x in existing_filenames):
            return filename

        i = 1
        while not all(x != filename for x in existing_filenames):
            filename = Path(f"data/search/{file_path_string}_{i}{suffix}")
            i += 1

        return filename

    def get_query_filename(self, *, filename: Path, instantiate: bool = False) -> Path:
        query_filename = Path("data/search/") / Path(str(filename.stem) + "_query.txt")
        if instantiate:
            with open(query_filename, "w", encoding="utf-8") as file:
                file.write("")
            input(
                f"Created {query_filename}. Please store your query in the file and press Enter to continue."
            )
            self.review_manager.dataset.add_changes(path=query_filename)
        return query_filename

    def __get_search_sources(
        self, *, selection_str: Optional[str] = None
    ) -> list[colrev.settings.SearchSource]:
        sources_selected = self.sources
        if selection_str and selection_str != "all":
            selected_filenames = {Path(f).name for f in selection_str.split(",")}
            sources_selected = [
                s for s in self.sources if s.filename.name in selected_filenames
            ]

        assert len(sources_selected) != 0
        for source in sources_selected:
            source.filename = self.review_manager.path / Path(source.filename)
        return sources_selected

    def remove_forthcoming(self, *, source: colrev.settings.SearchSource) -> None:
        """Remove forthcoming papers from a SearchSource"""

        if self.review_manager.settings.search.retrieve_forthcoming:
            return

        if source.filename.suffix != ".bib":
            print(f"{source.filename.suffix} not yet supported")
            return

        with open(source.filename, encoding="utf8") as bibtex_file:
            records = self.review_manager.dataset.load_records_dict(
                load_str=bibtex_file.read()
            )

            record_list = list(records.values())
            before = len(record_list)
            record_list = [r for r in record_list if "forthcoming" != r.get("year", "")]
            removed = before - len(record_list)
            self.review_manager.logger.info(
                f"{colors.GREEN}Removed {removed} forthcoming{colors.END}"
            )
            records = {r["ID"]: r for r in record_list}
            self.review_manager.dataset.save_records_dict_to_file(
                records=records, save_path=source.filename
            )

    # pylint: disable=no-self-argument
    def check_source_selection_exists(var_name: str) -> Callable:  # type: ignore
        """Check if the source selection exists"""

        # pylint: disable=no-self-argument
        def check_accepts(func_in: Callable) -> Callable:
            def new_f(self, *args, **kwds) -> Callable:  # type: ignore
                if kwds.get(var_name, None) is None:
                    return func_in(self, *args, **kwds)
                for search_source in kwds[var_name].split(","):
                    if Path(search_source) not in [
                        s.filename for s in self.review_manager.settings.sources
                    ]:
                        raise colrev_exceptions.ParameterError(
                            parameter="select",
                            value=kwds[var_name],
                            options=[
                                str(s.filename)
                                for s in self.review_manager.settings.sources
                            ],
                        )
                return func_in(self, *args, **kwds)

            new_f.__name__ = func_in.__name__
            return new_f

        return check_accepts

    def __get_new_search_files(self) -> list[Path]:
        """Retrieve new search files (not yet registered in settings)"""

        files = [
            f.relative_to(self.review_manager.path)
            for f in self.review_manager.search_dir.glob("**/*")
        ]

        # Only files that are not yet registered
        # (also exclude bib files corresponding to a registered file)
        files = [
            f
            for f in files
            if f not in [s.filename for s in self.review_manager.settings.sources]
            and not str(f).endswith("_query.txt")
            and ".~lock" not in str(f)
        ]

        return sorted(list(set(files)))

    def __get_heuristics_results_list(
        self,
        *,
        filepath: Path,
        search_sources: dict,
        data: str,
    ) -> list:
        results_list = []
        for (
            endpoint,
            endpoint_class,
        ) in search_sources.items():
            res = endpoint_class.heuristic(filepath, data)  # type: ignore
            self.review_manager.logger.debug(f"- {endpoint}: {res['confidence']}")
            if res["confidence"] == 0.0:
                continue
            try:
                result_item = {}

                res["endpoint"] = endpoint

                search_type = colrev.settings.SearchType.DB
                # Note : as the identifier, we use the filename
                # (if search results are added by file/not via the API)

                source_candidate = colrev.settings.SearchSource(
                    endpoint=endpoint,
                    filename=filepath,
                    search_type=search_type,
                    search_parameters={},
                    comment="",
                )

                result_item["source_candidate"] = source_candidate
                result_item["confidence"] = res["confidence"]

                results_list.append(result_item)
            except colrev_exceptions.UnsupportedImportFormatError:
                continue
        return results_list

    def __apply_source_heuristics(
        self, *, filepath: Path, search_sources: dict
    ) -> list[typing.Dict]:
        """Apply heuristics to identify source"""

        data = ""
        try:
            data = filepath.read_text()
        except UnicodeDecodeError:
            pass

        results_list = self.__get_heuristics_results_list(
            filepath=filepath,
            search_sources=search_sources,
            data=data,
        )

        # Reduce the results_list when there are results with very high confidence
        if [r for r in results_list if r["confidence"] > 0.95]:
            results_list = [r for r in results_list if r["confidence"] > 0.8]

        return results_list

    def add_most_likely_sources(self) -> None:
        """Get the most likely SearchSources

        returns a dictionary:
        {"filepath": [SearchSource1,..]}
        """

        heuristic_list = self.get_new_sources_heuristic_list()
        selected_search_sources = []

        for results_list in heuristic_list.values():
            # Use the last / unknown_source
            max_conf = 0.0
            best_candidate_pos = 0
            for i, heuristic_candidate in enumerate(results_list):
                if heuristic_candidate["confidence"] > max_conf:
                    best_candidate_pos = i + 1
                    max_conf = heuristic_candidate["confidence"]
            if not any(c["confidence"] > 0.1 for c in results_list):
                source = [
                    x
                    for x in results_list
                    if x["source_candidate"].endpoint == "colrev.unknown_source"
                ][0]
            else:
                selection = str(best_candidate_pos)
                source = results_list[int(selection) - 1]
            selected_search_sources.append(source["source_candidate"])
        for selected_search_source in selected_search_sources:
            self.review_manager.settings.sources.append(selected_search_source)
        self.review_manager.save_settings()

    def get_new_sources_heuristic_list(self) -> dict:
        """Get the heuristic result list of SearchSources candidates

        returns a dictionary:
        {"filepath": ({"search_source": SourceCandidate1", "confidence": 0.98},..]}
        """

        # pylint: disable=redefined-outer-name

        new_search_files = self.__get_new_search_files()
        if not new_search_files:
            self.review_manager.logger.info("No new search files...")
            return {}

        self.review_manager.logger.debug("Load available search_source endpoints...")

        search_source_identifiers = self.package_manager.discover_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.search_source,
            installed_only=True,
        )

        search_sources = self.package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.search_source,
            selected_packages=[{"endpoint": p} for p in search_source_identifiers],
            operation=self,
            instantiate_objects=False,
        )

        heuristic_results = {}
        for sfp_name in new_search_files:
            if not self.review_manager.high_level_operation:
                print()
            self.review_manager.logger.info(f"Discover new source: {sfp_name}")

            heuristic_results[sfp_name] = self.__apply_source_heuristics(
                filepath=sfp_name,
                search_sources=search_sources,
            )

        return heuristic_results

    def add_interactively(self, *, endpoint: str) -> colrev.settings.SearchSource:
        """Add a SearchSource interactively"""
        print(f"Interactively add {endpoint} as a SearchSource")
        print()

        keywords = input("Enter the keywords:")

        filename = self.get_unique_filename(
            file_path_string=f"{endpoint.replace('colrev.', '')}_{keywords}"
        )
        add_source = colrev.settings.SearchSource(
            endpoint=endpoint,
            filename=filename,
            search_type=colrev.settings.SearchType.DB,
            search_parameters={"query": keywords},
            comment="",
        )
        return add_source

    @check_source_selection_exists(  # pylint: disable=too-many-function-args
        "selection_str"
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

        for source in self.__get_search_sources(selection_str=selection_str):
            endpoint_dict = self.package_manager.load_packages(
                package_type=colrev.env.package_manager.PackageEndpointType.search_source,
                selected_packages=[source.get_dict()],
                operation=self,
                only_ci_supported=self.review_manager.in_ci_environment(),
            )
            if source.endpoint.lower() not in endpoint_dict:
                continue
            endpoint = endpoint_dict[source.endpoint.lower()]

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

            if not source.filename.is_file():
                continue

            self.remove_forthcoming(source=source)
            self.review_manager.dataset.format_records_file()
            self.review_manager.dataset.add_record_changes()
            self.review_manager.dataset.add_changes(path=source.filename)
            if not skip_commit:
                self.review_manager.create_commit(msg="Run search")

        if self.review_manager.in_ci_environment():
            print("\n\n")
