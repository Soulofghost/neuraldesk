import re
import math
import json
import logging
from typing import List, Dict, Any, Optional
from app.engine.embeddings import vector_engine

logger = logging.getLogger("neuraldesk.intelligence")

class DocumentIntelligence:
    def __init__(self):
        self.stop_words = {
            "the", "and", "a", "an", "in", "on", "of", "to", "for", "with", "at", "by", "from",
            "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does",
            "did", "but", "if", "or", "because", "as", "until", "while", "that", "this", "these",
            "those", "then", "so", "than", "too", "very", "can", "will", "just", "should", "now"
        }

    def summarize(self, text: str, max_sentences: int = 4) -> Dict[str, Any]:
        """
        Calculates sentence salience based on vector centrality and lexical frequency.
        """
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        if len(sentences) <= max_sentences:
            return {
                "summary": text.strip(),
                "sentence_count": len(sentences),
                "key_takeaways": [s.strip() for s in sentences if len(s.strip()) > 15]
            }

        # Calculate vector for full document
        doc_vector = vector_engine.embed(text)
        
        # Score each sentence
        scored = []
        for i, s in enumerate(sentences):
            s_clean = s.strip()
            if len(s_clean.split()) < 5:
                continue
            s_vec = vector_engine.embed(s_clean)
            sim = vector_engine.cosine_similarity(doc_vector, s_vec)
            # Position bias: early sentences often carry thesis
            pos_bonus = 0.15 if i < 3 else (0.1 if i == len(sentences) - 1 else 0.0)
            score = sim + pos_bonus
            scored.append((score, i, s_clean))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = sorted(scored[:max_sentences], key=lambda x: x[1])
        
        summary_text = " ".join([t[2] for t in top])
        takeaways = [t[2] for t in scored[:3]]

        return {
            "summary": summary_text,
            "sentence_count": len(sentences),
            "key_takeaways": takeaways
        }

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Identifies capitalized terms, technical acronyms, protocol names, and technologies.
        """
        # Tech acronyms: e.g. Raft, Paxos, HNSW, SQLite, WAL, API, HTTP, REST, CSS, SQL, JWT
        acronyms = set(re.findall(r'\b[A-Z]{2,10}\b', text))
        
        # Title case proper nouns / entities: e.g. Distributed Systems, Byzantine Fault, Vector Engine
        proper_phrases = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        filtered_proper = [p for p in proper_phrases if p.lower() not in self.stop_words and len(p) > 3]

        # Categorize into concepts, systems, and protocols
        entities = {
            "technologies": sorted(list(acronyms))[:12],
            "concepts": sorted(list(set(filtered_proper)))[:15],
            "entities_found": len(acronyms) + len(set(filtered_proper))
        }
        return entities

    def extract_keywords(self, text: str, top_k: int = 8) -> List[Dict[str, Any]]:
        words = re.findall(r'\b[a-zA-Z]{3,20}\b', text.lower())
        freq: Dict[str, int] = {}
        for w in words:
            if w not in self.stop_words:
                freq[w] = freq.get(w, 0) + 1

        sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [{"keyword": w, "frequency": count} for w, count in sorted_words[:top_k]]

    def extract_action_items(self, text: str) -> List[str]:
        """
        Detects imperative sentences, action items, recommendations, and tasks.
        """
        action_patterns = [
            r'(?:must|should|need to|ensure|implement|configure|deploy|validate|review|execute)\s+[^.!?]+[.!?]',
            r'(?:action item|todo|task):\s*[^.!?\n]+',
            r'^[*-]\s*(?:\[ \]\s*)?(?:implement|create|update|fix|check|add|verify)\s+[^.!?\n]+'
        ]
        items = []
        for pat in action_patterns:
            matches = re.findall(pat, text, re.IGNORECASE | re.MULTILINE)
            for m in matches:
                clean_m = m.strip().lstrip("*- ").strip()
                if clean_m and clean_m not in items:
                    items.append(clean_m[:180])
        return items[:8]

    def answer_question(self, question: str, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Retrieval-Augmented Question Answering grounded strictly in document chunks.
        Returns synthesized response with explicit passage citations.
        """
        if not chunks:
            return {
                "answer": "No document passages are available to evaluate this question.",
                "citations": [],
                "confidence": 0.0
            }

        q_vec = vector_engine.embed(question)
        q_terms = set(question.lower().split())

        scored_chunks = []
        for c in chunks:
            content = c["content"]
            emb = c.get("embedding")
            if isinstance(emb, str):
                try:
                    emb = json.loads(emb)
                except Exception:
                    emb = []
            
            vec_sim = vector_engine.cosine_similarity(q_vec, emb) if emb else 0.0
            content_lower = content.lower()
            term_overlap = sum(1 for t in q_terms if t in content_lower) / max(1, len(q_terms))
            score = (0.75 * vec_sim) + (0.25 * term_overlap)
            scored_chunks.append({
                "chunk_index": c.get("chunk_index", 0),
                "content": content,
                "score": score
            })

        scored_chunks.sort(key=lambda x: x["score"], reverse=True)
        top_chunks = scored_chunks[:3]

        if not top_chunks or top_chunks[0]["score"] < 0.08:
            return {
                "answer": f"Based on the indexed document context, no sufficiently relevant passages directly answer '{question}'.",
                "citations": [],
                "confidence": 0.0
            }

        citations = []
        answer_parts = []
        for idx, top in enumerate(top_chunks):
            chunk_num = top["chunk_index"] + 1
            citation_id = f"Chunk #{chunk_num}"
            citations.append({
                "citation": citation_id,
                "score": round(top["score"], 3),
                "snippet": top["content"][:200] + ("..." if len(top["content"]) > 200 else "")
            })
            # Extract most informative sentence from chunk
            sentences = re.split(r'(?<=[.!?])\s+', top["content"])
            best_sentence = max(sentences, key=lambda s: sum(1 for t in q_terms if t in s.lower()), default=sentences[0])
            answer_parts.append(f"{best_sentence.strip()} [{citation_id}]")

        synthesized = " ".join(answer_parts)
        return {
            "answer": synthesized,
            "citations": citations,
            "confidence": round(top_chunks[0]["score"], 3)
        }

intelligence_engine = DocumentIntelligence()
