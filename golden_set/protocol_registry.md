# Golden Evaluation Set: Protocol Registry

## Purpose

This registry catalogs 20 publicly available clinical trial protocols selected for
evaluating a table extraction pipeline. Protocols are organized from **simple** to
**complex** table structures across 7 therapeutic areas and 4 trial phases.

All PDFs are freely downloadable from the URLs below with no login required.

---

## Complexity Tier 1 -- Simple (single-page SoA, few footnotes, no merged cells)

### P-01  Brivaracetam Long-Term Extension (Epilepsy)

| Field | Value |
|---|---|
| NCT | NCT01339559 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/59/NCT01339559/Prot_000.pdf |
| Sponsor | UCB Pharma |
| Therapeutic Area | Neurology (Epilepsy / Partial-Onset Seizures) |
| Phase | III (Open-Label Extension) |
| Table Complexity | Single SoA table. Rolling enrollment with variable duration. Simple visit schedule that repeats at regular intervals. Minimal footnotes. Dose titration visits add a small number of conditional rows. |
| Why Valuable | Open-label extension protocols have compact, repeating SoA structures. Good baseline for calibrating extraction accuracy on straightforward tables before moving to harder cases. |

### P-02  Airway Clearance for Cystic Fibrosis (Pediatric + Adult)

| Field | Value |
|---|---|
| NCT | NCT04743206 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/06/NCT04743206/Prot_000.pdf |
| Sponsor | Investigator-Initiated |
| Therapeutic Area | Rare Disease / Pulmonary (Cystic Fibrosis) |
| Phase | IV |
| Table Complexity | Short intervention period. Single SoA page with ~10 assessment rows. Straightforward visit columns. Few footnotes. |
| Why Valuable | Small investigator-initiated study with minimal formatting complexity. Tests extraction of a clean, simple table. Provides a CF-specific baseline. |

---

## Complexity Tier 2 -- Moderate (multi-page SoA, moderate footnotes, some grouped headers)

### P-03  HERO Trial -- Relugolix for Prostate Cancer

| Field | Value |
|---|---|
| NCT | NCT03085095 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/95/NCT03085095/Prot_001.pdf |
| Sponsor | Myovant Sciences |
| Therapeutic Area | Oncology (Prostate Cancer) |
| Phase | III |
| Table Complexity | 48-week SoA spanning ~2 pages. Grouped column headers for visit windows. ~10 footnotes. Testosterone, PSA, ECG, and bone assessments. Oral vs. injectable arms with minor assessment differences. |
| Why Valuable | Large multinational trial (n=934). Published in NEJM. Two distinct treatment modalities (oral vs. depot injection) mapped to a single SoA. Moderate footnote density. |

### P-04  Baricitinib Long-Term Safety in RA (JADY)

| Field | Value |
|---|---|
| NCT | NCT01885078 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/78/NCT01885078/Prot_000.pdf |
| Sponsor | Eli Lilly |
| Therapeutic Area | Rheumatology (Rheumatoid Arthritis) |
| Phase | III (Long-Term Extension) |
| Table Complexity | Telescoping SoA spanning up to 84 months -- visits start frequent and space out. Two dose groups (2 mg, 4 mg) with different monitoring. Dense lab rows for JAK inhibitor safety (lymphocytes, lipids, CK). Eli Lilly protocol template format. |
| Why Valuable | Tests extraction of telescoping visit structures where column density changes across the table. Lilly template is distinct from Pfizer/AZ/AbbVie formats. |

### P-05  ULTIMATE I -- Ublituximab in Multiple Sclerosis

| Field | Value |
|---|---|
| NCT | NCT03277261 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/61/NCT03277261/Prot_000.pdf |
| Sponsor | TG Therapeutics |
| Therapeutic Area | Neurology (Relapsing Multiple Sclerosis) |
| Phase | III |
| Table Complexity | 96-week SoA with separate infusion-day assessments and clinic visit assessments. Double-blind double-dummy design (IV + oral placebo) creates parallel dosing rows. MRI timing at specific weeks. EDSS and Functional Systems scoring at every visit. ~12 footnotes. |
| Why Valuable | Published in NEJM. Active-comparator with double-dummy introduces dual schedule tracks within one SoA. MS-specific neurological assessments add unique rows not seen in other TAs. |

### P-06  Ataluren for Duchenne Muscular Dystrophy (ACT DMD)

