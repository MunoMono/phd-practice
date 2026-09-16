"""V3.10 query-anchor constrained selection over unchanged V3.2 candidates."""
from __future__ import annotations
import re
from collections import defaultdict
from typing import Any
from app.services.turin_retrieval_v39_documentary_anchors import ADEQUACY

EVENT_TERMS = {"close", "closed", "closure", "merge", "merged", "decision", "resolved", "resolution"}
OBJECT_TERMS = {"console", "ergonomics", "teaching", "learning", "students", "computing", "computer", "research"}

class TurinRetrievalV310QueryAnchors:
    @staticmethod
    def analyze(question: str) -> list[dict[str, Any]]:
        projects = re.findall(r"\b(?:job|project)\s+(?:number\s+)?(\d+)\b", question, re.I)
        asset_ids = re.findall(r"\barchival\s+asset\s+(\d+)\b", question, re.I)
        people = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", question)
        people = [person for person in people if person not in {"Design Education", "Design Research", "General Education"}]
        lower = question.lower()
        anchors = [{"raw_text": f"Job {item}", "normalized_value": item, "anchor_type": "EXACT_PROJECT_ID", "required_or_preferred": "required"} for item in projects]
        anchors += [{"raw_text": f"archival asset {item}", "normalized_value": item, "anchor_type": "EXACT_ASSET_ID", "required_or_preferred": "required"} for item in asset_ids]
        anchors += [{"raw_text": person, "normalized_value": person.lower(), "anchor_type": "PERSON", "required_or_preferred": "required"} for person in people]
        if len(people) >= 2: anchors.append({"raw_text": " + ".join(people[:2]), "normalized_value": "|".join(person.lower() for person in people[:2]), "anchor_type": "PERSON_PAIR", "required_or_preferred": "required"})
        for label, value in (("Design Education Unit", "design education unit"), ("Department of Design Research", "department of design research"), ("DDR", "ddr")):
            if value in lower: anchors.append({"raw_text": label, "normalized_value": value, "anchor_type": "INSTITUTION", "required_or_preferred": "required"})
        for term in sorted(EVENT_TERMS & set(re.findall(r"[a-z]+", lower))): anchors.append({"raw_text": term, "normalized_value": term, "anchor_type": "EVENT_ACTION", "required_or_preferred": "required"})
        for term in sorted(OBJECT_TERMS & set(re.findall(r"[a-z]+", lower))): anchors.append({"raw_text": term, "normalized_value": term, "anchor_type": "OBJECT_ACTIVITY", "required_or_preferred": "preferred"})
        return anchors

    @staticmethod
    def build(candidates: list[dict[str, Any]], question: str, required_facets: list[str], source_limit: int = 8) -> dict[str, Any]:
        anchors = TurinRetrievalV310QueryAnchors.analyze(question)
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for candidate in candidates: groups[str(candidate.get("canonical_asset_id") or candidate["document_id"])].append(candidate)
        profiles = [TurinRetrievalV310QueryAnchors._profile(key, rows, anchors, required_facets) for key, rows in groups.items()]
        ranked = sorted(profiles, key=TurinRetrievalV310QueryAnchors._key, reverse=True)
        for rank, profile in enumerate(ranked, 1): profile["source_profile_rank"] = rank
        selected=[]; covered=set()
        for profile in ranked:
            if len(selected) >= source_limit: profile["selection_status"]="SOURCE_POOL_TRUNCATION"; continue
            if not profile["required_anchor_satisfied"]:
                profile["selection_status"]="NOMINATED_BUT_ANCHOR_MISMATCH"; continue
            gain=set(profile["source_facet_union"])-covered
            if selected and not gain and not profile["documentary_anchor"]["is_strong_principal_anchor"]:
                profile["selection_status"]="NOT_SELECTED_NO_DOCUMENTARY_GAIN"; continue
            profile["selection_status"]="SELECTED"; selected.append(profile); covered.update(profile["source_facet_union"])
        bundles=[TurinRetrievalV310QueryAnchors._bundle(profile) for profile in selected]
        return {"query_anchors":anchors,"source_profiles":ranked,"evidence_bundles":bundles,"final_documentary_passages":[p for b in bundles for p in b["documentary_evidence"]],"retrieval_adequacy":"RETRIEVAL_SUFFICIENT" if bundles else "RETRIEVAL_INSUFFICIENT"}

    @staticmethod
    def _profile(source_id: str, rows: list[dict[str, Any]], anchors: list[dict[str, Any]], required_facets: list[str]) -> dict[str, Any]:
        ranked=sorted(rows,key=lambda p:(-p["passage_score"],p.get("chunk_index",0),str(p["chunk_id"])))
        best=ranked[0]; text=" ".join(str(p.get("chunk_text","")).lower() for p in ranked); metadata=" ".join(str(best.get(k,"")).lower() for k in ("title","filename","asset_pid","archive_record_pid")); graph=" ".join(str(x).lower() for x in best.get("authority_graph_signals",{}).get("authority_ids",[]))
        details=[]
        for anchor in anchors:
            value=anchor["normalized_value"]
            if anchor["anchor_type"]=="EXACT_PROJECT_ID": matched=bool(re.search(rf"\b(?:job|project)\s+(?:number\s+)?{re.escape(value)}\b",text+" "+metadata) or value in graph)
            elif anchor["anchor_type"]=="EXACT_ASSET_ID": matched=value == str(best.get("asset_pid") or "")
            elif anchor["anchor_type"]=="PERSON_PAIR": matched=all(person in text for person in value.split("|"))
            else: matched=value in text
            details.append({**anchor,"matched":matched})
        required=[item for item in details if item["required_or_preferred"]=="required"]
        matched=sum(item["matched"] for item in required); components=best.get("passage_score_components",{}); facets=set().union(*(set(p.get("facet_coverage",[])) for p in ranked))
        pair=next((item["matched"] for item in details if item["anchor_type"]=="PERSON_PAIR"),None)
        primary=set(required_facets)&set(best.get("facet_coverage",[])); adequacy=ADEQUACY.get(best.get("passage_adequacy"),0)
        return {"canonical_asset_id":source_id,"document_id":best["document_id"],"title":best.get("title"),"archive_record_pid":best.get("archive_record_pid"),"attached_media_pid":best.get("asset_pid"),"asset_pid":best.get("asset_pid"),"source_type":best.get("source_type"),"source_nomination": {"lanes":best.get("lane_nominations",[]),"signals":best.get("source_signals",{}),"authority_graph_signals":best.get("authority_graph_signals",{})},"top_passages":ranked,"required_anchors_total":len(required),"required_anchors_matched":matched,"preferred_anchors_total":len(details)-len(required),"preferred_anchors_matched":sum(i["matched"] for i in details if i["required_or_preferred"]=="preferred"),"anchor_coverage_ratio":matched/max(len(required),1),"anchor_match_details":details,"required_anchor_satisfied":matched==len(required),"person_pair_state":"BOTH_PERSONS_SAME_PASSAGE" if pair else "NEITHER" if pair is not None else None,"source_facet_union":sorted(facets),"best_passage_score":best["passage_score"],"best_passage_adequacy":best.get("passage_adequacy"),"additional_useful_passages":sum(ADEQUACY.get(p.get("passage_adequacy"),0)>0 for p in ranked)-1,"documentary_anchor":{"best_chunk_id":best["chunk_id"],"passage_adequacy":best.get("passage_adequacy"),"principal_facet_coverage":sorted(primary),"anchor_score":round(adequacy*100+len(primary)*5+best["passage_score"],4),"is_strong_principal_anchor":adequacy==3 and bool(primary)},"selection_status":"NOT_EVALUATED","source_profile_rank":None}

    @staticmethod
    def _key(p:dict[str,Any])->tuple[Any,...]:
        return (int(p["required_anchor_satisfied"]), p["required_anchors_matched"], int(p["person_pair_state"]=="BOTH_PERSONS_SAME_PASSAGE"), p["preferred_anchors_matched"], ADEQUACY.get(p["best_passage_adequacy"],0), len(p["documentary_anchor"]["principal_facet_coverage"]), p["best_passage_score"],p["additional_useful_passages"],sum(p["source_nomination"]["signals"].values()),p["canonical_asset_id"])

    @staticmethod
    def _bundle(profile:dict[str,Any])->dict[str,Any]:
        evidence=[profile["top_passages"][0]]
        for passage in profile["top_passages"][1:]:
            if ADEQUACY.get(passage.get("passage_adequacy"),0)>=2 and set(passage.get("facet_coverage",[]))-set(evidence[0].get("facet_coverage",[])): evidence.append(passage); break
        return {"source":{k:v for k,v in profile.items() if k!="top_passages"},"documentary_evidence":evidence,"evidential_limit":"Anchor matches demonstrate retrieval scope, not a historical conclusion."}
