# The MERL-T Knowledge Graph

## 1. Introduction

The Knowledge Graph (KG) is a core asset of the MERL-T architecture. It represents the collective intellectual asset of the ALIS community, providing a structured, machine-readable representation of the legal domain. Unlike a static database, the KG is a dynamic entity that evolves through the RLCF process, ensuring its accuracy, richness, and security over time.

The KG is used in the **Context Augmentation** phase of the MERL-T pipeline to retrieve structured information (triplets) that provides precise, factual context for the LLM expert modules. This allows the system to ground its reasoning in established legal relationships rather than relying solely on unstructured text.

### 1.1 Design Principles

The MERL-T Knowledge Graph is designed according to the following principles:

- **FAIR Principles**: Findable, Accessible, Interoperable, Reusable
- **Standards Alignment**: Conformance to international standards (ELI, Akoma Ntoso, LKIF Core)
- **Temporal Awareness**: Full support for multivigenza (multiple temporal versions) of legal norms
- **Granular Representation**: From documents down to individual clauses (commi, lettere, numeri)
- **Interoperability**: Bidirectional mapping with European and international legal ontologies
- **Provenance Tracking**: Complete lineage of knowledge and modifications
- **Technology Agnostic**: Conceptual model independent of specific implementation choices

### 1.2 Scope and Coverage

The MERL-T Knowledge Graph covers:

- **Legislative documents**: Laws, decrees, regulations, circulars at national and regional level
- **Judicial acts**: Court decisions, rulings, orders from all levels of jurisdiction
- **EU legislation**: Directives, regulations, decisions affecting Italian law
- **Legal concepts**: Abstract principles, rights, obligations, responsibilities
- **Legal subjects**: Natural persons, legal entities, public bodies, jurisdictional organs
- **Procedures**: Civil, criminal, administrative, and special procedures
- **Temporal evolution**: Full versioning and modification tracking
- **Legal reasoning**: Rules, propositions, facts, and their relationships

## 2. Node Types

The graph is composed of several distinct node types, each representing a different kind of legal entity.

### A. Norma (Legal Norm)

*   **Description**: Represents specific legal acts, such as articles of a code, laws, decrees, circulars, or ordinances. Norms are versioned to support multivigenza (temporal validity tracking).
*   **Properties**:
    *   `node_id` (String): A unique identifier for the norm node within the graph.
    *   `estremi` (String): The official identifier of the norm (e.g., "Art. 1414 c.c.", "Legge n. 40/2004").
    *   `URN` (String): Unique persistent identifier for the norm.
    *   `fonte` (String, optional): The source from which the norm is derived.
    *   `titolo` (String): The official title of the norm (e.g., "Approvazione del testo definitivo del Codice Penale").
    *   `descrizione` (String): A brief description of the norm's content.
    *   `testo_originale` (String): The original text of the norm as initially published.
    *   `testo_vigente` (String): The current text of the norm after all modifications.
    *   `stato` (Enum): Current status of the norm: `vigente`, `abrogato`, `sospeso`, `modificato`.
    *   `efficacia` (Enum): Temporal nature of the norm: `permanente`, `temporanea`, `emergenziale`.
    *   `versione` (String): Version identifier for temporal tracking.
    *   `data_versione` (Date): Date of this specific version.
    *   `data_pubblicazione` (Date): The publication date of the norm.
    *   `data_entrata_in_vigore` (Date): The date the norm came into force.
    *   `data_abrogazione` (Date, optional): The date the norm was repealed.
    *   `data_cessazione_efficacia` (Date, optional): The date the norm ceased to have effect.
    *   `ambito_territoriale` (Enum): Geographic scope: `nazionale`, `regionale`, `provinciale`, `comunale`, `specifico`.
    *   `ambito_di_applicazione` (String, optional): The territorial or personal scope of the norm.
    *   `materie` (List[String]): Thematic classifications (multiple subjects possible).
    *   `classificazione_tematica` (List[String], optional): Controlled vocabulary classification terms.
    *   `revisioni_costituzionali` (String, optional): References to constitutional reviews that affect the norm.
    *   `note_redazionali` (String, optional): Editorial notes and clarifications.
    *   `doi` (String, optional): Digital Object Identifier for persistent citation.
    *   `licenza` (String, optional): License under which the norm text is available (e.g., "CC-BY 4.0").

### B. Concetto Giuridico (Legal Concept)

*   **Description**: Represents abstract ideas or legal principles (e.g., "Simulazione" (Simulation), "Buona fede" (Good Faith), "Diritto di proprietà" (Right of Property)).
*   **Properties**:
    *   `node_id` (String): A unique identifier for the concept node.
    *   `nome` (String): The name of the concept (e.g., "Simulazione").
    *   `definizione` (String, optional): The definition of the concept.
    *   `ambito_di_applicazione` (String, optional): The field of application for the concept.

### C. Soggetto Giuridico (Legal Subject)

*   **Description**: Represents an entity to which the law applies (e.g., "Persona fisica" (Natural Person), "Società" (Company), "Ente Pubblico" (Public Body)).
*   **Properties**:
    *   `node_id` (String): A unique identifier for the subject node.
    *   `nome` (String): The name of the subject or category of subjects (e.g., "Mario Rossi", "Tribunale").
    *   `tipo` (String): The type of legal subject (e.g., "Persona fisica", "Persona giuridica").
    *   `ruolo` (String, optional): The role of the subject in a specific legal context (e.g., "Imputato" (Defendant), "Creditore" (Creditor)).
    *   `qualifiche` (String, optional): Qualifications or characteristics of the subject (e.g., "Minore emancipato" (Emancipated Minor)).

### D. Atto Giudiziario / Provvedimento (Judicial Act / Provision)

*   **Description**: Represents judicial decisions or administrative acts (e.g., "Sentenza Cassazione n.1234/2023", "Decreto Ministeriale").
*   **Properties**:
    *   `node_id` (String): A unique identifier for the act node.
    *   `estremi` (String): The official identifier of the act (e.g., "Sentenza Cassazione n.1234/2023").
    *   `descrizione` (String): A brief description of the act's content.
    *   `organo_emittente` (String): The body that issued the act (e.g., "Corte di Cassazione", "Ministero della Giustizia").
    *   `data` (Date): The date the act was issued.
    *   `tipologia` (String): The type of act (e.g., sentenza, ordinanza, decreto).
    *   `materia` (String): The field of law the act pertains to (e.g., "Diritto civile", "Diritto penale").
    *   `URN` (String, optional): The unique identifier according to the ELI standard.

### E. Dottrina / Commentario (Doctrine / Commentary)

*   **Description**: Represents texts and doctrinal opinions that interpret or comment on legal norms (e.g., "Manuale di diritto civile", "Commentario al Codice Penale").
*   **Properties**:
    *   `node_id` (String): A unique identifier for the doctrine node.
    *   `titolo` (String): The title of the doctrinal text.
    *   `autore` (String): The author(s) of the text.
    *   `descrizione` (String): A summary of the key concepts in the text.
    *   `data_pubblicazione` (Date): The publication date of the text.
    *   `fonte` (String): The source (e.g., journal, book, manual).

### F. Procedura / Processo (Procedure / Process)

*   **Description**: Represents sequences of acts regulated by a norm (e.g., "Processo Civile ordinario" (Ordinary Civil Procedure), "Procedura fallimentare" (Bankruptcy Procedure)).
*   **Properties**:
    *   `node_id` (String): A unique identifier for the procedure node.
    *   `nome` (String): The name of the procedure.
    *   `descrizione` (String): A description of the phases and acts that make up the procedure.
    *   `ambito` (String): The field of application for the procedure (e.g., "Diritto civile", "Diritto penale").
    *   `tipologia` (String): The type of procedure (e.g., Giudiziale, Stragiudiziale, Amministrativa).

### G. Comma / Lettera / Numero (Clause / Letter / Number)

*   **Description**: Represents sub-article granularity elements within legal texts. Essential for tracking precise modifications and citations at the clause level.
*   **Properties**:
    *   `node_id` (String): Unique identifier for the clause node.
    *   `tipo` (Enum): Type of structural element: `comma`, `lettera`, `numero`.
    *   `posizione` (String): Hierarchical position (e.g., "comma 2, lettera a, numero 3").
    *   `testo` (String): Full text of the clause.
    *   `testo_originale` (String): Original text as initially published.
    *   `ordinamento` (Integer): Sequential order within parent element.
    *   `data_versione` (Date): Version date for temporal tracking.

### H. Versione (Version)

*   **Description**: Represents a specific temporal version of a legal norm to support multivigenza. Each version captures the state of a norm at a specific point in time.
*   **Properties**:
    *   `node_id` (String): Unique identifier for the version node.
    *   `numero_versione` (String): Version identifier (e.g., "v1.0", "v2023-04-15").
    *   `data_inizio_validita` (Date): Start date of this version's validity.
    *   `data_fine_validita` (Date, optional): End date of validity (null for current version).
    *   `testo_completo` (String): Complete text of the norm at this version.
    *   `descrizione_modifiche` (String): Summary of changes from previous version.
    *   `fonte_modifica` (String): Reference to the modifying norm.
    *   `consolidato` (Boolean): Indicates if this is a consolidated text version.