| Field | Value |
|---|---|
| NCT | NCT01557400 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/00/NCT01557400/Prot_000.pdf |
| Sponsor | PTC Therapeutics |
| Therapeutic Area | Rare Disease / Pediatric (Duchenne Muscular Dystrophy) |
| Phase | III |
| Table Complexity | 48-week core + long-term extension SoA. Three-times-daily weight-based dosing (10/10/20 mg/kg). Pediatric-specific rows (growth, Tanner staging). 6MWT and timed function tests at defined intervals. North Star Ambulatory Assessment. |
| Why Valuable | Rare disease pediatric protocol. Weight-based dosing creates footnote complexity. Very long follow-up timeline (extension out to 336 weeks). Tests extraction of pediatric-specific assessment rows. |

---

## Complexity Tier 3 -- High (multi-page SoA, dense footnotes, merged cells, multi-period)

### P-07  STELLAR -- Sotatercept for Pulmonary Arterial Hypertension

| Field | Value |
|---|---|
| NCT | NCT04576988 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/88/NCT04576988/Prot_SAP_000.pdf |
| Sponsor | Acceleron Pharma / Merck |
| Therapeutic Area | Cardiology / Pulmonology (Pulmonary Arterial Hypertension) |
| Phase | III |
| Table Complexity | 21-day dosing cycle mapped to visit schedule. Right heart catheterization at specific visits only. Multi-page SoA with PAH-specific assessments (6MWD, WHO FC, hemodynamics). ~15 footnotes including dose-delay decision logic. Hematology-based dose modification rules. |
| Why Valuable | Published in NEJM, approved as Winrevair. PAH assessments (invasive hemodynamics, walk tests) create unique table rows. Dose-modification logic embedded in footnotes tests footnote-to-cell linking. |

### P-08  ELEVATE UC 12 -- Etrasimod for Ulcerative Colitis

| Field | Value |
|---|---|
| NCT | NCT03996369 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/69/NCT03996369/Prot_000.pdf |
| Sponsor | Arena Pharmaceuticals (now Pfizer) |
| Therapeutic Area | Gastroenterology / Autoimmune (Ulcerative Colitis) |
| Phase | III |
| Table Complexity | Separate screening, induction (12-week), and maintenance SoA tables within one protocol. Endoscopy scheduling at specific weeks. Modified Mayo Score sub-components. Ophthalmologic exam and cardiac monitoring (first-dose). Appendix 1 SoA with >20 footnotes. |
| Why Valuable | Three distinct SoA sections with different structures. S1P modulator cardiac monitoring creates an additional assessment domain. >20 footnotes is among the densest in the set. Tests multi-section extraction. |

### P-09  SURPASS J-mono -- Tirzepatide for Type 2 Diabetes

| Field | Value |
|---|---|
| NCT | NCT03861052 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/52/NCT03861052/Prot_000.pdf |
| Sponsor | Eli Lilly |
| Therapeutic Area | Endocrinology (Type 2 Diabetes Mellitus) |
| Phase | III |
| Table Complexity | 4-arm design (tirzepatide 5/10/15 mg + dulaglutide comparator) creates 4+ columns per visit. Dose-escalation sub-table nested within the SoA. HbA1c and body weight at frequent intervals. Japan-specific regulatory assessments add extra rows not in global protocols. |
| Why Valuable | Multi-dose-arm design creates wide column structures. Nested dose-titration table within the main SoA tests sub-table extraction. Japan-specific regulatory additions test handling of region-specific rows. |

### P-10  VICTOR -- Vericiguat for Heart Failure (HFrEF)

| Field | Value |
|---|---|
| NCT | NCT05093933 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/33/NCT05093933/Prot_SAP_000.pdf |
| Sponsor | Merck |
| Therapeutic Area | Cardiology (Heart Failure with Reduced Ejection Fraction) |
| Phase | III |
| Table Complexity | Event-driven design with variable follow-up -- mixes fixed visits with flexible event-driven contacts. KCCQ, 6MWD, NT-proBNP at periodic intervals. Grouped header cells for visit windows. ~12 footnotes for unscheduled visit triggers and dose titration. |
| Why Valuable | Event-driven cardiovascular outcomes trials have SoA tables that blend fixed and flexible visit structures, testing extraction logic for variable-length protocols. Merck format template. |

### P-11  Upadacitinib SELECT for Rheumatoid Arthritis

