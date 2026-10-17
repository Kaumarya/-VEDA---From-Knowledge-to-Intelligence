"""
VEDA Phase 4.9 Sealed Benchmark Generation Script (v7.0)
Constructs the frozen, non-templated v7.0 benchmark datasets for Phase 4.9:
1. data/corpus/eval_language_dataset_v7.json (Task A: Language Identification & Quality Filtering)
2. data/corpus/eval_near_dedup_dataset_v7.json (Task B: Near-Deduplication & Semantic Safety Guard)

Guarantees:
- Zero template loops or programmatic `{i+1}` iterations.
- Realistic, human-authored sentences across disjoint academic, scientific, historical, and technical domains.
- Clear, unambiguous annotation rules for ACCEPT, QUARANTINE, REJECT and duplicate vs distinct.
- Strict isolation from prior v2, v3, v4, v5, and v6 datasets (zero textual overlap).
- Cryptographic SHA-256 provenance recording.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

_ROOT = Path(__file__).resolve().parent.parent


def build_v7_language_dataset() -> Dict[str, Any]:
    # Development Split (60 samples)
    dev_samples = [
        # --- ACCEPT: Ordinary English Prose (10) ---
        {"sample_id": "v7_lang_dev_001", "category": "ordinary_english_prose",
         "text": "The timber bridge across the canyon was fortified with heavy iron trusses to support commercial freight wagons.",
         "expected_outcome": "ACCEPT", "domain": "civil_engineering_history"},
        {"sample_id": "v7_lang_dev_002", "category": "ordinary_english_prose",
         "text": "Modern meteorological stations deploy automated radiosonde balloons to gather atmospheric temperature profiles at high altitudes.",
         "expected_outcome": "ACCEPT", "domain": "meteorology"},
        {"sample_id": "v7_lang_dev_003", "category": "ordinary_english_prose",
         "text": "The village blacksmith tempered the carbon steel chisels in brine to achieve optimal cutting hardness and edge retention.",
         "expected_outcome": "ACCEPT", "domain": "traditional_metallurgy"},
        {"sample_id": "v7_lang_dev_004", "category": "ordinary_english_prose",
         "text": "Subterranean limestone caverns formed over thousands of years as carbonic acid slowly dissolved the calcium carbonate rock.",
         "expected_outcome": "ACCEPT", "domain": "speleology"},
        {"sample_id": "v7_lang_dev_005", "category": "ordinary_english_prose",
         "text": "Harbor authorities introduced strict container inspection standards to prevent invasive aquatic organisms from entering coastal bays.",
         "expected_outcome": "ACCEPT", "domain": "maritime_ecology"},
        {"sample_id": "v7_lang_dev_006", "category": "ordinary_english_prose",
         "text": "The historic cathedral clock tower incorporates an intricate pendulum escapement mechanism crafted by apprentice watchmakers.",
         "expected_outcome": "ACCEPT", "domain": "horology"},
        {"sample_id": "v7_lang_dev_007", "category": "ordinary_english_prose",
         "text": "Alpine glaciers deposited unsorted glacial till along the valley floor during successive Pleistocene glacial advances.",
         "expected_outcome": "ACCEPT", "domain": "geomorphology"},
        {"sample_id": "v7_lang_dev_008", "category": "ordinary_english_prose",
         "text": "The city health department opened public vaccination clinics across five municipal boroughs during the autumn flu outbreak.",
         "expected_outcome": "ACCEPT", "domain": "public_health"},
        {"sample_id": "v7_lang_dev_009", "category": "ordinary_english_prose",
         "text": "Artisanal glassblowers reheat molten silicate glass inside annealing lehrs to release mechanical internal stresses.",
         "expected_outcome": "ACCEPT", "domain": "glass_manufacturing"},
        {"sample_id": "v7_lang_dev_010", "category": "ordinary_english_prose",
         "text": "Ornithologists banded juvenile peregrine falcons to track their predatory dispersal patterns throughout eastern river gorges.",
         "expected_outcome": "ACCEPT", "domain": "wildlife_biology"},

        # --- ACCEPT: Expository Academic Prose (10) ---
        {"sample_id": "v7_lang_dev_011", "category": "expository_academic_prose",
         "text": "Quantum entanglement demonstrates non-local quantum state correlations that cannot be explained by classical hidden variable theories.",
         "expected_outcome": "ACCEPT", "domain": "quantum_mechanics"},
        {"sample_id": "v7_lang_dev_012", "category": "expository_academic_prose",
         "text": "Administrative law governs the procedural rulemaking and adjudicative authority exercised by regulatory executive agencies.",
         "expected_outcome": "ACCEPT", "domain": "administrative_law"},
        {"sample_id": "v7_lang_dev_013", "category": "expository_academic_prose",
         "text": "Mantle convection plumes generate intraplate volcanic hotspot tracks that remain stationary relative to moving oceanic plates.",
         "expected_outcome": "ACCEPT", "domain": "geodynamics"},
        {"sample_id": "v7_lang_dev_014", "category": "expository_academic_prose",
         "text": "Syntactic parsing algorithms construct hierarchical phrase structure trees from sequential natural language sentences.",
         "expected_outcome": "ACCEPT", "domain": "computational_linguistics"},
        {"sample_id": "v7_lang_dev_015", "category": "expository_academic_prose",
         "text": "Allosteric enzyme regulation modifies substrate affinity through conformational changes induced by effector molecule binding.",
         "expected_outcome": "ACCEPT", "domain": "biochemistry"},
        {"sample_id": "v7_lang_dev_016", "category": "expository_academic_prose",
         "text": "Thermodynamic free energy determines the spontaneous equilibrium direction of reversible chemical reactions under isobaric conditions.",
         "expected_outcome": "ACCEPT", "domain": "chemical_thermodynamics"},
        {"sample_id": "v7_lang_dev_017", "category": "expository_academic_prose",
         "text": "Phenomenological sociology investigates how social actors construct intersubjective shared meaning during everyday interactions.",
         "expected_outcome": "ACCEPT", "domain": "sociological_theory"},
        {"sample_id": "v7_lang_dev_018", "category": "expository_academic_prose",
         "text": "Radiocarbon dating measures the isotopic ratio of carbon fourteen to carbon twelve in deceased organic specimens.",
         "expected_outcome": "ACCEPT", "domain": "geochronology"},
        {"sample_id": "v7_lang_dev_019", "category": "expository_academic_prose",
         "text": "Fourier transform infrared spectroscopy characterizes vibrational molecular absorption bands in synthetic polymeric thin films.",
         "expected_outcome": "ACCEPT", "domain": "spectrochemical_analysis"},
        {"sample_id": "v7_lang_dev_020", "category": "expository_academic_prose",
         "text": "Histone acetylation modulates chromatin accessibility and regulates transcriptional activation of repressed eukaryotic gene promoters.",
         "expected_outcome": "ACCEPT", "domain": "epigenetics"},

        # --- ACCEPT: Scientific Figure Captions (5) ---
        {"sample_id": "v7_lang_dev_021", "category": "scientific_figure_captions",
         "text": "Figure 1: Atomic force microscope topography of epitaxial graphene grown on silicon carbide substrates.",
         "expected_outcome": "ACCEPT", "domain": "nanotechnology"},
        {"sample_id": "v7_lang_dev_022", "category": "scientific_figure_captions",
         "text": "Figure 2. Measured ultraviolet photoluminescence excitation spectra of colloidal zinc oxide nanocrystals at cryogenic temperatures.",
         "expected_outcome": "ACCEPT", "domain": "condensed_matter"},
        {"sample_id": "v7_lang_dev_023", "category": "scientific_figure_captions",
         "text": "Table 1: Calculated lattice parameters and mechanical fracture toughness for sintered silicon nitride ceramics.",
         "expected_outcome": "ACCEPT", "domain": "materials_science"},
        {"sample_id": "v7_lang_dev_024", "category": "scientific_figure_captions",
         "text": "Chart 3: Diurnal variation of photosynthetic carbon assimilation measured across three deciduous tree species.",
         "expected_outcome": "ACCEPT", "domain": "plant_physiology"},
        {"sample_id": "v7_lang_dev_025", "category": "scientific_figure_captions",
         "text": "Diagram 2. Cross-sectional schematic diagram of the high-vacuum cryogenic magnetron sputtering deposition chamber.",
         "expected_outcome": "ACCEPT", "domain": "thin_film_physics"},

        # --- ACCEPT: English with Foreign Quotes / Names (5) ---
        {"sample_id": "v7_lang_dev_026", "category": "foreign_names_and_quotes",
         "text": "The international legal commission concluded that the principle of pacta sunt servanda governs binding treaty obligations.",
         "expected_outcome": "ACCEPT", "domain": "international_law"},
        {"sample_id": "v7_lang_dev_027", "category": "foreign_names_and_quotes",
         "text": "German philosopher Arthur Schopenhauer analyzed the concept of Wille und Vorstellung in his foundational metaphysical treatises.",
         "expected_outcome": "ACCEPT", "domain": "metaphysics"},
        {"sample_id": "v7_lang_dev_028", "category": "foreign_names_and_quotes",
         "text": "The art historian emphasized that the painter adopted the dramatic chiaroscuro style popularized during the Italian Renaissance.",
         "expected_outcome": "ACCEPT", "domain": "art_history"},
        {"sample_id": "v7_lang_dev_029", "category": "foreign_names_and_quotes",
         "text": "Economists debate whether the principle of laissez-faire market competition provides sufficient stabilization during financial crises.",
         "expected_outcome": "ACCEPT", "domain": "macroeconomics"},
        {"sample_id": "v7_lang_dev_030", "category": "foreign_names_and_quotes",
         "text": "The constitutional judge delivered a writ of habeas corpus commanding the state custodian to present the detained prisoner.",
         "expected_outcome": "ACCEPT", "domain": "constitutional_law"},

        # --- QUARANTINE: Code, SQL & Structured Data (5) ---
        {"sample_id": "v7_lang_dev_031", "category": "code_sql_structured_data",
         "text": "SELECT transaction_id, merchant_name, settlement_amount FROM daily_clearing_records WHERE settlement_amount > 1000.00;",
         "expected_outcome": "QUARANTINE", "domain": "sql_data"},
        {"sample_id": "v7_lang_dev_032", "category": "code_sql_structured_data",
         "text": "INSERT INTO flight_reservations (booking_reference, passenger_name, flight_number) VALUES ('ABC123', 'John Doe', 'FL402');",
         "expected_outcome": "QUARANTINE", "domain": "sql_data"},
        {"sample_id": "v7_lang_dev_033", "category": "code_sql_structured_data",
         "text": "CREATE TABLE weather_stations (station_id INTEGER PRIMARY KEY, elevation_meters REAL, wind_speed_knots REAL);",
         "expected_outcome": "QUARANTINE", "domain": "sql_data"},
        {"sample_id": "v7_lang_dev_034", "category": "code_sql_structured_data",
         "text": "UPDATE patient_records SET discharge_status = 'COMPLETED', room_number = NULL WHERE patient_id = 90210;",
         "expected_outcome": "QUARANTINE", "domain": "sql_data"},
        {"sample_id": "v7_lang_dev_035", "category": "code_sql_structured_data",
         "text": "DROP TABLE obsolete_inventory_snapshots;",
         "expected_outcome": "QUARANTINE", "domain": "sql_data"},

        # --- QUARANTINE: Imperative Signage & Warnings (5) ---
        {"sample_id": "v7_lang_dev_036", "category": "imperative_signage_notices",
         "text": "DANGER: High pressure steam line. Keep clear of relief valve exhaust port at all times.",
         "expected_outcome": "QUARANTINE", "domain": "industrial_signage"},
        {"sample_id": "v7_lang_dev_037", "category": "imperative_signage_notices",
         "text": "CAUTION: Strong magnetic field hazard. Cardiac pacemakers and metallic implants prohibited beyond this point.",
         "expected_outcome": "QUARANTINE", "domain": "medical_safety"},
        {"sample_id": "v7_lang_dev_038", "category": "imperative_signage_notices",
         "text": "WARNING: Corrosive acid storage area. Chemical splash goggles and rubber apron mandatory.",
         "expected_outcome": "QUARANTINE", "domain": "chemical_safety"},
        {"sample_id": "v7_lang_dev_039", "category": "imperative_signage_notices",
         "text": "NOTICE: Server room access restricted to authorized IT operations personnel only.",
         "expected_outcome": "QUARANTINE", "domain": "facility_compliance"},
        {"sample_id": "v7_lang_dev_040", "category": "imperative_signage_notices",
         "text": "ALERT: Severe weather shelter location. Remain inside interior hallway until the storm passes.",
         "expected_outcome": "QUARANTINE", "domain": "emergency_signage"},

        # --- QUARANTINE: Short Headings & Fragments (5) ---
        {"sample_id": "v7_lang_dev_041", "category": "short_headings_and_fragments",
         "text": "Section 4.2 Analytical Spectrophotometry Calibration Procedures",
         "expected_outcome": "QUARANTINE", "domain": "technical_heading"},
        {"sample_id": "v7_lang_dev_042", "category": "short_headings_and_fragments",
         "text": "Chapter VIII: Advanced Structural Optimization Methods",
         "expected_outcome": "QUARANTINE", "domain": "textbook_heading"},
        {"sample_id": "v7_lang_dev_043", "category": "short_headings_and_fragments",
         "text": "Appendix D: Supplementary Chemical Reagent Specifications",
         "expected_outcome": "QUARANTINE", "domain": "monograph_heading"},
        {"sample_id": "v7_lang_dev_044", "category": "short_headings_and_fragments",
         "text": "Quarterly Financial Performance Summary Report 2024",
         "expected_outcome": "QUARANTINE", "domain": "corporate_heading"},
        {"sample_id": "v7_lang_dev_045", "category": "short_headings_and_fragments",
         "text": "Module 3: Linear Matrix Algebra Foundations",
         "expected_outcome": "QUARANTINE", "domain": "syllabus_heading"},

        # --- QUARANTINE: Germanic Latin Prose (5) ---
        {"sample_id": "v7_lang_dev_046", "category": "germanic_latin_prose",
         "text": "Die Entwicklung der modernen Halbleiterphysik fuehrte zu bahnbrechenden Entdeckungen in der Festkoerperchemie.",
         "expected_outcome": "QUARANTINE", "domain": "german_solid_state"},
        {"sample_id": "v7_lang_dev_047", "category": "germanic_latin_prose",
         "text": "Het waterbeheer in Nederland vereist voortdurende inspectie van dijken en gemalen langs de rivieren.",
         "expected_outcome": "QUARANTINE", "domain": "dutch_water_management"},
        {"sample_id": "v7_lang_dev_048", "category": "germanic_latin_prose",
         "text": "Abbildung 8: Mikroskopische Aufnahme der Kristallstruktur bei Raumtemperatur und Normaldruck.",
         "expected_outcome": "QUARANTINE", "domain": "german_scientific_caption"},
        {"sample_id": "v7_lang_dev_049", "category": "germanic_latin_prose",
         "text": "De haven van Rotterdam verwerkt jaarlijks miljoenen containers uit alle delen van de wereld door geautomatiseerde kranen.",
         "expected_outcome": "QUARANTINE", "domain": "dutch_logistics"},
        {"sample_id": "v7_lang_dev_050", "category": "germanic_latin_prose",
         "text": "Eine genaue Bestimmung der Reaktionsgeschwindigkeit ist fuer industrielle Synthesen von zentraler Bedeutung.",
         "expected_outcome": "QUARANTINE", "domain": "german_chemical_engineering"},

        # --- REJECT: Romance Latin Prose (5) ---
        {"sample_id": "v7_lang_dev_051", "category": "romance_latin_prose",
         "text": "La synthese des polymeres conducteurs necessite un controle rigoureux de la temperature dans le reacteur.",
         "expected_outcome": "REJECT", "domain": "french_polymer_chemistry"},
        {"sample_id": "v7_lang_dev_052", "category": "romance_latin_prose",
         "text": "El analisis mineralogico confirma la presencia de silicatos complejos en las rocas volcanicas de la cordillera.",
         "expected_outcome": "REJECT", "domain": "spanish_mineralogy"},
        {"sample_id": "v7_lang_dev_053", "category": "romance_latin_prose",
         "text": "I risultati dello studio clinico indicano un miglioramento significativo della pressione arteriosa nei pazienti trattati.",
         "expected_outcome": "REJECT", "domain": "italian_clinical_medicine"},
        {"sample_id": "v7_lang_dev_054", "category": "romance_latin_prose",
         "text": "Le ministre de la culture a inaugure la nouvelle exposition consacree aux chefs-d'œuvre du patrimoine architectural.",
         "expected_outcome": "REJECT", "domain": "french_cultural_news"},
        {"sample_id": "v7_lang_dev_055", "category": "romance_latin_prose",
         "text": "La produccion vinicola de la comarca se beneficia de un clima mediterraneo con escasas precipitaciones otoñales.",
         "expected_outcome": "REJECT", "domain": "spanish_viticulture"},

        # --- REJECT: Non-Latin Scripts (2) ---
        {"sample_id": "v7_lang_dev_056", "category": "non_latin_script",
         "text": "Аэродинамические испытания модели сверхзвукового самолета проводились в трансзвуковой аэродинамической трубе института.",
         "expected_outcome": "REJECT", "domain": "russian_aerospace"},
        {"sample_id": "v7_lang_dev_057", "category": "non_latin_script",
         "text": "量子计算利用量子力学的叠加态和纠缠特性来执行高度复杂的并行算法计算任务。",
         "expected_outcome": "REJECT", "domain": "chinese_quantum_computing"},

        # --- REJECT: Malformed Noise (3) ---
        {"sample_id": "v7_lang_dev_058", "category": "malformed_noise",
         "text": "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz",
         "expected_outcome": "REJECT", "domain": "repetition_noise"},
        {"sample_id": "v7_lang_dev_059", "category": "malformed_noise",
         "text": "%$#@! &*^~ {}[]| \\\\// ?>< :; `~ +_=-",
         "expected_outcome": "REJECT", "domain": "symbol_noise"},
        {"sample_id": "v7_lang_dev_060", "category": "malformed_noise",
         "text": "a b c d e f g h i j k l m n o p q r s t u v w x y z",
         "expected_outcome": "REJECT", "domain": "isolated_character_noise"},
    ]

    # Held-Out Sealed Test Split (60 samples)
    test_samples = [
        # --- ACCEPT: Ordinary English Prose (10) ---
        {"sample_id": "v7_lang_test_001", "category": "ordinary_english_prose",
         "text": "The coastal fishing fleet sheltered inside the protected harbor until the Atlantic gale warnings had expired.",
         "expected_outcome": "ACCEPT", "domain": "maritime_life"},
        {"sample_id": "v7_lang_test_002", "category": "ordinary_english_prose",
         "text": "Municipal engineers surveyed the river embankment to identify erosion damage caused by recent seasonal floods.",
         "expected_outcome": "ACCEPT", "domain": "hydraulic_engineering"},
        {"sample_id": "v7_lang_test_003", "category": "ordinary_english_prose",
         "text": "The local agricultural fair awarded blue ribbons for heirloom apple varieties and prize dairy heifers.",
         "expected_outcome": "ACCEPT", "domain": "agricultural_life"},
        {"sample_id": "v7_lang_test_004", "category": "ordinary_english_prose",
         "text": "Early telegraph operators transmitted urgent telegrams across vast distances using standardized Morse code sequences.",
         "expected_outcome": "ACCEPT", "domain": "telecommunications_history"},
        {"sample_id": "v7_lang_test_005", "category": "ordinary_english_prose",
         "text": "The botanical conservatory shelters tropical carnivorous plants inside climate-controlled glass greenhouses.",
         "expected_outcome": "ACCEPT", "domain": "horticulture"},
        {"sample_id": "v7_lang_test_006", "category": "ordinary_english_prose",
         "text": "Master carpenters assemble timber roof trusses using mortise and tenon joinery reinforced with oak pegs.",
         "expected_outcome": "ACCEPT", "domain": "timber_framing"},
        {"sample_id": "v7_lang_test_007", "category": "ordinary_english_prose",
         "text": "Marine biologists tagged juvenile humpback whales to monitor their annual migration route along the continental shelf.",
         "expected_outcome": "ACCEPT", "domain": "cetology"},
        {"sample_id": "v7_lang_test_008", "category": "ordinary_english_prose",
         "text": "The industrial weaving mill converted raw combed wool fibers into durable tweed fabrics for overseas export.",
         "expected_outcome": "ACCEPT", "domain": "textile_manufacturing"},
        {"sample_id": "v7_lang_test_009", "category": "ordinary_english_prose",
         "text": "Geologists discovered fossilized trilobite carapaces embedded within ancient marine shale layers in the limestone quarry.",
         "expected_outcome": "ACCEPT", "domain": "paleontology"},
        {"sample_id": "v7_lang_test_010", "category": "ordinary_english_prose",
         "text": "The volunteer mountain rescue team evacuated injured hikers during a sudden alpine blizzard on Mount Jefferson.",
         "expected_outcome": "ACCEPT", "domain": "wilderness_safety"},

        # --- ACCEPT: Expository Academic Prose (10) ---
        {"sample_id": "v7_lang_test_011", "category": "expository_academic_prose",
         "text": "The Navier-Stokes equations model the conservation of momentum in incompressible Newtonian fluid dynamic systems.",
         "expected_outcome": "ACCEPT", "domain": "fluid_dynamics"},
        {"sample_id": "v7_lang_test_012", "category": "expository_academic_prose",
         "text": "Epistemological coherentism maintains that belief justification depends upon mutually supportive inferential web networks.",
         "expected_outcome": "ACCEPT", "domain": "epistemology"},
        {"sample_id": "v7_lang_test_013", "category": "expository_academic_prose",
         "text": "Seismological tomography maps three-dimensional shear wave velocity anomalies within Earth's lower convective mantle.",
         "expected_outcome": "ACCEPT", "domain": "solid_earth_geophysics"},
        {"sample_id": "v7_lang_test_014", "category": "expository_academic_prose",
         "text": "Morphological derivation forms new lexical vocabulary items through affixation that frequently alters the grammatical word class.",
         "expected_outcome": "ACCEPT", "domain": "linguistic_morphology"},
        {"sample_id": "v7_lang_test_015", "category": "expository_academic_prose",
         "text": "Oxidative phosphorylation synthesizes adenosine triphosphate across the inner mitochondrial membrane via proton gradients.",
         "expected_outcome": "ACCEPT", "domain": "bioenergetics"},
        {"sample_id": "v7_lang_test_016", "category": "expository_academic_prose",
         "text": "The Meissner effect describes the complete expulsion of magnetic flux fields from the interior of a superconductor.",
         "expected_outcome": "ACCEPT", "domain": "superconductivity"},
        {"sample_id": "v7_lang_test_017", "category": "expository_academic_prose",
         "text": "Game theoretic equilibria characterize optimal strategic choices where no individual player gains by unilaterally deviating.",
         "expected_outcome": "ACCEPT", "domain": "game_theory"},
        {"sample_id": "v7_lang_test_018", "category": "expository_academic_prose",
         "text": "Synchrotron radiation sources produce intense collimated monochromatic X-ray beams for macromolecular crystallography.",
         "expected_outcome": "ACCEPT", "domain": "accelerator_physics"},
        {"sample_id": "v7_lang_test_019", "category": "expository_academic_prose",
         "text": "Markov decision processes provide a mathematical framework for modeling sequential decision making under uncertainty.",
         "expected_outcome": "ACCEPT", "domain": "reinforcement_learning"},
        {"sample_id": "v7_lang_test_020", "category": "expository_academic_prose",
         "text": "Cellular apoptosis initiates a controlled proteolytic caspase cascade resulting in systematic non-inflammatory cell clearance.",
         "expected_outcome": "ACCEPT", "domain": "cellular_biology"},

        # --- ACCEPT: Scientific Figure Captions (5) ---
        {"sample_id": "v7_lang_test_021", "category": "scientific_figure_captions",
         "text": "Figure 3: Transmission electron micrograph of multi-walled carbon nanotubes synthesized via chemical vapor deposition.",
         "expected_outcome": "ACCEPT", "domain": "carbon_nanomaterials"},
        {"sample_id": "v7_lang_test_022", "category": "scientific_figure_captions",
         "text": "Figure 4. Normalized optical transmittance spectra of antireflective silicon oxide coatings deposited on sapphire substrates.",
         "expected_outcome": "ACCEPT", "domain": "optics"},
        {"sample_id": "v7_lang_test_023", "category": "scientific_figure_captions",
         "text": "Table 2: Measured electrochemical oxidation potentials and charge transfer resistances for nickel hydroxide electrocatalysts.",
         "expected_outcome": "ACCEPT", "domain": "electrochemistry"},
        {"sample_id": "v7_lang_test_024", "category": "scientific_figure_captions",
         "text": "Chart 5: Temporal distribution of planetary nebulae discovered by wide-field astronomical sky surveys.",
         "expected_outcome": "ACCEPT", "domain": "astrophysics"},
        {"sample_id": "v7_lang_test_025", "category": "scientific_figure_captions",
         "text": "Diagram 4. Functional architecture diagram of the redundant triple-modular flight control computer subsystem.",
         "expected_outcome": "ACCEPT", "domain": "avionics_engineering"},

        # --- ACCEPT: English with Foreign Quotes / Names (5) ---
        {"sample_id": "v7_lang_test_026", "category": "foreign_names_and_quotes",
         "text": "Legal scholars argue that the principle of res judicata bars re-litigation of claims conclusively decided on their merits.",
         "expected_outcome": "ACCEPT", "domain": "civil_procedure"},
        {"sample_id": "v7_lang_test_027", "category": "foreign_names_and_quotes",
         "text": "Philosopher Baruch Spinoza formulated an influential monistic substance metaphysics in his posthumously published Ethics.",
         "expected_outcome": "ACCEPT", "domain": "rationalist_philosophy"},
        {"sample_id": "v7_lang_test_028", "category": "foreign_names_and_quotes",
         "text": "The literary biographer noted that the poet felt an intense sense of Sehnsucht while traveling through the Rhine valley.",
         "expected_outcome": "ACCEPT", "domain": "literary_biography"},
        {"sample_id": "v7_lang_test_029", "category": "foreign_names_and_quotes",
         "text": "Financial market regulators investigate whether corporate managers breached their fiduciary bona fide disclosure obligations.",
         "expected_outcome": "ACCEPT", "domain": "corporate_governance"},
        {"sample_id": "v7_lang_test_030", "category": "foreign_names_and_quotes",
         "text": "The historian examined how the Roman Senate invoked the senatus consultum ultimum during severe civil emergencies.",
         "expected_outcome": "ACCEPT", "domain": "ancient_history"},

        # --- QUARANTINE: Code, SQL & Structured Data (5) ---
        {"sample_id": "v7_lang_test_031", "category": "code_sql_structured_data",
         "text": "SELECT employee_id, department_name, base_salary FROM active_payroll WHERE base_salary >= 75000.00 ORDER BY employee_id;",
         "expected_outcome": "QUARANTINE", "domain": "sql_data"},
        {"sample_id": "v7_lang_test_032", "category": "code_sql_structured_data",
         "text": "INSERT INTO system_security_audit (log_id, user_identity, client_ip_address) VALUES (2048, 'security_admin', '10.0.0.1');",
         "expected_outcome": "QUARANTINE", "domain": "sql_data"},
        {"sample_id": "v7_lang_test_033", "category": "code_sql_structured_data",
         "text": "CREATE TABLE network_interfaces (interface_id INTEGER PRIMARY KEY, mac_address VARCHAR(17), mtu_bytes INTEGER);",
         "expected_outcome": "QUARANTINE", "domain": "sql_data"},
        {"sample_id": "v7_lang_test_034", "category": "code_sql_structured_data",
         "text": "UPDATE subscription_accounts SET renewal_status = 'CANCELLED' WHERE billing_cycle_end < CURRENT_DATE;",
         "expected_outcome": "QUARANTINE", "domain": "sql_data"},
        {"sample_id": "v7_lang_test_035", "category": "code_sql_structured_data",
         "text": "DELETE FROM cached_session_states WHERE session_expiry_timestamp < UNIX_TIMESTAMP();",
         "expected_outcome": "QUARANTINE", "domain": "sql_data"},

        # --- QUARANTINE: Imperative Signage & Warnings (5) ---
        {"sample_id": "v7_lang_test_036", "category": "imperative_signage_notices",
         "text": "DANGER: Flammable solvent storage bunker. No smoking, open flames, or ungrounded electrical tools permitted.",
         "expected_outcome": "QUARANTINE", "domain": "hazardous_materials"},
        {"sample_id": "v7_lang_test_037", "category": "imperative_signage_notices",
         "text": "CAUTION: Ionizing radiation source. Film radiation dosimeter badges required for entry beyond shielding doors.",
         "expected_outcome": "QUARANTINE", "domain": "nuclear_safety"},
        {"sample_id": "v7_lang_test_038", "category": "imperative_signage_notices",
         "text": "WARNING: Automatic robotic machinery starts without warning. Stay outside yellow safety floor perimeter.",
         "expected_outcome": "QUARANTINE", "domain": "robotics_safety"},
        {"sample_id": "v7_lang_test_039", "category": "imperative_signage_notices",
         "text": "NOTICE: Cleanroom garment gowning protocol strictly enforced before passing through air shower chamber.",
         "expected_outcome": "QUARANTINE", "domain": "semiconductor_facility"},
        {"sample_id": "v7_lang_test_040", "category": "imperative_signage_notices",
         "text": "ALERT: High pressure hydraulic testing in progress. Eye protection and protective shields mandatory.",
         "expected_outcome": "QUARANTINE", "domain": "testing_laboratory"},

        # --- QUARANTINE: Short Headings & Fragments (5) ---
        {"sample_id": "v7_lang_test_041", "category": "short_headings_and_fragments",
         "text": "Section 9.4 High-Performance Supercomputing Cluster Architecture",
         "expected_outcome": "QUARANTINE", "domain": "computer_systems"},
        {"sample_id": "v7_lang_test_042", "category": "short_headings_and_fragments",
         "text": "Chapter XII: Geotechnical Soil Mechanics and Foundation Design",
         "expected_outcome": "QUARANTINE", "domain": "geotechnical_engineering"},
        {"sample_id": "v7_lang_test_043", "category": "short_headings_and_fragments",
         "text": "Appendix G: Experimental Thermodynamic Dissociation Constants",
         "expected_outcome": "QUARANTINE", "domain": "physical_chemistry"},
        {"sample_id": "v7_lang_test_044", "category": "short_headings_and_fragments",
         "text": "Annual Environmental Sustainability Impact Assessment 2025",
         "expected_outcome": "QUARANTINE", "domain": "environmental_reporting"},
        {"sample_id": "v7_lang_test_045", "category": "short_headings_and_fragments",
         "text": "Module 5: Stochastic Probability and Random Processes",
         "expected_outcome": "QUARANTINE", "domain": "mathematics_curriculum"},

        # --- QUARANTINE: Germanic Latin Prose (5) ---
        {"sample_id": "v7_lang_test_046", "category": "germanic_latin_prose",
         "text": "Die experimentelle Bestimmung der spezifischen Waermekapazitaet erfolgte mit einem praezisen adiabatischen Kalorimeter.",
         "expected_outcome": "QUARANTINE", "domain": "german_calorimetry"},
        {"sample_id": "v7_lang_test_047", "category": "germanic_latin_prose",
         "text": "De moderne windturbines in de Noordzee leveren duurzame elektrische stroom aan duizenden huishoudens in West-Europa.",
         "expected_outcome": "QUARANTINE", "domain": "dutch_renewable_energy"},
        {"sample_id": "v7_lang_test_048", "category": "germanic_latin_prose",
         "text": "Abbildung 9: Gemessene Viskositaet der Polymerloesung in Abhaengigkeit von der Scherrate bei konstanter Temperatur.",
         "expected_outcome": "QUARANTINE", "domain": "german_rheology_caption"},
        {"sample_id": "v7_lang_test_049", "category": "germanic_latin_prose",
         "text": "Wetenschappelijk onderzoek naar mariene ecosystemen toont de kwetsbaarheid van koraalriffen voor oceanische verzuring aan.",
         "expected_outcome": "QUARANTINE", "domain": "dutch_marine_ecology"},
        {"sample_id": "v7_lang_test_050", "category": "germanic_latin_prose",
         "text": "Das thermodynamische Gleichgewicht eines Mehrstoffsystems haengt stark von Druck und Konzentration der Komponenten ab.",
         "expected_outcome": "QUARANTINE", "domain": "german_phase_equilibrium"},

        # --- REJECT: Romance Latin Prose (5) ---
        {"sample_id": "v7_lang_test_051", "category": "romance_latin_prose",
         "text": "La spectroscopie de resonance magnetique nucleaire permet d'elucider la structure tridimensionnelle des biomolecules.",
         "expected_outcome": "REJECT", "domain": "french_nmr_spectroscopy"},
        {"sample_id": "v7_lang_test_052", "category": "romance_latin_prose",
         "text": "El tratamiento termico del acero inoxidable mejora notablemente su resistencia a la corrosion intergranular bajo tension.",
         "expected_outcome": "REJECT", "domain": "spanish_materials_engineering"},
        {"sample_id": "v7_lang_test_053", "category": "romance_latin_prose",
         "text": "La diagnosi precoce delle patologie cardiovascolari riduce significativamente il rischio di complicazioni a lungo termine.",
         "expected_outcome": "REJECT", "domain": "italian_cardiology"},
        {"sample_id": "v7_lang_test_054", "category": "romance_latin_prose",
         "text": "Le conseil municipal a approuve le plan d'urbanisme visant a developper les transports en commun et les pistes cyclables.",
         "expected_outcome": "REJECT", "domain": "french_urbanism"},
        {"sample_id": "v7_lang_test_055", "category": "romance_latin_prose",
         "text": "Las investigaciones oceanograficas demuestran la importancia de las corrientes marinas en la regulacion termica global.",
         "expected_outcome": "REJECT", "domain": "spanish_oceanography"},

        # --- REJECT: Non-Latin Scripts (2) ---
        {"sample_id": "v7_lang_test_056", "category": "non_latin_script",
         "text": "Криогенные насосы обеспечивают сверхвысокий вакуум в камерах термоядерных исследовательских установок токамак.",
         "expected_outcome": "REJECT", "domain": "russian_plasma_physics"},
        {"sample_id": "v7_lang_test_057", "category": "non_latin_script",
         "text": "人工智能神经网络模型需要大规模高质量训练数据来实现精确的自然语言理解能力。",
         "expected_outcome": "REJECT", "domain": "chinese_machine_learning"},

        # --- REJECT: Malformed Noise (3) ---
        {"sample_id": "v7_lang_test_058", "category": "malformed_noise",
         "text": "wwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwww",
         "expected_outcome": "REJECT", "domain": "repetition_noise"},
        {"sample_id": "v7_lang_test_059", "category": "malformed_noise",
         "text": "[{()}] ~!@#$% ^&*()_+ |:<>? `~ -=\\;',./",
         "expected_outcome": "REJECT", "domain": "symbol_noise"},
        {"sample_id": "v7_lang_test_060", "category": "malformed_noise",
         "text": "q w e r t y u i o p a s d f g h j k l z x c v b n m",
         "expected_outcome": "REJECT", "domain": "isolated_character_noise"},
    ]

    return {
        "metadata": {
            "dataset_name": "eval_language_dataset_v7",
            "version": "7.0",
            "phase": "4.9",
            "target": "Blind Final Certification Preparation",
            "annotation_rules": {
                "ACCEPT": "Fluent, coherent English prose (general or academic), English scientific captions, and English prose quoting foreign phrases.",
                "QUARANTINE": "Coherent non-prose structured data (SQL, code), imperative safety signage, short fragments (<8 words), and Germanic Latin text.",
                "REJECT": "Romance Latin prose without English stopwords, non-Latin scripts, and corrupt/malformed alphabetic noise.",
            },
            "total_dev_samples": len(dev_samples),
            "total_test_samples": len(test_samples),
        },
        "development_split": dev_samples,
        "test_split": test_samples,
    }


def build_v7_near_dedup_dataset() -> Dict[str, Any]:
    # Development Split (20 pairs)
    dev_pairs = [
        # True Duplicates (8)
        {"pair_id": "v7_dedup_dev_001", "category": "exact_duplicate", "is_true_duplicate": True,
         "text_a": "The naval observatory astronomers tracked the trajectory of the newly discovered parabolic comet across the northern celestial sphere.",
         "text_b": "The naval observatory astronomers tracked the trajectory of the newly discovered parabolic comet across the northern celestial sphere."},
        {"pair_id": "v7_dedup_dev_002", "category": "reformatted_duplicate", "is_true_duplicate": True,
         "text_a": "High-pressure hydraulic pumps deliver fluid power to subterranean boring machines excavating the highway transit tunnel.",
         "text_b": "High-pressure hydraulic pumps deliver fluid power\nto subterranean boring machines excavating the highway transit tunnel."},
        {"pair_id": "v7_dedup_dev_003", "category": "paraphrase_duplicate", "is_true_duplicate": True,
         "text_a": "The attending surgeon administered 150 mg of intravenous anesthetic to the patient prior to beginning the laparoscopic procedure.",
         "text_b": "Prior to beginning the laparoscopic procedure, 150 mg of intravenous anesthetic was administered to the patient by the attending surgeon."},
        {"pair_id": "v7_dedup_dev_004", "category": "reordered_duplicate", "is_true_duplicate": True,
         "text_a": "Wind turbines generate clean electrical power. Transformer substations step up the alternating voltage for long-distance grid transmission.",
         "text_b": "Transformer substations step up the alternating voltage for long-distance grid transmission. Wind turbines generate clean electrical power."},
        {"pair_id": "v7_dedup_dev_005", "category": "unit_conversion_duplicate", "is_true_duplicate": True,
         "text_a": "The pipeline inspection robot traveled exactly 3000 meters through the subterranean natural gas distribution main.",
         "text_b": "The pipeline inspection robot traveled exactly 3 kilometers through the subterranean natural gas distribution main."},
        {"pair_id": "v7_dedup_dev_006", "category": "unit_conversion_duplicate", "is_true_duplicate": True,
         "text_a": "The research team weighed exactly 2500 milligrams of recrystallized acetylsalicylic acid on the microbalance.",
         "text_b": "The research team weighed exactly 2.5 grams of recrystallized acetylsalicylic acid on the microbalance."},
        {"pair_id": "v7_dedup_dev_007", "category": "unit_conversion_duplicate", "is_true_duplicate": True,
         "text_a": "The telemetry logging service reserved 1048576 bytes of shared memory for holding real-time flight sensor readings.",
         "text_b": "The telemetry logging service reserved 1 mib of shared memory for holding real-time flight sensor readings."},
        {"pair_id": "v7_dedup_dev_008", "category": "unit_conversion_duplicate", "is_true_duplicate": True,
         "text_a": "The industrial autoclave was maintained at maximum operating temperature for exactly 120 seconds during sterilization.",
         "text_b": "The industrial autoclave was maintained at maximum operating temperature for exactly 2 minutes during sterilization."},

        # Distinct / Safety Negatives (12)
        {"pair_id": "v7_dedup_dev_009", "category": "distant_negative", "is_true_duplicate": False,
         "text_a": "The Renaissance cathedral in Florence features an octagonal masonry dome designed by architect Filippo Brunelleschi.",
         "text_b": "Superconducting quantum interference devices measure extremely weak magnetic fields generated by neural current activity."},
        {"pair_id": "v7_dedup_dev_010", "category": "hard_negative_semantic_divergence", "is_true_duplicate": False,
         "text_a": "The state environmental commission resolved to expand commercial fishing quotas for Atlantic cod along the outer banks.",
         "text_b": "The state environmental commission resolved to reduce commercial fishing quotas for Atlantic cod along the outer banks."},
        {"pair_id": "v7_dedup_dev_011", "category": "safety_dosage_inversion", "is_true_duplicate": False,
         "text_a": "The intensive care nurse infused 5.0 milligrams of dopamine hydrochloride per kilogram hourly to maintain cardiac output.",
         "text_b": "The intensive care nurse infused 50.0 milligrams of dopamine hydrochloride per kilogram hourly to maintain cardiac output."},
        {"pair_id": "v7_dedup_dev_012", "category": "safety_unit_mismatch", "is_true_duplicate": False,
         "text_a": "The chemical reactor vessel was certified for a safe operating load of 15 bar internal gauge pressure.",
         "text_b": "The chemical reactor vessel was certified for a safe operating load of 15 meters internal gauge pressure."},
        {"pair_id": "v7_dedup_dev_013", "category": "safety_unit_mismatch", "is_true_duplicate": False,
         "text_a": "The subsea telecommunications umbilical cable delivers 25 amperes continuous direct current power to the repeater stations.",
         "text_b": "The subsea telecommunications umbilical cable delivers 25 volts continuous direct current power to the repeater stations."},
        {"pair_id": "v7_dedup_dev_014", "category": "safety_date_mismatch", "is_true_duplicate": False,
         "text_a": "The landmark international peace convention was formally ratified in Geneva on June 18, 1948 by twenty member states.",
         "text_b": "The landmark international peace convention was formally ratified in Geneva on June 18, 1952 by twenty member states."},
        {"pair_id": "v7_dedup_dev_015", "category": "safety_date_mismatch", "is_true_duplicate": False,
         "text_a": "The polar expedition established its permanent base camp on King George Island on March 12, 1975 under severe blizzard conditions.",
         "text_b": "The polar expedition established its permanent base camp on King George Island on October 12, 1975 under severe blizzard conditions."},
        {"pair_id": "v7_dedup_dev_016", "category": "safety_polarity_inversion", "is_true_duplicate": False,
         "text_a": "Preclinical in vitro assays demonstrated that the novel nanoparticle formulation was safe and non-toxic to human renal cells.",
         "text_b": "Preclinical in vitro assays demonstrated that the novel nanoparticle formulation was toxic and fatal to human renal cells."},
        {"pair_id": "v7_dedup_dev_017", "category": "safety_polarity_inversion", "is_true_duplicate": False,
         "text_a": "The municipal zoning board voted to permit construction of commercial warehousing facilities in the northern industrial district.",
         "text_b": "The municipal zoning board voted to prohibit construction of commercial warehousing facilities in the northern industrial district."},
        {"pair_id": "v7_dedup_dev_018", "category": "safety_polarity_inversion", "is_true_duplicate": False,
         "text_a": "The catalytic refinery cracking yield was measured as greater than 85% under standardized operating parameters.",
         "text_b": "The catalytic refinery cracking yield was measured as less than 85% under standardized operating parameters."},
        {"pair_id": "v7_dedup_dev_019", "category": "safety_negation_inversion", "is_true_duplicate": False,
         "text_a": "The automated avionics navigation subsystem was observed to drift significantly during transoceanic GPS blackout periods.",
         "text_b": "The automated avionics navigation subsystem was not observed to drift significantly during transoceanic GPS blackout periods."},
        {"pair_id": "v7_dedup_dev_020", "category": "safety_identifier_conflict", "is_true_duplicate": False,
         "text_a": "Diagnostic telemetry records from Reactor-A101 showed standard thermal distribution profiles across all cooling assemblies.",
         "text_b": "Diagnostic telemetry records from Reactor-B101 showed standard thermal distribution profiles across all cooling assemblies."},
    ]

    # Held-Out Sealed Test Split (20 pairs)
    test_pairs = [
        # True Duplicates (8)
        {"pair_id": "v7_dedup_test_001", "category": "exact_duplicate", "is_true_duplicate": True,
         "text_a": "Glaciological core drilling at the Antarctic ice plateau recovered continuous paleoclimatic ice samples spanning eight glacial cycles.",
         "text_b": "Glaciological core drilling at the Antarctic ice plateau recovered continuous paleoclimatic ice samples spanning eight glacial cycles."},
        {"pair_id": "v7_dedup_test_002", "category": "reformatted_duplicate", "is_true_duplicate": True,
         "text_a": "High-voltage transmission conductors step down electrical energy at suburban distribution substations for residential consumer consumption.",
         "text_b": "High-voltage transmission conductors step down electrical energy\nat suburban distribution substations  for residential consumer consumption."},
        {"pair_id": "v7_dedup_test_003", "category": "paraphrase_duplicate", "is_true_duplicate": True,
         "text_a": "The chief anesthesiologist injected 75 mg of lidocaine hydrochloride into the subcutaneous tissue before starting the minor operation.",
         "text_b": "Before starting the minor operation, 75 mg of lidocaine hydrochloride was injected into the subcutaneous tissue by the chief anesthesiologist."},
        {"pair_id": "v7_dedup_test_004", "category": "reordered_duplicate", "is_true_duplicate": True,
         "text_a": "Solar photovoltaic panels charge the stationary lithium-ion battery bank. Inverter modules supply regulated 230 volt alternating current.",
         "text_b": "Inverter modules supply regulated 230 volt alternating current. Solar photovoltaic panels charge the stationary lithium-ion battery bank."},
        {"pair_id": "v7_dedup_test_005", "category": "unit_conversion_duplicate", "is_true_duplicate": True,
         "text_a": "The autonomous surveying submersible dived to an ocean depth of exactly 2000 meters along the mid-Atlantic volcanic ridge.",
         "text_b": "The autonomous surveying submersible dived to an ocean depth of exactly 2 kilometers along the mid-Atlantic volcanic ridge."},
        {"pair_id": "v7_dedup_test_006", "category": "unit_conversion_duplicate", "is_true_duplicate": True,
         "text_a": "The analytical chemist dissolved exactly 1000 milligrams of potassium iodide in 100 ml of degassed deionized water.",
         "text_b": "The analytical chemist dissolved exactly 1 gram of potassium iodide in 100 ml of degassed deionized water."},
        {"pair_id": "v7_dedup_test_007", "category": "unit_conversion_duplicate", "is_true_duplicate": True,
         "text_a": "The operating system paging cache allocated exactly 2097152 bytes of virtual address space for process thread stacks.",
         "text_b": "The operating system paging cache allocated exactly 2 mib of virtual address space for process thread stacks."},
        {"pair_id": "v7_dedup_test_008", "category": "unit_conversion_duplicate", "is_true_duplicate": True,
         "text_a": "The automated blood centrifuge was operated at high angular velocity for exactly 180 seconds during serum separation.",
         "text_b": "The automated blood centrifuge was operated at high angular velocity for exactly 3 minutes during serum separation."},

        # Distinct / Safety Negatives (12)
        {"pair_id": "v7_dedup_test_009", "category": "distant_negative", "is_true_duplicate": False,
         "text_a": "Archaeological surveys in the Nile delta revealed mudbrick granary foundations dating to the Middle Kingdom period of ancient Egypt.",
         "text_b": "Nonlinear optical parametric oscillators generate wavelength-tunable coherent infrared laser pulses for spectroscopic diagnostics."},
        {"pair_id": "v7_dedup_test_010", "category": "hard_negative_semantic_divergence", "is_true_duplicate": False,
         "text_a": "The academic senate voted to approve the mandatory ethics curriculum requirement for all incoming doctoral research students.",
         "text_b": "The academic senate voted to reject the mandatory ethics curriculum requirement for all incoming doctoral research students."},
        {"pair_id": "v7_dedup_test_011", "category": "safety_dosage_inversion", "is_true_duplicate": False,
         "text_a": "The neonatal intensive care physician prescribed 2.5 milligrams of aminophylline twice daily to prevent infantile apnea episodes.",
         "text_b": "The neonatal intensive care physician prescribed 25.0 milligrams of aminophylline twice daily to prevent infantile apnea episodes."},
        {"pair_id": "v7_dedup_test_012", "category": "safety_unit_mismatch", "is_true_duplicate": False,
         "text_a": "The cryogenic liquid nitrogen storage vessel was rated for a maximum pressure threshold of 10 bar under standard conditions.",
         "text_b": "The cryogenic liquid nitrogen storage vessel was rated for a maximum pressure threshold of 10 meters under standard conditions."},
        {"pair_id": "v7_dedup_test_013", "category": "safety_unit_mismatch", "is_true_duplicate": False,
         "text_a": "The high-current laboratory rectifier delivers 50 amperes steady direct current output to the electrolytic refining cells.",
         "text_b": "The high-current laboratory rectifier delivers 50 volts steady direct current output to the electrolytic refining cells."},
        {"pair_id": "v7_dedup_test_014", "category": "safety_date_mismatch", "is_true_duplicate": False,
         "text_a": "The multilateral international maritime boundary treaty was formally ratified in London on May 24, 1965 by fifteen signatory states.",
         "text_b": "The multilateral international maritime boundary treaty was formally ratified in London on May 24, 1971 by fifteen signatory states."},
        {"pair_id": "v7_dedup_test_015", "category": "safety_date_mismatch", "is_true_duplicate": False,
         "text_a": "The high-altitude astronomical observatory completed its primary mirror installation on February 20, 1998 on Mauna Kea.",
         "text_b": "The high-altitude astronomical observatory completed its primary mirror installation on September 20, 1998 on Mauna Kea."},
        {"pair_id": "v7_dedup_test_016", "category": "safety_polarity_inversion", "is_true_duplicate": False,
         "text_a": "Comprehensive toxicology screening proved that the agricultural fungicide was nontoxic and safe for non-target pollinating honeybees.",
         "text_b": "Comprehensive toxicology screening proved that the agricultural fungicide was toxic and fatal for non-target pollinating honeybees."},
        {"pair_id": "v7_dedup_test_017", "category": "safety_polarity_inversion", "is_true_duplicate": False,
         "text_a": "The environmental protection agency confirmed that discharge of treated cooling water is permitted into the tidal estuary.",
         "text_b": "The environmental protection agency confirmed that discharge of treated cooling water is prohibited into the tidal estuary."},
        {"pair_id": "v7_dedup_test_018", "category": "safety_polarity_inversion", "is_true_duplicate": False,
         "text_a": "The catalytic ammonia synthesis yield was recorded as greater than 60% under standardized operating parameters.",
         "text_b": "The catalytic ammonia synthesis yield was recorded as less than 60% under standardized operating parameters."},
        {"pair_id": "v7_dedup_test_019", "category": "safety_negation_inversion", "is_true_duplicate": False,
         "text_a": "The backup cooling water circulation pump can easily maintain reactor vessel temperature during emergency shutdown.",
         "text_b": "The backup cooling water circulation pump can never maintain reactor vessel temperature during emergency shutdown."},
        {"pair_id": "v7_dedup_test_020", "category": "safety_identifier_conflict", "is_true_duplicate": False,
         "text_a": "Thermal performance sensor telemetry from Turbine-A405 showed completely stable operating temperatures under maximum load.",
         "text_b": "Thermal performance sensor telemetry from Turbine-B405 showed completely stable operating temperatures under maximum load."},
    ]

    return {
        "metadata": {
            "dataset_name": "eval_near_dedup_dataset_v7",
            "version": "7.0",
            "phase": "4.9",
            "target": "Blind Final Certification Preparation",
            "annotation_rules": {
                "True": "Exact duplicates, formatting/whitespace variants, reordered clauses, active/passive voice paraphrases, and equivalent SI/binary unit conversions.",
                "False": "Disjoint texts, numerical discrepancies (including 10x dosage inversions), physical unit mismatches, date/month mismatches, identifier conflicts, polarity inversions, and negation flips.",
            },
            "total_dev_pairs": len(dev_pairs),
            "total_test_pairs": len(test_pairs),
        },
        "development_split": dev_pairs,
        "test_split": test_pairs,
    }


def main() -> None:
    corpus_dir = _ROOT / "data" / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)

    # 1. Build and write Language Dataset v7.0
    lang_v7 = build_v7_language_dataset()
    lang_path = corpus_dir / "eval_language_dataset_v7.json"
    with open(lang_path, "w", encoding="utf-8") as f:
        json.dump(lang_v7, f, indent=2, ensure_ascii=False)
    lang_sha = hashlib.sha256(lang_path.read_bytes()).hexdigest()

    # 2. Build and write Near-Dedup Dataset v7.0
    dedup_v7 = build_v7_near_dedup_dataset()
    dedup_path = corpus_dir / "eval_near_dedup_dataset_v7.json"
    with open(dedup_path, "w", encoding="utf-8") as f:
        json.dump(dedup_v7, f, indent=2, ensure_ascii=False)
    dedup_sha = hashlib.sha256(dedup_path.read_bytes()).hexdigest()

    print("Phase 4.9 Sealed Benchmark Generation Complete:")
    print(f"  Language Dataset v7.0: {lang_path} (SHA-256: {lang_sha})")
    print(f"    Dev Samples:  {len(lang_v7['development_split'])}")
    print(f"    Test Samples: {len(lang_v7['test_split'])}")
    print(f"  Near-Dedup Dataset v7.0: {dedup_path} (SHA-256: {dedup_sha})")
    print(f"    Dev Pairs:  {len(dedup_v7['development_split'])}")
    print(f"    Test Pairs: {len(dedup_v7['test_split'])}")


if __name__ == "__main__":
    main()
