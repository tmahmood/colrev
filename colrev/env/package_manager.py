#! /usr/bin/env python
"""Discovering and using packages."""
from __future__ import annotations

import collections.abc
import dataclasses
import importlib.util
import json
import os
import sys
import typing
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import dacite
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin
from m2r import parse_from_file
from zope.interface.verify import verifyObject

import colrev.exceptions as colrev_exceptions
import colrev.operation
import colrev.record
import colrev.settings
from colrev.constants import Colors
from colrev.constants import Fields

# pylint: disable=too-many-lines
# pylint: disable=too-many-ancestors


# Inspiration for package descriptions:
# https://github.com/rstudio/reticulate/blob/
# 9ebca7ecc028549dadb3d51d2184f9850f6f9f9d/DESCRIPTION


# pylint: disable=colrev-missed-constant-usage
class PackageEndpointType(Enum):
    """An enum for the types of PackageEndpoints"""

    # pylint: disable=C0103
    review_type = "review_type"
    """Endpoint for review types"""
    search_source = "search_source"
    """Endpoint for search sources"""
    prep = "prep"
    """Endpoint for prep"""
    prep_man = "prep_man"
    """Endpoint for prep-man"""
    dedupe = "dedupe"
    """Endpoint for dedupe"""
    prescreen = "prescreen"
    """Endpoint for prescreen"""
    pdf_get = "pdf_get"
    """Endpoint for pdf-get"""
    pdf_get_man = "pdf_get_man"
    """Endpoint for pdf-get-man"""
    pdf_prep = "pdf_prep"
    """Endpoint for pdf-prep"""
    pdf_prep_man = "pdf_prep_man"
    """Endpoint for pdf-prep-man"""
    screen = "screen"
    """Endpoint for screen"""
    data = "data"
    """Endpoint for data"""


# pylint: disable=too-few-public-methods
class GeneralInterface(zope.interface.Interface):  # pylint: disable=inherit-non-class
    """The General Interface for all package endpoints

    Each package endpoint must implement the following attributes (methods)"""

    ci_supported = zope.interface.Attribute(
        """Flag indicating whether the package can be run in
        continuous integration environments (e.g. GitHub Actions)"""
    )


# pylint: disable=too-few-public-methods
class ReviewTypePackageEndpointInterface(
    GeneralInterface, zope.interface.Interface
):  # pylint: disable=inherit-non-class
    """The PackageEndpoint interface for ReviewTypes"""

    # pylint: disable=no-self-argument
    def initialize(settings: dict) -> dict:  # type: ignore
        """Initialize the review type"""
        return settings  # pragma: no cover


class SearchSourceHeuristicStatus(Enum):
    """Status of the SearchSource heuristic"""

    # pylint: disable=invalid-name
    na = "not_applicable"
    oni = "output_not_identifiable"
    supported = "supported"
    todo = "to_be_implemented"

    def __str__(self) -> str:
        return f"{self.name}"  # pragma: no cover


class SearchSourcePackageEndpointInterface(
    GeneralInterface, zope.interface.Interface
):  # pylint: disable=inherit-non-class
    """The PackageEndpoint interface for SearchSources"""

    settings_class = zope.interface.Attribute("""Class for the package settings""")
    source_identifier = zope.interface.Attribute(
        """Source identifier for search and provenance
        Retrieved records are identified through the source_identifier
        when they are added to/updated in the GeneralOriginFeed"""
    )
    search_types = zope.interface.Attribute(
        """SearchTypes associated with the SearchSource"""
    )

    heuristic_status: SearchSourceHeuristicStatus = zope.interface.Attribute(
        """The status of the SearchSource heuristic"""
    )
    short_name = zope.interface.Attribute("""Short name of the SearchSource""")
    docs_link = zope.interface.Attribute("""Link to the SearchSource website""")

    # pylint: disable=no-self-argument
    def heuristic(filename: Path, data: str):  # type: ignore
        """Heuristic to identify the SearchSource"""

    # pylint: disable=no-self-argument
    def add_endpoint(  # type: ignore
        operation: colrev.operation.Operation,
        params: dict,
    ) -> colrev.settings.SearchSource:
        """Add the SearchSource as an endpoint based on a query (passed to colrev search -a)
        params:
        - search_file="..." to add a DB search
        """

    # pylint: disable=no-self-argument
    def run_search(rerun: bool) -> None:  # type: ignore
        """Run a search of the SearchSource"""

    # pylint: disable=no-self-argument
    def get_masterdata(  # type: ignore
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ):
        """Retrieve masterdata from the SearchSource"""

    # pylint: disable=no-self-argument
    def load(  # type: ignore
        load_operation: colrev.ops.load.Load,
    ) -> dict:
        """Load records from the SearchSource (and convert to .bib)"""

    # pylint: disable=no-self-argument
    def prepare(record: dict, source: colrev.settings.SearchSource) -> None:  # type: ignore
        """Run the custom source-prep operation"""


