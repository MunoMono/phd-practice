# Statement of Work --- Turin Experiment Data Visualisation Research Suite

**Project:** Turin Experiment\
**Document type:** Statement of Work (SoW)\
**Version:** v0.1\
**Date:** 11 September 2026\
**Status:** Proposed development scope

## 1. Purpose

This Statement of Work defines the next development phase for the Turin
Experiment's **Data visualisation** area.

The existing **Semantic Atlas** provides a UMAP projection of the
archival corpus. The purpose of this phase is not to add visualisation
for its own sake, but to develop a small suite of complementary research
interfaces through which a researcher can interrogate semantic
proximity, archival structure, temporal change and critically framed
questions.

The governing principle is:

> **Every visualisation should provoke an archival question or make an
> evidential condition visible.**

The visualisations are exploratory research instruments. Spatial
proximity, clustering, absence or apparent movement must not be
represented as historical proof.

## 2. Proposed information architecture

The **Data visualisation** submenu will contain five research views:

-   **Semantic atlas** --- existing
-   **Semantic neighbourhoods** --- new
-   **Comparative views** --- new
-   **Temporal and documentary change** --- new
-   **Critical Inquiry** --- new

Conceptually:

-   **Atlas:** Where is everything?
-   **Neighbourhoods:** What is near this?
-   **Comparative:** How do structures differ?
-   **Temporal:** How does it change?
-   **Critical:** What happens when I deliberately look from this
    perspective?

The four new views should be implemented as separate JSX pages using the
existing Turin Experiment frontend architecture and shared components
where appropriate.

## 3. Existing Semantic Atlas

### 3.1 Scope

The existing Semantic Atlas remains the corpus-level overview.

It should continue to present the UMAP projection as a designed
representation of the modelled corpus rather than a neutral map of
historical reality.

### 3.2 Existing epistemic framing

Retain the current warning:

> **Spatial proximity is a prompt for archival investigation, not proof
> of relation.**

Retain visible sampling/completeness information such as:

-   visible point count;
-   indication when the view is not a complete archive map;
-   embedding/projection provenance where available.

### 3.3 Future shared capabilities

Where useful, the Atlas may later consume shared components developed
for the new pages, including point inspection, metadata filtering,
outlier highlighting and apparatus controls. This SoW does not require
redesigning the existing Atlas as a prerequisite for the four new pages.

------------------------------------------------------------------------

## 4. Semantic Neighbourhoods

### 4.1 Research purpose

This view asks:

> **What is close to this archival trace, and why might that proximity
> deserve investigation?**

It turns semantic proximity into an inspectable evidence pathway rather
than simply displaying points on a projection.

### 4.2 Entry points

The researcher should be able to initiate a neighbourhood from one or
more supported entities:

-   archival chunk or passage;
-   document;
-   person;
-   project;
-   phrase;
-   researcher-supplied concept.

### 4.3 Core functions

The page should support:

-   selection of a focal archival item;
-   nearest-neighbour retrieval using the evaluated embedding
    representation;
-   configurable neighbourhood sizes such as 10, 25 and 50;
-   similarity/proximity values;
-   local visualisation of the selected item and its neighbours;
-   optional connecting edges from the focal item to neighbours;
-   source title;
-   page or passage reference;
-   date where available;
-   source/document type;
-   associated people;
-   associated projects or job numbers where available;
-   direct navigation back to inspectable source evidence.

### 4.4 Evidential requirement

The interface must privilege the underlying archival passages over
generated explanation.

A neighbourhood must never be presented as evidence that the items are
historically related. It identifies computational proximity that may
warrant archival investigation.

------------------------------------------------------------------------

## 5. Comparative Views

### 5.1 Research purpose

This view asks:

> **What changes when the same corpus is examined through different
> archival or authority-data categories?**

It should allow comparison between machine-derived semantic structure
and known archival metadata structure.

### 5.2 Comparison dimensions

Subject to data availability, controls should support comparison or
colouring by:

-   date or period;
-   document/source type;
-   person;
-   project;
-   job number;
-   fonds;
-   archive-resolved versus legacy status;
-   teaching, research or administrative classification where such
    classification is supported by the data.

### 5.3 Core functions

The page should support:

-   metadata colour overlays;
-   filtering/highlighting of one category against the remaining corpus;
-   side-by-side views where methodologically useful;
-   person-versus-person comparison;
-   project-versus-project comparison;
-   source-type comparison;
-   later extension to archival-document versus oral-history comparison.

### 5.4 Research value

This view should help investigate questions such as:

-   Do semantic regions correspond to archival categories?
-   Are particular people concentrated within specific semantic
    territories?