| Field | Value |
|---|---|
| NCT | NCT03104400 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/00/NCT03104400/Prot_002.pdf |
| Sponsor | AbbVie |
| Therapeutic Area | Rheumatology (Rheumatoid Arthritis) |
| Phase | III |
| Table Complexity | Multi-period design: 24-week double-blind + 32-week blinded extension + rescue therapy. Placebo and active comparator (adalimumab) arms. DAS28, ACR20/50/70 at specific visits. Rescue therapy criteria create conditional branching in SoA. AbbVie protocol template format. |
| Why Valuable | Multi-period design with rescue therapy creates conditional branching where patients switch SoA tracks. AbbVie format is distinct from Lilly/Pfizer/Merck. Tests period-specific sub-table extraction. |

### P-12  ATLANTIS -- Lurbinectedin for Small Cell Lung Cancer

| Field | Value |
|---|---|
| NCT | NCT02566993 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/93/NCT02566993/Prot_000.pdf |
| Sponsor | PharmaMar |
| Therapeutic Area | Oncology (Small Cell Lung Cancer) |
| Phase | III |
| Table Complexity | Three-arm SoA (experimental vs. CAV vs. topotecan) with different cycle lengths per arm. Cycle-repeating structure across 6+ cycles. Complex footnote system for dose reduction rules. Lab monitoring varies by arm due to different toxicity profiles. |
| Why Valuable | Three comparator arms with different chemotherapy regimens mapped to one SoA is a challenging extraction target. Different cycle lengths per arm test column alignment logic. |

---

## Complexity Tier 4 -- Very High (multi-page SoA, 15+ footnotes, merged cells, nested tables, multi-arm)

### P-13  Pfizer C4591001 -- BNT162b2 COVID-19 Vaccine

| Field | Value |
|---|---|
| NCT | NCT04368728 |
| PDF (ClinicalTrials.gov) | https://cdn.clinicaltrials.gov/large-docs/28/NCT04368728/Prot_000.pdf |
| PDF (Pfizer CDN) | https://cdn.pfizer.com/pfizercom/2020-11/C4591001_Clinical_Protocol_Nov2020.pdf |
| PDF (TGHN mirror) | https://media.tghn.org/medialibrary/2020/11/C4591001_Clinical_Protocol_Nov2020_Pfizer_BioNTech.pdf |
| Sponsor | Pfizer / BioNTech |
| Therapeutic Area | Vaccines (COVID-19) |
| Phase | I/II/III (seamless) |
| Table Complexity | Separate SoA tables for Phase 1 (dose-escalation with sentinel cohorts, multiple vaccine candidates) and Phase 2/3 (two-dose regimen, 30k+ participants). Age-group-specific sub-schedules (16-55 vs. 55+). Blood sampling with precise timing windows. E-diary + in-clinic + telephone visit types mixed. ~18 footnotes per SoA section. |
| Why Valuable | Historically significant and heavily scrutinized -- extraction accuracy can be externally validated. Seamless Phase I-III design with separate SoA sections per phase. Multiple vaccine candidate arms in Phase 1 create wide column structures. Three distinct visit modalities. |

### P-14  Moderna mRNA-1273-P301 (COVE Study) -- COVID-19 Vaccine

| Field | Value |
|---|---|
| NCT | NCT04470427 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/27/NCT04470427/Prot_000.pdf |
| Sponsor | ModernaTX |
| Therapeutic Area | Vaccines (COVID-19) |
| Phase | III (3-part) |
| Table Complexity | Three-part study (Part A: blinded; Part B: open-label observational; Part C: booster) with separate SoA per part. Dense immunogenicity blood draw schedule with precise windows. Telephone contacts interleaved with in-person visits. Protocol Amendment 10 shows how SoA evolved. ~15 footnotes per section. |
| Why Valuable | Three distinct SoA sections with different structures in one document. Amendment 10 (latest available) captures maximal table evolution. Direct comparison with Pfizer protocol (P-13) tests cross-sponsor format handling. Moderna template format. |

### P-15  Pamrevlumab LELANTOS-2 for Duchenne Muscular Dystrophy

| Field | Value |
|---|---|
| NCT | NCT04632940 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/40/NCT04632940/Prot_000.pdf |
| Sponsor | FibroGen |
| Therapeutic Area | Rare Disease / Pediatric (Duchenne Muscular Dystrophy) |
| Phase | III |
| Table Complexity | IV infusion every 2 weeks for 52 weeks creates ~26 cycle columns. Ambulatory boys 6-12 years -- pediatric-specific growth/development rows. NSAA total score, timed function tests, MRI muscle assessments at defined intervals. Multi-page SoA with conditional imaging schedule. |
| Why Valuable | High column count (~26 infusion visits) tests extraction of very wide tables that span multiple pages. Pediatric assessments and MRI sub-schedule add distinct row groupings. Pairs with P-06 (ataluren) for same-disease cross-protocol comparison. |