### I. Direttiva UE / Regolamento UE (EU Directive / EU Regulation)

*   **Description**: Represents European Union legislative acts that require implementation or have direct effect in member states.
*   **Properties**:
    *   `node_id` (String): Unique identifier for the EU act node.
    *   `estremi` (String): Official identifier (e.g., "Direttiva 2019/1024/UE").
    *   `URN` (String): Unique persistent identifier for the EU act.
    *   `tipo` (Enum): Type of act: `direttiva`, `regolamento`, `decisione`.
    *   `titolo` (String): Official title of the act.
    *   `descrizione` (String): Summary of the act's content and objectives.
    *   `data_adozione` (Date): Date of adoption by EU institutions.
    *   `data_pubblicazione_gue` (Date): Publication date in Official Journal.
    *   `data_entrata_in_vigore` (Date): Date when the act came into force.
    *   `termine_recepimento` (Date, optional): Deadline for transposition (for directives).
    *   `base_giuridica` (String): Legal basis in EU treaties.
    *   `classificazione_tematica` (List[String]): Thematic classification terms.

### J. Organo Giurisdizionale / Amministrativo (Jurisdictional / Administrative Body)

*   **Description**: Represents courts, tribunals, ministries, and administrative authorities with hierarchical relationships. More structured than simple issuing body attribution.
*   **Properties**:
    *   `node_id` (String): Unique identifier for the body node.
    *   `nome` (String): Official name of the body (e.g., "Corte di Cassazione", "Ministero della Giustizia").
    *   `tipo` (Enum): Type of body: `giurisdizionale`, `amministrativo`, `costituzionale`, `internazionale`.
    *   `livello` (Enum): Hierarchical level: `supremo`, `appello`, `primo_grado`, `locale`.
    *   `competenza_territoriale` (String): Geographic jurisdiction.
    *   `competenza_materia` (List[String]): Subject matter jurisdiction.
    *   `sede` (String): Physical location of the body.
    *   `composizione` (String, optional): Composition and structure.

### K. Caso / Fatto (Case / Fact Pattern)

*   **Description**: Represents concrete legal cases or factual situations referenced in judicial acts or used for case-based reasoning.
*   **Properties**:
    *   `node_id` (String): Unique identifier for the case node.
    *   `identificativo` (String): Case identifier or reference number.
    *   `descrizione` (String): Description of the factual circumstances.
    *   `tipo_controversia` (String): Type of dispute or legal issue.
    *   `esito` (String, optional): Outcome of the case.
    *   `rilevanza` (String): Legal relevance or significance.
    *   `data` (Date, optional): Date of the case or decision.
    *   `parti` (List[String], optional): Parties involved.

### L. Termine / Scadenza (Term / Deadline)

*   **Description**: Represents temporal deadlines, time limits, or procedural terms established by legal norms. Essential for temporal reasoning and compliance tracking.
*   **Properties**:
    *   `node_id` (String): Unique identifier for the term node.
    *   `descrizione` (String): Description of the term or deadline.
    *   `durata` (String): Duration specification (e.g., "30 giorni", "6 mesi").
    *   `tipo` (Enum): Type of term: `perentorio`, `ordinatorio`, `sospensivo`, `decadenza`.
    *   `modalita_calcolo` (String): Method for calculating the term (e.g., "a partire dalla notifica").
    *   `prorogabile` (Boolean): Whether the term can be extended.
    *   `conseguenze_mancato_rispetto` (String): Consequences of missing the deadline.

### M. Sanzione (Sanction / Penalty)

*   **Description**: Represents legal consequences, penalties, or sanctions established by norms for violations or specific circumstances.
*   **Properties**:
    *   `node_id` (String): Unique identifier for the sanction node.
    *   `tipo` (Enum): Type of sanction: `penale`, `amministrativa`, `disciplinare`, `civile`.
    *   `descrizione` (String): Description of the sanction.
    *   `entita_minima` (String, optional): Minimum penalty (e.g., "500 EUR", "1 mese").
    *   `entita_massima` (String, optional): Maximum penalty (e.g., "5000 EUR", "2 anni").
    *   `modalita_applicazione` (String): How the sanction is applied.
    *   `circostanze_aggravanti` (List[String], optional): Aggravating circumstances.
    *   `circostanze_attenuanti` (List[String], optional): Mitigating circumstances.

### N. Definizione Legale (Legal Definition)

*   **Description**: Represents explicit definitions of legal terms provided within normative texts. Enables construction of a structured legal glossary.
*   **Properties**:
    *   `node_id` (String): Unique identifier for the definition node.
    *   `termine` (String): The term being defined.
    *   `definizione` (String): The legal definition.
    *   `ambito_applicazione` (String): Scope where this definition applies (e.g., "ai fini del presente articolo").
    *   `sinonimi` (List[String], optional): Alternative terms with the same meaning.
    *   `note` (String, optional): Clarifications or usage notes.

### O. Modalità Giuridica (Legal Modality)

*   **Description**: Represents deontic modalities - obligations, permissions, prohibitions, and powers that are fundamental to legal reasoning.
*   **Properties**:
    *   `node_id` (String): Unique identifier for the modality node.
    *   `tipo_modalita` (Enum): Type of modality: `obbligo` (obligation), `permesso` (permission), `divieto` (prohibition), `potere` (power), `immunita` (immunity), `disabilita` (disability).
    *   `descrizione` (String): Description of the modal constraint or entitlement.
    *   `soggetto_attivo` (String): The party holding the obligation/right/power.
    *   `soggetto_passivo` (String, optional): The party affected by the modality.
    *   `condizioni` (List[String], optional): Conditions under which the modality applies.
    *   `contesto` (String): Legal context defining the modality.
    *   `intensita` (Enum, optional): Strength of the modality: `assoluto`, `relativo`, `condizionato`.
    *   `derogabile` (Boolean): Whether the modality can be derogated.

### P. Responsabilità (Responsibility / Liability)

*   **Description**: Represents attribution of legal responsibility for acts, omissions, or conditions.
*   **Properties**:
    *   `node_id` (String): Unique identifier for the responsibility node.
    *   `tipo_responsabilita` (Enum): Type: `penale` (criminal), `civile` (civil), `amministrativa` (administrative), `disciplinare` (disciplinary), `oggettiva` (strict liability), `colposa` (negligence), `dolosa` (intentional).
    *   `descrizione` (String): Description of the responsibility attribution.
    *   `fondamento` (String): Legal basis for the responsibility (norm, principle).
    *   `elementi_costitutivi` (List[String]): Required elements (e.g., "fatto, danno, nesso causale, colpa").
    *   `regime_probatorio` (String, optional): Burden of proof rules.
    *   `prescrizione` (String, optional): Statute of limitations.
    *   `solidale` (Boolean, optional): Whether liability is joint and several.

### Q. Diritto Soggettivo (Subjective Right)

*   **Description**: Represents individual rights and legal entitlements held by subjects. Distinguished from obligations and powers.
*   **Properties**:
    *   `node_id` (String): Unique identifier for the right node.
    *   `nome` (String): Name of the right (e.g., "Diritto di proprietà", "Diritto al nome").
    *   `tipo_diritto` (Enum): Type: `assoluto` (absolute), `relativo` (relative), `reale` (real), `personale` (personal), `patrimoniale` (property), `non_patrimoniale` (non-property).
    *   `descrizione` (String): Description of the right's content.
    *   `titolare` (String, optional): Holder of the right (if specific).
    *   `opponibilita` (Enum): Who must respect it: `erga_omnes`, `inter_partes`.
    *   `rinunciabilita` (Boolean): Whether the right can be waived.
    *   `trasmissibilita` (Boolean): Whether the right can be transferred.
    *   `prescrittibilita` (Boolean): Whether the right is subject to prescription.
    *   `tutela` (List[String]): Legal protections available (e.g., "azione di rivendicazione", "risarcimento danni").

### R. Interesse Legittimo (Legitimate Interest)

*   **Description**: Represents legitimate interests in administrative law - positions of advantage toward public administration acts. Distinct from subjective rights in Italian administrative law.
*   **Properties**:
    *   `node_id` (String): Unique identifier for the legitimate interest node.
    *   `tipo` (Enum): Type: `pretensivo` (seeking a benefit), `oppositivo` (opposing an act).
    *   `descrizione` (String): Description of the interest.
    *   `bene_della_vita` (String): The concrete advantage sought.
    *   `titolare` (String, optional): Holder of the interest.
    *   `qualificazione` (String): Qualified legal position of the holder.
    *   `strumenti_tutela` (List[String]): Available remedies (e.g., "ricorso al TAR", "risarcimento danni").

### S. Principio Giuridico (Legal Principle)

*   **Description**: Represents fundamental legal principles that are not specific norms but general standards of interpretation and application. Includes constitutional principles, general principles of law, and fundamental rights principles.
*   **Properties**:
    *   `node_id` (String): Unique identifier for the principle node.
    *   `nome` (String): Name of the principle (e.g., "Principio di legalità", "Buona fede").
    *   `tipo` (Enum): Type: `costituzionale`, `generale_del_diritto`, `settoriale`, `internazionale`, `comunitario`.
    *   `descrizione` (String): Description and content of the principle.
    *   `ambito_applicazione` (String): Fields where the principle applies.
    *   `livello` (Enum): Hierarchical level: `fondamentale`, `generale`, `specifico`.
    *   `fonte` (String): Source of the principle (Constitution, case law, doctrine).
    *   `derogabile` (Boolean): Whether the principle admits exceptions.
    *   `bilanciabile` (Boolean): Whether it can be balanced with other principles.

