# Disegno Dettagliato: Architettura della Pipeline di Ingestione e Ragionamento

Questo documento descrive il flusso operativo e logico della pipeline, passo dopo passo, per garantire il massimo rigore metodologico e la piena aderenza allo schema `knowledge-graph.md`.

## Principio Guida

L'architettura si basa sulla **separazione e successiva integrazione** di due flussi di dati:
1.  **Flusso Normativo**: Ingestione e strutturazione della legge scritta (fonte di verità).
2.  **Flusso Interpretativo**: Ingestione e collegamento dei commenti (dottrina, giurisprudenza) alla struttura normativa.

---

## Esempio Guida: Art. 1414 c.c. (Simulazione)

Seguiremo il ciclo di vita delle informazioni relative a questo articolo.

---

### Fase 1: Ingestione Normativa (Agente: Il Normalizzatore - Versione Granulare)

**Obiettivo**: trasformare il payload dell’API (testo, metadati della norma, brocardi, massime, ratio, posizione) in un sotto-grafo MERL-T completo, combinando passi LLM orchestrati e arricchimenti deterministici.

*   **Input Generale**: dati per un singolo articolo (es. `Art. 1414 c.c.`) compresi `article_text`, `norma_data` (tipo atto, numero, URN), `brocardi_info` (brocardi, massime, ratio, spiegazione, position), `queue_position`.

