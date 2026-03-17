# Golden Evaluation Set: Protocol Registry

## Purpose

This registry catalogs 35 publicly available clinical trial protocols selected for
evaluating a table extraction pipeline. Protocols are organized from **simple** to
**complex** table structures across 14 therapeutic areas and multiple trial phases.

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

## Expansion Set (P-21 through P-35) -- Added to Fill Therapeutic Area Gaps

### P-21  CART-19 for Relapsed/Refractory NHL

| Field | Value |
|---|---|
| NCT | NCT02030834 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/34/NCT02030834/Prot_SAP_000.pdf |
| Sponsor | Penn/Novartis |
| Therapeutic Area | Hematology (Non-Hodgkin Lymphoma, CAR-T) |
| Phase | I/II |
| Complexity Tier | 4 |
| Table Complexity | Multi-period SoA covering leukapheresis, conditioning, infusion, and long-term follow-up. CAR-T-specific monitoring (CRS grading, neurotoxicity) creates unique assessment rows. Nested sub-tables for adverse event management algorithms. |

### P-22  Venetoclax + Obinutuzumab in CLL

| Field | Value |
|---|---|
| NCT | NCT04285567 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/67/NCT04285567/Prot_000.pdf |
| Sponsor | Roche/AbbVie |
| Therapeutic Area | Hematology (Chronic Lymphocytic Leukemia) |
| Phase | III |
| Complexity Tier | 3 |
| Table Complexity | Cycle-based SoA with venetoclax dose ramp-up schedule. Tumor lysis syndrome monitoring creates dense assessment windows in early cycles. Multi-arm design with different obinutuzumab schedules. Nested sub-tables for dose modifications. |

### P-23  Tisagenlecleucel Phase IIIb for Pediatric ALL

| Field | Value |
|---|---|
| NCT | NCT03123939 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/39/NCT03123939/Prot_000.pdf |
| Sponsor | Novartis |
| Therapeutic Area | Hematology (Pediatric Acute Lymphoblastic Leukemia, CAR-T) |
| Phase | IIIb |
| Complexity Tier | 4 |
| Table Complexity | Multi-period SoA spanning manufacturing, lymphodepleting chemotherapy, infusion, and 15-year long-term follow-up. Pediatric-specific assessments. CRS and neurotoxicity monitoring windows. |

### P-24  Oral Semaglutide Phase III (Novo Nordisk)

| Field | Value |
|---|---|
| NCT | NCT04707469 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/69/NCT04707469/Prot_000.pdf |
| Sponsor | Novo Nordisk |
| Therapeutic Area | Endocrinology (Type 2 Diabetes / GLP-1) |
| Phase | III |
| Complexity Tier | 3 |
| Table Complexity | Multi-arm design with dose-escalation sub-schedule. Novo Nordisk template format distinct from Lilly. HbA1c and body weight at frequent intervals. |

### P-25  Adoptive Cell Transfer in Soft Tissue Sarcoma

| Field | Value |
|---|---|
| NCT | NCT04052334 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/34/NCT04052334/Prot_SAP_000.pdf |
| Sponsor | NCI |
| Therapeutic Area | Oncology (Soft Tissue Sarcoma, Cell Therapy) |
| Phase | I |
| Complexity Tier | 4 |
| Table Complexity | Multi-period SoA covering tumor harvest, TIL expansion, conditioning chemotherapy, cell infusion, and IL-2 administration. Complex inpatient monitoring schedule. |

### P-26  Nemolizumab for Moderate-to-Severe Atopic Dermatitis

| Field | Value |
|---|---|
| NCT | NCT03985943 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/43/NCT03985943/Prot_000.pdf |
| Sponsor | Galderma R&D |
| Therapeutic Area | Dermatology (Moderate-to-Severe Atopic Dermatitis) |
| Phase | III |
| Complexity Tier | 3 |
| Table Complexity | Multi-arm design (nemolizumab vs. placebo) with 16-week treatment period. Dermatology-specific endpoints (EASI, IGA, NRS pruritus) at frequent intervals. ~750 subjects. Topical corticosteroid co-administration schedule. |

### P-27  Bimekizumab in Moderate-to-Severe Psoriasis

| Field | Value |
|---|---|
| NCT | NCT03131219 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/19/NCT03131219/Prot_000.pdf |
| Sponsor | UCB Pharma |
| Therapeutic Area | Dermatology (Plaque Psoriasis) |
| Phase | III |
| Complexity Tier | 2 |
| Table Complexity | Multi-arm multi-period design with initial treatment and randomized withdrawal. PASI 75/90/100 and IGA scoring at defined intervals. UCB protocol template. |

### P-28  Faricimab in Diabetic Macular Edema (YOSEMITE)

| Field | Value |
|---|---|
| NCT | NCT03823287 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/87/NCT03823287/Prot_000.pdf |
| Sponsor | Roche/Genentech |
| Therapeutic Area | Ophthalmology (Diabetic Macular Edema) |
| Phase | III |
| Complexity Tier | 3 |
| Table Complexity | Cycle-based intravitreal injection schedule with treat-and-extend dosing intervals. OCT and BCVA at every visit. Multi-arm design (faricimab Q8W, faricimab personalized, aflibercept Q8W). Ophthalmology-specific assessments. |