### T. Fatto Giuridico (Legal Fact)

*   **Description**: Represents events, acts, or states of affairs that produce legal effects.
*   **Properties**:
    *   `node_id` (String): Unique identifier for the legal fact node.
    *   `tipo_fatto` (Enum): Type: `atto_giuridico` (juridical act), `fatto_naturale` (natural fact), `comportamento` (conduct), `evento` (event), `stato` (state).
    *   `descrizione` (String): Description of the fact.
    *   `volontarieta` (Boolean): Whether the fact is voluntary or involuntary.
    *   `liceita` (Boolean): Whether the fact is licit or illicit.
    *   `data_fatto` (Date, optional): Date when the fact occurred.
    *   `luogo` (String, optional): Location where the fact occurred.
    *   `effetti_giuridici` (List[String]): Legal consequences produced.
    *   `rilevanza` (String): Legal relevance of the fact.

### U. Ruolo Giuridico (Legal Role)

*   **Description**: Represents functional legal roles that subjects can assume in legal relationships and procedures.
*   **Properties**:
    *   `node_id` (String): Unique identifier for the role node.
    *   `nome` (String): Name of the role (e.g., "Imputato", "Creditore", "Rappresentante").
    *   `tipo_ruolo` (Enum): Context type: `processuale` (procedural), `contrattuale` (contractual), `familiare` (family), `societario` (corporate), `amministrativo` (administrative).
    *   `descrizione` (String): Description of the role's functions and characteristics.
    *   `poteri` (List[String]): Powers associated with the role.
    *   `doveri` (List[String]): Duties associated with the role.
    *   `requisiti` (List[String]): Requirements to assume the role.
    *   `incompatibilita` (List[String], optional): Roles incompatible with this one.
    *   `temporaneo` (Boolean): Whether the role is temporary or permanent.

### V. Regola (Rule)

*   **Description**: Represents logical rules that can be applied for reasoning over the knowledge graph. These are meta-level constructs for inference.
*   **Properties**:
    *   `node_id` (String): Unique identifier for the rule node.
    *   `nome` (String): Name of the rule.
    *   `tipo_regola` (Enum): Type: `costitutiva` (constitutive), `regolativa` (regulative), `inferenza` (inference), `interpretativa` (interpretive).
    *   `premesse` (List[String]): Antecedent conditions (IF part).
    *   `conseguenze` (List[String]): Consequent conclusions (THEN part).
    *   `eccezioni` (List[String], optional): Exceptions to the rule (UNLESS part).
    *   `forza` (Enum): Strength: `assoluta`, `relativa`, `defeasible`.
    *   `ambito` (String): Scope of application.
    *   `formalizzazione` (String, optional): Formal logic representation.

### W. Proposizione Giuridica (Legal Proposition)

*   **Description**: Represents propositional content of legal statements - what is asserted by norms, acts, or doctrine.
*   **Properties**:
    *   `node_id` (String): Unique identifier for the proposition node.
    *   `contenuto` (String): Propositional content.
    *   `tipo` (Enum): Type: `descrittiva` (descriptive), `prescrittiva` (prescriptive), `valutativa` (evaluative).
    *   `modalita` (Enum, optional): Modal qualification: `necessaria`, `possibile`, `contingente`.
    *   `valore_verita` (Enum, optional): Truth value: `vera`, `falsa`, `indeterminata`, `contestata`.
    *   `contesto` (String): Context in which the proposition is asserted.
    *   `giustificazione` (String, optional): Justification or reasoning supporting the proposition.

## 3. Relation Types (Tipologie di Relazioni)

The nodes in the graph are connected by a set of well-defined relationships that capture the interactions between legal entities.

### 3.1 Common Relation Properties

All relationships in the knowledge graph should include the following properties where applicable:

*   `data_decorrenza` (Date): Date when the relationship becomes effective
*   `data_cessazione` (Date, optional): Date when the relationship ceases
*   `fonte_relazione` (String): Source establishing this relationship (norm, act, inference)
*   `certezza` (Enum): Confidence level: `esplicita` (explicit in text), `inferita` (inferred), `validata` (community validated)
*   `paragrafo_riferimento` (String, optional): Exact location in source text
*   `confidence_score` (Float, 0-1): Confidence score for inferred relationships
*   `validato_da` (String, optional): Validator identifier (for RLCF process)
*   `data_validazione` (Date, optional): Validation date

### 3.2 Structural Relations

#### 1. **contiene (contains)**
*   **Definition**: Structural containment between document elements (Norma contains Comma, Comma contains Lettera, etc.)
*   **Source**: `Norma` → `Comma`, `Comma` → `Lettera`, `Lettera` → `Numero`
*   **Example**: `(Art. 1414 c.c.) -[:contiene]-> (Art. 1414, comma 1)`

#### 2. **parte_di (part_of)**
*   **Definition**: Inverse of containment, indicating hierarchical membership
*   **Source**: `Comma` → `Norma`, `Lettera` → `Comma`, etc.
*   **Example**: `(Art. 1414, comma 1) -[:parte_di]-> (Art. 1414 c.c.)`

#### 3. **versione_precedente (previous_version)**
*   **Definition**: Links a version to its chronologically previous version
*   **Source**: `Versione` → `Versione`
*   **Example**: `(Art. 1414 c.c. v2023) -[:versione_precedente]-> (Art. 1414 c.c. v2020)`

#### 4. **versione_successiva (next_version)**
*   **Definition**: Links a version to its chronologically next version
*   **Source**: `Versione` → `Versione`
*   **Example**: `(Art. 1414 c.c. v2020) -[:versione_successiva]-> (Art. 1414 c.c. v2023)`

#### 5. **ha_versione (has_version)**
*   **Definition**: Links a norm to its temporal versions
*   **Source**: `Norma` → `Versione`
*   **Example**: `(Art. 1414 c.c.) -[:ha_versione]-> (Art. 1414 c.c. v2023)`

### 3.3 Modification Relations

These relations replace the generic "modifica" with specific types of normative changes.

#### 6. **sostituisce (replaces)**
*   **Definition**: Complete textual replacement of a norm or clause
*   **Source**: `Norma` → `Norma`, `Norma` → `Comma`
*   **Properties**: `testo_modificato` (String), `testo_nuovo` (String), `data_efficacia` (Date)
*   **Example**: `(Legge n. 123/2023, Art. 5) -[:sostituisce]-> (Art. 1414, comma 2)`

#### 7. **inserisce (inserts)**
*   **Definition**: Addition of new text without removing existing content
*   **Source**: `Norma` → `Norma`, `Norma` → `Comma`
*   **Properties**: `testo_inserito` (String), `posizione_inserimento` (String), `data_efficacia` (Date)
*   **Example**: `(D.L. n. 45/2024) -[:inserisce]-> (Art. 1414 c.c.)`

#### 8. **abroga_totalmente (totally_repeals)**
*   **Definition**: Complete repeal of a norm or provision
*   **Source**: `Norma` → `Norma`
*   **Properties**: `data_efficacia` (Date), `effetto` (Enum: `immediato`, `differito`)
*   **Example**: `(Legge n. 200/2023) -[:abroga_totalmente]-> (R.D. 1234/1930)`

#### 9. **abroga_parzialmente (partially_repeals)**
*   **Definition**: Repeal of specific clauses or portions of a norm
*   **Source**: `Norma` → `Comma`, `Norma` → `Lettera`
*   **Properties**: `parte_abrogata` (String), `data_efficacia` (Date)
*   **Example**: `(Legge n. 100/2024) -[:abroga_parzialmente]-> (Art. 1414, comma 3, lettera b)`

#### 10. **sospende (suspends)**
*   **Definition**: Temporary suspension of effectiveness
*   **Source**: `Norma` → `Norma`
*   **Properties**: `data_inizio_sospensione` (Date), `data_fine_sospensione` (Date), `motivo` (String)
*   **Example**: `(DPCM 15/03/2020) -[:sospende]-> (Art. 45 D.Lgs. 81/2008)`

#### 11. **proroga (extends)**
*   **Definition**: Extension of temporal deadlines or validity periods
*   **Source**: `Norma` → `Norma`, `Norma` → `Termine`
*   **Properties**: `nuova_scadenza` (Date), `durata_proroga` (String)
*   **Example**: `(D.L. n. 23/2024) -[:proroga]-> (Legge n. 15/2023, Art. 3)`

#### 12. **integra (supplements)**
*   **Definition**: Addition of content that complements without replacing
*   **Source**: `Norma` → `Norma`
*   **Properties**: `contenuto_integrativo` (String), `data_efficacia` (Date)
*   **Example**: `(Legge n. 88/2024) -[:integra]-> (Art. 1414 c.c.)`

#### 13. **deroga_a (derogates)**
*   **Definition**: Establishes an exception without modifying the original text
*   **Source**: `Norma` → `Norma`
*   **Properties**: `ambito_deroga` (String), `condizioni` (String), `temporanea` (Boolean)
*   **Example**: `(Legge speciale n. 44/2023) -[:deroga_a]-> (Art. 2043 c.c.)`