### P-16  CF Rare CFTR Variants -- Trikafta Responsiveness

| Field | Value |
|---|---|
| NCT | NCT03506061 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/61/NCT03506061/Prot_SAP_001.pdf |
| Sponsor | Likely Vertex Pharmaceuticals |
| Therapeutic Area | Rare Disease / Pulmonary (Cystic Fibrosis) |
| Phase | III |
| Table Complexity | Sweat chloride testing at specific visits with precise timing footnotes. Spirometry (FEV1) at every visit. CF-specific QoL instruments (CFQ-R). Dense hepatic monitoring lab panels. Complex eligibility screening SoA (genotype-dependent). Sputum microbiology schedule. |
| Why Valuable | Disease-specific assessments (sweat chloride, sputum micro) are unique to CF protocols. Genotype-dependent eligibility reflected in screening SoA creates conditional row logic. Tests extraction of specialized lab panels. |

### P-17  AstraZeneca Durvalumab + Chemoradiation (Oncology)

| Field | Value |
|---|---|
| NCT | NCT03830866 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/66/NCT03830866/Prot_000.pdf |
| Sponsor | AstraZeneca |
| Therapeutic Area | Oncology (Immuno-Oncology Combination) |
| Phase | III |
| Table Complexity | Multiple SoA sections: screening, chemoradiation phase (daily radiation + weekly chemo), immunotherapy consolidation phase (Q2W then Q4W cycles), and long-term follow-up. Dose modification tables embedded alongside SoA. AstraZeneca protocol template. Updated footnotes across amendments. |
| Why Valuable | Multi-phase oncology combination protocol (chemoradiation + immunotherapy) has the most treatment-phase transitions of any protocol in the set. Each phase has distinct cycle lengths and assessment cadences. AstraZeneca template format. |

---

## Complexity Tier 5 -- Extreme (platform/adaptive design, 20+ footnotes, nested sub-tables, multi-year, intra-day timepoints)

### P-18  DIAN-TU-001 -- Dominantly Inherited Alzheimer Network