# pylint: disable=too-few-public-methods
class PrepPackageEndpointInterface(
    GeneralInterface, zope.interface.Interface
):  # pylint: disable=inherit-non-class
    """The PackageEndpoint interface for prep operations"""

    settings_class = zope.interface.Attribute("""Class for the package settings""")
    source_correction_hint = zope.interface.Attribute(
        """Hint on how to correct metadata at source"""
    )

    always_apply_changes = zope.interface.Attribute(
        """Flag indicating whether changes should always be applied
        (even if the colrev_status does not transition to md_prepared)"""
    )

    # pylint: disable=no-self-argument
    def prepare(prep_operation: colrev.ops.prep.Prep, prep_record: dict) -> dict:  # type: ignore
        """Run the prep operation"""


# pylint: disable=too-few-public-methods
class PrepManPackageEndpointInterface(
    GeneralInterface, zope.interface.Interface
):  # pylint: disable=inherit-non-class
    """The PackageEndpoint interface for prep-man operations"""

    settings_class = zope.interface.Attribute("""Class for the package settings""")

    # pylint: disable=no-self-argument
    def prepare_manual(  # type: ignore
        prep_man_operation: colrev.ops.prep_man.PrepMan, records: dict
    ) -> dict:
        """Run the prep-man operation"""


# pylint: disable=too-few-public-methods
class DedupePackageEndpointInterface(
    GeneralInterface, zope.interface.Interface
):  # pylint: disable=inherit-non-class
    """The PackageEndpoint interface for dedupe operations"""

    settings_class = zope.interface.Attribute("""Class for the package settings""")

    # pylint: disable=no-self-argument
    def run_dedupe(dedupe_operation: colrev.ops.dedupe.Dedupe) -> None:  # type: ignore
        """Run the dedupe operation"""


# pylint: disable=too-few-public-methods
class PrescreenPackageEndpointInterface(
    GeneralInterface, zope.interface.Interface
):  # pylint: disable=inherit-non-class
    """The PackageEndpoint interface for prescreen operations"""

    settings_class = zope.interface.Attribute("""Class for the package settings""")

    # pylint: disable=no-self-argument
    def run_prescreen(  # type: ignore
        prescreen_operation: colrev.ops.prescreen.Prescreen, records: dict, split: list
    ) -> dict:
        """Run the prescreen operation"""


# pylint: disable=too-few-public-methods
class PDFGetPackageEndpointInterface(
    GeneralInterface, zope.interface.Interface
):  # pylint: disable=inherit-non-class
    """The PackageEndpoint interface for pdf-get operations"""

    settings_class = zope.interface.Attribute("""Class for the package settings""")

    # pylint: disable=no-self-argument
    def get_pdf(pdf_get_operation: colrev.ops.pdf_get.PDFGet, record: dict) -> dict:  # type: ignore
        """Run the pdf-get operation"""
        return record  # pragma: no cover


# pylint: disable=too-few-public-methods
class PDFGetManPackageEndpointInterface(
    GeneralInterface, zope.interface.Interface
):  # pylint: disable=inherit-non-class
    """The PackageEndpoint interface for pdf-get-man operations"""

    settings_class = zope.interface.Attribute("""Class for the package settings""")

    # pylint: disable=no-self-argument
    def pdf_get_man(  # type: ignore
        pdf_get_man_operation: colrev.ops.pdf_get_man.PDFGetMan, records: dict
    ) -> dict:
        """Run the pdf-get-man operation"""
        return records  # pragma: no cover


# pylint: disable=too-few-public-methods
class PDFPrepPackageEndpointInterface(
    GeneralInterface, zope.interface.Interface
):  # pylint: disable=inherit-non-class
    """The PackageEndpoint interface for pdf-prep operations"""

    settings_class = zope.interface.Attribute("""Class for the package settings""")

    # pylint: disable=unused-argument
    # pylint: disable=no-self-argument
    def prep_pdf(  # type: ignore
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,
        record: colrev.record.PrepRecord,
        pad: int,
    ) -> dict:
        """Run the prep-pdf operation"""
        return record.data  # pragma: no cover


# pylint: disable=too-few-public-methods
class PDFPrepManPackageEndpointInterface(
    GeneralInterface, zope.interface.Interface
):  # pylint: disable=inherit-non-class
    """The PackageEndpoint interface for pdf-prep-man operations"""

    settings_class = zope.interface.Attribute("""Class for the package settings""")

    # pylint: disable=no-self-argument
    def pdf_prep_man(  # type: ignore
        pdf_prep_man_operation: colrev.ops.prep_man.PrepMan, records: dict
    ) -> dict:
        """Run the prep-man operation"""
        return records  # pragma: no cover


# pylint: disable=too-few-public-methods
class ScreenPackageEndpointInterface(
    GeneralInterface, zope.interface.Interface
):  # pylint: disable=inherit-non-class
    """The PackageEndpoint interface for screen operations"""

    settings_class = zope.interface.Attribute("""Class for the package settings""")

    # pylint: disable=no-self-argument
    def run_screen(  # type: ignore
        screen_operation: colrev.ops.screen.Screen, records: dict, split: list
    ) -> dict:
        """Run the screen operation"""