#### 14. **consolida (consolidates)**
*   **Definition**: Creates a unified text from multiple scattered norms
*   **Source**: `Norma` (testo unico) → `Norma` (multiple sources)
*   **Properties**: `tipo_consolidamento` (Enum: `innovativo`, `compilativo`)
*   **Example**: `(D.Lgs. n. 81/2008) -[:consolida]-> (D.Lgs. n. 626/1994)`

### 3.4 Semantic Relations

#### 15. **disciplina (governs)**
*   **Definition**: Connects a `Norma` to a `Concetto Giuridico`, indicating that the norm governs that legal concept
*   **Source**: `Norma` → `Concetto Giuridico`
*   **Example**: `(Art. 1414 c.c.) -[:disciplina]-> (Simulazione)`

#### 16. **applica_a (applies_to)**
*   **Definition**: Connects a `Norma` to a `Soggetto Giuridico`, indicating to whom the norm applies
*   **Source**: `Norma` → `Soggetto Giuridico`
*   **Example**: `(Art. 3 Costituzione) -[:applica_a]-> (Tutti i cittadini)`

#### 17. **definisce (defines)**
*   **Definition**: Links a norm to the legal definitions it establishes
*   **Source**: `Norma` → `Definizione Legale`
*   **Example**: `(Art. 810 c.c.) -[:definisce]-> (Definizione di "beni")`

#### 18. **prevede_sanzione (prescribes_sanction)**
*   **Definition**: Links a norm to the sanctions it establishes
*   **Source**: `Norma` → `Sanzione`
*   **Example**: `(Art. 640 c.p.) -[:prevede_sanzione]-> (Reclusione da 6 mesi a 3 anni)`

#### 19. **stabilisce_termine (establishes_term)**
*   **Definition**: Links a norm to temporal deadlines it creates
*   **Source**: `Norma` → `Termine`
*   **Example**: `(Art. 163 c.p.c.) -[:stabilisce_termine]-> (Termine per comparsa di risposta)`

#### 20. **prevede (provides_for)**
*   **Definition**: Connects a `Norma` to a `Procedura/Processo`, indicating that the norm provides for that procedure
*   **Source**: `Norma` → `Procedura`
*   **Example**: `(Codice di Procedura Civile) -[:prevede]-> (Processo Civile ordinario)`

### 3.5 Dependency Relations

#### 21. **dipende_da (depends_on)**
*   **Definition**: Logical dependency between norms (one requires the other to be applicable)
*   **Source**: `Norma` → `Norma`, `Comma` → `Comma`
*   **Properties**: `tipo_dipendenza` (Enum: `condizionale`, `presupposto`, `rinvio`)
*   **Example**: `(Art. 1414, comma 3) -[:dipende_da]-> (Art. 1414, comma 1)`

#### 22. **presuppone (presupposes)**
*   **Definition**: Implicit prerequisite not explicitly cited but logically necessary
*   **Source**: `Norma` → `Norma`, `Norma` → `Concetto Giuridico`
*   **Properties**: `tipo_presupposto` (String)
*   **Example**: `(Art. 2043 c.c.) -[:presuppone]-> (Capacità di intendere e di volere)`

#### 23. **species (specializes)**
*   **Definition**: Hierarchical relationship of subordination (is-a relationship)
*   **Source**: `Concetto Giuridico` → `Concetto Giuridico`
*   **Example**: `(Simulazione relativa) -[:species]-> (Simulazione)`

### 3.6 Citation and Interpretation Relations

#### 24. **cita (cites)**
*   **Definition**: Explicit citation between legal documents
*   **Source**: `Norma` → `Norma`, `Atto Giudiziario` → `Norma`, etc.
*   **Properties**: `tipo_citazione` (Enum: `richiamo`, `riferimento`, `rinvio_recettizio`)
*   **Example**: `(Art. 1414 c.c.) -[:cita]-> (Art. 1373 c.c.)`

#### 25. **interpreta (interprets)**
*   **Definition**: Judicial or doctrinal interpretation of a norm
*   **Source**: `Atto Giudiziario` → `Norma`
*   **Properties**: `tipo_interpretazione` (Enum: `autentica`, `giurisprudenziale`, `dottrinale`), `orientamento` (Enum: `estensiva`, `restrittiva`, `letterale`)
*   **Example**: `(Sentenza Cass. 1234/2023) -[:interpreta]-> (Art. 1414 c.c.)`

#### 26. **commenta (comments_on)**
*   **Definition**: Doctrinal commentary on legal texts
*   **Source**: `Dottrina` → `Norma`, `Dottrina` → `Atto Giudiziario`
*   **Example**: `(Commentario Bianca) -[:commenta]-> (Art. 1414 c.c.)`

### 3.7 European and International Relations

#### 27. **attua (implements)**
*   **Definition**: National norm implementing EU directive or regulation
*   **Source**: `Norma` → `Direttiva UE` / `Regolamento UE`
*   **Properties**: `data_recepimento` (Date), `conforme` (Boolean), `note_conformita` (String)
*   **Example**: `(D.Lgs. n. 24/2019) -[:attua]-> (Direttiva 2019/1024/UE)`

#### 28. **recepisce (transposes)**
*   **Definition**: Specific transposition of EU directive into national law
*   **Source**: `Norma` → `Direttiva UE`
*   **Properties**: `integrale` (Boolean), `parziale` (Boolean), `adeguamento_necessario` (Boolean)
*   **Example**: `(Legge n. 123/2020) -[:recepisce]-> (Direttiva 2018/843/UE)`

#### 29. **conforme_a (complies_with)**
*   **Definition**: Indicates conformity with EU or international standards
*   **Source**: `Norma` → `Direttiva UE` / `Regolamento UE`
*   **Example**: `(Art. 5 D.Lgs. 196/2003) -[:conforme_a]-> (GDPR Art. 6)`

### 3.8 Institutional Relations

#### 30. **emesso_da (issued_by)**
*   **Definition**: Links an act to the body that issued it
*   **Source**: `Atto Giudiziario` → `Organo`, `Norma` → `Organo`
*   **Example**: `(Sentenza n.1234/2023) -[:emesso_da]-> (Corte di Cassazione)`

#### 31. **ha_competenza_su (has_jurisdiction_over)**
*   **Definition**: Establishes jurisdictional competence of a body
*   **Source**: `Organo` → `Materia` / `Territorio`
*   **Example**: `(TAR Lazio) -[:ha_competenza_su]-> (Atti amministrativi del Lazio)`

#### 32. **gerarchicamente_superiore (hierarchically_superior)**
*   **Definition**: Hierarchical relationship between judicial/administrative bodies
*   **Source**: `Organo` → `Organo`
*   **Example**: `(Corte di Cassazione) -[:gerarchicamente_superiore]-> (Corte d'Appello)`

### 3.9 Case-based Relations

#### 33. **riguarda (concerns)**
*   **Definition**: Links an act to the subjects or cases it concerns
*   **Source**: `Atto Giudiziario` → `Soggetto Giuridico` / `Caso`
*   **Example**: `(Sentenza n. 1234/2023) -[:riguarda]-> (Mario Rossi)`

#### 34. **applica_norma_a_caso (applies_norm_to_case)**
*   **Definition**: Links judicial reasoning connecting norm to specific case
*   **Source**: `Atto Giudiziario` → `Norma`, `Atto Giudiziario` → `Caso`
*   **Example**: `(Sentenza n. 1234/2023) -[:applica_norma_a_caso]-> (Art. 2043 c.c.)`

#### 35. **precedente_di (precedent_for)**
*   **Definition**: Case-law precedent relationship
*   **Source**: `Atto Giudiziario` → `Atto Giudiziario`
*   **Properties**: `forza_vincolante` (Enum: `vincolante`, `persuasivo`)
*   **Example**: `(Cass. Sez. Unite n. 500/2020) -[:precedente_di]-> (Cass. n. 1234/2023)`

### 3.10 Classification and Organization

#### 36. **fonte (source)**
*   **Definition**: Links a norm to its source document or code
*   **Source**: `Norma` → `Fonte del Diritto`
*   **Example**: `(Art. 1414 c.c.) -[:fonte]-> (Codice Civile)`

#### 37. **classifica_in (classifies_in)**
*   **Definition**: Thematic or taxonomic classification
*   **Source**: Any node → `Categoria` / EuroVoc term
*   **Properties**: `schema_classificazione` (String)
*   **Example**: `(Art. 1414 c.c.) -[:classifica_in]-> (EuroVoc: Contratti e obbligazioni)`

### 3.11 LKIF-Aligned Relations for Legal Modalities and Reasoning

#### 38. **impone (imposes)**
*   **Definition**: Links a norm to the obligations, prohibitions, or permissions it establishes
*   **Source**: `Norma` → `Modalità Giuridica`
*   **Properties**: `condizionale` (Boolean), `condizioni` (String, optional)
*   **Example**: `(Art. 2043 c.c.) -[:impone]-> (Obbligo di risarcimento del danno)`

