"""Static localisation for the catalog.

English is the pivot language: every other locale falls back to `en` before the
Bulgarian source, so no storefront ever shows Cyrillic to a non-Bulgarian visitor.
Locales that need their own wording (category names, menu labels) are listed here;
long product copy is provided in English and can be refined per locale from the
admin panel (manually or with the AI translate button).
"""

# ---------------------------------------------------------------- collections
COLLECTION_TR = {
    "all-peptides": {
        "en": {"title": "All peptides", "menu_title": "All peptides", "description": "Full catalogue of lyophilised research peptides with laboratory-verified purity above 99%, tested by Janoshik Labs."},
        "fr": {"title": "Tous les peptides", "menu_title": "Tous les peptides"},
        "de": {"title": "Alle Peptide", "menu_title": "Alle Peptide"},
        "cz": {"title": "Všechny peptidy", "menu_title": "Všechny peptidy"},
        "hu": {"title": "Összes peptid", "menu_title": "Összes peptid"},
        "pl": {"title": "Wszystkie peptydy", "menu_title": "Wszystkie peptydy"},
        "sk": {"title": "Všetky peptidy", "menu_title": "Všetky peptidy"},
        "si": {"title": "Vsi peptidi", "menu_title": "Vsi peptidi"},
        "gr": {"title": "Όλα τα πεπτίδια", "menu_title": "Όλα τα πεπτίδια"},
        "ro": {"title": "Toate peptidele", "menu_title": "Toate peptidele"},
    },
    "metabolic-studies": {
        "en": {"title": "Weight management", "menu_title": "Peptides for weight management", "description": "Peptides studied in relation to metabolism, appetite regulation and body composition."},
        "fr": {"title": "Gestion du poids", "menu_title": "Peptides pour la gestion du poids"},
        "de": {"title": "Gewichtsmanagement", "menu_title": "Peptide für Gewichtsmanagement"},
        "cz": {"title": "Hubnutí", "menu_title": "Peptidy na hubnutí"},
        "hu": {"title": "Fogyás", "menu_title": "Peptidek fogyáshoz"},
        "pl": {"title": "Redukcja masy", "menu_title": "Peptydy na redukcję masy"},
        "sk": {"title": "Chudnutie", "menu_title": "Peptidy na chudnutie"},
        "si": {"title": "Hujšanje", "menu_title": "Peptidi za hujšanje"},
        "gr": {"title": "Απώλεια βάρους", "menu_title": "Πεπτίδια για απώλεια βάρους"},
        "ro": {"title": "Slăbire", "menu_title": "Peptide pentru slăbire"},
    },
    "studies-on-healing": {
        "en": {"title": "Recovery", "menu_title": "Peptides for recovery", "description": "Peptides studied in relation to tissue repair and regeneration."},
        "fr": {"title": "Récupération", "menu_title": "Peptides pour la récupération"},
        "de": {"title": "Regeneration", "menu_title": "Peptide für Regeneration"},
        "cz": {"title": "Regenerace", "menu_title": "Peptidy na regeneraci"},
        "hu": {"title": "Regeneráció", "menu_title": "Peptidek regenerációhoz"},
        "pl": {"title": "Regeneracja", "menu_title": "Peptydy na regenerację"},
        "sk": {"title": "Regenerácia", "menu_title": "Peptidy na regeneráciu"},
        "si": {"title": "Regeneracija", "menu_title": "Peptidi za regeneracijo"},
        "gr": {"title": "Αποκατάσταση", "menu_title": "Πεπτίδια για αποκατάσταση"},
        "ro": {"title": "Recuperare", "menu_title": "Peptide pentru recuperare"},
    },
    "secretagogues": {
        "en": {"title": "Muscle", "menu_title": "Peptides for muscle", "description": "Secretagogues and peptides studied in relation to growth hormone and muscle tissue."},
        "fr": {"title": "Muscle", "menu_title": "Peptides pour le muscle"},
        "de": {"title": "Muskeln", "menu_title": "Peptide für Muskeln"},
        "cz": {"title": "Svaly", "menu_title": "Peptidy na svaly"},
        "hu": {"title": "Izom", "menu_title": "Peptidek izomhoz"},
        "pl": {"title": "Mięśnie", "menu_title": "Peptydy na mięśnie"},
        "sk": {"title": "Svaly", "menu_title": "Peptidy na svaly"},
        "si": {"title": "Mišice", "menu_title": "Peptidi za mišice"},
        "gr": {"title": "Μυϊκή μάζα", "menu_title": "Πεπτίδια για μυϊκή μάζα"},
        "ro": {"title": "Masă musculară", "menu_title": "Peptide pentru masă musculară"},
    },
    "longevity-and-more": {
        "en": {"title": "Skin & longevity", "menu_title": "Peptides for skin", "description": "Peptides studied in relation to skin, collagen synthesis and ageing processes."},
        "fr": {"title": "Peau & longévité", "menu_title": "Peptides pour la peau"},
        "de": {"title": "Haut & Longevity", "menu_title": "Peptide für die Haut"},
        "cz": {"title": "Kůže", "menu_title": "Peptidy na kůži"},
        "hu": {"title": "Bőr", "menu_title": "Peptidek a bőrhöz"},
        "pl": {"title": "Skóra", "menu_title": "Peptydy na skórę"},
        "sk": {"title": "Koža", "menu_title": "Peptidy na kožu"},
        "si": {"title": "Koža", "menu_title": "Peptidi za kožo"},
        "gr": {"title": "Δέρμα", "menu_title": "Πεπτίδια για το δέρμα"},
        "ro": {"title": "Piele", "menu_title": "Peptide pentru piele"},
    },
    "melanin-i-libido": {
        "en": {"title": "Melanin & libido", "menu_title": "Peptides for libido & melanin", "description": "Melanocortin peptides studied in relation to pigmentation and libido."},
        "fr": {"title": "Mélanine & libido", "menu_title": "Peptides pour libido & mélanine"},
        "de": {"title": "Melanin & Libido", "menu_title": "Peptide für Libido & Melanin"},
        "cz": {"title": "Melanin a libido", "menu_title": "Peptidy na libido a melanin"},
        "hu": {"title": "Melanin és libidó", "menu_title": "Peptidek libidóhoz és melaninhoz"},
        "pl": {"title": "Melanina i libido", "menu_title": "Peptydy na libido i melaninę"},
        "sk": {"title": "Melanín a libido", "menu_title": "Peptidy na libido a melanín"},
        "si": {"title": "Melanin in libido", "menu_title": "Peptidi za libido in melanin"},
        "gr": {"title": "Μελανίνη & λίμπιντο", "menu_title": "Πεπτίδια για λίμπιντο & μελανίνη"},
        "ro": {"title": "Melanină și libido", "menu_title": "Peptide pentru libido și melanină"},
    },
    "immunology": {
        "en": {"title": "Immunity", "menu_title": "Peptides for immunity", "description": "Peptides studied in relation to the immune response."},
        "fr": {"title": "Immunité", "menu_title": "Peptides pour l'immunité"},
        "de": {"title": "Immunsystem", "menu_title": "Peptide für das Immunsystem"},
        "cz": {"title": "Imunita", "menu_title": "Peptidy na imunitu"},
        "hu": {"title": "Immunitás", "menu_title": "Peptidek az immunitáshoz"},
        "pl": {"title": "Odporność", "menu_title": "Peptydy na odporność"},
        "sk": {"title": "Imunita", "menu_title": "Peptidy na imunitu"},
        "si": {"title": "Imunost", "menu_title": "Peptidi za imunost"},
        "gr": {"title": "Ανοσία", "menu_title": "Πεπτίδια για την ανοσία"},
        "ro": {"title": "Imunitate", "menu_title": "Peptide pentru imunitate"},
    },
}

