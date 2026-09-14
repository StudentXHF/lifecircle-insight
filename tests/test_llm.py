import pytest

from app.services.llm import LLMAPIError, _chat_completions_url, _evidence_payload, _extract_content


def test_llm_url_accepts_base_or_full_endpoint():
    assert _chat_completions_url('http://model.local/v1') == 'http://model.local/v1/chat/completions'
    full = 'http://model.local/v1/chat/completions'
    assert _chat_completions_url(full) == full


def test_llm_evidence_excludes_pois_coordinates_and_api_details():
    evidence = _evidence_payload(
        {
            'mode': 'real',
            'center_name': '社区',
            'city': '上海市',
            'coverage': {},
            'blind_spots': [{'missing_labels': ['药店'], 'lng': 121.6, 'lat': 31.2}],
            'warnings': [],
            'pois': [{'name': '敏感设施名称'}],
            'api_stats': {'calls': [{'url': 'secret'}]},
        }
    )
    text = str(evidence)
    assert '121.6' not in text
    assert '敏感设施名称' not in text
    assert 'secret' not in text
    assert evidence['blind_spot_missing_categories'] == ['药店']


def test_llm_empty_content_reports_safe_diagnostics():
    with pytest.raises(LLMAPIError, match='reasoning_chars=3'):
        _extract_content(
            {
                'choices': [
                    {
                        'finish_reason': 'length',
                        'message': {'content': '', 'reasoning_content': '思考中'},
                    }
                ]
            }
        )