### P-29  HPTN 083 -- Cabotegravir PrEP for HIV Prevention

| Field | Value |
|---|---|
| NCT | NCT02720094 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/94/NCT02720094/Prot_001.pdf |
| Sponsor | NIAID |
| Therapeutic Area | Infectious Disease (HIV Prevention / PrEP) |
| Phase | IIb/III |
| Complexity Tier | 3 |
| Table Complexity | Multi-period design with oral lead-in phase transitioning to injectable phase. Dense lab monitoring for HIV acquisition, hepatitis B/C status, renal function. Behavioral assessments interleaved with clinical visits. Long-acting injectable dosing schedule. |

### P-30  Bictegravir/FTC/TAF in HIV-1/HBV Co-Infection

| Field | Value |
|---|---|
| NCT | NCT03547908 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/08/NCT03547908/Prot_000.pdf |
| Sponsor | Gilead Sciences |
| Therapeutic Area | Infectious Disease (HIV-1/HBV Co-Infection) |
| Phase | III |
| Complexity Tier | 3 |
| Table Complexity | Multi-arm active-comparator design. Dual monitoring for both HIV viral load and HBV DNA/markers. Dense hepatic function monitoring with HBV flare criteria. Gilead protocol template format. |

### P-31  Tezepelumab in Severe Uncontrolled Asthma (NAVIGATOR)

| Field | Value |
|---|---|
| NCT | NCT03347279 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/79/NCT03347279/Prot_002.pdf |
| Sponsor | AstraZeneca |
| Therapeutic Area | Respiratory (Severe Uncontrolled Asthma) |
| Phase | III |
| Complexity Tier | 3 |
| Table Complexity | 52-week treatment + 12-week follow-up SoA. Multi-arm design. Spirometry (FEV1) at every visit. FeNO, blood eosinophils, IgE at defined intervals. AstraZeneca template format. Adolescent + adult sub-populations. |

### P-32  Ensifentrine in COPD (ENHANCE-2)

| Field | Value |
|---|---|
| NCT | NCT04456673 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/73/NCT04456673/Prot_000.pdf |
| Sponsor | Verona Pharma |
| Therapeutic Area | Respiratory (COPD) |
| Phase | III |
| Complexity Tier | 2 |
| Table Complexity | Multi-arm design with nebulized drug. Spirometry at multiple timepoints within single visits. COPD-specific PROs (SGRQ, E-RS). Moderate footnote density. |

### P-33  Esketamine Nasal Spray for Treatment-Resistant Depression (TRANSFORM-2)

| Field | Value |
|---|---|
| NCT | NCT02418585 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/85/NCT02418585/Prot_000.pdf |
| Sponsor | Janssen Research & Development |
| Therapeutic Area | Psychiatry (Treatment-Resistant Depression) |
| Phase | III |
| Complexity Tier | 3 |
| Table Complexity | Multi-period design: 4-week double-blind induction + optional open-label optimization + follow-up. Nasal spray dosing with post-dose observation periods. MADRS, PHQ-9, CGI-S at frequent intervals. Multi-arm (esketamine + new OAD vs. placebo + new OAD). Janssen protocol template. |

### P-34  Atezolizumab + Chemotherapy in Triple-Negative Breast Cancer (IMpassion031)

| Field | Value |
|---|---|
| NCT | NCT03197935 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/35/NCT03197935/Prot_000.pdf |
| Sponsor | Hoffmann-La Roche |
| Therapeutic Area | Oncology (Triple-Negative Breast Cancer) |
| Phase | III |
| Complexity Tier | 3 |
| Table Complexity | Multi-phase neoadjuvant design: nab-paclitaxel phase + anthracycline phase + surgery + adjuvant atezolizumab. Cycle-based chemotherapy schedule with different cycle lengths per phase. Cardiac monitoring (LVEF) at defined intervals. PD-L1 biomarker assessments. Roche protocol template. |

### P-35  Onasemnogene Abeparvovec Gene Therapy for SMA (SPR1NT)

| Field | Value |
|---|---|
| NCT | NCT03912831 |
| PDF | https://cdn.clinicaltrials.gov/large-docs/31/NCT03912831/Prot_SAP_000.pdf |
| Sponsor | Novartis Gene Therapies |
| Therapeutic Area | Gene Therapy (Spinal Muscular Atrophy, Presymptomatic) |
| Phase | III |
| Complexity Tier | 4 |
| Table Complexity | Single IV infusion with multi-year follow-up SoA. Pediatric-specific milestones (motor function, developmental assessments). Hepatotoxicity monitoring with dense lab panels post-infusion. CHOP INTEND, Bayley-III, HINE-2 scoring instruments. Gene therapy-specific immune monitoring (anti-AAV9 antibodies). |

---

## Coverage Matrix

### By Therapeutic Area