_EN_DISCLAIMER = (
    "<p><em>This information is compiled from published scientific material, largely based on cellular and "
    "animal models. It is provided for educational purposes only and does not constitute medical advice, "
    "a diagnosis or a dosing recommendation.</em></p>"
)

# ---------------------------------------------------------------- products (English pivot)
PRODUCT_TR = {
    "bpc-157-5": {"en": {
        "title": "BPC-157 5mg/10mg", "subtitle": "Body Protection Compound",
        "description": "<h2>What is BPC-157?</h2><p>BPC-157 is a pentadecapeptide of 15 amino acids — a synthetic research fragment related to the body protection compound (BPC) originally described in human gastric juice.</p><p>It has been examined mainly in preclinical and laboratory settings exploring tissue repair processes involving muscle, tendon, ligament and other connective tissue structures.</p><h3>Reported observations</h3><ul><li><strong>Injury healing</strong> — observations in experimental tendon, muscle and bone models.</li><li><strong>Inflammatory processes</strong> — changes in the inflammatory response and local tissue reactions.</li><li><strong>Gastrointestinal protection</strong> — changes in mucosal barrier integrity in experimental models.</li><li><strong>Circulation</strong> — angiogenesis and microcirculation in damaged tissue.</li></ul>" + _EN_DISCLAIMER}},
    "fgtb-500": {"en": {
        "title": "TB-500 (frag. 17-23) 10mg", "subtitle": "Thymosin beta-4 fragment",
        "description": "<h2>What is TB-500?</h2><p>TB-500 is a synthetic fragment (17-23) of thymosin beta-4, a naturally occurring peptide studied in relation to cell migration, angiogenesis and tissue repair.</p><p>Published data comes predominantly from laboratory and animal models and does not establish clinical efficacy in humans.</p>" + _EN_DISCLAIMER}},
    "2-tesamorelin": {"en": {
        "title": "Tesamorelin 10mg", "subtitle": "GHRH analogue",
        "description": "<h2>What is Tesamorelin?</h2><p>Tesamorelin is a stabilised analogue of growth hormone-releasing hormone (GHRH) studied in relation to endogenous GH secretion and visceral adipose tissue metabolism.</p>" + _EN_DISCLAIMER}},
    "mots-c": {"en": {
        "title": "MOTS-c 10mg", "subtitle": "Mitochondrial peptide",
        "description": "<h2>What is MOTS-c?</h2><p>MOTS-c is a mitochondrial-derived peptide of 16 amino acids studied in relation to metabolic regulation, insulin sensitivity and AMPK signalling.</p>" + _EN_DISCLAIMER}},
    "1-ghk-cu": {"en": {
        "title": "GHK-Cu (copper peptide) 100mg", "subtitle": "Copper tripeptide",
        "description": "<h2>What is GHK-Cu?</h2><p>GHK-Cu is a copper tripeptide (glycyl-L-histidyl-L-lysine) studied in relation to gene expression, collagen synthesis and protection against oxidative stress in skin models.</p>" + _EN_DISCLAIMER}},
    "pp-thymosin-beta-4": {"en": {
        "title": "Thymosin beta-4 5mg", "subtitle": "Regenerative peptide",
        "description": "<h2>What is Thymosin beta-4?</h2><p>Thymosin beta-4 is a 43 amino acid peptide studied in relation to actin dynamics, cell migration and tissue repair.</p>" + _EN_DISCLAIMER}},
    "3-ipamorelin-1": {"en": {
        "title": "Ipamorelin 10mg", "subtitle": "Selective GH secretagogue",
        "description": "<h2>What is Ipamorelin?</h2><p>Ipamorelin is a selective pentapeptide ghrelin receptor agonist studied in relation to growth hormone release with minimal impact on cortisol and prolactin in experimental models.</p>" + _EN_DISCLAIMER}},
    "acjc-1295": {"en": {
        "title": "CJC-1295 (no DAC) 5mg", "subtitle": "GHRH analogue",
        "description": "<h2>What is CJC-1295?</h2><p>CJC-1295 without DAC (modified GRF 1-29) is a GHRH analogue studied in relation to pulsatile growth hormone secretion and the GH/IGF-1 axis.</p>" + _EN_DISCLAIMER}},
    "axchgh-frag-176-191": {"en": {
        "title": "hGH frag (176-191) 5mg", "subtitle": "Growth hormone fragment",
        "description": "<h2>What is hGH frag 176-191?</h2><p>The 176-191 fragment of human growth hormone has been studied in relation to lipolysis in adipose tissue in experimental models, without the growth-related effects described for the full hormone.</p>" + _EN_DISCLAIMER}},
    "pt-141": {"en": {
        "title": "PT-141 10mg", "subtitle": "Bremelanotide",
        "description": "<h2>What is PT-141?</h2><p>PT-141 (bremelanotide) is a melanocortin receptor agonist studied in relation to central mechanisms of sexual arousal.</p>" + _EN_DISCLAIMER}},
    "dsip-5mg": {"en": {
        "title": "DSIP (Delta Sleep Inducing Peptide) 5mg", "subtitle": "Delta sleep inducing peptide",
        "description": "<h2>What is DSIP?</h2><p>DSIP is a nonapeptide studied in relation to delta sleep phases, neuroendocrine regulation and the stress response.</p>" + _EN_DISCLAIMER}},
    "melanotan-ii": {"en": {
        "title": "Melanotan I 10mg", "subtitle": "Melanocortin analogue",
        "description": "<h2>What is Melanotan I?</h2><p>Melanotan I (afamelanotide) is a synthetic α-MSH analogue studied in relation to melanogenesis and photoprotection in experimental models.</p>" + _EN_DISCLAIMER}},
    "thymosin-alpha-1": {"en": {
        "title": "Thymosin alpha-1 5mg", "subtitle": "Immunomodulator",
        "description": "<h2>What is Thymosin alpha-1?</h2><p>Thymosin alpha-1 is a 28 amino acid peptide studied in relation to modulation of the T-cell response and innate immunity.</p>" + _EN_DISCLAIMER}},
    "aaigf-lr3": {"en": {
        "title": "IGF-1 LR3 (Long arginine 3) 1mg", "subtitle": "Insulin-like growth factor",
        "description": "<h2>What is IGF-1 LR3?</h2><p>IGF-1 LR3 is a long-acting analogue of insulin-like growth factor 1 studied in relation to cell proliferation and anabolic signalling pathways.</p>" + _EN_DISCLAIMER}},
    "vdgfghrp-6": {"en": {
        "title": "GHRP-6 5mg", "subtitle": "Growth hormone releasing peptide",
        "description": "<h2>What is GHRP-6?</h2><p>GHRP-6 is a hexapeptide studied in relation to the ghrelin receptor, growth hormone release and appetite in experimental models.</p>" + _EN_DISCLAIMER}},
    "sermorelin": {"en": {
        "title": "Sermorelin 5mg", "subtitle": "GHRH (1-29)",
        "description": "<h2>What is Sermorelin?</h2><p>Sermorelin is a GHRH (1-29) analogue studied in relation to stimulation of natural growth hormone secretion.</p>" + _EN_DISCLAIMER}},
}

