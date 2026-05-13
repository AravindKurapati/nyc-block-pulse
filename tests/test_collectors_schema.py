"""Contract tests for collectors that were broken against live Socrata schemas.

These tests capture the exact dataset IDs and $select field lists each
collector sends, and assert they match the current published schemas:

- DOB Permit Issuance (ipu4-2q9a): valid $select field names
- HPD Complaints (ygpa-z7cr): current dataset ID, not retired uwyv-629c
- SLA Liquor Licenses (9s3h-dpkz on data.ny.gov): current dataset ID, not retired wg8y-fzsj
"""
from __future__ import annotations

from nyc_pulse.collectors import dob_permits, hpd_complaints, liquor


# Valid field names taken from data.cityofnewyork.us/api/views/rbx6-tga4.json
# (the legacy ipu4-2q9a dataset is frozen since 2020-06; current permits live
# in DOB NOW: Build – Approved Permits = rbx6-tga4). Fields the collector
# references that are NOT in this set will produce a 400 from Socrata.
DOB_VALID_FIELDS = {
    "applicant_business_address", "applicant_business_name",
    "applicant_first_name", "applicant_last_name", "applicant_license",
    "applicant_middle_name", "approved_date", "apt_condo_no_s", "bbl", "bin",
    "block", "borough", "c_b_no", "census_tract", "community_board",
    "council_district", "estimated_job_costs", "expired_date", "filing_reason",
    "filing_representative_business_name", "filing_representative_first_name",
    "filing_representative_last_name", "filing_representative_middle_initial",
    "house_no", "issued_date", "job_description", "job_filing_number",
    "latitude", "longitude", "lot", "nta", "owner_business_name", "owner_city",
    "owner_name", "owner_state", "owner_street_address", "owner_zip_code",
    "permit_status", "permittee_s_license_type", "sequence_number",
    "street_name", "tracking_number", "work_on_floor", "work_permit",
    "work_type", "zip_code",
}


def test_dob_uses_current_dataset_id(monkeypatch):
    """ipu4-2q9a is frozen at 2020; current DOB permits are in rbx6-tga4."""
    captured = {}

    def fake_fetch(dataset_id, where, select, limit=50_000, offset=0):
        captured["dataset_id"] = dataset_id
        captured["select"] = select
        captured["where"] = where
        return []

    monkeypatch.setattr(dob_permits, "fetch_socrata", fake_fetch)
    dob_permits.collect_dob_permits(days=7)

    assert captured["dataset_id"] == "rbx6-tga4", (
        f"DOB collector must hit rbx6-tga4 (DOB NOW: Build – Approved Permits); "
        f"ipu4-2q9a was decommissioned and stops at 2020-06. "
        f"Saw: {captured.get('dataset_id')!r}"
    )
    # Date filter must use issued_date (the DOB NOW analog).
    assert "issued_date" in captured["where"]

    select_fields = {f.strip() for f in captured["select"].split(",")}
    invalid = select_fields - DOB_VALID_FIELDS
    assert not invalid, (
        f"DOB $select references fields that don't exist in rbx6-tga4: {invalid}. "
        f"This causes Socrata to return HTTP 400 for the entire request."
    )


def test_hpd_complaints_uses_current_dataset_id(monkeypatch):
    captured = {}

    def fake_fetch(dataset_id, where, select, limit=50_000, offset=0):
        captured["dataset_id"] = dataset_id
        captured["where"] = where
        captured["select"] = select
        return []

    monkeypatch.setattr(hpd_complaints, "fetch_socrata", fake_fetch)
    hpd_complaints.collect_hpd_complaints(days=7)

    assert captured["dataset_id"] == "ygpa-z7cr", (
        f"hpd_complaints points at {captured['dataset_id']!r} which is retired; "
        f"the current Housing Maintenance Code Complaints dataset is ygpa-z7cr "
        f"(retired IDs return HTTP 403)"
    )
    # Schema sanity: current dataset uses received_date / complaint_id / etc.
    assert "received_date" in captured["where"], (
        "HPD complaints date filter must use received_date (not opendate, which "
        "doesn't exist in the current schema)"
    )
    select_fields = {f.strip() for f in captured["select"].split(",")}
    # A few sentinel fields that MUST exist in the new schema.
    assert "complaint_id" in select_fields
    assert "received_date" in select_fields


