--
-- PostgreSQL database dump
--

\restrict rf4YwGebEgYb9aZpL99uBQKMTvG6V2oBIIgKczX0c5AvF5bEVYrJXr2rBBF3DP0

-- Dumped from database version 14.19 (Homebrew)
-- Dumped by pg_dump version 14.19 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Data for Name: digital_assets; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO public.digital_assets VALUES (1, 'phd-diagram.png', 'image/png', 's3://testamentary-traces/diagrams/phd-diagram.png', 245000, '{"desc": "diagram"}', '2026-01-18 10:21:04.304719');
INSERT INTO public.digital_assets VALUES (2, 'cybernetic-loops.png', 'image/png', 's3://diagrams/cybernetic-loops.png', 189000, '{}', '2026-01-18 10:23:47.764391');
INSERT INTO public.digital_assets VALUES (3, 'evidence-graph.png', 'image/png', 's3://visualizations/evidence-graph.png', 312000, '{}', '2026-01-18 10:23:47.764391');
INSERT INTO public.digital_assets VALUES (4, 'temporal-drift.png', 'image/png', 's3://charts/temporal-drift.png', 156000, '{}', '2026-01-18 10:23:47.764391');
INSERT INTO public.digital_assets VALUES (5, 'system-arch.png', 'image/png', 's3://diagrams/system-arch.png', 278000, '{}', '2026-01-18 10:23:47.764391');
INSERT INTO public.digital_assets VALUES (6, 'methodology.pdf', 'application/pdf', 's3://papers/methodology.pdf', 1240000, '{}', '2026-01-18 10:23:47.764391');
INSERT INTO public.digital_assets VALUES (7, 'analysis.pdf', 'application/pdf', 's3://papers/analysis.pdf', 980000, '{}', '2026-01-18 10:23:47.764391');


--
-- Data for Name: document_embeddings; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO public.document_embeddings VALUES (1, 'chunk-001', 'Sample document content about testamentary traces', 'research-paper-1.pdf', '{"type": "research"}', '2026-01-18 10:05:53.186708');


--
-- Data for Name: experiments; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO public.experiments VALUES (1, 'exp-001', 'Baseline RAG', 'Initial baseline', 'granite-4.0-h-small', '{"temperature": 0.7}', '{"accuracy": 0.85}', NULL, '2026-01-18 10:06:16.015861', '2026-01-18 10:06:16.015861');


--
-- Data for Name: research_sessions; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO public.research_sessions VALUES (1, 'session-001', 'What are testamentary traces?', 'Testamentary traces refer to archival residues, evidential chains, and interpretive traces that can be surfaced across the corpus.', '{"duration": 45}', '2026-01-18 10:06:14.705238');


--
-- Name: digital_assets_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.digital_assets_id_seq', 8, true);


--
-- Name: document_embeddings_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.document_embeddings_id_seq', 7, true);


--
-- Name: experiments_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.experiments_id_seq', 2, true);


--
-- Name: research_sessions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.research_sessions_id_seq', 3, true);


--
-- PostgreSQL database dump complete
--

\unrestrict rf4YwGebEgYb9aZpL99uBQKMTvG6V2oBIIgKczX0c5AvF5bEVYrJXr2rBBF3DP0