-   Do projects cross otherwise distinct semantic regions?
-   Do different source types construct noticeably different
    representations of DDR activity?

The visualisation itself must not answer these questions automatically.

------------------------------------------------------------------------

## 6. Temporal & Documentary Change

### 6.1 Research purpose

This view asks:

> **How does the semantic and documentary character of the corpus change
> through time?**

### 6.2 Core functions

Subject to sufficiently reliable date metadata, the page should support:

-   year and/or decade filtering;
-   a time slider;
-   progressive or animated corpus views where useful;
-   comparison of earlier and later periods;
-   semantic trails for selected people, projects or concepts;
-   identification of first/early appearances of concepts in the
    digitised corpus;
-   visualisation of changing concentrations of documentary material;
-   inspection of the archival evidence underlying any apparent temporal
    movement.

### 6.3 Semantic trails

A semantic trail may connect chronologically ordered traces associated
with a selected person, project or concept.

Such a trail represents change in the **documentary/semantic
representation available in the corpus**. It must not be labelled as
proof of intellectual, biographical or institutional development without
independent historical interpretation.

------------------------------------------------------------------------

## 7. Critical Inquiry

### 7.1 Research purpose

This view provides a deliberately researcher-led mode of computational
inquiry.

It asks:

> **What becomes visible when the archive is examined through an
> explicitly chosen critical perspective?**

The theoretical or critical lens is supplied by the researcher. The
computational system assists in locating material for investigation.

### 7.2 Candidate critical lenses

Initial interface options may include:

-   feminist inquiry;
-   labour and authorship;
-   marginalised voices;
-   institutional hierarchy;
-   teaching and care;
-   centre and periphery;
-   custom researcher-defined inquiry.

These labels should be treated as research starting points rather than
machine classifications of archival material.

### 7.3 Concept probe

The page should provide a researcher-controlled concept/proposition
input.

Examples might include:

-   `unacknowledged technical labour`
-   `institutional power`
-   `gendered work`
-   `professional status`
-   `scientific legitimacy`
-   `care`
-   `pedagogy`

The supplied phrase should be embedded using the same compatible
semantic embedding space as the corpus, enabling the system to identify
archival passages nearest to the conceptual probe.

### 7.4 Results and inspection

The interface should enable the researcher to:

-   inspect nearest passages;
-   see their location or distribution in semantic space;
-   identify associated people, projects, dates and source types where
    supported;
-   investigate dense and sparse areas;
-   identify possible representational asymmetries;
-   navigate directly to underlying archival evidence.

### 7.5 Required epistemic statement

The page should visibly communicate a statement substantially equivalent
to:

> **Critical lens supplied by researcher. Computational proximity
> indicates material for investigation, not confirmation of the
> proposition.**

### 7.6 Generated interpretation

The first response to a critical probe should be evidence and structure,
not an automatically generated Qwen conclusion.

Model-assisted interpretation may be offered subsequently, but it must
remain visibly distinct from archival evidence and researcher
interpretation.

------------------------------------------------------------------------

## 8. Shared Exploratory Modes

The following capabilities should be implemented as reusable
modes/components rather than separate top-level pages where practical:

-   all points;
-   dense regions;
-   outliers;
-   sparse regions;
-   point selection;
-   source inspection;
-   metadata filters;
-   provenance display.

Outlier status or sparse semantic space must not automatically be
equated with historical marginalisation or archival absence. Such
patterns are prompts for investigation and must be interpreted in
relation to corpus composition and archival survival.

## 9. Apparatus and Projection Controls

UMAP and embedding configuration should be inspectable without
dominating the primary research interface.

An apparatus/method controls panel or drawer should expose, where
applicable:

-   embedding model and version;
-   embedding dimensionality;
-   UMAP parameters;
-   number of neighbours;
-   minimum distance;
-   random seed;
-   corpus/sample size;
-   projection generation date;
-   corpus version;
-   relevant software/runtime provenance.

The current evaluated semantic embedding experiment should remain
clearly distinguished from the LLM:

**BAAI/bge-small-en-v1.5 · 384 dimensions**

The embedding model is not Qwen and must not be presented as such.

## 10. Projection Robustness / "Challenge This Map"

A shared advanced function should allow the researcher to investigate
whether visually persuasive structures remain stable under changes to
the computational projection.

Where feasible, controls should support comparison across:

-   UMAP random seed;
-   neighbour count;
-   minimum distance;
-   sample versus full eligible corpus;
-   embedding/projection version.

The purpose is methodological scrutiny rather than optimisation for the
most visually compelling map.

The interface should encourage the question:

