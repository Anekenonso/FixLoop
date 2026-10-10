from src.fixloop import enrichment

def test_enrich_contributor_offline_fallback():
    res = enrichment.enrich_contributor("tester", mock=True)
    assert res["ok"] is True
    assert res["provider"] == "crustdata"
    assert res["company"] == "OpenSource Contributor"
    assert "team_size" in res

def test_enrich_contributor_enterprise_user():
    res = enrichment.enrich_contributor("enterprise_lead", mock=True)
    assert res["ok"] is True
    assert res["company"] == "Enterprise Partner"
    assert res["tier"] == "enterprise_tier_2"

def test_analyze_target_market():
    market = enrichment.analyze_target_market(5000)
    assert market["credits_available"] == 5000
    assert market["potential_icp_queries"] == 500
    assert "Python" in market["primary_icp"]
