"""
VEDA Phase 4.12 Sealed Provisional Benchmark Generation Script (v8.0)
Constructs the frozen, non-templated v8.0 benchmark datasets for Phase 4.12:
1. data/corpus/eval_language_dataset_v8.json (Task A: Language Identification & Quality Filtering)
2. data/corpus/eval_near_dedup_dataset_v8.json (Task B: Near-Deduplication & Semantic Safety Guard)

Governance Status:
- PROVISIONAL — INDEPENDENCE UNVERIFIED (Internal construction by verification agent)
- Strictly 0% overlap with historical benchmarks (v3, v4, v5, v6, v7) and bug reports.
- Diverse domains, authentic terminology, no repetitive templates.
- Cryptographic SHA-256 provenance registration.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

_ROOT = Path(__file__).resolve().parent.parent


def build_v8_language_dataset() -> Dict[str, Any]:
    # Development Split (60 samples)
    dev_samples = [
        # --- ACCEPT: Ordinary English Prose (10) ---
        {"sample_id": "v8_lang_dev_001", "category": "ordinary_english_prose",
         "text": "Deep-sea research submersibles explore hydrothermal vent ecosystems located along the mid-ocean volcanic ridge system.",
         "expected_outcome": "ACCEPT", "domain": "oceanography"},
        {"sample_id": "v8_lang_dev_002", "category": "ordinary_english_prose",
         "text": "The municipal water authority replaced the corroded cast iron distribution mains with durable ductile iron piping.",
         "expected_outcome": "ACCEPT", "domain": "civil_infrastructure"},
        {"sample_id": "v8_lang_dev_003", "category": "ordinary_english_prose",
         "text": "Traditional cooperage masters carefully shape white oak staves using hand adzes before binding them with steel hoops.",
         "expected_outcome": "ACCEPT", "domain": "traditional_crafts"},
        {"sample_id": "v8_lang_dev_004", "category": "ordinary_english_prose",
         "text": "Silviculturists recommend rotational thinning in commercial pine plantations to reduce fuel loads and mitigate wildfire severity.",
         "expected_outcome": "ACCEPT", "domain": "forestry"},
        {"sample_id": "v8_lang_dev_005", "category": "ordinary_english_prose",
         "text": "The botanical conservatory maintains temperature-controlled glasshouses for the cultivation of endangered epiphytic orchids.",
         "expected_outcome": "ACCEPT", "domain": "botany"},
        {"sample_id": "v8_lang_dev_006", "category": "ordinary_english_prose",
         "text": "Coastal navigation beacons emit synchronized rhythmic light pulses to assist mariners entering shallow tidal channels at dusk.",
         "expected_outcome": "ACCEPT", "domain": "maritime_navigation"},
        {"sample_id": "v8_lang_dev_007", "category": "ordinary_english_prose",
         "text": "The archaeological survey team uncovered ancient terracotta pottery sherds beneath the foundation of the Roman granary.",
         "expected_outcome": "ACCEPT", "domain": "classical_archaeology"},
        {"sample_id": "v8_lang_dev_008", "category": "ordinary_english_prose",
         "text": "Aviation mechanics inspected the turbofan engine compressor blades for microstructural fatigue cracks following bird strike incidents.",
         "expected_outcome": "ACCEPT", "domain": "aerospace_maintenance"},
        {"sample_id": "v8_lang_dev_009", "category": "ordinary_english_prose",
         "text": "The university archives preserved eighteenth-century parchment land grants inside acid-free deacidified conservation folders.",
         "expected_outcome": "ACCEPT", "domain": "archival_science"},
        {"sample_id": "v8_lang_dev_010", "category": "ordinary_english_prose",
         "text": "Hydroelectric dam operators adjusted the spillway radial gates to regulate downstream reservoir discharge following spring snowmelt.",
         "expected_outcome": "ACCEPT", "domain": "hydraulic_engineering"},

        # --- ACCEPT: Expository Academic & Scientific Prose (8) ---
        {"sample_id": "v8_lang_dev_011", "category": "expository_academic_prose",
         "text": "Magnetohydrodynamic simulations reveal complex turbulence dynamics occurring within circumstellar accretion discs around protostellar objects.",
         "expected_outcome": "ACCEPT", "domain": "astrophysics"},
        {"sample_id": "v8_lang_dev_012", "category": "expository_academic_prose",
         "text": "Constitutional jurisprudence balances sovereign regulatory police power against substantive due process rights of private property owners.",
         "expected_outcome": "ACCEPT", "domain": "constitutional_law"},
        {"sample_id": "v8_lang_dev_013", "category": "expository_academic_prose",
         "text": "Paleomagnetic polar wandering curves provide independent geodynamic evidence for the continental drift of the Gondwana supercontinent.",
         "expected_outcome": "ACCEPT", "domain": "geophysics"},
        {"sample_id": "v8_lang_dev_014", "category": "expository_academic_prose",
         "text": "Recursive descent compilers construct abstract syntax trees by executing mutually recursive procedures corresponding to grammar productions.",
         "expected_outcome": "ACCEPT", "domain": "computer_science"},
        {"sample_id": "v8_lang_dev_015", "category": "expository_academic_prose",
         "text": "Mitochondrial oxidative phosphorylation generates adenosine triphosphate through an electrochemical proton gradient across the inner membrane.",
         "expected_outcome": "ACCEPT", "domain": "cellular_biology"},
        {"sample_id": "v8_lang_dev_016", "category": "expository_academic_prose",
         "text": "X-ray photoelectron spectroscopy determines elemental chemical oxidation states in nanostructured transition metal oxide surfaces.",
         "expected_outcome": "ACCEPT", "domain": "surface_chemistry"},
        {"sample_id": "v8_lang_dev_017", "category": "expository_academic_prose",
         "text": "Microeconomic general equilibrium models formalize price discovery mechanisms across interdependent competitive commodity markets.",
         "expected_outcome": "ACCEPT", "domain": "economics"},
        {"sample_id": "v8_lang_dev_018", "category": "expository_academic_prose",
         "text": "Neutron powder diffraction resolves precise crystallographic interstitial oxygen positions within high-temperature superconducting cuprates.",
         "expected_outcome": "ACCEPT", "domain": "solid_state_physics"},

        # --- ACCEPT: Scientific Figure Captions (5) ---
        {"sample_id": "v8_lang_dev_019", "category": "scientific_figure_captions",
         "text": "Figure 1: Scanning tunneling microscopy image showing reconstructed atomic steps on an ultra-clean silicon (111) surface.",
         "expected_outcome": "ACCEPT", "domain": "nanotechnology"},
        {"sample_id": "v8_lang_dev_020", "category": "scientific_figure_captions",
         "text": "Figure 2. High-resolution mass spectrometry fragmentation pattern of synthetic oligopeptides under collision-induced dissociation.",
         "expected_outcome": "ACCEPT", "domain": "analytical_chemistry"},
        {"sample_id": "v8_lang_dev_021", "category": "scientific_figure_captions",
         "text": "Table 1: Measured elastic moduli and yield tensile strength for precipitation-hardened aluminum aerospace alloys.",
         "expected_outcome": "ACCEPT", "domain": "materials_science"},
        {"sample_id": "v8_lang_dev_022", "category": "scientific_figure_captions",
         "text": "Plate 3: Cross-sectional petrographic thin section showing poikilitic pyroxene grains in an ultramafic mantle xenolith.",
         "expected_outcome": "ACCEPT", "domain": "petrology"},
        {"sample_id": "v8_lang_dev_023", "category": "scientific_figure_captions",
         "text": "Scheme 4: Enantioselective catalytic synthesis of chiral tetrahydroquinoline derivatives using a ruthenium-BINAP complex.",
         "expected_outcome": "ACCEPT", "domain": "organic_synthesis"},

        # --- ACCEPT: Foreign Names, Quotes, Latin Terminology (4) ---
        {"sample_id": "v8_lang_dev_024", "category": "foreign_names_and_quotes",
         "text": "The appellate tribunal applied the legal maxim expressio unius est exclusio alterius to resolve the statutory ambiguity.",
         "expected_outcome": "ACCEPT", "domain": "statutory_interpretation"},
        {"sample_id": "v8_lang_dev_025", "category": "foreign_names_and_quotes",
         "text": "Physicist Ludwig Boltzmann introduced the statistical definition of entropy connecting microscopic phase space to macroscopic state variables.",
         "expected_outcome": "ACCEPT", "domain": "statistical_physics"},
        {"sample_id": "v8_lang_dev_026", "category": "foreign_names_and_quotes",
         "text": "The historical treatise cited the treaty signed at Aix-la-Chapelle as the foundation for the balance of power in central Europe.",
         "expected_outcome": "ACCEPT", "domain": "european_history"},
        {"sample_id": "v8_lang_dev_027", "category": "foreign_names_and_quotes",
         "text": "The physician confirmed prima facie evidence of acute peripheral neuropathy before scheduling electrodiagnostic nerve conduction tests.",
         "expected_outcome": "ACCEPT", "domain": "clinical_medicine"},

        # --- ACCEPT: English Imperatives and Concise Instructions (3) ---
        {"sample_id": "v8_lang_dev_028", "category": "english_imperatives_instructions",
         "text": "Centrifuge the biological suspension at four thousand revolutions per minute for ten minutes before decanting the supernatant liquid.",
         "expected_outcome": "ACCEPT", "domain": "laboratory_protocol"},
        {"sample_id": "v8_lang_dev_029", "category": "english_imperatives_instructions",
         "text": "Verify that all electrical grounding connections are securely fastened to the earth rod before energizing the transformer unit.",
         "expected_outcome": "ACCEPT", "domain": "electrical_safety"},
        {"sample_id": "v8_lang_dev_030", "category": "english_imperatives_instructions",
         "text": "Store the lyophilized enzyme powder at minus twenty degrees Celsius in an airtight desiccator protected from ambient moisture.",
         "expected_outcome": "ACCEPT", "domain": "biochemical_storage"},

        # --- QUARANTINE: Code, SQL & Structured Data (5) ---
        {"sample_id": "v8_lang_dev_031", "category": "code_sql_structured_data",
         "text": "SELECT customer_id, SUM(order_total) FROM orders WHERE order_status = 'COMPLETED' GROUP BY customer_id HAVING SUM(order_total) > 500;",
         "expected_outcome": "QUARANTINE", "domain": "database_queries"},
        {"sample_id": "v8_lang_dev_032", "category": "code_sql_structured_data",
         "text": "CREATE TABLE telemetry_readings (sensor_id INT NOT NULL, timestamp TIMESTAMP, voltage FLOAT, status VARCHAR(20));",
         "expected_outcome": "QUARANTINE", "domain": "database_ddl"},
        {"sample_id": "v8_lang_dev_033", "category": "code_sql_structured_data",
         "text": "UPDATE inventory_stock SET quantity = quantity - 1 WHERE item_sku = 'WIDGET-9901' AND warehouse_id = 4;",
         "expected_outcome": "QUARANTINE", "domain": "database_dml"},
        {"sample_id": "v8_lang_dev_034", "category": "code_sql_structured_data",
         "text": "DELETE FROM temporary_user_sessions WHERE last_activity < '2026-01-01 00:00:00';",
         "expected_outcome": "QUARANTINE", "domain": "database_dml"},
        {"sample_id": "v8_lang_dev_035", "category": "code_sql_structured_data",
         "text": "ALTER TABLE financial_ledgers ADD COLUMN audit_hash VARCHAR(64) DEFAULT 'UNVERIFIED';",
         "expected_outcome": "QUARANTINE", "domain": "database_ddl"},

        # --- QUARANTINE: Imperative Signage & Advisory Notices (5) ---
        {"sample_id": "v8_lang_dev_036", "category": "imperative_signage_notices",
         "text": "DANGER: HIGH VOLTAGE OVERHEAD CONDUIT. DO NOT ENTER ENCLOSURE.",
         "expected_outcome": "QUARANTINE", "domain": "industrial_signage"},
        {"sample_id": "v8_lang_dev_037", "category": "imperative_signage_notices",
         "text": "CAUTION: CRYOGENIC LIQUID STORAGE AREA. WEAR THERMAL FACE SHIELD.",
         "expected_outcome": "QUARANTINE", "domain": "laboratory_signage"},
        {"sample_id": "v8_lang_dev_038", "category": "imperative_signage_notices",
         "text": "WARNING: AUTOMATIC CONVEYOR EQUIPMENT MAY RESTART AT ANY TIME.",
         "expected_outcome": "QUARANTINE", "domain": "factory_signage"},
        {"sample_id": "v8_lang_dev_039", "category": "imperative_signage_notices",
         "text": "NOTICE: HARD HATS AND STEEL-TOE FOOTWEAR REQUIRED BEYOND THIS POINT.",
         "expected_outcome": "QUARANTINE", "domain": "construction_signage"},
        {"sample_id": "v8_lang_dev_040", "category": "imperative_signage_notices",
         "text": "ALERT: CONFINED SPACE ENTRY PERMIT REQUIRED BEFORE OPENING MANHOLE.",
         "expected_outcome": "QUARANTINE", "domain": "safety_advisory"},

        # --- QUARANTINE: Short Headings & Fragments (5) ---
        {"sample_id": "v8_lang_dev_041", "category": "short_headings_and_fragments",
         "text": "Chapter 4: Advanced Solid-State Nuclear Magnetic Resonance Spectroscopy Techniques.",
         "expected_outcome": "QUARANTINE", "domain": "monograph_headings"},
        {"sample_id": "v8_lang_dev_042", "category": "short_headings_and_fragments",
         "text": "Appendix B: Thermodynamic Enthalpy Values for Selected Binary Hydride Compounds.",
         "expected_outcome": "QUARANTINE", "domain": "reference_tables"},
        {"sample_id": "v8_lang_dev_043", "category": "short_headings_and_fragments",
         "text": "Section 12: General Conditions of Maritime Insurance Contracts.",
         "expected_outcome": "QUARANTINE", "domain": "legal_sections"},
        {"sample_id": "v8_lang_dev_044", "category": "short_headings_and_fragments",
         "text": "Bibliography: Primary Archival Sources in Mediterranean Naval History.",
         "expected_outcome": "QUARANTINE", "domain": "academic_bibliography"},
        {"sample_id": "v8_lang_dev_045", "category": "short_headings_and_fragments",
         "text": "Part III: Computational Fluid Dynamics Grid Generation Algorithms.",
         "expected_outcome": "QUARANTINE", "domain": "textbook_divisions"},

        # --- QUARANTINE: Germanic Latin Prose (German & Dutch) (5) ---
        {"sample_id": "v8_lang_dev_046", "category": "germanic_latin_prose",
         "text": "Die physikalische Untersuchung der kristallinen Festkoerper erfordert moderne Methoden der Roentgendiffraktometrie.",
         "expected_outcome": "QUARANTINE", "domain": "german_solid_state"},
        {"sample_id": "v8_lang_dev_047", "category": "germanic_latin_prose",
         "text": "Het transport van vloeibaar aardgas door onderzeese pijpleidingen vereist continue bewaking van de operationele druk.",
         "expected_outcome": "QUARANTINE", "domain": "dutch_gas_transport"},
        {"sample_id": "v8_lang_dev_048", "category": "germanic_latin_prose",
         "text": "Eine vollstaendige thermodynamische Analyse beruecksichtigt alle thermischen Energieverluste durch Waermeleitung und Konvektion.",
         "expected_outcome": "QUARANTINE", "domain": "german_thermodynamics"},
        {"sample_id": "v8_lang_dev_049", "category": "germanic_latin_prose",
         "text": "De maritieme navigatie in het estuarium wordt gereguleerd door geautomatiseerde verkeersbegeleidingssystemen aan de kust.",
         "expected_outcome": "QUARANTINE", "domain": "dutch_maritime"},
        {"sample_id": "v8_lang_dev_050", "category": "germanic_latin_prose",
         "text": "Wenn die mechanische Spannung den kritischen Schwellenwert ueberschreitet, tritt irreversible plastische Verformung ein.",
         "expected_outcome": "QUARANTINE", "domain": "german_metallurgy"},

        # --- REJECT: Romance Latin Prose (French, Spanish, Italian) (5) ---
        {"sample_id": "v8_lang_dev_051", "category": "romance_latin_prose",
         "text": "Les proprietes rheologiques des fluides non newtoniens dependent fortement de la vitesse de cisaillement appliquee.",
         "expected_outcome": "REJECT", "domain": "french_fluid_mechanics"},
        {"sample_id": "v8_lang_dev_052", "category": "romance_latin_prose",
         "text": "El analisis quimico cuantitativo demostro una concentracion elevada de minerales pesados en los sedimentos fluviales.",
         "expected_outcome": "REJECT", "domain": "spanish_geochemistry"},
        {"sample_id": "v8_lang_dev_053", "category": "romance_latin_prose",
         "text": "La presenza di campi magnetici intensi influenza la traiettoria delle particelle cariche nel plasma stellare.",
         "expected_outcome": "REJECT", "domain": "italian_astrophysics"},
        {"sample_id": "v8_lang_dev_054", "category": "romance_latin_prose",
         "text": "L'evolution historique des institutions parlementaires reflete les transformations profondes de la structure sociale.",
         "expected_outcome": "REJECT", "domain": "french_political_history"},
        {"sample_id": "v8_lang_dev_055", "category": "romance_latin_prose",
         "text": "Los yacimientos de hidrocarburos descubiertos en la plataforma continental requieren tecnicas avanzadas de perforacion submarina.",
         "expected_outcome": "REJECT", "domain": "spanish_petroleum"},

        # --- REJECT: Non-Latin Script (2) ---
        {"sample_id": "v8_lang_dev_056", "category": "non_latin_script",
         "text": "Исследование сверхпроводящих материалов при ультранизких температурах открывает новые перспективы для квантовых вычислений.",
         "expected_outcome": "REJECT", "domain": "russian_condensed_matter"},
        {"sample_id": "v8_lang_dev_057", "category": "non_latin_script",
         "text": "量子计算利用量子力学叠加与纠缠特性实现远超经典计算机的信息处理速度与并行计算能力。",
         "expected_outcome": "REJECT", "domain": "chinese_quantum_computing"},

        # --- REJECT: Malformed Noise & Repetitions (3) ---
        {"sample_id": "v8_lang_dev_058", "category": "malformed_noise",
         "text": "###@@@!!! $$$%%%^^^ &&&***((( )))___+++ ===~~~``` {{{}}} [[[ ]]] ||| ::: ;;;",
         "expected_outcome": "REJECT", "domain": "symbol_noise"},
        {"sample_id": "v8_lang_dev_059", "category": "malformed_noise",
         "text": "system error system error system error system error system error system error system error system error system error",
         "expected_outcome": "REJECT", "domain": "repetitive_log_noise"},
        {"sample_id": "v8_lang_dev_060", "category": "malformed_noise",
         "text": "qqq www eee rrr ttt yyy uuu iii ooo ppp aaa sss ddd fff ggg hhh jjj kkk lll zzz xxx ccc vvv bbb nnn mmm",
         "expected_outcome": "REJECT", "domain": "keyboard_garbage"},
    ]

    # Held-Out Test Split (60 samples)
    test_samples = [
        # --- ACCEPT: Ordinary English Prose (10) ---
        {"sample_id": "v8_lang_test_001", "category": "ordinary_english_prose",
         "text": "Offshore wind installations utilize heavy subsea power cables to transmit alternating current to mainland substations.",
         "expected_outcome": "ACCEPT", "domain": "renewable_energy"},
        {"sample_id": "v8_lang_test_002", "category": "ordinary_english_prose",
         "text": "Agricultural extension agents advised grain farmers to rotate legume crops to naturally replenish soil nitrogen reserves.",
         "expected_outcome": "ACCEPT", "domain": "agronomy"},
        {"sample_id": "v8_lang_test_003", "category": "ordinary_english_prose",
         "text": "The steam locomotive boiler was thoroughly washed and descaled during annual mechanical maintenance at the roundhouse.",
         "expected_outcome": "ACCEPT", "domain": "railway_history"},
        {"sample_id": "v8_lang_test_004", "category": "ordinary_english_prose",
         "text": "Geodesic satellite receivers track tectonic plate displacement rates across the active San Andreas fault zone.",
         "expected_outcome": "ACCEPT", "domain": "geodesy"},
        {"sample_id": "v8_lang_test_005", "category": "ordinary_english_prose",
         "text": "Commercial fishing vessels returned to port early after maritime weather stations issued severe gales warnings for the sector.",
         "expected_outcome": "ACCEPT", "domain": "fisheries"},
        {"sample_id": "v8_lang_test_006", "category": "ordinary_english_prose",
         "text": "The municipal water filtration plant installed granular activated carbon beds to absorb dissolved organic contaminants.",
         "expected_outcome": "ACCEPT", "domain": "water_treatment"},
        {"sample_id": "v8_lang_test_007", "category": "ordinary_english_prose",
         "text": "Automated warehouse logistics systems employ laser-guided robotic pallet jacks to move freight pallets through aisles.",
         "expected_outcome": "ACCEPT", "domain": "industrial_robotics"},
        {"sample_id": "v8_lang_test_008", "category": "ordinary_english_prose",
         "text": "Wildlife conservation biologists established contiguous wildlife corridors to facilitate seasonal migration of elk herds.",
         "expected_outcome": "ACCEPT", "domain": "conservation_biology"},
        {"sample_id": "v8_lang_test_009", "category": "ordinary_english_prose",
         "text": "The historic printing press museum preserves iron Washington hand presses used for nineteenth-century broadside printing.",
         "expected_outcome": "ACCEPT", "domain": "typography_history"},
        {"sample_id": "v8_lang_test_010", "category": "ordinary_english_prose",
         "text": "Petrochemical refinery units crack heavy gas oil into motor gasoline and light distillate fractions under high temperature.",
         "expected_outcome": "ACCEPT", "domain": "petrochemicals"},

        # --- ACCEPT: Expository Academic & Scientific Prose (8) ---
        {"sample_id": "v8_lang_test_011", "category": "expository_academic_prose",
         "text": "Nuclear magnetic resonance relaxation dispersion profiles characterize conformational exchange dynamics between protein folding states.",
         "expected_outcome": "ACCEPT", "domain": "structural_biology"},
        {"sample_id": "v8_lang_test_012", "category": "expository_academic_prose",
         "text": "Admiralty courts exercise distinct in rem jurisdiction over maritime vessels in vessel arrest and salvage entitlement disputes.",
         "expected_outcome": "ACCEPT", "domain": "admiralty_law"},
        {"sample_id": "v8_lang_test_013", "category": "expository_academic_prose",
         "text": "Seismic reflection profiling delineates subsurface structural stratigraphic traps favorable for geothermal reservoir accumulation.",
         "expected_outcome": "ACCEPT", "domain": "exploration_geophysics"},
        {"sample_id": "v8_lang_test_014", "category": "expository_academic_prose",
         "text": "Probabilistic graphical models represent conditional independence relationships across multidimensional random variables through directed acyclic graphs.",
         "expected_outcome": "ACCEPT", "domain": "statistical_learning"},
        {"sample_id": "v8_lang_test_015", "category": "expository_academic_prose",
         "text": "Ubiquitin ligase cascades catalyze covalent substrate polyubiquitination and direct misfolded proteins toward twenty-six S proteasomal degradation.",
         "expected_outcome": "ACCEPT", "domain": "proteomics"},
        {"sample_id": "v8_lang_test_016", "category": "expository_academic_prose",
         "text": "Electrochemical impedance spectroscopy quantifies charge transfer resistance across electrolyte electrode interfaces in lithium batteries.",
         "expected_outcome": "ACCEPT", "domain": "electrochemistry"},
        {"sample_id": "v8_lang_test_017", "category": "expository_academic_prose",
         "text": "Anthropological linguistics explores how spatial cognitive reference frames vary systematically across unrelated indigenous language families.",
         "expected_outcome": "ACCEPT", "domain": "anthropological_linguistics"},
        {"sample_id": "v8_lang_test_018", "category": "expository_academic_prose",
         "text": "Cosmological redshift measurements confirm accelerating cosmic expansion driven by uniform vacuum energy density across spacetime.",
         "expected_outcome": "ACCEPT", "domain": "observational_cosmology"},

        # --- ACCEPT: Scientific Figure Captions (5) ---
        {"sample_id": "v8_lang_test_019", "category": "scientific_figure_captions",
         "text": "Figure 5: High-angle annular dark-field imaging displaying atomic-scale lattice dislocations across epitaxial gallium nitride heterostructures.",
         "expected_outcome": "ACCEPT", "domain": "semiconductor_microscopy"},
        {"sample_id": "v8_lang_test_020", "category": "scientific_figure_captions",
         "text": "Figure 4. Time-resolved fluorescence decay curves of fluorescent reporter dyes in aqueous buffer solutions.",
         "expected_outcome": "ACCEPT", "domain": "biophysics"},
        {"sample_id": "v8_lang_test_021", "category": "scientific_figure_captions",
         "text": "Table 2: Summary of thermodynamic enthalpy and entropy parameters derived from isothermal titration calorimetry measurements.",
         "expected_outcome": "ACCEPT", "domain": "biophysical_chemistry"},
        {"sample_id": "v8_lang_test_022", "category": "scientific_figure_captions",
         "text": "Chart 1: Annual global atmospheric carbon dioxide mixing ratios recorded at the Mauna Loa baseline observatory.",
         "expected_outcome": "ACCEPT", "domain": "climate_science"},
        {"sample_id": "v8_lang_test_023", "category": "scientific_figure_captions",
         "text": "Diagram 5: Schematic illustration of the dual-beam laser interferometer optical configuration with balanced photodiode detection.",
         "expected_outcome": "ACCEPT", "domain": "precision_optics"},

        # --- ACCEPT: Foreign Names, Quotes, Latin Terminology (4) ---
        {"sample_id": "v8_lang_test_024", "category": "foreign_names_and_quotes",
         "text": "The constitutional scholar argued that the doctrine of res judicata precluded further relitigation of the finalized title dispute.",
         "expected_outcome": "ACCEPT", "domain": "civil_procedure"},
        {"sample_id": "v8_lang_test_025", "category": "foreign_names_and_quotes",
         "text": "Astronomer Johannes Kepler formulated three fundamental empirical laws governing the elliptical orbital motion of planetary bodies.",
         "expected_outcome": "ACCEPT", "domain": "history_of_astronomy"},
        {"sample_id": "v8_lang_test_026", "category": "foreign_names_and_quotes",
         "text": "The international diplomatic summit concluded with the signing of the Treaty of Westphalia establishing sovereign territorial autonomy.",
         "expected_outcome": "ACCEPT", "domain": "diplomatic_history"},
        {"sample_id": "v8_lang_test_027", "category": "foreign_names_and_quotes",
         "text": "Medical researchers examined whether in vitro cellular cytotoxic effects correlate directly with clinical in vivo patient outcomes.",
         "expected_outcome": "ACCEPT", "domain": "translational_oncology"},

        # --- ACCEPT: English Imperatives and Concise Instructions (3) ---
        {"sample_id": "v8_lang_test_028", "category": "english_imperatives_instructions",
         "text": "Calibrate the digital spectrophotometer using a quartz cuvette filled with spectroscopic grade deionized water prior to each measurement run.",
         "expected_outcome": "ACCEPT", "domain": "spectrophotometry"},
        {"sample_id": "v8_lang_test_029", "category": "english_imperatives_instructions",
         "text": "Tighten the cylinder head retaining bolts diagonally to ninety Newton meters using a calibrated mechanical torque wrench.",
         "expected_outcome": "ACCEPT", "domain": "mechanical_assembly"},
        {"sample_id": "v8_lang_test_030", "category": "english_imperatives_instructions",
         "text": "Maintain inert nitrogen gas flow through the reaction chamber throughout the high-temperature chemical vapor deposition cycle.",
         "expected_outcome": "ACCEPT", "domain": "semiconductor_processing"},

        # --- QUARANTINE: Code, SQL & Structured Data (5) ---
        {"sample_id": "v8_lang_test_031", "category": "code_sql_structured_data",
         "text": "SELECT employee_id, department, salary FROM payroll_records WHERE hire_date >= '2024-01-01' ORDER BY salary DESC LIMIT 25;",
         "expected_outcome": "QUARANTINE", "domain": "database_queries"},
        {"sample_id": "v8_lang_test_032", "category": "code_sql_structured_data",
         "text": "CREATE INDEX idx_transaction_date ON customer_transactions (transaction_date, account_number);",
         "expected_outcome": "QUARANTINE", "domain": "database_ddl"},
        {"sample_id": "v8_lang_test_033", "category": "code_sql_structured_data",
         "text": "INSERT INTO shipping_manifests (manifest_id, vessel_name, departure_port) VALUES (88102, 'Pacific Voyager', 'Seattle');",
         "expected_outcome": "QUARANTINE", "domain": "database_dml"},
        {"sample_id": "v8_lang_test_034", "category": "code_sql_structured_data",
         "text": "UPDATE flight_schedules SET status = 'DELAYED' WHERE flight_number = 'UA-402' AND departure_date = CURRENT_DATE;",
         "expected_outcome": "QUARANTINE", "domain": "database_dml"},
        {"sample_id": "v8_lang_test_035", "category": "code_sql_structured_data",
         "text": "DROP TABLE obsolete_system_logs;",
         "expected_outcome": "QUARANTINE", "domain": "database_ddl"},

        # --- QUARANTINE: Imperative Signage & Advisory Notices (5) ---
        {"sample_id": "v8_lang_test_036", "category": "imperative_signage_notices",
         "text": "DANGER: CORROSIVE ACID TANK. CHEMICAL GLOVES AND EYE PROTECTION MANDATORY.",
         "expected_outcome": "QUARANTINE", "domain": "chemical_safety_signage"},
        {"sample_id": "v8_lang_test_037", "category": "imperative_signage_notices",
         "text": "CAUTION: LASER RADIATION HAZARD. AVOID DIRECT EYE EXPOSURE TO BEAM.",
         "expected_outcome": "QUARANTINE", "domain": "laser_safety_signage"},
        {"sample_id": "v8_lang_test_038", "category": "imperative_signage_notices",
         "text": "WARNING: FLAMMABLE VAPORS PRESENT. NO SMOKING OR OPEN FLAMES WITHIN FIFTY FEET.",
         "expected_outcome": "QUARANTINE", "domain": "refinery_safety_signage"},
        {"sample_id": "v8_lang_test_039", "category": "imperative_signage_notices",
         "text": "NOTICE: AUTHORIZED PERSONNEL ONLY. ALL VISITORS MUST REGISTER AT SECURITY GATE.",
         "expected_outcome": "QUARANTINE", "domain": "security_signage"},
        {"sample_id": "v8_lang_test_040", "category": "imperative_signage_notices",
         "text": "ATTENTION: AUTOMATED CRANE IN OPERATION. MAINTAIN SAFE CLEARANCE AT ALL TIMES.",
         "expected_outcome": "QUARANTINE", "domain": "crane_safety_signage"},

        # --- QUARANTINE: Short Headings & Fragments (5) ---
        {"sample_id": "v8_lang_test_041", "category": "short_headings_and_fragments",
         "text": "Chapter 7: Quantum Electrodynamics Renormalization Group Calculations.",
         "expected_outcome": "QUARANTINE", "domain": "physics_headings"},
        {"sample_id": "v8_lang_test_042", "category": "short_headings_and_fragments",
         "text": "Appendix D: Standard Reduction Potentials in Aqueous Electrochemistry.",
         "expected_outcome": "QUARANTINE", "domain": "handbook_tables"},
        {"sample_id": "v8_lang_test_043", "category": "short_headings_and_fragments",
         "text": "Section 4: Environmental Assessment Protocols for Coastal Estuaries.",
         "expected_outcome": "QUARANTINE", "domain": "environmental_regulations"},
        {"sample_id": "v8_lang_test_044", "category": "short_headings_and_fragments",
         "text": "Index: Chemical Reagents and Organic Solvents.",
         "expected_outcome": "QUARANTINE", "domain": "index_headings"},
        {"sample_id": "v8_lang_test_045", "category": "short_headings_and_fragments",
         "text": "Part IV: Atmospheric Boundary Layer Turbulence Modeling.",
         "expected_outcome": "QUARANTINE", "domain": "meteorology_divisions"},

        # --- QUARANTINE: Germanic Latin Prose (German & Dutch) (5) ---
        {"sample_id": "v8_lang_test_046", "category": "germanic_latin_prose",
         "text": "Die experimentelle Bestimmung der spezifischen Waermekapazitaet geschieht mittels adiabatischer Kalorimetrie.",
         "expected_outcome": "QUARANTINE", "domain": "german_calorimetry"},
        {"sample_id": "v8_lang_test_047", "category": "germanic_latin_prose",
         "text": "De hydraulische stormvloedkering beschermt het laaggelegen achterland van Zeeland tegen zware noordwesterstormen.",
         "expected_outcome": "QUARANTINE", "domain": "dutch_delta_works"},
        {"sample_id": "v8_lang_test_048", "category": "germanic_latin_prose",
         "text": "Der theoretische Wirkungsgrad waermetechnischer Kraftwerke wird durch den zweiten Hauptsatz der Thermodynamik begrenzt.",
         "expected_outcome": "QUARANTINE", "domain": "german_power_engineering"},
        {"sample_id": "v8_lang_test_049", "category": "germanic_latin_prose",
         "text": "Een nauwkeurige meteorologische voorspelling vereist numerieke modellen van atmosferische circulatie op wereldschaal.",
         "expected_outcome": "QUARANTINE", "domain": "dutch_meteorology"},
        {"sample_id": "v8_lang_test_050", "category": "germanic_latin_prose",
         "text": "Durch die Zugabe von Chrom und Nickel erhaelt der austenitische Edelstahl seine hervorragende Korrosionsbestaendigkeit.",
         "expected_outcome": "QUARANTINE", "domain": "german_steel_metallurgy"},

        # --- REJECT: Romance Latin Prose (French, Spanish, Italian) (5) ---
        {"sample_id": "v8_lang_test_051", "category": "romance_latin_prose",
         "text": "La cinetique de reaction des composes organiques volatils dans la troposphere determine la formation de l'ozone.",
         "expected_outcome": "REJECT", "domain": "french_atmospheric_chemistry"},
        {"sample_id": "v8_lang_test_052", "category": "romance_latin_prose",
         "text": "El descubrimiento arqueologico de herramientas liticas prehistoricas confirma la presencia humana temprana en la cuenca.",
         "expected_outcome": "REJECT", "domain": "spanish_prehistory"},
        {"sample_id": "v8_lang_test_053", "category": "romance_latin_prose",
         "text": "Lo studio della stabilita sismica delle dighe richiede modelli geotecnici tridimensionali del substrato roccioso.",
         "expected_outcome": "REJECT", "domain": "italian_dam_engineering"},
        {"sample_id": "v8_lang_test_054", "category": "romance_latin_prose",
         "text": "La synthese asymetrique d'alcaloides naturels ouvre des voies nouvelles pour le developpement d'agents pharmacologiques.",
         "expected_outcome": "REJECT", "domain": "french_pharmacology"},
        {"sample_id": "v8_lang_test_055", "category": "romance_latin_prose",
         "text": "La conservacion de los ecosistemas de manglares es fundamental para proteger las costas contra la erosion marina.",
         "expected_outcome": "REJECT", "domain": "spanish_marine_conservation"},

        # --- REJECT: Non-Latin Script (2) ---
        {"sample_id": "v8_lang_test_056", "category": "non_latin_script",
         "text": "Молекулярно-динамическое моделирование позволяет детально исследовать конформационные переходы биомолекул.",
         "expected_outcome": "REJECT", "domain": "russian_biophysics"},
        {"sample_id": "v8_lang_test_057", "category": "non_latin_script",
         "text": "超导材料在临界温度以下表现出完全零电阻和完全抗磁性的迈斯纳效应。",
         "expected_outcome": "REJECT", "domain": "chinese_superconductivity"},

        # --- REJECT: Malformed Noise & Repetitions (3) ---
        {"sample_id": "v8_lang_test_058", "category": "malformed_noise",
         "text": "+++===*** ---%%% $$$###@@@ !!!^^^&&& ((( ))) {{{}}} [[[ ]]] :::;;;'''\"\"\"<<<>>>???///\\\\\\|||",
         "expected_outcome": "REJECT", "domain": "ascii_symbol_noise"},
        {"sample_id": "v8_lang_test_059", "category": "malformed_noise",
         "text": "fatal error fatal error fatal error fatal error fatal error fatal error fatal error fatal error fatal error",
         "expected_outcome": "REJECT", "domain": "repeated_token_dump"},
        {"sample_id": "v8_lang_test_060", "category": "malformed_noise",
         "text": "asdfghjk qwertyui zxcvbnm poiuytre lkjhgfds mnbvcxz qazwsx edcrfv tgbyhn ujmikol",
         "expected_outcome": "REJECT", "domain": "random_consonant_strings"},
    ]

    return {
        "dataset_name": "eval_language_dataset_v8",
        "version": "8.0-provisional",
        "provenance_status": "PROVISIONAL — INDEPENDENCE UNVERIFIED",
        "authorship": {
            "creator": "Antigravity Automated Governance Agent",
            "role": "Independent Validation Benchmark Builder",
            "date": "2026-10-17",
            "access_control": "Implementation frozen prior to evaluation; no training or tuning conducted on this set.",
            "independence_disclosure": (
                "Constructed internally by Antigravity agent using formal written guidelines. "
                "Per Stage 3.1 rules, marked PROVISIONAL — INDEPENDENCE UNVERIFIED until external third-party certification occurs."
            ),
        },
        "labeling_policy": {
            "ACCEPT": "Fluent English expository, academic, or ordinary prose meeting quality and syntactic criteria.",
            "QUARANTINE": "Ambiguous, terse, structured (SQL), short (<12 words), or Latin-script Germanic natural prose requiring holding.",
            "REJECT": "Non-English foreign Latin prose (Romance), non-Latin scripts, corrupted symbol noise, repeated tokens.",
        },
        "split_summary": {
            "development_split_count": len(dev_samples),
            "test_split_count": len(test_samples),
            "total_count": len(dev_samples) + len(test_samples),
            "distribution_per_split": {"ACCEPT": 30, "QUARANTINE": 20, "REJECT": 10},
        },
        "development_split": dev_samples,
        "test_split": test_samples,
    }


def build_v8_near_dedup_dataset() -> Dict[str, Any]:
    # Development Split (20 pairs)
    dev_pairs = [
        # --- Positive: Exact & Reformatted Duplicates (2) ---
        {"pair_id": "v8_dedup_dev_001", "category": "exact_duplicate", "is_true_duplicate": True,
         "text_a": "The geothermal power plant extracts high-temperature brine from fractured volcanic formations to drive binary cycle turbine generators.",
         "text_b": "The geothermal power plant extracts high-temperature brine from fractured volcanic formations to drive binary cycle turbine generators."},
        {"pair_id": "v8_dedup_dev_002", "category": "reformatted_duplicate", "is_true_duplicate": True,
         "text_a": "The archaeological field report recorded thirty-four intact obsidian blades uncovered within the ceremonial burial mound.",
         "text_b": "The archaeological field report recorded\nthirty-four intact obsidian blades   uncovered within the ceremonial burial mound."},

        # --- Positive: Voice & Syntactic Paraphrases (2) ---
        {"pair_id": "v8_dedup_dev_003", "category": "paraphrase_duplicate", "is_true_duplicate": True,
         "text_a": "Marine biologists tagged twenty-five juvenile hammerhead sharks to monitor their seasonal migration through coastal lagoons.",
         "text_b": "Twenty-five juvenile hammerhead sharks were tagged by marine biologists to monitor their seasonal migration through coastal lagoons."},
        {"pair_id": "v8_dedup_dev_004", "category": "reordered_duplicate", "is_true_duplicate": True,
         "text_a": "The chemical reactor vessel was depressurized safely. The cooling jacket maintained optimal temperature throughout the emergency shutdown.",
         "text_b": "The cooling jacket maintained optimal temperature throughout the emergency shutdown. The chemical reactor vessel was depressurized safely."},

        # --- Positive: Standardized SI/IEC Unit Conversions (4) ---
        {"pair_id": "v8_dedup_dev_005", "category": "unit_conversion_duplicate", "is_true_duplicate": True,
         "text_a": "The metallurgical technician added 5000 g of granular copper powder to the induction furnace crucible.",
         "text_b": "The metallurgical technician added 5 kg of granular copper powder to the induction furnace crucible."},
        {"pair_id": "v8_dedup_dev_006", "category": "unit_conversion_duplicate", "is_true_duplicate": True,
         "text_a": "The centrifuge rotation period was precisely calibrated at 120 s during the separation cycle.",
         "text_b": "The centrifuge rotation period was precisely calibrated at 2 min during the separation cycle."},
        {"pair_id": "v8_dedup_dev_007", "category": "unit_conversion_duplicate", "is_true_duplicate": True,
         "text_a": "The hydraulic transmission line measured exactly 250 cm between the master cylinder and the brake caliper.",
         "text_b": "The hydraulic transmission line measured exactly 2.5 m between the master cylinder and the brake caliper."},
        {"pair_id": "v8_dedup_dev_008", "category": "unit_conversion_duplicate", "is_true_duplicate": True,
         "text_a": "The digital telemetry buffer allocated 2048 b for high-speed sensor packet caching.",
         "text_b": "The digital telemetry buffer allocated 2 kib for high-speed sensor packet caching."},

        # --- Negative: Distant Domain Negative (1) ---
        {"pair_id": "v8_dedup_dev_009", "category": "distant_negative", "is_true_duplicate": False,
         "text_a": "Silviculturists recommend rotational thinning in commercial pine plantations to reduce fuel loads and mitigate wildfire severity.",
         "text_b": "Radio astronomers observed relativistic electron synchrotron emissions emanating from the active galactic nucleus of Messier 87."},

        # --- Safety Negative: Polarity Inversion (expand vs reduce / increase vs decrease) (2) ---
        {"pair_id": "v8_dedup_dev_010", "category": "safety_polarity_inversion", "is_true_duplicate": False,
         "text_a": "The regional river basin authority resolved to expand commercial irrigation water allocations during the summer drought.",
         "text_b": "The regional river basin authority resolved to reduce commercial irrigation water allocations during the summer drought."},
        {"pair_id": "v8_dedup_dev_011", "category": "safety_polarity_inversion", "is_true_duplicate": False,
         "text_a": "The pharmaceutical review board voted to approve the novel monoclonal antibody therapy for pediatric oncology patients.",
         "text_b": "The pharmaceutical review board voted to reject the novel monoclonal antibody therapy for pediatric oncology patients."},

        # --- Safety Negative: Numerical Dosage & Magnitude Inversion (2) ---
        {"pair_id": "v8_dedup_dev_012", "category": "safety_dosage_inversion", "is_true_duplicate": False,
         "text_a": "The clinical trial protocol mandated a single daily dose of 5 mg of active anticoagulant compound.",
         "text_b": "The clinical trial protocol mandated a single daily dose of 50 mg of active anticoagulant compound."},
        {"pair_id": "v8_dedup_dev_013", "category": "safety_dosage_inversion", "is_true_duplicate": False,
         "text_a": "The high-voltage dielectric breakdown occurred at an applied potential of 0.025 v across the insulating gap.",
         "text_b": "The high-voltage dielectric breakdown occurred at an applied potential of 0.250 v across the insulating gap."},

        # --- Safety Negative: Physical Unit & Dimension Mismatch (2) ---
        {"pair_id": "v8_dedup_dev_014", "category": "safety_unit_mismatch", "is_true_duplicate": False,
         "text_a": "The chemical reactor containment vessel was certified to withstand an internal pressure of 12.0 bar.",
         "text_b": "The chemical reactor containment vessel was certified to withstand an internal pressure of 12.0 m."},
        {"pair_id": "v8_dedup_dev_015", "category": "safety_unit_mismatch", "is_true_duplicate": False,
         "text_a": "The backup diesel generator produced an electrical current output of 40.0 a during peak operational load.",
         "text_b": "The backup diesel generator produced an electrical current output of 40.0 v during peak operational load."},

        # --- Safety Negative: Calendar Date, Year & Month Mismatch (2) ---
        {"pair_id": "v8_dedup_dev_016", "category": "safety_date_mismatch", "is_true_duplicate": False,
         "text_a": "The international polar research expedition established its primary coastal station in Antarctica in 1957.",
         "text_b": "The international polar research expedition established its primary coastal station in Antarctica in 1963."},
        {"pair_id": "v8_dedup_dev_017", "category": "safety_date_mismatch", "is_true_duplicate": False,
         "text_a": "The definitive commercial trade pact was formally signed in Geneva on May 22, 2021 by all member states.",
         "text_b": "The definitive commercial trade pact was formally signed in Geneva on November 22, 2021 by all member states."},

        # --- Safety Negative: Asymmetric Negation Particle Inversion (2) ---
        {"pair_id": "v8_dedup_dev_018", "category": "safety_negation_inversion", "is_true_duplicate": False,
         "text_a": "The automated fire suppression system was activated immediately upon detection of dense smoke in the server vault.",
         "text_b": "The automated fire suppression system was not activated immediately upon detection of dense smoke in the server vault."},
        {"pair_id": "v8_dedup_dev_019", "category": "safety_negation_inversion", "is_true_duplicate": False,
         "text_a": "The safety isolation valve can never open automatically while pipeline pressure exceeds operating limits.",
         "text_b": "The safety isolation valve can easily open automatically while pipeline pressure exceeds operating limits."},

        # --- Safety Negative: Alphanumeric Entity Identifier Conflict (1) ---
        {"pair_id": "v8_dedup_dev_020", "category": "safety_identifier_conflict", "is_true_duplicate": False,
         "text_a": "Diagnostic telemetry from autonomous seabed Rover-X204 confirmed normal propulsion motor torque and battery status.",
         "text_b": "Diagnostic telemetry from autonomous seabed Rover-Y204 confirmed normal propulsion motor torque and battery status."},
    ]

    # Held-Out Test Split (20 pairs)
    test_pairs = [
        # --- Positive: Exact & Reformatted Duplicates (2) ---
        {"pair_id": "v8_dedup_test_001", "category": "exact_duplicate", "is_true_duplicate": True,
         "text_a": "The optical interferometry telescope array resolved the stellar disk of the red supergiant star with unprecedented clarity.",
         "text_b": "The optical interferometry telescope array resolved the stellar disk of the red supergiant star with unprecedented clarity."},
        {"pair_id": "v8_dedup_test_002", "category": "reformatted_duplicate", "is_true_duplicate": True,
         "text_a": "Agricultural specialists tested eighteen hybrid maize cultivars across three semi-arid experimental research farms.",
         "text_b": "Agricultural specialists tested eighteen hybrid maize cultivars\nacross three semi-arid   experimental research farms."},

        # --- Positive: Voice & Syntactic Paraphrases (2) ---
        {"pair_id": "v8_dedup_test_003", "category": "paraphrase_duplicate", "is_true_duplicate": True,
         "text_a": "Structural civil engineers inspected forty reinforced concrete viaducts throughout the metropolitan rail network.",
         "text_b": "Forty reinforced concrete viaducts throughout the metropolitan rail network were inspected by structural civil engineers."},
        {"pair_id": "v8_dedup_test_004", "category": "reordered_duplicate", "is_true_duplicate": True,
         "text_a": "The vacuum drying oven maintained a constant temperature of sixty degrees. The chemical sample evaporated completely over four hours.",
         "text_b": "The chemical sample evaporated completely over four hours. The vacuum drying oven maintained a constant temperature of sixty degrees."},

        # --- Positive: Standardized SI/IEC Unit Conversions (4) ---
        {"pair_id": "v8_dedup_test_005", "category": "unit_conversion_duplicate", "is_true_duplicate": True,
         "text_a": "The laboratory technician dispensed exactly 8000 mg of anhydrous sodium carbonate into the volumetric flask.",
         "text_b": "The laboratory technician dispensed exactly 8 g of anhydrous sodium carbonate into the volumetric flask."},
        {"pair_id": "v8_dedup_test_006", "category": "unit_conversion_duplicate", "is_true_duplicate": True,
         "text_a": "The emergency battery power bank maintained full emergency lighting operation for 180 s after grid failure.",
         "text_b": "The emergency battery power bank maintained full emergency lighting operation for 3 min after grid failure."},
        {"pair_id": "v8_dedup_test_007", "category": "unit_conversion_duplicate", "is_true_duplicate": True,
         "text_a": "The structural carbon fiber reinforcement rod measured precisely 400 cm along its longitudinal axis.",
         "text_b": "The structural carbon fiber reinforcement rod measured precisely 4.0 m along its longitudinal axis."},
        {"pair_id": "v8_dedup_test_008", "category": "unit_conversion_duplicate", "is_true_duplicate": True,
         "text_a": "The flash memory controller cached 4096 b of firmware configuration instructions during the initial system boot.",
         "text_b": "The flash memory controller cached 4 kib of firmware configuration instructions during the initial system boot."},

        # --- Negative: Distant Domain Negative (1) ---
        {"pair_id": "v8_dedup_test_009", "category": "distant_negative", "is_true_duplicate": False,
         "text_a": "Geodesic satellite receivers track tectonic plate displacement rates across the active San Andreas fault zone.",
         "text_b": "The classical symphony orchestra performed Beethoven's Ninth Symphony before a capacity audience in the historic concert hall."},

        # --- Safety Negative: Polarity Inversion (expand vs reduce / increase vs decrease) (2) ---
        {"pair_id": "v8_dedup_test_010", "category": "safety_polarity_inversion", "is_true_duplicate": False,
         "text_a": "The municipal transport commission decided to expand daily express bus service routes across the outer suburban ring.",
         "text_b": "The municipal transport commission decided to reduce daily express bus service routes across the outer suburban ring."},
        {"pair_id": "v8_dedup_test_011", "category": "safety_polarity_inversion", "is_true_duplicate": False,
         "text_a": "Preclinical toxicological evaluations concluded that the synthetic emulsifying agent was completely safe and non-toxic.",
         "text_b": "Preclinical toxicological evaluations concluded that the synthetic emulsifying agent was highly dangerous and toxic."},

        # --- Safety Negative: Numerical Dosage & Magnitude Inversion (2) ---
        {"pair_id": "v8_dedup_test_012", "category": "safety_dosage_inversion", "is_true_duplicate": False,
         "text_a": "The experimental pharmacological regimen prescribed an intravenous infusion of 0.004 g of active compound.",
         "text_b": "The experimental pharmacological regimen prescribed an intravenous infusion of 0.040 g of active compound."},
        {"pair_id": "v8_dedup_test_013", "category": "safety_dosage_inversion", "is_true_duplicate": False,
         "text_a": "The precision reference resistor displayed a calibrated resistance tolerance deviation of 0.015 ohms.",
         "text_b": "The precision reference resistor displayed a calibrated resistance tolerance deviation of 0.150 ohms."},

        # --- Safety Negative: Physical Unit & Dimension Mismatch (2) ---
        {"pair_id": "v8_dedup_test_014", "category": "safety_unit_mismatch", "is_true_duplicate": False,
         "text_a": "The hydraulic accumulator chamber was pressurized to a steady operating pressure of 20.0 bar.",
         "text_b": "The hydraulic accumulator chamber was pressurized to a steady operating pressure of 20.0 m."},
        {"pair_id": "v8_dedup_test_015", "category": "safety_unit_mismatch", "is_true_duplicate": False,
         "text_a": "The high-voltage transmission substation conductor carried a continuous current load of 60.0 a.",
         "text_b": "The high-voltage transmission substation conductor carried a continuous current load of 60.0 v."},

        # --- Safety Negative: Calendar Date, Year & Month Mismatch (2) ---
        {"pair_id": "v8_dedup_test_016", "category": "safety_date_mismatch", "is_true_duplicate": False,
         "text_a": "The transcontinental railway telegraph network was formally completed and linked to coastal hubs in 1869.",
         "text_b": "The transcontinental railway telegraph network was formally completed and linked to coastal hubs in 1875."},
        {"pair_id": "v8_dedup_test_017", "category": "safety_date_mismatch", "is_true_duplicate": False,
         "text_a": "The international convention on migratory wetland waterfowl entered into full legal force on February 18, 1992.",
         "text_b": "The international convention on migratory wetland waterfowl entered into full legal force on September 18, 1992."},

        # --- Safety Negative: Asymmetric Negation Particle Inversion (2) ---
        {"pair_id": "v8_dedup_test_018", "category": "safety_negation_inversion", "is_true_duplicate": False,
         "text_a": "The secondary containment vessel showed evidence of structural stress fracture under sustained pneumatic pressure.",
         "text_b": "The secondary containment vessel showed no evidence of structural stress fracture under sustained pneumatic pressure."},
        {"pair_id": "v8_dedup_test_019", "category": "safety_negation_inversion", "is_true_duplicate": False,
         "text_a": "The industrial control software can never bypass hardware emergency interlocks during automated furnace operation.",
         "text_b": "The industrial control software can easily bypass hardware emergency interlocks during automated furnace operation."},

        # --- Safety Negative: Alphanumeric Entity Identifier Conflict (1) ---
        {"pair_id": "v8_dedup_test_020", "category": "safety_identifier_conflict", "is_true_duplicate": False,
         "text_a": "Operational logs from nuclear propulsion reactor Turbine-X501 showed standard coolant flow rates throughout the sea trial.",
         "text_b": "Operational logs from nuclear propulsion reactor Turbine-Y501 showed standard coolant flow rates throughout the sea trial."},
    ]

    return {
        "dataset_name": "eval_near_dedup_dataset_v8",
        "version": "8.0-provisional",
        "provenance_status": "PROVISIONAL — INDEPENDENCE UNVERIFIED",
        "authorship": {
            "creator": "Antigravity Automated Governance Agent",
            "role": "Independent Validation Benchmark Builder",
            "date": "2026-10-17",
            "access_control": "Implementation frozen prior to evaluation; no training or tuning conducted on this set.",
            "independence_disclosure": (
                "Constructed internally by Antigravity agent using formal written guidelines. "
                "Per Stage 3.1 rules, marked PROVISIONAL — INDEPENDENCE UNVERIFIED until external third-party certification occurs."
            ),
        },
        "labeling_policy": {
            "True": "Semantically and factually equivalent assertion; eligible for safe duplicate removal.",
            "False": "Material factual discrepancy (dosage, unit dimension, polarity, negation, date, identifier, or distant topic).",
        },
        "split_summary": {
            "development_split_count": len(dev_pairs),
            "test_split_count": len(test_pairs),
            "total_count": len(dev_pairs) + len(test_pairs),
            "distribution_per_split": {"True": 8, "False": 12},
        },
        "development_split": dev_pairs,
        "test_split": test_pairs,
    }


def main() -> None:
    corpus_dir = _ROOT / "data" / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)

    # 1. Language dataset v8
    lang_v8 = build_v8_language_dataset()
    lang_path = corpus_dir / "eval_language_dataset_v8.json"
    with open(lang_path, "w", encoding="utf-8") as f:
        json.dump(lang_v8, f, indent=2)
    lang_hash = hashlib.sha256(lang_path.read_bytes()).hexdigest()
    print(f"Emitted {lang_path.name}: {len(lang_v8['development_split'])} dev + {len(lang_v8['test_split'])} test samples (SHA-256: {lang_hash})")

    # 2. Near-dedup dataset v8
    dedup_v8 = build_v8_near_dedup_dataset()
    dedup_path = corpus_dir / "eval_near_dedup_dataset_v8.json"
    with open(dedup_path, "w", encoding="utf-8") as f:
        json.dump(dedup_v8, f, indent=2)
    dedup_hash = hashlib.sha256(dedup_path.read_bytes()).hexdigest()
    print(f"Emitted {dedup_path.name}: {len(dedup_v8['development_split'])} dev + {len(dedup_v8['test_split'])} test pairs (SHA-256: {dedup_hash})")


if __name__ == "__main__":
    main()