> **Does this apparent relationship survive when the computational
> representation is perturbed?**

## 11. Architectural and Research Constraints

Development must preserve the distinction between:

1.  archival/source evidence;
2.  archival and database authority assertions;
3.  semantic embedding/projection outputs;
4.  model-generated interpretation;
5.  researcher interpretation and assessment.

Embedding-based visual analytics must remain distinguishable from the
formal question-led retrieval pipeline.

The visualisation suite must not silently alter the evidence supplied to
formal research runs or change the governed retrieval contract.

No visual proximity, cluster, outlier, sparse region, concept match or
semantic trail should be described as historical fact solely because it
appears in the computational representation.

## 12. Interaction Principle

Across the suite, the preferred research interaction is:

> **See → interrogate → inspect → compare → return to evidence.**

Where generative AI is introduced, the preferred sequence is:

> **Researcher inquiry → computational pattern/proximity → archival
> evidence inspection → optional model assistance → researcher
> interpretation.**

This ensures that Qwen does not become the first or authoritative
interpreter of exploratory visual patterns.

## 13. Relationship to Question-led Inquiry

The Data visualisation suite complements rather than replaces the
existing research interrogation workflow.

The instrument therefore supports parallel forms of inquiry:

  -----------------------------------------------------------------------
  Mode                    Starting point          Computational role
  ----------------------- ----------------------- -----------------------
  Question-led inquiry    Known historical        Governed retrieval and
                          question                evidence-linked model
                                                  interpretation

  Exploratory semantic    Patterns not yet known  Embeddings, UMAP and
  inquiry                                         visual investigation

  Critical inquiry        Researcher-supplied     Semantic probing of
                          theoretical lens        presence, absence,
                                                  hierarchy and
                                                  representation
  -----------------------------------------------------------------------

The distinction between these modes should remain visible in both the UI
and research documentation.

## 14. Suggested Development Order

Development should proceed incrementally.

**Phase 1 --- Semantic Neighbourhoods**

Implement focal-item selection, nearest neighbours, similarity/proximity
display and archival evidence/provenance inspection.

**Phase 2 --- Comparative Views**

Add reusable metadata colouring/filtering and comparison capabilities,
drawing on existing archival and authority metadata.

**Phase 3 --- Temporal & Documentary Change**

Introduce temporal filtering and semantic trails after date coverage and
behaviour have been validated.

**Phase 4 --- Critical Inquiry**

Introduce researcher-defined critical lenses and concept probes using
the established embedding space.

**Phase 5 --- Robustness and cross-view refinement**

Add projection comparison, outlier/sparse-region modes and shared
"Challenge This Map" apparatus controls.

## 15. Acceptance Criteria

This phase is complete when:

-   the four new Data visualisation pages are available through the
    application submenu;
-   each page has a clearly stated research purpose;
-   semantic outputs can be traced back to inspectable archival
    evidence;
-   relevant provenance is visible;
-   metadata comparison uses authoritative data where available;
-   concept probes are visibly researcher supplied;
-   critical inquiry does not automatically convert proximity into a
    historical claim;
-   UMAP/embedding apparatus is inspectable;
-   Qwen and the semantic embedding model remain explicitly distinct;
-   exploratory visualisation does not modify the formal governed
    retrieval contract;
-   uncertainty, sampling and representational limitations are visible
    in the UI;
-   shared components are reused where appropriate rather than
    duplicating visualisation logic;
-   existing Semantic Atlas behaviour is not regressed.

## 16. Out of Scope

Unless separately approved, this SoW does not require:

-   replacing PostgreSQL FTS as the principal formal retrieval method;
-   activating embedding retrieval within formal research runs;
-   treating UMAP clusters as canonical classifications;
-   automatically generating historical conclusions from clusters;
-   fabricating missing embeddings, metadata or archival evidence;
-   redesigning unrelated areas of the Turin Experiment;
-   altering the frozen formal research corpus or approved question
    register.

## 17. Research Outcome

The intended outcome is not simply a richer set of charts.

The Data visualisation suite should enable the Turin Experiment to
investigate several complementary questions about computational archival
practice:

-   Where is evidence for a question?
-   What unexpected structures become visible?
-   What lies semantically near a selected archival trace?
-   How do those structures differ across documentary categories?
-   How does the modelled corpus change through time?
-   What becomes visible when a researcher deliberately approaches the
    archive through a critical lens?
-   Which apparent computational structures remain persuasive after the
    representation itself is challenged?

The suite therefore develops UMAP and semantic visualisation as an
**exploratory archival research practice**, while retaining provenance,
uncertainty and researcher interpretation as governing methodological
principles.