#### 39. **conferisce (confers)**
*   **Definition**: Links a norm to the powers or rights it confers to subjects
*   **Source**: `Norma` → `Diritto Soggettivo`, `Norma` → `Modalità Giuridica` (potere)
*   **Properties**: `beneficiario` (String, optional)
*   **Example**: `(Art. 832 c.c.) -[:conferisce]-> (Diritto di proprietà)`

#### 40. **titolare_di (holder_of)**
*   **Definition**: Links a legal subject to rights, powers, or obligations they hold
*   **Source**: `Soggetto Giuridico` → `Diritto Soggettivo`, `Soggetto Giuridico` → `Modalità Giuridica`
*   **Example**: `(Proprietario) -[:titolare_di]-> (Diritto di proprietà)`

#### 41. **riveste_ruolo (plays_role)**
*   **Definition**: Links a legal subject to the roles they assume in legal contexts
*   **Source**: `Soggetto Giuridico` → `Ruolo Giuridico`
*   **Properties**: `contesto` (String), `temporaneo` (Boolean)
*   **Example**: `(Mario Rossi) -[:riveste_ruolo]-> (Imputato)`

#### 42. **attribuisce_responsabilita (attributes_responsibility)**
*   **Definition**: Links a norm or judicial act to responsibility attributions
*   **Source**: `Norma` → `Responsabilità`, `Atto Giudiziario` → `Responsabilità`
*   **Properties**: `soggetto_responsabile` (String, optional)
*   **Example**: `(Art. 2043 c.c.) -[:attribuisce_responsabilita]-> (Responsabilità civile extracontrattuale)`

#### 43. **responsabile_per (responsible_for)**
*   **Definition**: Links a subject to the responsibilities attributed to them
*   **Source**: `Soggetto Giuridico` → `Responsabilità`
*   **Properties**: `fondamento` (String), `grado` (Enum: `piena`, `parziale`, `concorrente`)
*   **Example**: `(Medico) -[:responsabile_per]-> (Responsabilità professionale)`

#### 44. **esprime_principio (expresses_principle)**
*   **Definition**: Links a norm or act to the legal principles it expresses or applies
*   **Source**: `Norma` → `Principio Giuridico`, `Atto Giudiziario` → `Principio Giuridico`
*   **Example**: `(Art. 2 Cost.) -[:esprime_principio]-> (Principio di solidarietà sociale)`

#### 45. **conforma_a (conforms_to)**
*   **Definition**: Indicates conformity with a legal principle
*   **Source**: `Norma` → `Principio Giuridico`, `Atto Giudiziario` → `Principio Giuridico`
*   **Example**: `(Legge n. 241/1990) -[:conforma_a]-> (Principio di trasparenza amministrativa)`

#### 46. **deroga_principio (derogates_principle)**
*   **Definition**: Indicates exceptional departure from a principle
*   **Source**: `Norma` → `Principio Giuridico`
*   **Properties**: `giustificazione` (String), `ambito_deroga` (String)
*   **Example**: `(Legge emergenziale) -[:deroga_principio]-> (Principio di libertà di circolazione)`

#### 47. **bilancia_con (balances_with)**
*   **Definition**: Indicates balancing between competing principles
*   **Source**: `Principio Giuridico` → `Principio Giuridico`
*   **Properties**: `contesto` (String), `prevalenza` (Enum: `nessuna`, `primo`, `secondo`)
*   **Example**: `(Libertà di espressione) -[:bilancia_con]-> (Diritto alla privacy)`

#### 48. **produce_effetto (produces_effect)**
*   **Definition**: Links a legal fact to the legal effects it produces
*   **Source**: `Fatto Giuridico` → `Modalità Giuridica`, `Fatto Giuridico` → `Diritto Soggettivo`, `Fatto Giuridico` → `Responsabilità`
*   **Properties**: `automatico` (Boolean), `condizioni` (String, optional)
*   **Example**: `(Contratto di compravendita) -[:produce_effetto]-> (Trasferimento della proprietà)`

#### 49. **presupposto_di (prerequisite_for)**
*   **Definition**: Indicates that a fact is a necessary prerequisite for legal effects
*   **Source**: `Fatto Giuridico` → `Fatto Giuridico`, `Fatto Giuridico` → `Modalità Giuridica`
*   **Example**: `(Capacità di agire) -[:presupposto_di]-> (Validità del contratto)`

#### 50. **costitutivo_di (constitutive_of)**
*   **Definition**: Indicates that a fact or act constitutes (creates) a legal relationship or status
*   **Source**: `Fatto Giuridico` → `Diritto Soggettivo`, `Fatto Giuridico` → `Ruolo Giuridico`
*   **Example**: `(Matrimonio) -[:costitutivo_di]-> (Status di coniuge)`

#### 51. **estingue (extinguishes)**
*   **Definition**: Indicates that a fact extinguishes a right, obligation, or relationship
*   **Source**: `Fatto Giuridico` → `Diritto Soggettivo`, `Fatto Giuridico` → `Modalità Giuridica`
*   **Properties**: `modo_estinzione` (Enum: `totale`, `parziale`)
*   **Example**: `(Pagamento) -[:estingue]-> (Obbligo di restituire)`

#### 52. **modifica_efficacia (modifies_efficacy)**
*   **Definition**: Indicates that a fact modifies the efficacy of rights or obligations
*   **Source**: `Fatto Giuridico` → `Diritto Soggettivo`, `Fatto Giuridico` → `Modalità Giuridica`
*   **Properties**: `tipo_modifica` (Enum: `sospende`, `limita`, `estende`)
*   **Example**: `(Accettazione con beneficio d'inventario) -[:modifica_efficacia]-> (Responsabilità per debiti ereditari)`

#### 53. **applica_regola (applies_rule)**
*   **Definition**: Links judicial acts or reasoning to the rules applied
*   **Source**: `Atto Giudiziario` → `Regola`
*   **Properties**: `esplicita` (Boolean)
*   **Example**: `(Sentenza Cass.) -[:applica_regola]-> (Regola: chi agisce deve provare)`

#### 54. **implica (implies)**
*   **Definition**: Logical implication between propositions or rules
*   **Source**: `Proposizione Giuridica` → `Proposizione Giuridica`, `Regola` → `Proposizione Giuridica`
*   **Properties**: `tipo_implicazione` (Enum: `logica`, `pragmatica`, `analogica`)
*   **Example**: `(Proposizione: X è proprietario) -[:implica]-> (Proposizione: X può disporre del bene)`

#### 55. **contradice (contradicts)**
*   **Definition**: Indicates contradiction between propositions or norms
*   **Source**: `Proposizione Giuridica` → `Proposizione Giuridica`, `Norma` → `Norma`
*   **Properties**: `tipo_contraddizione` (Enum: `logica`, `assiologica`, `temporale`)
*   **Example**: `(Norma speciale) -[:contradice]-> (Norma generale)`

#### 56. **giustifica (justifies)**
*   **Definition**: Provides justification or reasoning support
*   **Source**: `Principio Giuridico` → `Norma`, `Proposizione Giuridica` → `Proposizione Giuridica`, `Norma` → `Modalità Giuridica`
*   **Properties**: `tipo_giustificazione` (Enum: `deduttiva`, `analogica`, `teleologica`, `sistematica`)
*   **Example**: `(Principio di uguaglianza) -[:giustifica]-> (Divieto di discriminazione)`

#### 57. **limita (limits)**
*   **Definition**: Indicates limitation of rights, powers, or principles
*   **Source**: `Norma` → `Diritto Soggettivo`, `Principio Giuridico` → `Diritto Soggettivo`, `Modalità Giuridica` → `Modalità Giuridica`
*   **Properties**: `tipo_limite` (Enum: `intrinseco`, `estrinseco`, `temporale`, `territoriale`), `proporzionale` (Boolean)
*   **Example**: `(Art. 832 c.c., comma 2) -[:limita]-> (Diritto di proprietà)`

#### 58. **tutela (protects)**
*   **Definition**: Links protective norms or mechanisms to the rights/interests they protect
*   **Source**: `Norma` → `Diritto Soggettivo`, `Norma` → `Interesse Legittimo`, `Procedura` → `Diritto Soggettivo`
*   **Properties**: `tipo_tutela` (Enum: `preventiva`, `successiva`, `cautelare`, `reintegratoria`, `risarcitoria`)
*   **Example**: `(Art. 700 c.p.c.) -[:tutela]-> (Diritti in pericolo)`

#### 59. **viola (violates)**
*   **Definition**: Indicates violation of norms, rights, or principles
*   **Source**: `Fatto Giuridico` → `Norma`, `Fatto Giuridico` → `Diritto Soggettivo`, `Fatto Giuridico` → `Modalità Giuridica`
*   **Properties**: `gravita` (Enum: `lieve`, `grave`, `gravissima`), `dolosa` (Boolean)
*   **Example**: `(Inadempimento contrattuale) -[:viola]-> (Obbligo di prestazione)`

#### 60. **compatibile_con (compatible_with)**
*   **Definition**: Indicates compatibility between norms, principles, or rights
*   **Source**: `Norma` → `Norma`, `Principio Giuridico` → `Principio Giuridico`, `Diritto Soggettivo` → `Diritto Soggettivo`
*   **Example**: `(Libertà di impresa) -[:compatibile_con]-> (Tutela dell'ambiente)`

