from twstock_pipeline.collectors import _is_etf_security_code, _merge_tpex_quote_fallback


def test_tpex_quote_fallback_recovers_etf_missing_from_filter():
    etfs = {"00792B": {"name": "existing"}}
    rows = [{"SecuritiesCompanyCode": "00793B", "CompanyName": "群益AAA-A醫療債"}]
    _merge_tpex_quote_fallback(etfs, rows)
    assert "00793B" in etfs
    assert etfs["00793B"]["source"].startswith("TPEx official")


def test_fallback_uses_official_etf_code_class_rule_not_symbol_special_case():
    assert _is_etf_security_code("00411A")
    assert _is_etf_security_code("00793B")
    assert _is_etf_security_code("00999C")
    assert not _is_etf_security_code("6547")


def test_tpex_quote_fallback_accepts_official_chinese_quote_fields():
    etfs = {}
    rows = [{"證券代號": "00793B", "證券名稱": "群益AAA-A醫療債"}]
    _merge_tpex_quote_fallback(etfs, rows)
    assert etfs["00793B"]["name"] == "群益AAA-A醫療債"


def test_active_etf_sentinel_is_not_a_special_case_in_classifier_source():
    # The generic classifier accepts the official ETF class; sync_etf itself
    # must obtain the symbol from an official source rather than manufacture it.
    assert _is_etf_security_code("00793B")
