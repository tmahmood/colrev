#!/usr/bin/env python
"""Test the exclude_languages prep package"""
import pytest

import colrev.ops.built_in.prep.exclude_languages
import colrev.ops.prep
from colrev.constants import Fields


@pytest.fixture(scope="package", name="elp_elp")
def elp(
    prep_operation: colrev.ops.prep.Prep,
) -> colrev.ops.built_in.prep.exclude_languages.ExcludeLanguagesPrep:
    """Fixture returning an ExcludeLanguagesPrep instance"""
    settings = {"endpoint": "colrev.exclude_languages"}
    elp_instance = colrev.ops.built_in.prep.exclude_languages.ExcludeLanguagesPrep(
        prep_operation=prep_operation, settings=settings
    )
    return elp_instance


@pytest.mark.parametrize(
    "input_value, expected",
    [
        (
            {
                Fields.TITLE: "An Integrated Framework for Understanding Digital Work in Organizations",
            },
            {
                Fields.TITLE: "An Integrated Framework for Understanding Digital Work in Organizations",
                Fields.LANGUAGE: "eng",
                Fields.D_PROV: {
                    Fields.LANGUAGE: {"note": "", "source": "LanguageDetector"}
                },
            },
        ),
        (
            {
                Fields.TITLE: 'Corrigendum to "Joint collaborative planning as a governance mechanism to strengthen the chain of IT value co-creation" [J. Strategic Inf. Syst. 21(3) (2012) 182-200]',
            },
            {
                Fields.TITLE: 'Corrigendum to "Joint collaborative planning as a governance mechanism to strengthen the chain of IT value co-creation" [J. Strategic Inf. Syst. 21(3) (2012) 182-200]',
                Fields.LANGUAGE: "eng",
                Fields.D_PROV: {
                    Fields.LANGUAGE: {"note": "", "source": "LanguageDetector"}
                },
            },
        ),
        (
            {
                Fields.TITLE: "A discussion about Action Research studies and their variations in Smart Cities and the challenges in Latin America [Uma discussão sobre o uso da Pesquisa-Ação e suas variações em estudos sobre Cidades Inteligentes e os desafios na América Latina]"
            },
            {
                Fields.TITLE: "A discussion about Action Research studies and their variations in Smart Cities and the challenges in Latin America",
                "title_por": "Uma discussão sobre o uso da Pesquisa-Ação e suas variações em estudos sobre Cidades Inteligentes e os desafios na América Latina",
                Fields.D_PROV: {
                    Fields.LANGUAGE: {"note": "", "source": "LanguageDetector_split"},
                    "title_por": {"note": "", "source": "LanguageDetector_split"},
                },
                Fields.MD_PROV: {
                    Fields.TITLE: {
                        "note": "",
                        "source": "original|LanguageDetector_split",
                    }
                },
                Fields.LANGUAGE: "eng",
            },
        ),
        (
            {
                Fields.TITLE: "Coliving housing: home cultures of precarity for the new creative class [Alojamiento en convivencia: culturas domésticas de la precariedad para la nueva clase creativa] [La vie en colocation : les cultures du domicile issues de la précarité et la nouvelle classe créative]"
            },
            {
                Fields.TITLE: "Coliving housing: home cultures of precarity for the new creative class",
                "title_spa": "Alojamiento en convivencia: culturas domésticas de la precariedad para la nueva clase creativa",
                "title_fra": "La vie en colocation : les cultures du domicile issues de la précarité et la nouvelle classe créative",
                Fields.D_PROV: {
                    Fields.LANGUAGE: {"note": "", "source": "LanguageDetector_split"},
                    "title_fra": {"note": "", "source": "LanguageDetector_split"},
                    "title_spa": {"note": "", "source": "LanguageDetector_split"},
                },
                Fields.MD_PROV: {
                    Fields.TITLE: {
                        "note": "",
                        "source": "original|LanguageDetector_split",
                    }
                },
                Fields.LANGUAGE: "eng",
            },
        ),
    ],
)
def test_prep_exclude_languages(
    elp_elp: colrev.ops.built_in.prep.exclude_languages.ExcludeLanguagesPrep,
    input_value: dict,
    expected: dict,
) -> None:
    """Test the prep_exclude_languages"""
    record = colrev.record.PrepRecord(data=input_value)
    returned_record = elp_elp.prepare(prep_operation=elp_elp, record=record)
    actual = returned_record.data
    assert expected == actual
