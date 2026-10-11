import os, json, urllib.request

OLLAMA_URL = os.environ.get("ANAMNESIS_OLLAMA_URL", "http://localhost:11434/api/embeddings")
MODEL = os.environ.get("ANAMNESIS_EMBED_MODEL", "nomic-embed-text")
BACKEND = os.environ.get("ANAMNESIS_EMBED_BACKEND", "ollama")
FASTEMBED_MODEL = os.environ.get("ANAMNESIS_FASTEMBED_MODEL", "nomic-ai/nomic-embed-text-v1.5")
FASTEMBED_CACHE = os.path.expanduser(os.environ.get("ANAMNESIS_FASTEMBED_CACHE", "~/.cache/anamnesis/fastembed"))
BODY_CAP = 3000  # keep Title+Type+Description header + body under the embed model's context


def build_payload(name, typ, description, body):
    header = f"Title: {name}\nType: {typ}\nDescription: {description}\n\nBody:\n"
    return header + (body or "")[:BODY_CAP]


_fe = None


def embed(text, model=MODEL, url=OLLAMA_URL, timeout=30):
    global _fe
    if BACKEND == "fastembed":
        if _fe is None:
            from fastembed import TextEmbedding
            _fe = TextEmbedding(FASTEMBED_MODEL, cache_dir=FASTEMBED_CACHE)
        return next(iter(_fe.embed([text]))).tolist()
    data = json.dumps({"model": model, "prompt": text}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)["embedding"]
