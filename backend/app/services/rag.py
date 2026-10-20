import csv
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from openai import OpenAI
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.config import CHAT_MODEL, DATA_DIR, OPENAI_API_KEY, OPENAI_BASE_URL


EXCLUDED_KNOWLEDGE_FILES = set()

# 单个知识文件最多占用几个检索名额。一份长文档可能被切成多块，
# 不限流时容易出现同一个文件的 3~4 个分段占满 top_k，挤掉其他来源。
MAX_CHUNKS_PER_SOURCE = 2


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def tokenize(text: str):
    return re.findall(r"[a-zA-Z0-9]+|[\u4e00-\u9fff]", (text or "").lower())


def chunk_text(text: str, chunk_size=520, overlap=90):
    text = normalize_text(text)
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def infer_domain(path: Path):
    name = path.name
    if "体重" in name or "减脂" in name:
        return "体重管理"
    if "食谱" in name:
        return "食谱推荐"
    if "运动" in name:
        return "运动建议"
    if "睡眠" in name:
        return "生活方式"
    if "客服" in name or "合规" in name:
        return "客服合规"
    if path.parent.name == "food_database":
        return "食物营养库"
    return "健康知识"


class RAGService:
    def __init__(self):
        self.docs = []
        self.vectorizer = HashingVectorizer(
            n_features=1536,
            analyzer="char_wb",
            ngram_range=(2, 4),
            alternate_sign=False,
            norm="l2",
        )
        self.matrix = None
        self.doc_tokens = []
        self.idf = {}
        self.avgdl = 1
        self.load()

    def load(self):
        docs = []
        for folder in [DATA_DIR / "knowledge_base", DATA_DIR / "recipes", DATA_DIR / "food_database"]:
            for path in sorted(folder.glob("*")):
                if path.is_dir() or path.name.startswith(".") or path.name in EXCLUDED_KNOWLEDGE_FILES:
                    continue
                if path.suffix.lower() in {".md", ".txt"}:
                    chunks = chunk_text(path.read_text(encoding="utf-8", errors="ignore"))
                elif path.suffix.lower() == ".csv":
                    chunks = []
                    with path.open("r", encoding="utf-8-sig", newline="") as file:
                        reader = csv.DictReader(file)
                        for row in reader:
                            chunks.append("；".join([f"{k}：{v}" for k, v in row.items() if v]))
                else:
                    continue
                for idx, chunk in enumerate(chunks, 1):
                    docs.append({
                        "source": path.name,
                        "domain": infer_domain(path),
                        "chunk_id": idx,
                        "content": chunk,
                    })
        self.docs = docs
        texts = [x["content"] for x in docs] or [""]
        self.matrix = self.vectorizer.transform(texts)
        self._build_bm25(texts)
        return self

    def _build_bm25(self, texts):
        self.doc_tokens = [tokenize(text) for text in texts]
        df = defaultdict(int)
        for tokens in self.doc_tokens:
            for token in set(tokens):
                df[token] += 1
        total = max(len(texts), 1)
        self.idf = {token: math.log(1 + (total - count + 0.5) / (count + 0.5)) for token, count in df.items()}
        self.avgdl = sum(len(tokens) for tokens in self.doc_tokens) / total

    def _bm25(self, query):
        q_tokens = tokenize(query)
        scores = []
        for tokens in self.doc_tokens:
            tf = Counter(tokens)
            doc_len = len(tokens) or 1
            score = 0
            for token in q_tokens:
                if token not in tf:
                    continue
                score += self.idf.get(token, 0) * (tf[token] * 2.5) / (
                    tf[token] + 1.5 * (1 - 0.75 + 0.75 * doc_len / max(self.avgdl, 1))
                )
            scores.append(score)
        return scores

    def retrieve(self, question: str, top_k=6):
        q_vec = self.vectorizer.transform([question])
        vector_scores = cosine_similarity(q_vec, self.matrix)[0]
        bm25_scores = self._bm25(question)
        max_v = max(vector_scores) if len(vector_scores) else 1
        max_b = max(bm25_scores) if bm25_scores else 1
        rows = []
        for idx, doc in enumerate(self.docs):
            score = 0.65 * (vector_scores[idx] / max_v if max_v else 0) + 0.35 * (bm25_scores[idx] / max_b if max_b else 0)
            rows.append((idx, score))
        rows.sort(key=lambda x: x[1], reverse=True)
        picked = []
        per_source = Counter()
        for idx, score in rows:
            source = self.docs[idx]["source"]
            if per_source[source] >= MAX_CHUNKS_PER_SOURCE:
                continue
            per_source[source] += 1
            picked.append((idx, score))
            if len(picked) >= top_k:
                break
        return [
            {"rank": rank, **self.docs[idx], "score": round(float(score), 4)}
            for rank, (idx, score) in enumerate(picked, 1)
        ]

    def answer(self, question: str, top_k=6):
        sources = self.retrieve(question, top_k)
        context = "\n\n".join([f"[{i}] {x['source']} | {x['domain']}\n{x['content']}" for i, x in enumerate(sources, 1)])
        if not OPENAI_API_KEY:
            answer = "当前未配置 API Key，先给出基于知识库证据的抽取式摘要：\n" + "\n".join(
                [f"- {x['content'][:160]}... [{i}]" for i, x in enumerate(sources[:4], 1)]
            )
        else:
            client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
            prompt = f"""你是健康管理平台的 AI 营养顾问。请基于证据回答，不做医疗诊断，不承诺治疗或快速瘦身。
回答结构：直接结论、执行建议、风险提示、引用来源。

用户问题：{question}

证据：
{context}
"""
            resp = client.chat.completions.create(
                model=CHAT_MODEL,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
            )
            answer = resp.choices[0].message.content
        return {"answer": answer, "sources": sources}


rag_service = RAGService()