class DataPackageEndpointInterface(
    GeneralInterface, zope.interface.Interface
):  # pylint: disable=inherit-non-class
    """The PackageEndpoint interface for data operations"""

    settings_class = zope.interface.Attribute("""Class for the package settings""")

    # pylint: disable=no-self-argument

    def update_data(  # type: ignore
        data_operation: colrev.ops.data.Data,
        records: dict,
        synthesized_record_status_matrix: dict,
        silent_mode: bool,
    ) -> None:
        """Run the data operation (data extraction, analysis, synthesis)"""

    def update_record_status_matrix(  # type: ignore
        data_operation: colrev.ops.data.Data,
        synthesized_record_status_matrix: dict,
        endpoint_identifier: str,
    ) -> None:
        """Update the record status matrix,
        i.e., indicate whether the record is rev_synthesized for the given endpoint_identifier
        """

    def get_advice(  # type: ignore
        review_manager: colrev.review_manager.ReviewManager,
    ) -> dict:
        """Get advice on how to operate the data package endpoint"""


@dataclass
class DefaultSettings(JsonSchemaMixin):
    """Endpoint settings"""

    endpoint: str

    @classmethod
    def load_settings(cls, *, data: dict):  # type: ignore
        """Load the settings from dict"""

        required_fields = [field.name for field in dataclasses.fields(cls)]
        available_fields = list(data.keys())

        converters = {Path: Path}
        settings = from_dict(
            data_class=cls,
            data=data,
            config=dacite.Config(type_hooks=converters),  # type: ignore  # noqa
        )

        non_supported_fields = [f for f in available_fields if f not in required_fields]

        if non_supported_fields:
            raise colrev_exceptions.ParameterError(
                parameter="non_supported_fields",
                value=",".join(non_supported_fields),
                options=[],
            )

        return settings


@dataclass
class DefaultSourceSettings(colrev.settings.SearchSource, JsonSchemaMixin):
    """Search source settings"""

    # pylint: disable=duplicate-code
    # pylint: disable=too-many-instance-attributes
    endpoint: str
    filename: Path
    search_type: colrev.settings.SearchType
    search_parameters: dict
    comment: typing.Optional[str]