#### 61. **incompatibile_con (incompatible_with)**
*   **Definition**: Indicates incompatibility requiring resolution or choice
*   **Source**: `Norma` → `Norma`, `Ruolo Giuridico` → `Ruolo Giuridico`, `Modalità Giuridica` → `Modalità Giuridica`
*   **Properties**: `criterio_risoluzione` (Enum: `gerarchico`, `cronologico`, `specialita`)
*   **Example**: `(Ruolo di giudice) -[:incompatibile_con]-> (Ruolo di avvocato difensore)`

#### 62. **specifica (specifies)**
*   **Definition**: Relationship of specification between abstract and concrete norms/concepts
*   **Source**: `Norma` → `Norma`, `Concetto Giuridico` → `Concetto Giuridico`, `Principio Giuridico` → `Norma`
*   **Example**: `(Norme attuative) -[:specifica]-> (Legge quadro)`

#### 63. **esemplifica (exemplifies)**
*   **Definition**: Links concrete instances or cases to abstract categories
*   **Source**: `Caso` → `Concetto Giuridico`, `Fatto Giuridico` → `Regola`
*   **Example**: `(Caso specifico di simulazione) -[:esemplifica]-> (Concetto di simulazione)`

#### 64. **causa_di (cause_of)**
*   **Definition**: Causal relationship between facts producing legal effects
*   **Source**: `Fatto Giuridico` → `Fatto Giuridico`
*   **Properties**: `tipo_causalita` (Enum: `materiale`, `giuridica`, `efficiente`, `occasionale`)
*   **Example**: `(Comportamento colposo) -[:causa_di]-> (Danno)`

#### 65. **condizione_di (condition_for)**
*   **Definition**: Indicates a condition (suspensive or resolutive) for legal effects
*   **Source**: `Fatto Giuridico` → `Modalità Giuridica`, `Fatto Giuridico` → `Diritto Soggettivo`
*   **Properties**: `tipo_condizione` (Enum: `sospensiva`, `risolutiva`)
*   **Example**: `(Avveramento della condizione) -[:condizione_di]-> (Efficacia del contratto)`

## 4. Temporal Versioning and Multivigenza

### 4.1 Conceptual Model

The MERL-T Knowledge Graph implements full support for **multivigenza**, the principle that a single legal norm can have multiple valid versions at different points in time. This is essential for:

- Historical legal research
- Temporal reasoning ("what was the law on date X?")
- Tracking legislative evolution
- Compliance verification at specific dates

### 4.2 Versioning Strategy

Each `Norma` can have multiple `Versione` nodes connected via `ha_versione` relationships. Versions form a temporal chain through `versione_precedente` and `versione_successiva` relationships.

**Key principles:**

1. **Immutability**: Once created, version nodes are never modified (append-only)
2. **Completeness**: Each version contains the complete text as it was at that point in time
3. **Traceability**: Every modification is linked to its source (modifying norm)
4. **Validity periods**: Each version has explicit start and end dates for its validity

### 4.3 Temporal Queries

The model supports queries like:

- "What was the text of Art. 1414 c.c. on 2020-03-15?"
- "Which norms modified Art. 1414 c.c. between 2018 and 2023?"
- "Show me all versions of this article"
- "What changes did Legge n. 123/2023 introduce to this norm?"

### 4.4 Intra-Article Granularity

Versioning applies not just to entire articles but also to individual sub-article elements:

- **Commi** (clauses)
- **Lettere** (letters)
- **Numeri** (numbers)

This allows precise tracking of modifications like: "Legge n. X sostituisce solo l'art. 5, comma 2, lettera b"

## 5. Metadata and Provenance

### 5.1 FAIR Principles Implementation

The MERL-T Knowledge Graph adheres to **FAIR** (Findable, Accessible, Interoperable, Reusable) principles:

#### Findable
- **Persistent identifiers**: ELI URNs, DOIs for datasets
- **Rich metadata**: Extensive node properties
- **Indexed**: Full-text search capabilities
- **Registered**: Entries in legal registries and catalogs

#### Accessible
- **Open protocols**: Standard query interfaces
- **Authentication when needed**: Role-based access for sensitive data
- **Long-term preservation**: Versioned archival storage
- **Multiple formats**: Export to RDF, JSON, XML, CSV

#### Interoperable
- **Standard vocabularies**: ELI, EuroVoc, LKIF
- **Structured formats**: Akoma Ntoso, RDF/OWL
- **Cross-references**: Links to external legal databases
- **APIs**: RESTful and SPARQL endpoints

#### Reusable
- **Clear licenses**: CC-BY 4.0, Open Government License
- **Provenance**: Full tracking of data sources and transformations
- **Documentation**: Comprehensive ontology and API docs
- **Quality metrics**: Validation reports, completeness scores

### 5.2 Provenance Tracking

Every node and relationship should track:

**Creation provenance:**
- `creato_da` (String): System or user who created the entry
- `data_creazione` (Date): Creation timestamp
- `fonte_originale` (String): Original data source (Normattiva, GU, EUR-Lex, etc.)
- `metodo_acquisizione` (Enum): `manuale`, `automatico`, `semi-automatico`

**Modification provenance:**
- `modificato_da` (List[String]): Users/systems who modified
- `data_ultima_modifica` (Date): Last modification timestamp
- `storico_modifiche` (JSON): Complete change history

**Validation provenance:**
- `validato_da` (List[String]): Community validators (RLCF process)
- `data_validazione` (Date): Validation timestamp
- `punteggio_qualita` (Float, 0-1): Quality score from RLCF
- `numero_validazioni` (Integer): Count of validation events

**Lineage:**
- `derivato_da` (String): Parent node if this was derived
- `trasformazioni` (List[String]): Processing steps applied
- `versione_schema` (String): KG schema version used

### 5.3 Quality Metadata

To support RLCF and continuous improvement:

**Completeness indicators:**
- `completezza` (Float, 0-1): How complete is this node's information
- `campi_mancanti` (List[String]): Fields that still need data
- `richness_score` (Float, 0-1): Richness of connections

**Verification status:**
- `verificato` (Boolean): Has this been human-verified
- `richiede_verifica` (Boolean): Flagged for review
- `segnalazioni` (Integer): Number of user reports
- `controverso` (Boolean): Conflicting information exists

**Usage metrics:**
- `accessi` (Integer): Number of times accessed
- `citazioni_interne` (Integer): How many other nodes reference this
- `rilevanza` (Float): Computed relevance score

## 6. Knowledge Graph Population and Validation

### 6.1 Population Strategy

The MERL-T KG is populated through a **hybrid approach**:

#### Automatic Extraction
- **NER (Named Entity Recognition)**: Fine-tuned legal-BERT models for Italian legal texts
- **Pattern-based extraction**: Rule-based systems for structured elements (dates, article numbers, URNs)
- **Relationship extraction**: Machine learning models to identify citations, modifications, and references
- **OCR + NER pipeline**: For historical documents and scanned sources

**Target accuracy**: F1-score ≥ 85% for entity recognition, ≥ 75% for relationship extraction

#### Manual Validation
- **Expert review**: Legal professionals validate automatically extracted information
- **Conflict resolution**: Human arbitration for ambiguous cases
- **Enrichment**: Addition of context, interpretations, and implicit relationships

#### Community Feedback (RLCF)
- **Crowdsourced validation**: ALIS community votes on relationship accuracy
- **Correction proposals**: Users submit fixes and improvements
- **Reputation system**: Validators earn reputation based on accuracy
- **Continuous learning**: Feedback loops improve extraction models

### 6.2 Validation Mechanisms

**Schema validation:**
- **Constraint checking**: Enforce node property requirements
- **Relationship validation**: Ensure source/target node types are correct
- **Cardinality rules**: Check minimum/maximum relationship counts
- **Data type validation**: Verify dates, URNs, enums match expected formats

**Semantic validation:**
- **Consistency checks**: Detect contradictory relationships (e.g., norm both vigente and abrogato)
- **Temporal coherence**: Verify date sequences make sense (data_pubblicazione < data_entrata_in_vigore)
- **Reference integrity**: Ensure cited norms exist and are correctly identified
- **Version continuity**: Check version chains have no gaps

**Continuous monitoring:**
- **Automated tests**: Regular validation runs on the entire graph
- **Anomaly detection**: Flag unusual patterns or outliers
- **Completeness reports**: Track coverage of key legal domains
- **Quality dashboards**: Real-time metrics on KG health

### 6.3 Integration with External Sources

The MERL-T KG integrates with:

- **Normattiva**: Official Italian legislation database
- **EUR-Lex**: EU legal database
- **Gazzetta Ufficiale**: Italian Official Gazette archives
- **Corte Costituzionale**: Constitutional court decisions
- **Cassazione**: Supreme court rulings
- **Legal commentary databases**: Doctrinal sources

**Integration patterns:**
- **Periodic synchronization**: Regular imports of new norms and acts
- **Change detection**: Identify modifications to existing norms
- **Reconciliation**: Merge information from multiple sources
- **Link validation**: Verify external references remain valid

## 7. Future Extensions

### 7.1 Completed Extensions (Now Part of Core Model)

The following extensions have been fully integrated into the core MERL-T KG model:

- ✅ **Modalità Giuridica** (Legal Modality): Full deontic logic with obligations, permissions, prohibitions, powers, immunities, disabilities
- ✅ **Principio Giuridico** (Legal Principle): Constitutional and general principles with balancing
- ✅ **Fatto Giuridico** (Legal Fact): Events with legal consequences, causality, and effects
- ✅ **Diritto Soggettivo** (Subjective Right): Individual rights with full property specification
- ✅ **Interesse Legittimo** (Legitimate Interest): Administrative law interests (Italian-specific)
- ✅ **Responsabilità** (Responsibility): Full liability attribution across all types
- ✅ **Ruolo Giuridico** (Legal Role): Procedural, contractual, family, corporate roles
- ✅ **Regola** (Rule): Inference and interpretive rules for reasoning
- ✅ **Proposizione Giuridica** (Legal Proposition): Propositional content with truth values

### 7.2 Planned Node Types

Future extensions under consideration:

- **Obbligo Specifico** (Specific Obligation): Individual obligation instances linked to contracts or judicial orders
- **Prova / Mezzo di Prova** (Evidence): Evidentiary elements in judicial proceedings
- **Rimedio Giuridico** (Legal Remedy): Available remedies for rights violations
- **Efficacia Giuridica** (Legal Efficacy): Explicit modeling of legal effects as first-class entities
- **Situazione Giuridica Soggettiva** (Subjective Legal Situation): Abstract supertype for rights, obligations, powers, and interests
- **Documento Contrattuale** (Contractual Document): Specific modeling of contracts and agreements
- **Clausola Contrattuale** (Contractual Clause): Individual contract clauses
- **Bene Giuridico** (Legal Good): Protected legal interests (especially for criminal law)

### 7.3 Advanced Reasoning Extensions

Current implementation supports basic reasoning. Future extensions include:

- **Knowledge graph embeddings**: TransE, TransD, DistMult for link prediction
- **Rule-based inference**: Derive implicit relationships through logical rules (leveraging `Regola` nodes)
- **Temporal reasoning**: Advanced temporal queries and validity inference
- **Analogical reasoning**: Identify similar cases and norms for case-based recommendations
- **Counterfactual reasoning**: "What if" scenarios for legislative impact analysis
- **Conflict detection**: Automated identification of normative contradictions
- **Gap analysis**: Detection of regulatory gaps or unaddressed situations

### 7.4 Multilingual Support

Future extensions for multilingual capabilities:

- **Translation nodes**: Link Italian norms to EU multilingual versions
- **Multilingual definitions**: Legal terminology in multiple languages
- **Cross-lingual search**: Query in any language, retrieve relevant Italian norms
- **Harmonization mapping**: Link equivalent concepts across legal systems (e.g., Italian vs. French legal concepts)
- **Comparative law support**: Explicit modeling of equivalences and differences between jurisdictions

### 7.5 Integration with RLCF

The Knowledge Graph serves as the **ground truth** for the MERL-T RLCF process:

- **Triplet extraction**: Context augmentation retrieves KG triplets for LLM input
- **Validation feedback**: LLM outputs are validated against KG facts
- **Continuous enrichment**: Validated LLM outputs add new relationships to KG
- **Quality scoring**: Community feedback updates confidence scores on relationships
- **Adversarial validation**: Detect and correct hallucinations through KG cross-checking

## 8. Summary

The MERL-T Knowledge Graph represents a comprehensive model for Italian legal knowledge. Its design incorporates:

### 8.1 Core Components

- **23 distinct node types** organized across multiple categories:
  - **Legal Documents**: Norma, Versione, Comma/Lettera/Numero, Atto Giudiziario, Dottrina
  - **Legal Entities**: Soggetto Giuridico, Organo Giurisdizionale/Amministrativo, Ruolo Giuridico
  - **Legal Concepts**: Concetto Giuridico, Definizione Legale, Principio Giuridico
  - **Legal Relations**: Diritto Soggettivo, Interesse Legittimo, Modalità Giuridica, Responsabilità
  - **Procedures and Facts**: Procedura, Fatto Giuridico, Caso
  - **Consequences**: Sanzione, Termine
  - **EU Integration**: Direttiva UE, Regolamento UE
  - **Reasoning**: Regola, Proposizione Giuridica

- **65 relationship types** organized into 11 semantic categories:
  - **Structural** (5): containment, versioning, hierarchy
  - **Modification** (9): substitutes, inserts, repeals, suspends, extends, supplements, derogates, consolidates
  - **Semantic** (6): governs, applies_to, defines, sanctions, terms, procedures
  - **Dependency** (3): depends_on, presupposes, specializes
  - **Citation & Interpretation** (3): cites, interprets, comments
  - **European** (3): implements, transposes, complies
  - **Institutional** (3): issued_by, jurisdiction, hierarchy
  - **Case-based** (3): concerns, applies_norm_to_case, precedent
  - **Classification** (2): source, classifies_in
  - **LKIF Modalities** (28): imposes, confers, holder_of, plays_role, responsibility attribution, principles, legal effects, implications, justifications, limitations, protections, violations, compatibility, specification, causality, conditions

### 8.2 Advanced Features

- **Full temporal versioning** with multivigenza support
  - Immutable version nodes
  - Complete temporal chains
  - Intra-article granularity (comma, lettera, numero)

- **Comprehensive provenance tracking**
  - Creation, modification, validation metadata
  - Community feedback integration (RLCF)
  - Quality metrics and confidence scores

- **FAIR principles implementation**
  - Findable: persistent identifiers (ELI, DOI)
  - Accessible: open protocols, multiple formats
  - Interoperable: standard vocabularies and formats
  - Reusable: clear licenses, comprehensive documentation

- **Hybrid population strategy**
  - Automatic extraction (NER, pattern-based, ML)
  - Expert validation
  - Community feedback (RLCF process)
  - Target accuracy: F1 ≥ 85% for entities, ≥ 75% for relations

### 8.3 Italian Legal System Specificity

The model addresses the specific characteristics of the Italian legal system:
- Diritto Soggettivo vs. Interesse Legittimo distinction
- Constitutional and general principles (Principi Giuridici)
- Administrative law structures (TAR, competenze)
- Italian procedure types (processo civile, penale, amministrativo)
- Codice Civile and Codice Penale structural modeling

### 8.4 Integration and Reasoning

- **Knowledge graph embeddings** for link prediction (TransE, TransD)
- **Rule-based inference** for implicit relationship derivation
- **Temporal reasoning** for validity queries at specific dates
- **Analogical reasoning** for case-based recommendations
- **RLCF integration** for continuous improvement and hallucination detection

### 8.5 Technology Agnosticism

This conceptual model is implementation-agnostic and can be realized in:
- **Property graph databases** (Neo4j, ArangoDB)
- **RDF triple stores** (Blazegraph, GraphDB, Virtuoso)
- **Hybrid systems** combining property graphs with SPARQL endpoints
- **Knowledge graph frameworks** (RDFLib, Apache Jena)

The model prioritizes semantic consistency, clarity, and extensibility while supporting the specific needs of the Italian legal domain and the MERL-T RLCF architecture.

## 9. Standards and Ontologies Alignment

This section describes how the MERL-T Knowledge Graph aligns with and maps to international legal standards and ontologies, ensuring interoperability with European and global legal information systems.

### 9.1 LKIF Core Ontology Alignment

The **Legal Knowledge Interchange Format (LKIF) Core** ontology provides 15 modules for legal domain modeling. MERL-T achieves **full alignment** with all modules:

| LKIF Core Module | MERL-T Coverage | MERL-T Node Types | Key Relations |
|------------------|-----------------|-------------------|---------------|
| **1. Top ontology** | **Full** | All base node types with hierarchical organization | `species`, `parte_di`, `contiene` |
| **2. Place, Time, Process** | **Full** | Temporal properties on all nodes, `Procedura`, temporal versioning (`Versione`) | `ha_versione`, `versione_precedente`, `versione_successiva`, `prevede` |
| **3. Role** | **Full** | `Ruolo Giuridico` with powers, duties, and requirements | `riveste_ruolo`, `incompatibile_con` |
| **4. Legal role** | **Full** | `Soggetto Giuridico`, `Ruolo Giuridico` with procedural, contractual, family, corporate roles | `riveste_ruolo`, `titolare_di`, `responsabile_per` |
| **5. Legal action** | **Full** | `Fatto Giuridico` (juridical acts, natural facts, conduct, events), `Atto Giudiziario` | `produce_effetto`, `costitutivo_di`, `estingue`, `causa_di` |
| **6. Expression** | **Full** | `Norma`, `Dottrina`, `Atto Giudiziario`, `Versione` with full text and metadata | `interpreta`, `commenta`, `cita` |
| **7. Proposition** | **Full** | `Proposizione Giuridica` with truth values, modalities, and justifications | `implica`, `contradice`, `giustifica` |
| **8. Legal modality** | **Full** | `Modalità Giuridica` (obligations, permissions, prohibitions, powers, immunities, disabilities) | `impone`, `conferisce`, `limita`, `viola` |
| **9. Norm** | **Full** | `Norma` with extensive properties, versioning, status, efficacy | All modification relations (§3.3), `disciplina`, `applica_a` |
| **10. Rule** | **Full** | `Regola` with premises, consequences, exceptions, and strength | `applica_regola`, `implica`, `giustifica` |
| **11. Modification** | **Full** | 9 specific modification relations (§3.3) plus version tracking | `sostituisce`, `inserisce`, `abroga_totalmente`, `abroga_parzialmente`, `sospende`, `proroga`, `integra`, `deroga_a`, `consolida` |
| **12. Medium** | **Full** | Source and format properties, `fonte`, DOI, URN, licenses | `fonte`, metadata properties |
| **13. Document** | **Full** | All document node types (`Norma`, `Atto Giudiziario`, `Dottrina`, `Direttiva UE`) | `emesso_da`, `fonte`, structural relations |
| **14. Jurisdiction** | **Full** | `Organo Giurisdizionale/Amministrativo` with hierarchies and competences | `emesso_da`, `ha_competenza_su`, `gerarchicamente_superiore` |
| **15. Responsibility** | **Full** | `Responsabilità` (criminal, civil, administrative, disciplinary, strict, negligence, intentional) | `attribuisce_responsabilita`, `responsabile_per` |