def test_hpd_complaints_normalizes_new_schema(monkeypatch):
    """Verify field-name mapping handles the new dataset shape, not the old."""

    def fake_fetch(dataset_id, where, select, limit=50_000, offset=0):
        return [
            {
                "complaint_id": "12345",
                "problem_id": "67890",
                "type": "EMERGENCY",
                "major_category": "HEAT/HOT WATER",
                "minor_category": "ENTIRE BUILDING",
                "problem_code": "NO HEAT",
                "house_number": "123",
                "street_name": "MAIN ST",
                "borough": "MANHATTAN",
                "bbl": "1000010001",
                "bin": "1000001",
                "latitude": "40.7",
                "longitude": "-73.9",
                "received_date": "2026-05-01T00:00:00",
                "complaint_status": "OPEN",
            }
        ]

    monkeypatch.setattr(hpd_complaints, "fetch_socrata", fake_fetch)
    events = hpd_complaints.collect_hpd_complaints(days=7)

    assert len(events) == 1
    e = events[0]
    assert e["id"] == "hpd_complaint_12345"
    assert e["source"] == "hpd_complaints"
    assert e["lat"] == 40.7
    assert e["lon"] == -73.9
    assert e["status"] == "OPEN"
    assert e["address"] == "123 MAIN ST"
    assert e["bbl"] == "1000010001"
    assert e["bin"] == "1000001"


def test_liquor_uses_current_dataset_id(monkeypatch):
    """SLA dataset wg8y-fzsj is retired; current is 9s3h-dpkz."""
    captured = {}

    def fake_fetch(dataset_id, where, limit=50_000, offset=0, select="*", base_url=None):
        captured["dataset_id"] = dataset_id
        captured["where"] = where
        captured["base_url"] = base_url
        return []

    monkeypatch.setattr(liquor, "fetch_socrata", fake_fetch)
    liquor.collect_liquor(limit=2)

    assert captured["dataset_id"] == "9s3h-dpkz", (
        f"liquor collector must hit dataset 9s3h-dpkz (current), not the retired "
        f"wg8y-fzsj. Saw: {captured.get('dataset_id')!r}"
    )
    # Must point at NY State portal, not NYC.
    assert captured["base_url"] and "data.ny.gov" in captured["base_url"]
    # County filter must be case-insensitive (the new dataset stores mixed-case).
    assert "premisescounty" in captured["where"]


def test_liquor_normalizes_new_schema(monkeypatch):
    """Verify field-name mapping uses the new SLA schema."""

    rows_payload = [
        {
            "licensepermitid": "0001-22-100483",
            "premisescounty": "New York",
            "type": "1",
            "class": "0340",
            "description": "Restaurant",
            "legalname": "ACME RESTAURANT LLC",
            "dba": "ACME GRILL",
            "actualaddressofpremises": "123 BROADWAY",
            "city": "NEW YORK",
            "statename": "New York",
            "zipcode": "10001",
            "originalissuedate": "2024-01-01T00:00:00.000",
            "effectivedate": "2025-01-01T00:00:00.000",
            "expirationdate": "2027-01-01T00:00:00.000",
            "georeference": {"coordinates": [-73.99, 40.75], "type": "Point"},
        }
    ]

    def fake_fetch(*a, **k):
        return rows_payload

    monkeypatch.setattr(liquor, "fetch_socrata", fake_fetch)
    events = liquor.collect_liquor(limit=2)
    assert len(events) == 1
    e = events[0]
    assert e["id"] == "sla_0001-22-100483"
    assert e["source"] == "liquor"
    assert e["lat"] == 40.75
    assert e["lon"] == -73.99
    # Description-based event_type (Restaurant/Liquor Store/etc.)
    assert "Restaurant" in (e["event_type"] or e["category"] or "")


def test_nypd_crime_uses_correct_dataset_and_fields(monkeypatch):
    captured = {}

    def fake_fetch(dataset_id, where, select, limit=50_000, offset=0):
        captured["dataset_id"] = dataset_id
        captured["where"] = where
        captured["select"] = select
        return []

    from nyc_pulse.collectors import nypd_crime

    monkeypatch.setattr(nypd_crime, "fetch_socrata", fake_fetch)
    nypd_crime.collect_nypd_crime(days=7)

    assert captured["dataset_id"] == "qgea-i56i"
    assert "cmplnt_fr_dt" in captured["where"]
    select_fields = {f.strip() for f in captured["select"].split(",")}
    for required in (
        "cmplnt_num",
        "cmplnt_fr_dt",
        "ofns_desc",
        "law_cat_cd",
        "latitude",
        "longitude",
    ):
        assert required in select_fields, f"Missing field: {required}"