| Field | Value |
|---|---|
| NCT | NCT04623242 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/42/NCT04623242/Prot_000.pdf |
| Sponsor | Washington University in St. Louis |
| Therapeutic Area | Neurology (Dominantly Inherited Alzheimer's Disease) |
| Phase | II/III (Adaptive Platform) |
| Table Complexity | **265-page master protocol**. Adaptive platform trial with multiple treatment arms that can be added/dropped. Multi-year follow-up SoA spanning 4+ years. Assessments include: cognitive batteries (multiple instruments), amyloid PET, tau PET, volumetric MRI, CSF collection, blood biomarkers. Separate SoA per study period. 20+ footnotes. Multiple imaging sub-schedules. |
| Why Valuable | The most complex protocol in this set. Platform trial design with adaptive randomization creates the most challenging SoA extraction target. Biomarker-driven endpoints with multiple imaging modalities. 265 pages with deeply nested, multi-page SoA tables. Gold standard for maximum complexity testing. |

### P-19  Pfizer C5481001 -- Combination COVID-19 + RSV Vaccine

| Field | Value |
|---|---|
| NCT | NCT05886777 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/77/NCT05886777/Prot_000.pdf |
| Sponsor | Pfizer |
| Therapeutic Area | Vaccines (COVID-19 + RSV Combination) |
| Phase | I/II |
| Table Complexity | Multi-cohort design with different vaccine formulations per cohort. Each cohort has its own SoA variant. Age-group-specific sub-schedules. Immunogenicity sampling at precise post-vaccination intervals. Safety monitoring with e-diary + in-clinic components. Multiple SoA sections that are structurally similar but differ in details. |
| Why Valuable | Multi-cohort vaccine protocol with SoA variants per cohort tests the ability to extract and differentiate structurally similar but distinct tables. Combination antigen targeting is a next-generation vaccine design pattern. |

### P-20  MEK162 Pediatric Phase I/II -- Low-Grade Glioma

| Field | Value |
|---|---|
| NCT | NCT02285439 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/39/NCT02285439/Prot_SAP_000.pdf |
| Sponsor | Novartis / NCI (PBTC) |
| Therapeutic Area | Pediatric Oncology (Low-Grade Glioma, NF1, Ras/Raf tumors) |
| Phase | I/II |
| Table Complexity | Combined Phase I dose-escalation + Phase II expansion in one protocol with separate SoA structures. Three disease strata (BRAF fusion LGG, NF1 LGG, other Ras/Raf tumors) with stratum-specific assessments. 28-day continuous dosing cycles. Pediatric-specific rows (Tanner staging, growth velocity). Imaging every 3 cycles with precise windows. |
| Why Valuable | Combines Phase I and Phase II in one protocol with distinct table structures per phase. Three strata create conditional assessment logic. Pediatric oncology assessments (growth, development) alongside standard oncology assessments. Tests extraction of dose-escalation schema tables alongside standard SoA. |

---

## Coverage Matrix

### By Therapeutic Area

| Therapeutic Area | Protocols | Count |
|---|---|---|
| Oncology | P-03, P-12, P-17, P-20 | 4 |
| Cardiology | P-07, P-10 | 2 |
| Neurology | P-01, P-05, P-18 | 3 |
| Rare Disease | P-02, P-06, P-15, P-16 | 4 |
| Vaccines | P-13, P-14, P-19 | 3 |
| Pediatric | P-06, P-15, P-20 (also P-02) | 3-4 |
| Autoimmune / Rheumatology | P-04, P-08, P-11 | 3 |
| Endocrinology | P-09 | 1 |

### By Phase

| Phase | Protocols | Count |
|---|---|---|
| I or I/II | P-19, P-20 | 2 |
| II/III | P-18 | 1 |
| III | P-01 thru P-17 (most) | 15 |
| IV | P-02 | 1 |
| Extension | P-01, P-04 | 2 |

### By Sponsor Template Format

| Sponsor Format | Protocols |
|---|---|
| Pfizer | P-13, P-19 |
| Moderna | P-14 |
| Eli Lilly | P-04, P-09 |
| AbbVie | P-11 |
| AstraZeneca | P-17 |
| Merck | P-10 |
| Novartis | P-20 |
| Other (small/mid pharma, academic) | P-01, P-02, P-03, P-05, P-06, P-07, P-08, P-12, P-15, P-16, P-18 |

### By Table Complexity Dimension

| Dimension | Protocols |
|---|---|
| Multi-page SoA | P-03 thru P-20 |
| Dense footnotes (15+) | P-07, P-08, P-13, P-14, P-18 |
| Merged/grouped header cells | P-03, P-05, P-10, P-13 |
| Cycle-repeating structures | P-03, P-09, P-12, P-15, P-17 |
| Multi-arm / multi-period SoA | P-09, P-11, P-12, P-13, P-14, P-17 |
| Conditional/branching logic | P-07, P-11, P-16, P-18 |
| Nested sub-tables | P-09, P-13, P-20 |
| Multi-year follow-up | P-04, P-06, P-15, P-18 |
| Multiple distinct SoA sections | P-08, P-13, P-14, P-17, P-18, P-19, P-20 |
| Pediatric-specific assessments | P-02, P-06, P-15, P-20 |
| Platform/adaptive design | P-18 |
| High column count (25+) | P-15 |

---

## How to Download

All 20 protocols are hosted on ClinicalTrials.gov's CDN at URLs matching:
```
https://cdn.clinicaltrials.gov/large-docs/{last2digits_of_NCT}/{NCT_number}/Prot_000.pdf
```

No authentication is required. PDFs can be downloaded directly via `curl`, `wget`,
or browser. Protocol P-13 (Pfizer BNT162) is additionally mirrored on Pfizer's CDN
and the Global Health Network (TGHN).

---

## Additional Sources for Expansion

If the golden set needs to grow beyond 20 protocols:

| Source | URL | Access Model |
|---|---|---|
| FDA Drugs@FDA (approval packages) | https://www.accessdata.fda.gov/scripts/cder/daf/ | Free, immediate |
| EU Clinical Trials Register (CTIS) | https://euclinicaltrials.eu/ | Free, search required |
| YODA Project (J&J/Medtronic data) | https://yoda.yale.edu/ | Free, application required |
| Vivli (multi-sponsor data) | https://vivli.org/ | Free, application required |
| ClinicalStudyDataRequest.com | https://www.clinicalstudydatarequest.com/ | Free, application required |
| TransCelerate Common Protocol Template | https://www.transceleratebiopharmainc.com/ | Free, form submission |