# ---------------------------------------------------------------- articles
ARTICLE_TR = {
    "tesamorelin": {"en": {"title": "Tesamorelin: pharmacology, metabolic effects and research relevance", "excerpt": "A review of tesamorelin's mechanism of action, its relation to the GH/IGF-1 axis and the metabolic observations reported in published research."}},
    "mots-c": {"en": {"title": "MOTS-c peptide: mitochondrial signalling factor and metabolic effects", "excerpt": "How the mitochondrial-derived peptide MOTS-c influences AMPK signalling and the metabolic profile in experimental models."}},
    "triumph3-study-on-retatrutide": {"en": {"title": "Retatrutide – triple GIP, GLP-1 and glucagon agonist in obesity", "excerpt": "Data from retatrutide research and the potential of triple receptor agonist activity."}},
    "ghk-cu-gene-data": {"en": {"title": "Regenerative and protective actions of GHK-Cu in light of new gene data", "excerpt": "The copper tripeptide GHK-Cu and its influence on gene expression, collagen and skin repair processes."}},
    "cjc-1295-gh-igf1": {"en": {"title": "Activating the GH/IGF-1 axis with CJC-1295 – a long-acting GHRH analogue", "excerpt": "Mechanism of action of CJC-1295 and observations on pulsatile growth hormone secretion."}},
}