def test_nypd_crime_normalizes_row(monkeypatch):
    from nyc_pulse.collectors import nypd_crime

    def fake_fetch(*a, **k):
        return [
            {
                "cmplnt_num": "123456789",
                "cmplnt_fr_dt": "2026-05-01T00:00:00",
                "ofns_desc": "ASSAULT 3 & RELATED OFFENSES",
                "law_cat_cd": "MISDEMEANOR",
                "latitude": "40.73082",
                "longitude": "-73.99763",
                "boro_nm": "MANHATTAN",
            }
        ]

    monkeypatch.setattr(nypd_crime, "fetch_socrata", fake_fetch)
    events = nypd_crime.collect_nypd_crime(days=7)

    assert len(events) == 1
    e = events[0]
    assert e["id"] == "crime_123456789"
    assert e["source"] == "nypd_crime"
    assert e["event_type"] == "misdemeanor"
    assert e["lat"] == 40.73082
    assert e["lon"] == -73.99763


def test_fdny_fire_uses_correct_dataset_and_fields(monkeypatch):
    captured = {}

    def fake_fetch(dataset_id, where, select, limit=50_000, offset=0):
        captured["dataset_id"] = dataset_id
        captured["where"] = where
        captured["select"] = select
        return []

    from nyc_pulse.collectors import fdny_fire

    monkeypatch.setattr(fdny_fire, "fetch_socrata", fake_fetch)
    fdny_fire.collect_fdny_fire(days=7)

    assert captured["dataset_id"] == "erm2-nwe9"
    assert "incident_datetime" in captured["where"]
    select_fields = {f.strip() for f in captured["select"].split(",")}
    for required in (
        "starfire_incident_id",
        "incident_datetime",
        "incident_type_desc",
        "latitude",
        "longitude",
    ):
        assert required in select_fields, f"Missing field: {required}"


def test_fdny_fire_normalizes_row(monkeypatch):
    from nyc_pulse.collectors import fdny_fire

    def fake_fetch(*a, **k):
        return [
            {
                "starfire_incident_id": "987654",
                "incident_datetime": "2026-05-02T14:30:00",
                "incident_type_desc": "300 - Rescue, EMS incident, other",
                "latitude": "40.74220",
                "longitude": "-73.97440",
                "borough_desc": "3 - Manhattan",
            }
        ]

    monkeypatch.setattr(fdny_fire, "fetch_socrata", fake_fetch)
    events = fdny_fire.collect_fdny_fire(days=7)

    assert len(events) == 1
    e = events[0]
    assert e["id"] == "fire_987654"
    assert e["source"] == "fdny_fire"
    assert e["event_type"] == "fire_incident"
    assert e["lat"] == 40.74220
    assert e["lon"] == -73.97440


def test_evictions_uses_correct_dataset_and_fields(monkeypatch):
    captured = {}

    def fake_fetch(dataset_id, where, select, limit=50_000, offset=0):
        captured["dataset_id"] = dataset_id
        captured["where"] = where
        captured["select"] = select
        return []

    from nyc_pulse.collectors import evictions

    monkeypatch.setattr(evictions, "fetch_socrata", fake_fetch)
    evictions.collect_evictions(days=7)

    assert captured["dataset_id"] == "6z8x-vjye"
    assert "executed_date" in captured["where"]
    select_fields = {f.strip() for f in captured["select"].split(",")}
    for required in (
        "court_index_number",
        "executed_date",
        "eviction_address",
        "latitude",
        "longitude",
    ):
        assert required in select_fields, f"Missing field: {required}"


def test_evictions_normalizes_row(monkeypatch):
    from nyc_pulse.collectors import evictions

    def fake_fetch(*a, **k):
        return [
            {
                "court_index_number": "LT-001234-26/BX",
                "executed_date": "2026-04-15T00:00:00",
                "eviction_address": "100 MAIN ST",
                "latitude": "40.85460",
                "longitude": "-73.89030",
                "borough": "BRONX",
                "residential_commercial_ind": "Residential",
            }
        ]

    monkeypatch.setattr(evictions, "fetch_socrata", fake_fetch)
    events = evictions.collect_evictions(days=7)

    assert len(events) == 1
    e = events[0]
    assert e["id"] == "eviction_LT-001234-26/BX_2026-04-15"
    assert e["source"] == "evictions"
    assert e["event_type"] == "eviction"
    assert e["address"] == "100 MAIN ST"
    assert e["lat"] == 40.85460
    assert e["lon"] == -73.89030