*   **Passo 1.1 – Estrazione Strutturale (LLM Call #1)**
    *   **Input**: solo `article_text`.
    *   **Prompt**: analista strutturale; estrazione di `Norma`, `Comma/Lettera/Numero` con `posizione`, `tipo_segmento`, `testo`.
    *   **Output grafo**: nodi strutturali + relazioni `contiene`/`parte_di`.
    *   **Validazione**: `MATCH (n:Norma {estremi:"Art. 1414 c.c."}) RETURN EXISTS((n)-[:contiene]->(:`Comma/Lettera/Numero`))`.

*   **Passo 1.2 – Estrazione dei Concetti Giuridici (LLM Call #2)**
    *   **Input**: `article_text` + `brocardi_info` (brocardi, ratio, spiegazione).
    *   **Prompt**: ontologo; costruzione di `ConcettoGiuridico` con campi obbligatori (`nome`) e opzionali (`definizione`, `ambito_di_applicazione`), relazione `disciplina` verso la `Norma` (con `properties.certezza`).
    *   **Output**: nodi `ConcettoGiuridico` + relazioni `disciplina`.
    *   **Validazione**: `MATCH (:Norma {estremi:"Art. 1414 c.c."})-[:disciplina]->(:`Concetto Giuridico`) RETURN count(*) > 0`.

*   **Passo 1.3 – Estrazione della Giurisprudenza (LLM Call #3, batching)**
    *   **Input**: elenco `brocardi_info.massime`; ripulito e suddiviso in batch di dimensione configurabile dall’utente (“Massime per batch” in Streamlit).
    *   **Prompt**: massimario; per ogni massima del batch creare `AttoGiudiziario` (con `estremi`, `descrizione`, eventuali `organo_emittente`, `data`) e relazione `interpreta` con `properties.tipo_interpretazione`/`orientamento`.
    *   **Output**: per ogni batch, più `AttoGiudiziario` + relative `interpreta`. Ogni batch viene tracciato con `stage_label` (“Fase 1.3 - Giurisprudenza (batch X)”).
    *   **Validazione**: `MATCH (:Atto Giudiziario)-[:interpreta]->(:Norma {estremi:"Art. 1414 c.c."}) RETURN count(*) > 0`.

*   **Passo 1.4 – Estrazione della Ratio Legis (LLM Call #4)**
    *   **Input**: `brocardi_info.Ratio`.
    *   **Prompt**: filosofo del diritto; costruzione di un `Principio Giuridico` (proprietà `nome`, `descrizione`, `tipo`, `ambito_applicazione`) collegato alla `Norma` via `esprime_principio` con `properties.certezza`/`confidence_score`.
    *   **Output**: nodo `PrincipioGiuridico` + relazione `esprime_principio`.
    *   **Validazione**: `MATCH (:Norma {estremi:"Art. 1414 c.c."})-[:esprime_principio]->(:`Principio Giuridico`) RETURN count(*) > 0`.

*   **Passo 1.5 – Classificazione gerarchica (derivata da `brocardi_info.position`, senza LLM)**
    *   **Input**: stringa `position` (es. `Codice Civile > LIBRO QUARTO - … > Titolo IX … > Articolo 2043`).
    *   **Logica**:
        * parsing deterministico della stringa in segmenti (`Codice`, `Libro`, `Titolo`, `Articolo`);
        * creazione per ciascun livello di un nodo `Concetto Giuridico` con `label "Categoria: …"`, `properties` (`nome`, `schema: "brocardi_position"`, `livello`);
        * collegamento fra livelli consecutivi con relazioni `species` (catena gerarchica);
        * collegamento della `Norma` a ogni livello tramite `classifica_in` (`properties.schema_classificazione: "brocardi_position"`).
    *   **Output**: un `ExtractionResult` “position-derived” (no costo LLM) aggiunto a `all_results`.
    *   **Validazione**: `MATCH (:Norma {estremi:"Art. 1414 c.c."})-[:classifica_in]->(:`Concetto Giuridico {schema:"brocardi_position"}) RETURN count(*) > 0`.

## Fase 2: Ingestione Interpretativa (Agente: L'Esegeta)

**Obiettivo**: Analizzare un testo dottrinale e collegare la sua conoscenza al grafo preesistente.

### Passo 2.1: Input
Un chunk di testo da un manuale: *"La dottrina dominante, rappresentata da G. Verdi nel suo 'Manuale dei Contratti', critica l'interpretazione estensiva dell'Art. 1414 c.c. data da una certa giurisprudenza."*

### Passo 2.2: Arricchimento del Contesto (Graph-Awareness)
Prima di interrogare l'LLM, il sistema esegue una query per recuperare i nodi già esistenti menzionati nel testo.
`MATCH (n) WHERE n.estremi = "Art. 1414 c.c." OR n.nome = "G. Verdi" RETURN n`
Questo permette di fornire all'LLM un contesto più ricco.

### Passo 2.3: Prompt all'"Esegeta"
> "Sei un ricercatore giuridico. Il tuo compito è analizzare il testo seguente e collegarlo alla conoscenza già presente nel nostro grafo.
>
> **Contesto dal Grafo:**
> - Esiste già un nodo: `(n:Norma {estremi: 'Art. 1414 c.c.'})`
>
> **Testo da Analizzare:**
> ```
> {testo_del_chunk}
> ```
>
> **Istruzioni:**
> 1.  Identifica nuove entità non presenti nel contesto (es. un'opera di `Dottrina`).
> 2.  Focalizzati sull'estrazione della **relazione principale** tra le nuove entità e quelle esistenti. Che tipo di argomentazione viene fatta? È un commento (`commenta`), una critica (`critica`), un'esemplificazione (`esemplifica`)?
> 3.  Produci un JSON con solo i nuovi nodi e le nuove relazioni."

### Passo 2.4: Output JSON dell'LLM
```json
{
  "entities": [
    {"type": "Dottrina", "label": "Manuale dei Contratti di G. Verdi", "properties": {"titolo": "Manuale dei Contratti", "autore": "G. Verdi"}}
  ],
  "relationships": [
    {"source_label": "Manuale dei Contratti di G. Verdi", "target_label": "Art. 1414 c.c.", "type": "critica", "confidence": 0.9}
  ]
}
```

### Passo 2.5: Azione sul Grafo
Il `Neo4jWriter` esegue `MERGE` sul nuovo nodo `Dottrina` e `MERGE` sulla nuova relazione `critica`, collegandola al nodo `Norma` **già esistente**.

### Passo 2.6: Query di Validazione (Test)
`MATCH (:Dottrina {autore:"G. Verdi"})-[r:critica]->(:Norma {estremi:"Art. 1414 c.c."}) RETURN count(r) > 0`
**Risultato Atteso**: `true`.

---

## Fase 3: Arricchimento Tassonomico (Agente: Il Tassonomista)

**Obiettivo**: Creare una gerarchia tra i concetti giuridici per abilitare un ragionamento più profondo.

### Passo 3.1: Input
L'agente viene eseguito periodicamente. Esegue una query per trovare concetti potenzialmente correlati ma non ancora collegati gerarchicamente.
`MATCH (c:ConcettoGiuridico) WHERE NOT (c)-[:species]-() AND NOT ()-[:species]->(c) RETURN c.nome`
**Risultato Query**: `["Simulazione", "Simulazione Assoluta", "Simulazione Relativa", "Negozio Giuridico", "Buona Fede"]`

### Passo 3.2: Prompt al "Tassonomista"
> "Sei un ontologo del diritto. Data la seguente lista di concetti giuridici, identifica e restituisci **solo** le relazioni gerarchiche di tipo `species` (un concetto è un tipo specifico di un altro) o `parte_di`.
>
> **Lista Concetti:**
> `["Simulazione", "Simulazione Assoluta", "Simulazione Relativa", "Negozio Giuridico", "Buona Fede"]`
>
> **Formato output:** `[{"source": "Nome Concetto Specifico", "target": "Nome Concetto Generale", "type": "species"}]`"

### Passo 3.3: Output JSON dell'LLM
```json
[
  {"source": "Simulazione Assoluta", "target": "Simulazione", "type": "species"},
  {"source": "Simulazione Relativa", "target": "Simulazione", "type": "species"},
  {"source": "Simulazione", "target": "Negozio Giuridico", "type": "species"}
]
```

### Passo 3.4: Azione sul Grafo
Uno script dedicato prende queste relazioni e le crea nel grafo usando `MERGE`, costruendo la gerarchia.

### Passo 3.5: Query di Validazione (Test)
`MATCH (:ConcettoGiuridico {nome:"Simulazione Assoluta"})-[:species]->(:ConcettoGiuridico {nome:"Simulazione"}) RETURN count(*) > 0`
**Risultato Atteso**: `true`.

---

## 4. Flusso di Supervisione dell'Esperto

In ogni fase, le estrazioni dell'LLM con `confidence < 0.85` (o un'altra soglia) non vengono scritte direttamente, ma accodate in una "coda di revisione". L'interfaccia Streamlit presenterà queste estrazioni all'esperto di dominio, che potrà:
- **Approvare**: L'informazione viene scritta nel grafo.
- **Correggere**: Modifica l'entità o la relazione prima di approvare.
- **Rifiutare**: L'informazione viene scartata.

Le decisioni dell'esperto vengono salvate e usate per creare un "golden dataset" per il futuro fine-tuning degli agenti LLM.
