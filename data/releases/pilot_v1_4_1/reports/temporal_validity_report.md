# Temporal Validity Report

**Run ID:** `95bac495-6940-47be-b3ff-339fd97afa3e`  
**Pipeline run date:** 2026-07-24  
**Observations:** 25

## Temporal fit distribution (selected snapshots)

- **high:** 13
  - BLUE MOON COMMUNICATION CONSULTANTS GMBH / pre_event (target 2022-07-01, capture 2022-07-07, Δ=6.0d)
  - PETER-LACKE HOLDING GMBH / pre_pre_event (target 2011-07-01, capture 2011-07-09, Δ=8.0d)
  - PETER-LACKE HOLDING GMBH / pre_event (target 2013-07-01, capture 2013-07-03, Δ=2.0d)
  - PETER-LACKE HOLDING GMBH / event (target 2015-07-01, capture 2015-05-22, Δ=40.0d)
  - ANLAGENTECHNIK LEICHTLE GMBH / pre_pre_event (target 2019-07-01, capture 2019-07-23, Δ=22.0d)
  - ANLAGENTECHNIK LEICHTLE GMBH / pre_event (target 2021-07-01, capture 2021-06-23, Δ=8.0d)
  - ANLAGENTECHNIK LEICHTLE GMBH / event (target 2023-07-01, capture 2023-05-29, Δ=33.0d)
  - ANLAGENTECHNIK LEICHTLE GMBH / post_event (target 2025-07-01, capture 2025-06-15, Δ=16.0d)
  - MYRENNE GMBH / pre_pre_event (target 2008-07-01, capture 2008-08-20, Δ=50.0d)
  - MYRENNE GMBH / pre_event (target 2010-07-01, capture 2010-04-27, Δ=65.0d)
  - MYRENNE GMBH / post_event (target 2014-07-01, capture 2014-05-17, Δ=45.0d)
  - MYRENNE GMBH / post_post_event (target 2016-07-01, capture 2016-08-01, Δ=31.0d)
  - MSF-VATHAUER ANTRIEBSTECHNIK GMBH & CO. KG / post_post_event (target 2010-07-01, capture 2010-06-18, Δ=13.0d)
- **moderate:** 4
  - BLUE MOON COMMUNICATION CONSULTANTS GMBH / pre_pre_event (target 2020-07-01, capture 2020-11-01, Δ=123.0d)
  - BLUE MOON COMMUNICATION CONSULTANTS GMBH / post_event (target 2026-07-01, capture 2026-03-04, Δ=119.0d)
  - MSF-VATHAUER ANTRIEBSTECHNIK GMBH & CO. KG / event (target 2006-01-01, capture 2005-09-09, Δ=114.0d)
  - MSF-VATHAUER ANTRIEBSTECHNIK GMBH & CO. KG / post_event (target 2008-07-01, capture 2008-03-27, Δ=96.0d)
- **low:** 2
  - BLUE MOON COMMUNICATION CONSULTANTS GMBH / event (target 2024-07-01, capture 2025-03-14, Δ=256.0d)
  - MSF-VATHAUER ANTRIEBSTECHNIK GMBH & CO. KG / pre_pre_event (target 2002-07-01, capture 2001-07-23, Δ=343.0d)
- **very_low:** 1
  - MSF-VATHAUER ANTRIEBSTECHNIK GMBH & CO. KG / pre_event (target 2004-07-01, capture 2005-09-09, Δ=435.0d)

## Event snapshots vs known event dates

- **BLUE MOON COMMUNICATION CONSULTANTS GMBH:** status=selected, event_date=2024-07-01, capture=2025-03-14, position=after_event, days_from_event=256.0
- **PETER-LACKE HOLDING GMBH:** status=selected, event_date=2015-07-01, capture=2015-05-22, position=before_event, days_from_event=-40.0
- **ANLAGENTECHNIK LEICHTLE GMBH:** status=selected, event_date=2023-07-01, capture=2023-05-29, position=before_event, days_from_event=-33.0
- **MYRENNE GMBH:** status=event_unavailable, event_date=2012-04-15, capture=2011-08-10, position=before_event, days_from_event=-249.0
- **MSF-VATHAUER ANTRIEBSTECHNIK GMBH & CO. KG:** status=selected, event_date=2006-01-01, capture=2005-09-09, position=before_event, days_from_event=-114.0

## Adjacent-period overlap

- MSF-VATHAUER ANTRIEBSTECHNIK GMBH & CO. KG / pre_event: gap=1509 days to previous selected capture
- MSF-VATHAUER ANTRIEBSTECHNIK GMBH & CO. KG / event: gap=0 days to previous selected capture

## Homepage missing but archived subpages available

- PETER-LACKE HOLDING GMBH / post_event
- PETER-LACKE HOLDING GMBH / post_post_event

## Observation recommendations

### include (16)
- BLUE MOON COMMUNICATION CONSULTANTS GMBH / pre_pre_event [selected, fit=moderate]
- BLUE MOON COMMUNICATION CONSULTANTS GMBH / pre_event [selected, fit=high]
- BLUE MOON COMMUNICATION CONSULTANTS GMBH / event [selected, fit=low]
- BLUE MOON COMMUNICATION CONSULTANTS GMBH / post_event [selected, fit=moderate]
- PETER-LACKE HOLDING GMBH / pre_pre_event [selected, fit=high]
- PETER-LACKE HOLDING GMBH / pre_event [selected, fit=high]
- ANLAGENTECHNIK LEICHTLE GMBH / pre_pre_event [selected, fit=high]
- ANLAGENTECHNIK LEICHTLE GMBH / pre_event [selected, fit=high]
- ANLAGENTECHNIK LEICHTLE GMBH / post_event [selected, fit=high]
- MYRENNE GMBH / pre_pre_event [selected, fit=high]
- MYRENNE GMBH / pre_event [selected, fit=high]
- MYRENNE GMBH / post_event [selected, fit=high]
- MYRENNE GMBH / post_post_event [selected, fit=high]
- MSF-VATHAUER ANTRIEBSTECHNIK GMBH & CO. KG / pre_pre_event [selected, fit=low]
- MSF-VATHAUER ANTRIEBSTECHNIK GMBH & CO. KG / post_event [selected, fit=moderate]
- MSF-VATHAUER ANTRIEBSTECHNIK GMBH & CO. KG / post_post_event [selected, fit=high]

### sensitivity_analysis (3)
- PETER-LACKE HOLDING GMBH / event [selected, fit=high]
- ANLAGENTECHNIK LEICHTLE GMBH / event [selected, fit=high]
- MSF-VATHAUER ANTRIEBSTECHNIK GMBH & CO. KG / event [selected, fit=moderate]

### exclude (5)
- BLUE MOON COMMUNICATION CONSULTANTS GMBH / post_post_event [future_unavailable, fit=None]
- PETER-LACKE HOLDING GMBH / post_event [beyond_tolerance, fit=None]
- PETER-LACKE HOLDING GMBH / post_post_event [beyond_tolerance, fit=None]
- ANLAGENTECHNIK LEICHTLE GMBH / post_post_event [future_unavailable, fit=None]
- MYRENNE GMBH / event [event_unavailable, fit=low]

### exclude_duplicate_capture (1)
- MSF-VATHAUER ANTRIEBSTECHNIK GMBH & CO. KG / pre_event [selected, fit=very_low]