| Therapeutic Area | Protocols | Count |
|---|---|---|
| Oncology | P-03, P-12, P-17, P-20, P-25, P-34 | 6 |
| Cardiology | P-07, P-10 | 2 |
| Neurology | P-01, P-05, P-18 | 3 |
| Rare Disease | P-02, P-06, P-15, P-16 | 4 |
| Vaccines | P-13, P-14, P-19 | 3 |
| Autoimmune / Rheumatology | P-04, P-08, P-11 | 3 |
| Endocrinology | P-09, P-24 | 2 |
| Hematology / CAR-T | P-21, P-22, P-23 | 3 |
| Dermatology | P-26, P-27 | 2 |
| Ophthalmology | P-28 | 1 |
| Infectious Disease | P-29, P-30 | 2 |
| Respiratory | P-31, P-32 | 2 |
| Psychiatry | P-33 | 1 |
| Gene Therapy | P-35 | 1 |

### By Phase

| Phase | Protocols | Count |
|---|---|---|
| I | P-25 | 1 |
| I/II | P-19, P-20, P-21 | 3 |
| IIb/III | P-29 | 1 |
| II/III | P-18 | 1 |
| III | P-03 thru P-17 (most), P-22, P-24, P-26, P-27, P-28, P-30, P-31, P-32, P-33, P-34, P-35 | 25 |
| IIIb | P-23 | 1 |
| IV | P-02 | 1 |
| I/II/III | P-13 | 1 |
| Extension | P-01, P-04 | 2 |

### By Sponsor Template Format

| Sponsor Format | Protocols |
|---|---|
| Pfizer | P-13, P-19 |
| Moderna | P-14 |
| Eli Lilly | P-04, P-09 |
| AbbVie | P-11, P-22 |
| AstraZeneca | P-17, P-31 |
| Merck | P-10 |
| Novartis | P-20, P-23, P-35 |
| Roche/Genentech | P-22, P-28, P-34 |
| Gilead | P-30 |
| Janssen/J&J | P-33 |
| Novo Nordisk | P-24 |
| NIAID | P-29 |
| Other (small/mid pharma, academic) | P-01, P-02, P-03, P-05, P-06, P-07, P-08, P-12, P-15, P-16, P-18, P-21, P-25, P-26, P-27, P-32 |

### By Table Complexity Dimension

| Dimension | Protocols |
|---|---|
| Multi-page SoA | P-03 thru P-35 |
| Dense footnotes (15+) | P-07, P-08, P-13, P-14, P-18, P-21, P-29, P-33 |
| Merged/grouped header cells | P-03, P-05, P-10, P-13, P-22, P-26, P-28, P-30 |
| Cycle-repeating structures | P-03, P-09, P-12, P-15, P-17, P-22, P-28, P-34 |
| Multi-arm / multi-period SoA | P-09, P-11, P-12, P-13, P-14, P-17, P-21, P-23, P-26, P-27, P-29, P-31, P-33, P-34 |
| Conditional/branching logic | P-07, P-11, P-16, P-18, P-22 |
| Nested sub-tables | P-09, P-13, P-20, P-21, P-22 |
| Multi-year follow-up | P-04, P-06, P-15, P-18, P-23, P-35 |
| Multiple distinct SoA sections | P-08, P-13, P-14, P-17, P-18, P-19, P-20, P-34 |
| Pediatric-specific assessments | P-02, P-06, P-15, P-20, P-23, P-35 |
| Platform/adaptive design | P-18 |
| High column count (25+) | P-15 |
| CAR-T / cell therapy monitoring | P-21, P-23, P-25 |
| Gene therapy immune monitoring | P-35 |
| Dermatology scoring (PASI/EASI/IGA) | P-26, P-27 |
| Ophthalmology assessments (OCT/BCVA) | P-28 |
| Infectious disease viral monitoring | P-29, P-30 |
| Psychiatric rating scales (MADRS/PHQ) | P-33 |

---

## How to Download

All 35 protocols are hosted on ClinicalTrials.gov's CDN at URLs matching:
```
https://cdn.clinicaltrials.gov/large-docs/{last2digits_of_NCT}/{NCT_number}/Prot_000.pdf
```

Note: Some protocols use variant filenames (e.g., `Prot_001.pdf`, `Prot_002.pdf`,
`Prot_SAP_000.pdf`). The exact URL for each protocol is listed in its entry above
and in `registry.json`.

No authentication is required. PDFs can be downloaded directly via `curl`, `wget`,
or browser. Protocol P-13 (Pfizer BNT162) is additionally mirrored on Pfizer's CDN
and the Global Health Network (TGHN).

---

## Additional Sources for Future Expansion

| Source | URL | Access Model |
|---|---|---|
| FDA Drugs@FDA (approval packages) | https://www.accessdata.fda.gov/scripts/cder/daf/ | Free, immediate |
| EU Clinical Trials Register (CTIS) | https://euclinicaltrials.eu/ | Free, search required |
| YODA Project (J&J/Medtronic data) | https://yoda.yale.edu/ | Free, application required |
| Vivli (multi-sponsor data) | https://vivli.org/ | Free, application required |
| ClinicalStudyDataRequest.com | https://www.clinicalstudydatarequest.com/ | Free, application required |
| TransCelerate Common Protocol Template | https://www.transceleratebiopharmainc.com/ | Free, form submission |