#### 9.1.1 Detailed LKIF Module Mapping

**Module 1 - Top Ontology**: Full coverage through typed node hierarchy, `species` relations for taxonomic organization, and structural containment relations (`contiene`, `parte_di`).

**Module 2 - Place, Time, Process**:
- **Time**: Comprehensive temporal properties (`data_pubblicazione`, `data_entrata_in_vigore`, `data_versione`, etc.), versioning system with `Versione` nodes
- **Place**: Territorial properties (`ambito_territoriale`, `competenza_territoriale`, `luogo`)
- **Process**: `Procedura` node with phases, acts, and procedural types

**Module 3 & 4 - Role and Legal Role**: Dedicated `Ruolo Giuridico` node type covering:
- Procedural roles (imputato, creditore, rappresentante)
- Contractual roles
- Family roles
- Corporate roles
- Administrative roles
- With associated powers, duties, requirements, and incompatibilities

**Module 5 - Legal Action**: `Fatto Giuridico` comprehensively models:
- Juridical acts (voluntary, intentional)
- Natural facts (involuntary events)
- Conduct (human behavior)
- Events and states
- With legal effects, licit/illicit distinction, and causality

**Module 7 - Proposition**: `Proposizione Giuridica` captures:
- Descriptive, prescriptive, and evaluative propositions
- Modal qualifications (necessary, possible, contingent)
- Truth values (true, false, indeterminate, contested)
- Justification and context

**Module 8 - Legal Modality**: `Modalità Giuridica` implements full deontic logic:
- **Obligations** (obblighi): What must be done
- **Permissions** (permessi): What may be done
- **Prohibitions** (divieti): What must not be done
- **Powers** (poteri): Capacity to create legal effects
- **Immunities** (immunità): Protection from others' powers
- **Disabilities** (disabilità): Lack of legal capacity

**Module 10 - Rule**: `Regola` node supports:
- Constitutive rules (create legal categories)
- Regulative rules (govern behavior)
- Inference rules (for reasoning)
- Interpretive rules
- With premises (IF), consequences (THEN), exceptions (UNLESS)
- Defeasible and absolute rules

**Module 15 - Responsibility**: `Responsabilità` node provides:
- Criminal responsibility (penale)
- Civil liability (civile)
- Administrative responsibility (amministrativa)
- Disciplinary responsibility (disciplinare)
- Strict liability (oggettiva)
- Negligence (colposa) and intentional (dolosa)
- With constitutive elements, burden of proof, statute of limitations

#### 9.1.2 MERL-T Extensions Beyond LKIF

MERL-T extends LKIF Core with Italian-specific legal concepts:

- **Diritto Soggettivo vs. Interesse Legittimo**: Fundamental distinction in Italian law between subjective rights and legitimate interests in administrative law
- **Principio Giuridico**: Constitutional and general principles as first-class entities
- **Granular structural elements**: Comma, Lettera, Numero for precise intra-article references
- **EU integration**: Direttiva UE, Regolamento UE nodes with implementation relations
- **Temporal versioning**: Full multivigenza support beyond LKIF's basic temporal model
- **Sanctions**: Dedicated node type with aggravating/mitigating circumstances
- **Terms and deadlines**: Explicit temporal reasoning support

### 9.2 Akoma Ntoso Mapping

**Akoma Ntoso** (Architecture for Knowledge-Oriented Management of African Normative Texts) is the international XML standard for legislative documents. The MERL-T KG maintains bidirectional mapping:

| Akoma Ntoso Element | MERL-T KG Node | Notes |
|---------------------|----------------|-------|
| `<act>` | Norma | Top-level document |
| `<article>` | Norma (tipo: articolo) | Individual article |
| `<paragraph>` | Comma | Paragraph/clause |
| `<point>` | Lettera | Lettered point |
| `<subpoint>` | Numero | Numbered sub-point |
| `<quotedStructure>` | Definizione Legale | Quoted definitions |
| `<mod>` | Relazioni di modifica | Modifications |
| `<activeRef>` | cita | Active references |
| `<passiveRef>` | Inverse citations | Passive references |

#### 9.2.1 FRBR Levels

Akoma Ntoso is built on **FRBR** (Functional Requirements for Bibliographic Records) model:

- **Work**: Abstract legal work (e.g., "Codice Civile")
- **Expression**: Specific language version
- **Manifestation**: Format (PDF, XML, HTML)
- **Item**: Specific digital instance

The MERL-T KG models primarily at the **Work** and **Expression** levels, with temporal versions representing different expressions of the same work.

### 9.3 ELI (European Legislation Identifier)

All `Norma` and `Direttiva UE` / `Regolamento UE` nodes include **ELI URNs** in the format:

```
/eli/{jurisdiction}/{type}/{year}/{month}/{day}/{natural_identifier}/{language}
```

**Example:**
```
/eli/it/legge/2023/12/15/123/ita
```

**Benefits of ELI integration:**
- Unique identification across European systems
- Interoperability with EUR-Lex and national databases
- Machine-readable references
- Persistent URLs for digital access
- Cross-border legal information exchange

The `URN` property on norm nodes contains the ELI identifier, enabling automatic linking to official legislative sources.

### 9.4 EuroVoc Thesaurus

The **EuroVoc** multilingual thesaurus provides controlled vocabulary for classification. MERL-T nodes use the `classificazione_tematica` property to link to EuroVoc concepts via the `classifica_in` relation.

**Benefits:**
- Multilingual search and retrieval
- Harmonized classification across EU member states
- Integration with EU institutional systems
- Standardized subject matter categorization
- 27 official EU languages support

**Example mapping:**
- Art. 1414 c.c. → EuroVoc: "1236 - civil law" + "1586 - contracts and obligations"

**Implementation**: The property `classificazione_tematica` contains EuroVoc concept codes, enabling semantic search and cross-lingual discovery.

### 9.5 RDF/OWL Compliance

While the MERL-T KG is technology-agnostic, it can be fully expressed in **RDF/OWL** format:

**Namespace conventions:**
```
@prefix merl: <http://merl-t.org/ontology#>
@prefix eli: <http://data.europa.eu/eli/ontology#>
@prefix lkif: <http://www.estrellaproject.org/lkif-core/>
@prefix eurovoc: <http://eurovoc.europa.eu/>
```

**Node types** map to `owl:Class` declarations
**Properties** map to `owl:DatatypeProperty` or `owl:ObjectProperty`
**Relations** map to `owl:ObjectProperty` with domain and range restrictions

This allows the KG to be published as **Linked Open Data** and queried via standard **SPARQL** endpoints.

### 9.6 Integration with External Legal Databases

The MERL-T KG integrates with major legal information systems through standard identifiers and mappings:

| System | Integration Method | MERL-T Property |
|--------|-------------------|-----------------|
| **Normattiva** (Italian legislation) | ELI URN, official identifiers | `URN`, `estremi` |
| **EUR-Lex** (EU law) | ELI URN, CELEX numbers | `URN`, `estremi` |
| **Gazzetta Ufficiale** (Official Gazette) | Publication references | `data_pubblicazione`, `fonte` |
| **Corte Costituzionale** | Decision numbers | `estremi` on `Atto Giudiziario` |
| **Cassazione** | Case law identifiers | `estremi` on `Atto Giudiziario` |
| **EuroVoc** | Thesaurus codes | `classificazione_tematica` |

### 9.7 Standards Compliance Summary

The MERL-T Knowledge Graph achieves compliance with:

- ✅ **LKIF Core Ontology**: Full coverage of all 15 modules
- ✅ **Akoma Ntoso**: Bidirectional mapping for legislative documents
- ✅ **ELI**: European Legislation Identifier for unique norm identification
- ✅ **EuroVoc**: Multilingual thesaurus for subject classification
- ✅ **FRBR**: Functional Requirements for Bibliographic Records
- ✅ **RDF/OWL**: Semantic Web standards compliance
- ✅ **FAIR Principles**: Findable, Accessible, Interoperable, Reusable

This comprehensive standards alignment ensures that the MERL-T KG can:
- Exchange data with European legal systems
- Support cross-border legal research
- Enable semantic interoperability
- Facilitate legal tech innovation
- Maintain long-term accessibility and preservation