class PackageManager:
    """The PackageManager provides functionality for package lookup and discovery"""

    package_type_overview = {
        PackageEndpointType.review_type: {
            "import_name": ReviewTypePackageEndpointInterface,
            "custom_class": "CustomReviewType",
            "operation_name": "operation",
        },
        PackageEndpointType.search_source: {
            "import_name": SearchSourcePackageEndpointInterface,
            "custom_class": "CustomSearchSource",
            "operation_name": "source_operation",
        },
        PackageEndpointType.prep: {
            "import_name": PrepPackageEndpointInterface,
            "custom_class": "CustomPrep",
            "operation_name": "prep_operation",
        },
        PackageEndpointType.prep_man: {
            "import_name": PrepManPackageEndpointInterface,
            "custom_class": "CustomPrepMan",
            "operation_name": "prep_man_operation",
        },
        PackageEndpointType.dedupe: {
            "import_name": DedupePackageEndpointInterface,
            "custom_class": "CustomDedupe",
            "operation_name": "dedupe_operation",
        },
        PackageEndpointType.prescreen: {
            "import_name": PrescreenPackageEndpointInterface,
            "custom_class": "CustomPrescreen",
            "operation_name": "prescreen_operation",
        },
        PackageEndpointType.pdf_get: {
            "import_name": PDFGetPackageEndpointInterface,
            "custom_class": "CustomPDFGet",
            "operation_name": "pdf_get_operation",
        },
        PackageEndpointType.pdf_get_man: {
            "import_name": PDFGetManPackageEndpointInterface,
            "custom_class": "CustomPDFGetMan",
            "operation_name": "pdf_get_man_operation",
        },
        PackageEndpointType.pdf_prep: {
            "import_name": PDFPrepPackageEndpointInterface,
            "custom_class": "CustomPDFPrep",
            "operation_name": "pdf_prep_operation",
        },
        PackageEndpointType.pdf_prep_man: {
            "import_name": PDFPrepManPackageEndpointInterface,
            "custom_class": "CustomPDFPrepMan",
            "operation_name": "pdf_prep_man_operation",
        },
        PackageEndpointType.screen: {
            "import_name": ScreenPackageEndpointInterface,
            "custom_class": "CustomScreen",
            "operation_name": "screen_operation",
        },
        PackageEndpointType.data: {
            "import_name": DataPackageEndpointInterface,
            "custom_class": "CustomData",
            "operation_name": "data_operation",
        },
    }

    package: typing.Dict[str, typing.Dict[str, typing.Dict]]

    def __init__(self, *, verbose: bool = False) -> None:
        self.verbose = verbose
        self.packages = self.__load_package_endpoints_index()
        self.__flag_installed_packages()
        colrev_spec = importlib.util.find_spec("colrev")
        if colrev_spec is None:  # pragma: no cover
            raise colrev_exceptions.MissingDependencyError(dep="colrev")
        if colrev_spec.origin is None:  # pragma: no cover
            raise colrev_exceptions.MissingDependencyError(dep="colrev")
        self.__colrev_path = Path(colrev_spec.origin).parents[1]
        self.__package_endpoints_json_file = self.__colrev_path / Path(
            "colrev/template/package_endpoints.json"
        )
        self.__search_source_types_json_file = self.__colrev_path / Path(
            "colrev/template/search_source_types.json"
        )

    def __load_package_endpoints_index(self) -> dict:
        filedata = colrev.env.utils.get_package_file_content(
            file_path=Path("template/package_endpoints.json")
        )
        if not filedata:
            raise colrev_exceptions.CoLRevException(
                "Package index not available (colrev/template/package_endpoints.json)"
            )

        package_dict = json.loads(filedata.decode("utf-8"))

        packages: typing.Dict[PackageEndpointType, dict] = {}
        for key, package_list in package_dict.items():
            packages[PackageEndpointType[key]] = {}
            for package_item in package_list:
                assert " " not in package_item["package_endpoint_identifier"]
                assert " " not in package_item["endpoint"]
                assert package_item["package_endpoint_identifier"].islower()
                packages[PackageEndpointType[key]][
                    package_item["package_endpoint_identifier"]
                ] = {"endpoint": package_item["endpoint"]}

        return packages

    def __flag_installed_packages(self) -> None:
        for package_type, package_list in self.packages.items():
            for package_identifier, package in package_list.items():
                try:
                    self.load_package_endpoint(
                        package_type=package_type, package_identifier=package_identifier
                    )
                    package["installed"] = True
                except (AttributeError, ModuleNotFoundError) as exc:
                    if hasattr(exc, "name"):
                        if package_identifier.split(".")[0] != exc.name:  # type: ignore
                            if self.verbose:
                                raise exc
                            print(f"Error loading package {package_identifier}: {exc}")

                    package["installed"] = False

    def __replace_path_by_str(self, *, orig_dict):  # type: ignore
        for key, value in orig_dict.items():
            if isinstance(value, collections.abc.Mapping):
                orig_dict[key] = self.__replace_path_by_str(orig_dict=value)
            else:
                if isinstance(value, Path):
                    orig_dict[key] = str(value)
                else:
                    orig_dict[key] = value
        return orig_dict

    def __apply_package_details_fixes(
        self, *, package_type: PackageEndpointType, package_details: dict
    ) -> None:
        # gh_issue https://github.com/CoLRev-Environment/colrev/issues/66
        # apply validation when parsing settings during package init (based on _details)
        # later : package version?

        # Note : fix because Path is not (yet) supported.
        if "paper_path" in package_details["properties"]:
            package_details["properties"]["paper_path"]["type"] = "path"
        if "word_template" in package_details["properties"]:
            package_details["properties"]["word_template"]["type"] = "path"
        if "paper_output" in package_details["properties"]:
            package_details["properties"]["paper_output"]["type"] = "path"

        if PackageEndpointType.search_source == package_type:
            package_details["properties"]["filename"] = {"type": "path"}

        package_details = self.__replace_path_by_str(orig_dict=package_details)  # type: ignore

    def get_package_details(
        self, *, package_type: PackageEndpointType, package_identifier: str
    ) -> dict:
        """Get the package details"""

        package_class = self.load_package_endpoint(
            package_type=package_type, package_identifier=package_identifier.lower()
        )
        settings_class = getattr(package_class, "settings_class", None)
        if settings_class is None:
            msg = f"{package_identifier} could not be loaded"
            raise colrev_exceptions.ServiceNotAvailableException(msg)
        package_details = dict(settings_class.json_schema())  # type: ignore

        # To address cases of inheritance, see:
        # https://stackoverflow.com/questions/22689900/
        # json-schema-allof-with-additionalproperties
        if "allOf" in package_details:
            selection = {}
            for candidate in package_details["allOf"]:
                selection = candidate
                # prefer the one with properties
                if "properties" in candidate:
                    break
            package_details = selection

        for parameter in [
            i for i in settings_class.__annotations__.keys() if i[:1] != "_"
        ]:
            # tooltip, min, max, options: determined from settings_class._details dict
            # Note : tooltips are not in docstrings because
            # attribute docstrings are not supported (https://peps.python.org/pep-0224/)
            # pylint: disable=protected-access

            if not hasattr(settings_class, "_details"):
                continue
            if parameter not in settings_class._details:
                continue
            if "tooltip" in settings_class._details[parameter]:
                package_details["properties"][parameter][
                    "tooltip"
                ] = settings_class._details[parameter]["tooltip"]

            if "min" in settings_class._details[parameter]:
                package_details["properties"][parameter][
                    "min"
                ] = settings_class._details[parameter]["min"]

            if "max" in settings_class._details[parameter]:
                package_details["properties"][parameter][
                    "max"
                ] = settings_class._details[parameter]["max"]

            if "options" in settings_class._details[parameter]:
                package_details["properties"][parameter][
                    "options"
                ] = settings_class._details[parameter]["options"]

        self.__apply_package_details_fixes(
            package_type=package_type, package_details=package_details
        )

        return package_details

    def discover_packages(
        self, *, package_type: PackageEndpointType, installed_only: bool = False
    ) -> typing.Dict:
        """Discover packages"""

        discovered_packages = self.packages[package_type]
        for package_identifier, package in discovered_packages.items():
            if installed_only and not package["installed"]:
                continue
            package_class = self.load_package_endpoint(
                package_type=package_type, package_identifier=package_identifier
            )
            discovered_packages[package_identifier] = package
            discovered_packages[package_identifier][
                "description"
            ] = package_class.__doc__
            discovered_packages[package_identifier]["installed"] = package["installed"]

        return discovered_packages

    def load_package_endpoint(  # type: ignore
        self, *, package_type: PackageEndpointType, package_identifier: str
    ):
        """Load a package endpoint"""

        package_identifier = package_identifier.lower()
        if package_identifier not in self.packages[package_type]:
            raise colrev_exceptions.MissingDependencyError(
                f"{package_identifier} ({package_type}) not available"
            )

        package_str = self.packages[package_type][package_identifier]["endpoint"]
        package_module = package_str.rsplit(".", 1)[0]
        package_class = package_str.rsplit(".", 1)[-1]
        imported_package = importlib.import_module(package_module)
        package_class = getattr(imported_package, package_class)
        return package_class

    def __drop_broken_packages(
        self,
        *,
        packages_dict: dict,
        package_type: PackageEndpointType,
        ignore_not_available: bool,
    ) -> None:
        package_details = self.package_type_overview[package_type]
        broken_packages = []
        for k, val in packages_dict.items():
            if "custom_flag" not in val:
                continue
            try:
                packages_dict[k]["endpoint"] = getattr(  # type: ignore
                    val["endpoint"], package_details["custom_class"]
                )
                del packages_dict[k]["custom_flag"]
            except AttributeError as exc:
                # Note : these may also be (package name) conflicts
                if not ignore_not_available:
                    raise colrev_exceptions.MissingDependencyError(
                        f"Dependency {k} not available"
                    ) from exc
                broken_packages.append(k)
                print(f"Skipping broken package ({k})")
                packages_dict.pop(k, None)

    def __get_packages_dict(
        self,
        *,
        selected_packages: list,
        package_type: PackageEndpointType,
        ignore_not_available: bool,
    ) -> typing.Dict:
        # avoid changes in the config
        selected_packages = deepcopy(selected_packages)

        packages_dict: typing.Dict = {}
        for selected_package in selected_packages:
            package_identifier = selected_package["endpoint"].lower()
            packages_dict[package_identifier] = {}

            packages_dict[package_identifier]["settings"] = selected_package

            # 1. Load built-in packages
            if not Path(package_identifier + ".py").is_file():
                if package_identifier not in self.packages[package_type]:
                    raise colrev_exceptions.MissingDependencyError(
                        "Built-in dependency "
                        + f"{package_identifier} ({package_type}) not in package_endpoints.json. "
                    )
                if not self.packages[package_type][package_identifier][
                    "installed"
                ]:  # pragma: no cover
                    raise colrev_exceptions.MissingDependencyError(
                        f"Dependency {package_identifier} ({package_type}) not found. "
                        f"Please install it\n  pip install {package_identifier.split('.')[0]}"
                    )
                packages_dict[package_identifier][
                    "endpoint"
                ] = self.load_package_endpoint(
                    package_type=package_type, package_identifier=package_identifier
                )

            #     except ModuleNotFoundError as exc:
            #         if ignore_not_available:
            #             print(f"Could not load {selected_package}")
            #             del packages_dict[package_identifier]
            #             continue
            #         raise colrev_exceptions.MissingDependencyError(
            #             "Dependency "
            #             f"{package_identifier} ({package_type}) not installed. "
            #             "Please install it\n  pip install "
            #             f"{package_identifier.split('.')[0]}"
            #         ) from exc

            # 2. Load custom packages in the directory
            elif Path(package_identifier + ".py").is_file():
                try:
                    # to import custom packages from the project dir
                    sys.path.append(".")
                    packages_dict[package_identifier]["settings"] = selected_package
                    packages_dict[package_identifier][
                        "endpoint"
                    ] = importlib.import_module(package_identifier, ".")
                    packages_dict[package_identifier]["custom_flag"] = True
                except ModuleNotFoundError as exc:  # pragma: no cover
                    if ignore_not_available:
                        print(f"Could not load {selected_package}")
                        del packages_dict[package_identifier]
                        continue
                    raise colrev_exceptions.MissingDependencyError(
                        "Dependency "
                        + f"{package_identifier} ({package_type}) not found. "
                        "Please install it\n  pip install "
                        f"{package_identifier.split('.')[0]}"
                    ) from exc

        return packages_dict

    # pylint: disable=too-many-arguments
    def load_packages(
        self,
        *,
        package_type: PackageEndpointType,
        selected_packages: list,
        operation: colrev.operation.Operation,
        ignore_not_available: bool = False,
        instantiate_objects: bool = True,
        only_ci_supported: bool = False,
    ) -> typing.Dict[str, typing.Dict[str, typing.Any]]:
        """Load the packages for a particular package_type"""

        packages_dict = self.__get_packages_dict(
            selected_packages=selected_packages,
            package_type=package_type,
            ignore_not_available=ignore_not_available,
        )
        self.__drop_broken_packages(
            packages_dict=packages_dict,
            package_type=package_type,
            ignore_not_available=ignore_not_available,
        )

        package_details = self.package_type_overview[package_type]
        endpoint_class = package_details["import_name"]  # type: ignore
        to_remove = []
        for package_identifier, package_class in packages_dict.items():
            params = {
                package_details["operation_name"]: operation,
                "settings": package_class["settings"],
            }
            if package_type == "search_source":
                del params["check_operation"]

            if "endpoint" not in package_class:
                raise colrev_exceptions.MissingDependencyError(
                    f"{package_identifier} is not available"
                )

            if instantiate_objects:
                try:
                    packages_dict[package_identifier] = package_class["endpoint"](
                        **params
                    )
                    if only_ci_supported:
                        if not packages_dict[package_identifier].ci_supported:
                            to_remove.append(package_identifier)
                            continue
                    verifyObject(endpoint_class, packages_dict[package_identifier])
                except colrev_exceptions.ServiceNotAvailableException as sna_exc:
                    if sna_exc.dep == "docker":
                        print(
                            f"{Colors.ORANGE}Docker not available. Deactivate "
                            f"{package_identifier}{Colors.END}"
                        )
                        to_remove.append(package_identifier)
                    else:
                        raise sna_exc
            else:
                packages_dict[package_identifier] = package_class["endpoint"]

        packages_dict = {k: v for k, v in packages_dict.items() if k not in to_remove}

        return packages_dict

    def __import_package_docs(self, docs_link: str, identifier: str) -> str:
        extensions_index_path = Path(__file__).parent.parent.parent / Path(
            "docs/source/resources/extensions_index"
        )
        local_built_in_path = Path(__file__).parent.parent / Path("ops/built_in")

        if (
            "https://github.com/CoLRev-Environment/colrev/blob/main/colrev/ops/built_in/"
            in docs_link
        ):
            docs_link = docs_link.replace(
                "https://github.com/CoLRev-Environment/colrev/blob/main/colrev/ops/built_in",
                str(local_built_in_path),
            )
            output = parse_from_file(docs_link)
        else:
            # to be retreived through requests for external packages
            # output = convert('# Title\n\nSentence.')
            return "NotImplemented"

        file_path = Path(f"{identifier}.rst")
        target = extensions_index_path / file_path
        with open(target, "w", encoding="utf-8") as file:
            # NOTE: at this point, we may add metadata
            # (such as package status, authors, url etc.)
            file.write(output)

        return str(file_path)

    def __write_docs_for_index(self, docs_for_index: dict) -> None:
        extensions_index_path = Path(__file__).parent.parent.parent / Path(
            "docs/source/resources/extensions_index.rst"
        )
        extensions_index_path_content = extensions_index_path.read_text(
            encoding="utf-8"
        )
        new_doc = []
        # append header
        for line in extensions_index_path_content.split("\n"):
            new_doc.append(line)
            if ":caption:" in line:
                new_doc.append("")
                break

        # append new links
        for endpoint_type in [
            "review_type",
            "search_source",
            "prep",
            "prep_man",
            "dedupe",
            "prescreen",
            "pdf_get",
            "pdf_get_man",
            "pdf_prep",
            "pdf_prep_man",
            "screen",
            "data",
        ]:
            new_doc.append("")
            new_doc.append(endpoint_type)
            new_doc.append("-----------------------------")
            new_doc.append("")

            new_doc.append(".. toctree::")
            new_doc.append("   :maxdepth: 1")
            new_doc.append("")

            doc_items = docs_for_index[endpoint_type]
            for doc_item in sorted(doc_items, key=lambda d: d["identifier"]):
                if doc_item == "NotImplemented":
                    print(doc_item["path"])
                    continue
                new_doc.append(f"   extensions_index/{doc_item['path']}")

        with open(extensions_index_path, "w", encoding="utf-8") as file:
            for line in new_doc:
                file.write(line + "\n")

    # pylint: disable=too-many-locals
    # pylint: disable=too-many-arguments
    def __add_package_endpoints(
        self,
        *,
        selected_package: str,
        package_endpoints_json: dict,
        package_endpoints: dict,
        docs_for_index: dict,
        package_status: dict,
    ) -> None:
        for endpoint_type, endpoint_list in package_endpoints_json.items():
            if endpoint_type not in package_endpoints["endpoints"]:
                continue

            package_list = "\n -  ".join(
                p["package_endpoint_identifier"]
                for p in package_endpoints["endpoints"][endpoint_type]
            )
            print(f" load {endpoint_type}: \n -  {package_list}")
            for endpoint_item in package_endpoints["endpoints"][endpoint_type]:
                if (
                    not endpoint_item["package_endpoint_identifier"].split(".")[0]
                    == selected_package
                ):
                    continue
                self.packages[PackageEndpointType[endpoint_type]][
                    endpoint_item["package_endpoint_identifier"]
                ] = {"endpoint": endpoint_item["endpoint"], "installed": True}
                endpoint = self.load_package_endpoint(
                    package_type=PackageEndpointType[endpoint_type],
                    package_identifier=endpoint_item["package_endpoint_identifier"],
                )

                # Add development status information (if available on package_status)
                e_list = [
                    x
                    for x in package_status[endpoint_type]
                    if x["package_endpoint_identifier"]
                    == endpoint_item["package_endpoint_identifier"]
                ]
                if e_list:
                    endpoint_item["status"] = e_list[0]["status"]
                else:
                    package_status[endpoint_type].append(
                        {
                            "package_endpoint_identifier": endpoint_item[
                                "package_endpoint_identifier"
                            ],
                            "status": "RED",
                        }
                    )
                    endpoint_item["status"] = "RED"

                endpoint_item["status"] = (
                    endpoint_item["status"]
                    .replace("STABLE", "|STABLE|")
                    .replace("MATURING", "|MATURING|")
                    .replace("EXPERIMENTAL", "|EXPERIMENTAL|")
                )
                endpoint_item["status_linked"] = endpoint_item["status"]

                # Generate the contents displayed in the docs (see "datatemplate:json")
                # load short_description dynamically...
                short_description = endpoint.__doc__
                if "\n" in endpoint.__doc__:
                    short_description = endpoint.__doc__.split("\n")[0]
                endpoint_item["short_description"] = short_description

                endpoint_item["ci_supported"] = endpoint.ci_supported

                code_link = (
                    "https://github.com/CoLRev-Environment/colrev/blob/main/"
                    + endpoint_item["endpoint"].replace(".", "/")
                )
                # In separate packages, we the main readme.md file should be used
                code_link = code_link[: code_link.rfind("/")]
                code_link += ".md"
                if hasattr(endpoint, "docs_link"):
                    docs_link = endpoint.docs_link
                else:
                    docs_link = code_link

                package_index_path = self.__import_package_docs(
                    docs_link, endpoint_item["package_endpoint_identifier"]
                )

                item = {
                    "path": package_index_path,
                    "short_description": endpoint_item["short_description"],
                    "identifier": endpoint_item["package_endpoint_identifier"],
                }
                try:
                    docs_for_index[endpoint_type].append(item)
                except KeyError:
                    docs_for_index[endpoint_type] = [item]

                # Note: link format for the sphinx docs
                endpoint_item["short_description"] = (
                    endpoint_item["short_description"]
                    + " (:doc:`instructions </resources/extensions_index/"
                    + f"{endpoint_item['package_endpoint_identifier']}>`)"
                )
                if endpoint_type == "search_source":
                    endpoint_item["search_types"] = [
                        x.value for x in endpoint.search_types
                    ]

            endpoint_list += [
                x
                for x in package_endpoints["endpoints"][endpoint_type]
                if x["package_endpoint_identifier"].split(".")[0] == selected_package
            ]

    def __extract_search_source_types(self, *, package_endpoints_json: dict) -> None:
        search_source_types: typing.Dict[str, list] = {}
        for search_source_type in colrev.settings.SearchType:
            if search_source_type.value not in search_source_types:
                search_source_types[search_source_type.value] = []
            for search_source in package_endpoints_json["search_source"]:
                if search_source_type.value in search_source["search_types"]:
                    search_source_types[search_source_type.value].append(search_source)

        for key in search_source_types:
            search_source_types[key] = sorted(
                search_source_types[key],
                key=lambda d: d["package_endpoint_identifier"],
            )

        json_object = json.dumps(search_source_types, indent=4)
        with open(self.__search_source_types_json_file, "w", encoding="utf-8") as file:
            file.write(json_object)
            file.write("\n")  # to avoid pre-commit/eof-fix changes

    def __load_packages_json(self) -> list:
        filedata = colrev.env.utils.get_package_file_content(
            file_path=Path("template/packages.json")
        )
        if not filedata:  # pragma: no cover
            raise colrev_exceptions.CoLRevException(
                "Package index not available (colrev/template/packages.json)"
            )
        packages = json.loads(filedata.decode("utf-8"))
        return packages

    def __load_package_status_json(self) -> dict:
        filedata = colrev.env.utils.get_package_file_content(
            file_path=Path("template/package_status.json")
        )
        if not filedata:  # pragma: no cover
            raise colrev_exceptions.CoLRevException(
                "Package index not available (colrev/template/package_status.json)"
            )
        packages = json.loads(filedata.decode("utf-8"))
        return packages

    def update_package_list(self) -> None:
        """Generates the template/package_endpoints.json
        based on the packages in template/packages.json
        and the endpoints.json files in the top directory of each package."""

        os.chdir(self.__colrev_path)
        packages = self.__load_packages_json()
        package_status = self.__load_package_status_json()
        self.__package_endpoints_json_file.unlink(missing_ok=True)

        package_endpoints_json: typing.Dict[str, list] = {
            x.name: [] for x in self.package_type_overview
        }
        docs_for_index: typing.Dict[str, list] = {}

        for package in packages:
            print(f'Loading package endpoints from {package["module"]}')
            module_spec = importlib.util.find_spec(package["module"])

            endpoints_path = Path(module_spec.origin).parent / Path(  # type:ignore
                ".colrev_endpoints.json"
            )
            if not endpoints_path.is_file():  # pragma: no cover
                print(f"File does not exist: {endpoints_path}")
                continue

            try:
                with open(endpoints_path, encoding="utf-8") as file:
                    package_endpoints = json.load(file)
            except json.decoder.JSONDecodeError as exc:  # pragma: no cover
                print(f"Invalid json {exc}")
                continue

            self.__add_package_endpoints(
                selected_package=package["module"],
                package_endpoints_json=package_endpoints_json,
                package_endpoints=package_endpoints,
                docs_for_index=docs_for_index,
                package_status=package_status,
            )
            self.__extract_search_source_types(
                package_endpoints_json=package_endpoints_json
            )
        for key in package_endpoints_json.keys():
            package_endpoints_json[key] = sorted(
                package_endpoints_json[key],
                key=lambda d: d["package_endpoint_identifier"],
            )

        json_object = json.dumps(package_endpoints_json, indent=4)
        with open(self.__package_endpoints_json_file, "w", encoding="utf-8") as file:
            file.write(json_object)
            file.write("\n")  # to avoid pre-commit/eof-fix changes

        json_object = json.dumps(package_status, indent=4)
        with open(
            Path("colrev/template/package_status.json"), "w", encoding="utf-8"
        ) as file:
            file.write(json_object)
            file.write("\n")  # to avoid pre-commit/eof-fix changes

        self.__write_docs_for_index(docs_for_index)

    # pylint: disable=too-many-locals
    def add_endpoint_for_operation(
        self,
        *,
        operation: colrev.operation.Operation,
        package_identifier: str,
        params: str,
        prompt_on_same_source: bool = True,
    ) -> None:
        """Add a package_endpoint"""

        settings = operation.review_manager.settings
        package_type_dict = {
            colrev.operation.OperationsType.search: {
                "package_type": colrev.env.package_manager.PackageEndpointType.search_source,
                "endpoint_location": settings.sources,
            },
            colrev.operation.OperationsType.prep: {
                "package_type": colrev.env.package_manager.PackageEndpointType.prep,
                "endpoint_location": settings.prep.prep_rounds[
                    0
                ].prep_package_endpoints,
            },
            colrev.operation.OperationsType.prep_man: {
                "package_type": colrev.env.package_manager.PackageEndpointType.prep_man,
                "endpoint_location": settings.prep.prep_man_package_endpoints,
            },
            colrev.operation.OperationsType.dedupe: {
                "package_type": colrev.env.package_manager.PackageEndpointType.dedupe,
                "endpoint_location": settings.dedupe.dedupe_package_endpoints,
            },
            colrev.operation.OperationsType.prescreen: {
                "package_type": colrev.env.package_manager.PackageEndpointType.prescreen,
                "endpoint_location": settings.prescreen.prescreen_package_endpoints,
            },
            colrev.operation.OperationsType.pdf_get: {
                "package_type": colrev.env.package_manager.PackageEndpointType.pdf_get,
                "endpoint_location": settings.pdf_get.pdf_get_package_endpoints,
            },
            colrev.operation.OperationsType.pdf_get_man: {
                "package_type": colrev.env.package_manager.PackageEndpointType.pdf_get_man,
                "endpoint_location": settings.pdf_get.pdf_get_man_package_endpoints,
            },
            colrev.operation.OperationsType.pdf_prep: {
                "package_type": colrev.env.package_manager.PackageEndpointType.pdf_prep,
                "endpoint_location": settings.pdf_prep.pdf_prep_package_endpoints,
            },
            colrev.operation.OperationsType.pdf_prep_man: {
                "package_type": colrev.env.package_manager.PackageEndpointType.pdf_prep_man,
                "endpoint_location": settings.pdf_prep.pdf_prep_man_package_endpoints,
            },
            colrev.operation.OperationsType.screen: {
                "package_type": colrev.env.package_manager.PackageEndpointType.screen,
                "endpoint_location": settings.screen.screen_package_endpoints,
            },
            colrev.operation.OperationsType.data: {
                "package_type": colrev.env.package_manager.PackageEndpointType.data,
                "endpoint_location": settings.data.data_package_endpoints,
            },
        }

        package_type = package_type_dict[operation.type]["package_type"]
        endpoints = package_type_dict[operation.type]["endpoint_location"]

        registered_endpoints = [
            e["endpoint"] if isinstance(e, dict) else e.endpoint for e in endpoints  # type: ignore
        ]
        if package_identifier in registered_endpoints and prompt_on_same_source:
            operation.review_manager.logger.warning(
                f"Package {package_identifier} already in {endpoints}"
            )
            if "y" != input("Continue [y/n]?"):
                return

        operation.review_manager.logger.info(
            f"{Colors.GREEN}Add {operation.type} package:{Colors.END} {package_identifier}"
        )

        endpoint_dict = self.load_packages(
            package_type=package_type,  # type: ignore
            selected_packages=[{"endpoint": package_identifier}],
            operation=operation,
            instantiate_objects=False,
        )

        e_class = endpoint_dict[package_identifier]
        if hasattr(endpoint_dict[package_identifier], "add_endpoint"):
            if params:
                if params.startswith("http"):
                    params_dict = {Fields.URL: params}
                else:
                    params_dict = {}
                    for item in params.split(";"):
                        key, value = item.split("=")
                        params_dict[key] = value
            else:
                params_dict = {}
            add_source = e_class.add_endpoint(  # type: ignore
                operation=operation, params=params_dict
            )
            operation.review_manager.settings.sources.append(add_source)
            operation.review_manager.save_settings()
            operation.review_manager.dataset.add_changes(
                path=add_source.filename, ignore_missing=True
            )

        else:
            add_package = {"endpoint": package_identifier}
            endpoints.append(add_package)  # type: ignore

        operation.review_manager.save_settings()
        operation.review_manager.create_commit(
            msg=f"Add {operation.type} {package_identifier}",
        )
